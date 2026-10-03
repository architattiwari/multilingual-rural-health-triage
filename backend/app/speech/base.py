"""Speech provider interfaces. Swap the implementation without touching callers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None  # ISO 639-1 as reported by the provider
    confidence: float | None  # 0..1 when the provider supplies enough information
    low_confidence: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AudioClip:
    data: bytes
    content_type: str


class SpeechToTextProvider(ABC):
    name: str

    @abstractmethod
    def transcribe(self, audio: bytes, *, filename: str, content_type: str, language_hint: str | None) -> Transcript:
        """Raise ai.base.ProviderError on failure."""


class TextToSpeechProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(self, text: str, *, language: str) -> AudioClip:
        """Raise ai.base.ProviderError on failure."""
