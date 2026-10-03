"""Provider interfaces for LLM and translation. Implementations are swappable."""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable

import httpx


class ProviderError(Exception):
    """Any failure of an external provider. Messages must not contain patient data."""

    def __init__(self, provider: str, reason: str, *, retryable: bool = False) -> None:
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.retryable = retryable


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete_json(self, *, system: str, user: str, max_tokens: int = 700) -> str:
        """Return the raw model text. Callers must validate it before use."""


class TranslationProvider(ABC):
    name: str

    @abstractmethod
    def translate(self, text: str, target_language: str) -> str:
        """Translate patient facing text. Callers validate the result."""


def with_retries[T](call: Callable[[], T], *, provider: str, attempts: int = 2, backoff: float = 0.4) -> T:
    """Retry transient failures (timeouts, 429, 5xx) a bounded number of times."""
    last: ProviderError | None = None
    for attempt in range(attempts):
        try:
            return call()
        except httpx.TimeoutException:
            last = ProviderError(provider, "timeout", retryable=True)
        except httpx.TransportError:
            last = ProviderError(provider, "network_error", retryable=True)
        except ProviderError as exc:
            if not exc.retryable:
                raise
            last = exc
        if attempt + 1 < attempts:
            time.sleep(backoff * (attempt + 1))
    assert last is not None
    raise last


def raise_for_status(provider: str, response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    retryable = response.status_code == 429 or response.status_code >= 500
    raise ProviderError(provider, f"http_{response.status_code}", retryable=retryable)
