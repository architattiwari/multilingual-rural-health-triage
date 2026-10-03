"""LLM assisted extraction with strict validation.

The LLM can only ADD present symptoms on top of the rule based result, and only
when the quoted evidence really occurs in the patient's message. It can never
remove a finding, lower severity, or set a triage level. Anything that fails
validation is dropped and logged, and the rule based result stands.
"""

import json
import re
import unicodedata

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.clinical.concepts import CONCEPTS, is_red_flag
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.domain.clinical import Duration, ExtractedSymptom, ExtractionResult, Severity

from .base import LLMProvider, ProviderError
from .prompts import EXTRACTION_SYSTEM, build_extraction_user_message

log = get_logger("ai.extraction")

_MAX_ITEMS = 12


class _LLMSymptom(BaseModel):
    concept: str
    evidence: str = Field(min_length=2, max_length=120)
    severity: Severity = Severity.UNKNOWN
    confidence: float = Field(default=0.6, ge=0, le=1)

    @field_validator("concept")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in CONCEPTS or v == "unspecified_critical_symptom":
            raise ValueError("unknown concept")
        return v


class _LLMOther(BaseModel):
    label: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z \-]{1,39}$")
    evidence: str = Field(min_length=2, max_length=120)


class LLMExtractionPayload(BaseModel):
    symptoms: list[_LLMSymptom] = Field(default_factory=list, max_length=_MAX_ITEMS)
    other_symptoms: list[_LLMOther] = Field(default_factory=list, max_length=_MAX_ITEMS)
    age_years: float | None = Field(default=None, ge=0, le=120)
    duration_days: float | None = Field(default=None, gt=0, le=3650)


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no json object")
    data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def _evidence_in_text(evidence: str, text: str) -> bool:
    norm = lambda s: re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()  # noqa: E731
    return norm(evidence) in norm(text)


class LLMExtractor:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def propose(self, text: str) -> LLMExtractionPayload | None:
        """Ask the model, validate, and return a payload or None on any failure."""
        try:
            raw = self._provider.complete_json(system=EXTRACTION_SYSTEM, user=build_extraction_user_message(text))
        except ProviderError as exc:
            metrics.inc("llm_failures_total", reason=exc.reason)
            log.warning("llm extraction provider failure", extra={"provider": exc.provider, "reason": exc.reason})
            return None
        try:
            return LLMExtractionPayload.model_validate(_parse_json(raw))
        except (ValueError, ValidationError, json.JSONDecodeError):
            # Never log the raw output: it may repeat patient text or injected content.
            metrics.inc("llm_failures_total", reason="invalid_output")
            log.warning("llm output rejected by schema validation")
            return None

    def merge(self, text: str, base: ExtractionResult) -> ExtractionResult:
        payload = self.propose(text)
        if payload is None:
            return base
        known = {s.concept for s in base.symptoms}
        for item in payload.symptoms:
            if not _evidence_in_text(item.evidence, text):
                metrics.inc("llm_rejected_items_total", reason="evidence_not_in_text")
                continue
            if item.concept in known:
                continue
            # A deterministic negation wins for ordinary symptoms. For red flags the
            # model may still escalate, because a false alarm is safer than a miss.
            if item.concept in base.negated and not is_red_flag(item.concept):
                continue
            base.symptoms.append(
                ExtractedSymptom(
                    concept=item.concept, original_text=item.evidence, confidence=min(item.confidence, 0.75),
                    severity=item.severity, source="llm",
                    duration=base.duration and Duration(value=base.duration.value, unit=base.duration.unit),
                )
            )
            known.add(item.concept)
        if base.age_years is None and payload.age_years is not None:
            base.age_years = payload.age_years
        return base
