"""FastAPI dependencies: settings, database session, service, auth and rate limiting."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Path, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import RateLimited
from app.models.orm import Conversation
from app.providers import Providers
from app.services.conversation_service import ConversationService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_providers(request: Request) -> Providers:
    return request.app.state.providers


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DbDep = Annotated[Session, Depends(get_db)]


def get_service(db: DbDep, settings: SettingsDep, providers: Annotated[Providers, Depends(get_providers)]) -> ConversationService:
    return ConversationService(db, settings, providers)


ServiceDep = Annotated[ConversationService, Depends(get_service)]


def client_key(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, settings: SettingsDep) -> None:
    if not request.app.state.limiter.allow(f"std:{client_key(request, settings)}", settings.rate_limit_per_minute):
        raise RateLimited()


def heavy_rate_limit(request: Request, settings: SettingsDep) -> None:
    """Stricter limit for endpoints that call paid external providers."""
    if not request.app.state.limiter.allow(f"heavy:{client_key(request, settings)}", settings.rate_limit_heavy_per_minute):
        raise RateLimited()


def current_conversation(
    service: ServiceDep,
    conversation_id: Annotated[str, Path(min_length=36, max_length=36)],
    x_conversation_token: Annotated[str | None, Header(description="Token returned when the conversation was created.")] = None,
) -> Conversation:
    return service.authorize(conversation_id, x_conversation_token)


ConversationDep = Annotated[Conversation, Depends(current_conversation)]
