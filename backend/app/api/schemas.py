"""Request and response models exposed through OpenAPI."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.clinical import TriageLevel, TriageStatus
from app.services.localization import EmergencyContact, PatientResult

Language = Literal["hi", "hi-Latn", "en", "mr", "gu", "pa", "bn", "ta", "te", "kn", "ml", "or", "ur"]


class ErrorBody(BaseModel):
    code: str
    message: str
    error_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Language | None = Field(default=None, description="Preferred language for patient facing text.")


class ConversationCreated(BaseModel):
    conversation_id: str
    access_token: str = Field(description="Send as X-Conversation-Token on every later request. Shown only once.")
    language: str
    assistant_message: str
    disclaimer: str
    expires_in_hours: int
    emergency_contact: EmergencyContact | None = None


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=5000, description="Patient message or transcript.")
    source: Literal["text", "voice"] = "text"
    language_hint: Language | None = None


class AnswerIn(MessageIn):
    question_id: str = Field(min_length=1, max_length=60)


class ExtractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=5000)


class SpeechIn(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionOut(BaseModel):
    question_id: str
    kind: Literal["yes_no", "number", "free_text", "duration"]
    text: str
    required_for_triage: bool


class SymptomOut(BaseModel):
    name: str
    original_text: str
    normalized_concept: str
    confidence: float
    requires_clarification: bool
    duration_days: float | None = None
    severity: str


class StateSummary(BaseModel):
    language: str
    detected_language: str | None
    age_years: float | None
    symptoms: list[SymptomOut]
    missing_information: list[str]
    red_flags: list[str]
    followup_count: int


class TriageOut(BaseModel):
    assessment_id: str
    triage_level: TriageLevel
    reason_codes: list[str]
    recommended_action: str
    confidence: float | None = None
    requires_human_review: bool
    engine_version: str
    rules_version: str
    patient: PatientResult


class TurnResponse(BaseModel):
    conversation_id: str
    triage_status: TriageStatus
    assistant_message: str
    question: QuestionOut | None
    triage: TriageOut | None
    state: StateSummary
    disclaimer: str


class MessageOut(BaseModel):
    role: Literal["patient", "assistant"]
    text: str
    source: str
    created_at: str


class ConversationOut(BaseModel):
    conversation_id: str
    triage_status: TriageStatus
    messages: list[MessageOut]
    state: StateSummary
    pending_question: QuestionOut | None
    disclaimer: str


class TranscriptOut(BaseModel):
    text: str
    language: str | None
    confidence: float | None
    low_confidence: bool
    usable: bool
    warnings: list[str]
    duration_seconds: float | None = None


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, bool]


class MetaOut(BaseModel):
    api_version: str
    engine_version: str
    rules_version: str
    languages: list[str]
    limits: dict[str, int]
    providers: dict[str, bool]
    emergency_contact: EmergencyContact | None
    disclaimers: dict[str, str]
