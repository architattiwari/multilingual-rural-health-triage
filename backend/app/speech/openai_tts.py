"""Text to speech through an OpenAI compatible /audio/speech endpoint."""

import httpx

from app.ai.base import ProviderError, raise_for_status, with_retries
from app.core.config import Settings

from .base import AudioClip, TextToSpeechProvider

_MAX_CHARS = 1200


class OpenAITextToSpeech(TextToSpeechProvider):
    name = "openai-tts"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._key = settings.tts_api_key.get_secret_value()
        if not self._key:
            raise ProviderError(self.name, "not_configured")
        self._model, self._voice = settings.tts_model, settings.tts_voice
        self._client = client or httpx.Client(base_url=settings.tts_api_base_url, timeout=settings.tts_timeout_seconds)

    def synthesize(self, text: str, *, language: str) -> AudioClip:
        # The endpoint infers language from the text itself, so `language` is informational here.
        payload = {"model": self._model, "voice": self._voice, "input": text[:_MAX_CHARS], "response_format": "mp3"}

        def call() -> bytes:
            response = self._client.post("/audio/speech", json=payload, headers={"Authorization": f"Bearer {self._key}"})
            raise_for_status(self.name, response)
            if not response.content:
                raise ProviderError(self.name, "empty_audio")
            return response.content

        return AudioClip(data=with_retries(call, provider=self.name), content_type="audio/mpeg")
