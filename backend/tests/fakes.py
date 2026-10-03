"""TEST FIXTURES ONLY. These fakes are never imported by application code."""

from app.ai.base import LLMProvider, ProviderError, TranslationProvider
from app.speech.base import AudioClip, SpeechToTextProvider, TextToSpeechProvider, Transcript


class FakeLLM(LLMProvider):
    name = "fake-llm"

    def __init__(self, response: str | Exception = '{"symptoms": []}') -> None:
        self.response = response
        self.calls = 0

    def complete_json(self, *, system: str, user: str, max_tokens: int = 700) -> str:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeSTT(SpeechToTextProvider):
    name = "fake-stt"

    def __init__(self, transcript: Transcript | Exception) -> None:
        self.transcript = transcript
        self.last_hint: str | None = None

    def transcribe(self, audio: bytes, *, filename: str, content_type: str, language_hint: str | None) -> Transcript:
        self.last_hint = language_hint
        if isinstance(self.transcript, Exception):
            raise self.transcript
        return self.transcript


class FakeTTS(TextToSpeechProvider):
    name = "fake-tts"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def synthesize(self, text: str, *, language: str) -> AudioClip:
        if self.fail:
            raise ProviderError(self.name, "down")
        return AudioClip(b"ID3fakeaudio", "audio/mpeg")


class FakeTranslator(TranslationProvider):
    name = "fake-translator"

    def translate(self, text: str, target_language: str) -> str:
        return f"[{target_language}] {text}"
