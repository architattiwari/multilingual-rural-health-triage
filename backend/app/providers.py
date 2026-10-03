"""Provider registry built from settings. Unconfigured providers are simply absent."""

from dataclasses import dataclass

from app.ai.anthropic_provider import AnthropicLLMProvider
from app.ai.base import LLMProvider, ProviderError, TranslationProvider
from app.ai.extraction import LLMExtractor
from app.ai.translation import LLMTranslationProvider
from app.core.config import Settings
from app.core.logging import get_logger
from app.speech.base import SpeechToTextProvider, TextToSpeechProvider
from app.speech.openai_stt import OpenAISpeechToText
from app.speech.openai_tts import OpenAITextToSpeech

log = get_logger("providers")


@dataclass
class Providers:
    stt: SpeechToTextProvider | None = None
    tts: TextToSpeechProvider | None = None
    llm: LLMProvider | None = None
    translation: TranslationProvider | None = None

    @property
    def extractor(self) -> LLMExtractor | None:
        return LLMExtractor(self.llm) if self.llm else None

    def status(self) -> dict[str, bool]:
        return {"speech_to_text": self.stt is not None, "text_to_speech": self.tts is not None,
                "llm": self.llm is not None, "translation": self.translation is not None}


def build_providers(settings: Settings) -> Providers:
    providers = Providers()
    for attr, factory in (("stt", OpenAISpeechToText), ("tts", OpenAITextToSpeech), ("llm", AnthropicLLMProvider)):
        try:
            setattr(providers, attr, factory(settings))
        except ProviderError:
            log.info("provider not configured", extra={"provider": attr})
    if providers.llm and settings.translation_language_list:
        providers.translation = LLMTranslationProvider(providers.llm)
    return providers
