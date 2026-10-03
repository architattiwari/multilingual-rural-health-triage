"""Optional translation of patient facing text for languages without reviewed templates."""

import re

from app.core.logging import get_logger

from .base import LLMProvider, ProviderError, TranslationProvider
from .prompts import TRANSLATION_SYSTEM

log = get_logger("ai.translation")

_DIGITS = re.compile(r"\d+")


def validate_translation(source: str, output: str) -> bool:
    """Reject empty, runaway, markup carrying or number changing translations."""
    if not output.strip() or "<" in output or ">" in output:
        return False
    ratio = len(output) / max(len(source), 1)
    if not 0.3 <= ratio <= 4.0:
        return False
    return sorted(_DIGITS.findall(source)) == sorted(_DIGITS.findall(output))


class LLMTranslationProvider(TranslationProvider):
    name = "llm"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def translate(self, text: str, target_language: str) -> str:
        user = f"Target language code: {target_language}\n<text>\n{text}\n</text>"
        try:
            output = self._llm.complete_json(system=TRANSLATION_SYSTEM, user=user, max_tokens=500).strip()
        except ProviderError as exc:
            raise ProviderError(self.name, exc.reason) from exc
        if not validate_translation(text, output):
            log.warning("translation rejected by validation", extra={"target": target_language})
            raise ProviderError(self.name, "invalid_translation")
        return output
