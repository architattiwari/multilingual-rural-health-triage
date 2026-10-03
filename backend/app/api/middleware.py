"""ASGI middleware: request ids, timing, security headers and request size limits."""

import json
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.logging import get_logger, request_id_ctx
from app.core.metrics import metrics

log = get_logger("http")


class _TooLarge(Exception):
    pass


class RequestContextMiddleware:
    """Assigns a request id, records latency and adds security headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:16]
        token = request_id_ctx.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                ]
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            route = scope.get("route")
            path = getattr(route, "path", "unmatched")
            metrics.observe(path, elapsed)
            metrics.inc("http_requests_total", route=path, status=str(status["code"]))
            log.info("request", extra={"method": scope["method"], "route": path, "status": status["code"],
                                       "duration_ms": round(elapsed * 1000, 1)})
            request_id_ctx.reset(token)


class BodyLimitMiddleware:
    """Rejects oversized bodies, including chunked uploads without a Content-Length."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.json_limit = settings.max_json_body_bytes
        self.audio_limit = settings.max_audio_bytes + 64 * 1024  # multipart framing overhead

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        limit = self.audio_limit if scope["path"].endswith("/audio/transcribe") else self.json_limit
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(send)
            return
        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps({"error": {"code": "payload_too_large", "message": "The request is too large.",
                                     "error_id": uuid.uuid4().hex[:12]}}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
