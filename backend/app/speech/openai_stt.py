"""Speech to text through an OpenAI compatible /audio/transcriptions endpoint (default model whisper-1)."""

import math

import httpx

from app.ai.base import ProviderError, raise_for_status, with_retries
from app.core.config import Settings

from .base import SpeechToTextProvider, Transcript

_LANG_CODES = {"hindi": "hi", "english": "en", "urdu": "ur", "marathi": "mr", "gujarati": "gu", "punjabi": "pa",
               "bengali": "bn", "tamil": "ta", "telugu": "te", "nepali": "ne", "sanskrit": "sa"}


class OpenAISpeechToText(SpeechToTextProvider):
    name = "openai-whisper"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._key = settings.speech_api_key.get_secret_value()
        if not self._key:
            raise ProviderError(self.name, "not_configured")
        self._model = settings.speech_model
        self._min_conf = settings.speech_min_confidence
        self._client = client or httpx.Client(base_url=settings.speech_api_base_url, timeout=settings.speech_timeout_seconds)

    def transcribe(self, audio: bytes, *, filename: str, content_type: str, language_hint: str | None) -> Transcript:
        data = {"model": self._model, "response_format": "verbose_json", "temperature": "0"}
        if language_hint:
            data["language"] = language_hint

        def call() -> dict:
            response = self._client.post(
                "/audio/transcriptions", data=data, files={"file": (filename, audio, content_type)},
                headers={"Authorization": f"Bearer {self._key}"},
            )
            raise_for_status(self.name, response)
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderError(self.name, "malformed_response") from exc
            if not isinstance(payload, dict):
                raise ProviderError(self.name, "malformed_response")
            return payload

        payload = with_retries(call, provider=self.name)
        text = str(payload.get("text", "")).strip()
        segments = [s for s in payload.get("segments", []) if isinstance(s, dict)]
        logprobs = [s["avg_logprob"] for s in segments if isinstance(s.get("avg_logprob"), (int, float))]
        no_speech = [s["no_speech_prob"] for s in segments if isinstance(s.get("no_speech_prob"), (int, float))]
        confidence = round(min(1.0, math.exp(sum(logprobs) / len(logprobs))), 2) if logprobs else None
        language = _LANG_CODES.get(str(payload.get("language", "")).lower())

        warnings: list[str] = []
        low = not text
        if not text:
            warnings.append("empty_transcript")
        if no_speech and sum(no_speech) / len(no_speech) > 0.6:
            low = True
            warnings.append("probably_no_speech")
        if confidence is not None and confidence < self._min_conf:
            low = True
            warnings.append("low_confidence")
        if language == "ur":
            warnings.append("urdu_script_possible")  # Hindi speech is sometimes returned in Urdu script
        return Transcript(text=text, language=language, confidence=confidence, low_confidence=low, warnings=tuple(warnings))
