"""LLM provider using the Anthropic Messages API over HTTPS."""

import httpx

from app.core.config import Settings

from .base import LLMProvider, ProviderError, raise_for_status, with_retries


class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._key = settings.llm_api_key.get_secret_value()
        if not self._key:
            raise ProviderError(self.name, "not_configured")
        self._model = settings.llm_model
        self._client = client or httpx.Client(base_url=settings.llm_api_base_url, timeout=settings.llm_timeout_seconds)

    def complete_json(self, *, system: str, user: str, max_tokens: int = 700) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

        def call() -> str:
            response = self._client.post("/v1/messages", json=payload, headers=headers)
            raise_for_status(self.name, response)
            try:
                blocks = response.json()["content"]
                return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            except (KeyError, ValueError, TypeError) as exc:
                raise ProviderError(self.name, "malformed_response") from exc

        return with_retries(call, provider=self.name)
