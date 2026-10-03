"""Structured clinical information model.

This is the single source of truth carried through a conversation. It records
what the patient said, how it was interpreted and how sure the system is, so a
colloquial phrase is never silently turned into a clinical assumption.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class FindingStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class TriageLevel(StrEnum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    NON_URGENT = "non_urgent"


class TriageStatus(StrEnum):
    INFORMATION_GATHERING = "information_gathering"
    EMERGENCY = "emergency"
    COMPLETE = "complete"


Progression = Literal["worsening", "improving", "stable"]
Sex = Literal["female", "male", "other"]
Source = Literal["rules", "llm", "answer"]
DurationUnit = Literal["hours", "days", "weeks", "months", "years"]

_UNIT_DAYS = {"hours": 1 / 24, "days": 1, "weeks": 7, "months": 30, "years": 365}


class Duration(BaseModel):
    value: float = Field(gt=0, le=1000)
    unit: DurationUnit

    @property
    def days(self) -> float:
        return self.value * _UNIT_DAYS[self.unit]


class Symptom(BaseModel):
    concept: str
    name: str
    original_text: str = Field(max_length=120)
    normalized_concept: str
    confidence: float = Field(ge=0, le=1)
    requires_clarification: bool = False
    body_location: str | None = None
    duration: Duration | None = None
    severity: Severity = Severity.UNKNOWN
    sudden_onset: bool = False
    progression: Progression | None = None
    source: Source = "rules"


class PatientInfo(BaseModel):
    age_years: float | None = Field(default=None, ge=0, le=120)
    sex: Sex | None = None
    pregnant: bool | None = None


class ClinicalState(BaseModel):
    """Persisted conversation state. Contains no names or contact details."""

    schema_version: str = "1"
    conversation_id: str
    language: str = "hi"  # language used for patient facing text
    detected_language: str | None = None
    patient: PatientInfo = Field(default_factory=PatientInfo)
    symptoms: list[Symptom] = Field(default_factory=list)
    findings: dict[str, FindingStatus] = Field(default_factory=dict)
    medical_context: list[str] = Field(default_factory=list)
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    progression: Progression | None = None
    risk_factors: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    asked_questions: dict[str, int] = Field(default_factory=dict)
    answered_questions: list[str] = Field(default_factory=list)
    pending_question_id: str | None = None
    followup_count: int = 0
    turn_count: int = 0
    max_level_reached: TriageLevel | None = None
    triage_status: TriageStatus = TriageStatus.INFORMATION_GATHERING

    def symptom(self, concept: str) -> Symptom | None:
        return next((s for s in self.symptoms if s.concept == concept), None)

    def present(self, concept: str) -> bool:
        return self.findings.get(concept) == FindingStatus.PRESENT

    def status(self, concept: str) -> FindingStatus:
        return self.findings.get(concept, FindingStatus.UNKNOWN)

    def has_context(self, tag: str) -> bool:
        return tag in self.medical_context


class ExtractedSymptom(BaseModel):
    concept: str
    original_text: str
    confidence: float
    severity: Severity = Severity.UNKNOWN
    sudden_onset: bool = False
    duration: Duration | None = None
    source: Source = "rules"


class ExtractionResult(BaseModel):
    """Output of one extraction pass over a single patient utterance."""

    symptoms: list[ExtractedSymptom] = Field(default_factory=list)
    negated: list[str] = Field(default_factory=list)
    age_years: float | None = None
    sex: Sex | None = None
    pregnant: bool | None = None
    temperature_c: float | None = None
    context: list[str] = Field(default_factory=list)
    progression: Progression | None = None
    duration: Duration | None = None
    residual_tokens: list[str] = Field(default_factory=list)
    detected_language: str | None = None
    language_confidence: float = 0.0
    code_mixed: bool = False
    injection_suspected: bool = False
