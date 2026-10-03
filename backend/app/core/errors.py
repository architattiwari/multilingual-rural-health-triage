"""Application errors mapped to safe, user facing responses."""

import uuid


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    public_message = "Something went wrong. Please try again."

    def __init__(self, public_message: str | None = None, *, detail: str | None = None) -> None:
        super().__init__(detail or public_message or self.public_message)
        if public_message:
            self.public_message = public_message
        self.error_id = uuid.uuid4().hex[:12]


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"
    public_message = "The request could not be processed."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    public_message = "Conversation not found."


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    public_message = "Missing or invalid conversation token."


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    public_message = "Too many requests. Please wait a moment and try again."


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"
    public_message = "The upload is too large."


class UnsupportedMedia(AppError):
    status_code = 415
    code = "unsupported_media"
    public_message = "This audio format is not supported."


class ProviderUnavailable(AppError):
    status_code = 503
    code = "provider_unavailable"
    public_message = "This feature is temporarily unavailable. Please type your answer instead."


class ConversationLimit(AppError):
    status_code = 409
    code = "conversation_limit"
    public_message = "This conversation has reached its limit. Please start a new one."
