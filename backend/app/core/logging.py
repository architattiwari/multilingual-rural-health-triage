"""Structured JSON logging with request correlation.

Log records carry identifiers and timings only. Patient text, tokens and
provider payloads must never be passed to the logger.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
# Keys that must never be emitted even if a caller passes them by mistake.
_FORBIDDEN_KEYS = {"text", "transcript", "token", "access_token", "password", "api_key", "authorization"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "component": record.name,
            "request_id": request_id_ctx.get(),
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in _FORBIDDEN_KEYS:
                payload[key] = value
        if record.exc_info:
            # Exception type only. Messages can echo user input.
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # These loggers print full URLs, which can contain conversation ids.
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(component)
