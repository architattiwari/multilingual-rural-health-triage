"""Application factory."""

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.middleware import BodyLimitMiddleware, RequestContextMiddleware
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.metrics import metrics
from app.core.security import SlidingWindowLimiter
from app.database.session import make_session_factory
from app.providers import Providers, build_providers

log = get_logger("app")

DESCRIPTION = """
Preliminary health triage guidance for rural users in Hindi, Hindi English mixed speech and Marwari influenced Hindi.

**This service provides preliminary health triage guidance. It does not diagnose medical conditions and does not replace
a qualified healthcare professional.**

### Authentication
Patients are anonymous. `POST /conversations` returns a random `access_token`, shown once. Send it as the
`X-Conversation-Token` header on every request for that conversation. Tokens expire with the conversation.

### Errors
All errors use `{"error": {"code", "message", "error_id"}}`. Stack traces are never returned.
"""


def create_app(settings: Settings | None = None, providers: Providers | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_for_runtime()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info("startup", extra={"env": settings.app_env, "version": __version__})
        yield

    app = FastAPI(title="Multilingual Rural Health Triage Assistant", version=__version__, description=DESCRIPTION,
                  lifespan=lifespan, docs_url="/docs", redoc_url=None,
                  openapi_tags=[{"name": "system"}, {"name": "conversation"}, {"name": "voice"}, {"name": "analysis"}, {"name": "triage"}])
    app.state.settings = settings
    app.state.providers = providers if providers is not None else build_providers(settings)
    app.state.session_factory = make_session_factory(settings)
    app.state.limiter = SlidingWindowLimiter()

    app.add_middleware(BodyLimitMiddleware, settings=settings)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Content-Type", "X-Conversation-Token"], expose_headers=["X-Request-ID"], max_age=600)
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("application error", extra={"error_id": exc.error_id, "code": exc.code})
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.public_message, "error_id": exc.error_id}})

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Report the failing fields only. Pydantic's default payload echoes the submitted input.
        fields = [".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()]
        metrics.inc("validation_failures_total")
        return JSONResponse(status_code=422, content={"error": {"code": "validation_failed", "error_id": "-",
                            "message": "Invalid request: " + ", ".join(sorted(set(fields)))}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "error_id": "-",
                            "message": "Not found." if exc.status_code == 404 else "Request failed."}})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        error = AppError()
        log.error("unhandled exception", exc_info=exc, extra={"error_id": error.error_id})
        metrics.inc("unhandled_errors_total")
        return JSONResponse(status_code=500, content={"error": {"code": error.code, "message": error.public_message,
                                                                "error_id": error.error_id}})

    app.include_router(router)

    if settings.metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        def metrics_endpoint(request: Request) -> PlainTextResponse:
            expected = settings.metrics_token.get_secret_value()
            if expected:
                supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
                if not hmac.compare_digest(supplied, expected):
                    return PlainTextResponse("unauthorized", status_code=401)
            elif settings.app_env == "production":
                return PlainTextResponse("metrics disabled without METRICS_TOKEN", status_code=404)
            return PlainTextResponse(metrics.render())

    return app


def app_factory() -> FastAPI:
    return create_app()
