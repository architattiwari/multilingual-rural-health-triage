"""Conversation orchestration.

Pipeline per patient turn:
  sanitise, extract (rules, then optional LLM), merge into clinical state,
  interpret the answer to the pending question, evaluate the deterministic
  triage engine, then either stop (emergency or enough information) or pick the
  next question.

The emergency override lives here: once the engine returns emergency, no
further question is asked and the level can never drop for the conversation.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clinical.extractor import extract
from app.clinical.questions import Question, apply_answer, get_question, next_question, required_outstanding
from app.clinical.state import merge_extraction, refresh_derived
from app.clinical.triage import TriageResult, evaluate
from app.core.config import Settings
from app.core.errors import ConversationLimit, ProviderUnavailable, Unauthorized, ValidationFailed
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.core.security import (
    hash_token,
    looks_like_prompt_injection,
    new_conversation_token,
    sanitize_text,
    verify_token,
)
from app.database.repository import ConversationRepository
from app.domain.clinical import ClinicalState, TriageLevel, TriageStatus
from app.models.orm import Conversation, TriageAssessment
from app.providers import Providers
from app.speech.audio import AudioInfo, validate_audio
from app.speech.base import AudioClip, Transcript

from .localization import Localizer, PatientResult, resolve_language

log = get_logger("conversation")
_RANK = {TriageLevel.NON_URGENT: 0, TriageLevel.URGENT: 1, TriageLevel.EMERGENCY: 2}


@dataclass
class TurnOutcome:
    state: ClinicalState
    assistant_message: str
    question: Question | None
    result: TriageResult | None
    patient_result: PatientResult | None
    assessment_id: str | None


class TriageNotReady(Exception):
    pass


def result_from_assessment(row: TriageAssessment, state: ClinicalState) -> TriageResult:
    return TriageResult(
        triage_level=TriageLevel(row.level), reason_codes=list(row.reason_codes), rules_triggered=list(row.rules_triggered),
        red_flags=list(row.red_flags), recommended_action={"emergency": "seek_emergency_care_now",
                                                          "urgent": "seek_medical_evaluation_promptly",
                                                          "non_urgent": "routine_consultation_and_monitoring"}[row.level],
        requires_human_review=row.requires_human_review, information_complete=not state.missing_information,
        information_used=list(row.information_used), engine_version=row.engine_version, rules_version=row.rules_version,
    )


class ConversationService:
    def __init__(self, db: Session, settings: Settings, providers: Providers) -> None:
        self.db, self.settings, self.providers = db, settings, providers
        self.repo = ConversationRepository(db)
        self.localizer = Localizer(settings, providers.translation)

    # ---- lifecycle -------------------------------------------------------
    def create(self, language_hint: str | None, request_id: str | None) -> tuple[Conversation, str, str]:
        """Create a conversation. Returns (row, plaintext token, first assistant message)."""
        lang = resolve_language(None, language_hint, self.settings)
        state = ClinicalState(conversation_id=str(uuid.uuid4()), language=lang)
        first = get_question("chief_complaint")
        assert first is not None
        state.pending_question_id = first.question_id
        state.asked_questions[first.question_id] = 1
        token = new_conversation_token()
        conv = self.repo.create(state, hash_token(token, self.settings.secret_bytes), self.settings.conversation_retention_hours)
        message = self.localizer.greeting(lang) + first.text(lang if lang in ("hi", "hi-Latn", "en") else "hi")
        self.repo.add_message(conv.id, "assistant", message, source="system", language=lang)
        self.repo.audit("conversation_created", conversation_id=conv.id, request_id=request_id, detail={"language": lang})
        return conv, token, message

    def authorize(self, conversation_id: str, token: str | None) -> Conversation:
        """Single failure mode for missing, wrong or expired credentials, so ids cannot be probed."""
        conv = self.repo.get_active(conversation_id)
        if conv is None or not token or not verify_token(token, conv.token_hash, self.settings.secret_bytes):
            raise Unauthorized()
        return conv

    def load_state(self, conv: Conversation) -> ClinicalState:
        return ClinicalState.model_validate(conv.state_json)

    def delete(self, conv: Conversation, request_id: str | None) -> None:
        self.repo.audit("conversation_deleted", conversation_id=None, request_id=request_id)
        self.repo.delete(conv.id)

    # ---- speech ----------------------------------------------------------
    def transcribe(self, conv: Conversation, audio: bytes, declared_type: str | None, language_hint: str | None,
                   request_id: str | None) -> tuple[Transcript, AudioInfo]:
        info = validate_audio(audio, declared_type, self.settings)
        if self.providers.stt is None:
            raise ProviderUnavailable("Voice input is not available right now. Please type your message.")
        from app.ai.base import ProviderError

        hint = language_hint if language_hint in {"hi", "en"} else self.settings.speech_default_language
        try:
            transcript = self.providers.stt.transcribe(audio, filename=f"audio.{info.extension}", content_type=info.content_type,
                                                       language_hint=hint)
        except ProviderError as exc:
            metrics.inc("speech_failures_total", reason=exc.reason)
            log.warning("speech provider failure", extra={"provider": exc.provider, "reason": exc.reason})
            raise ProviderUnavailable("We could not process the recording. Please try again or type your message.") from exc
        warnings = list(transcript.warnings)
        if info.very_quiet:
            warnings.append("very_quiet_audio")
        if warnings:
            metrics.inc("speech_low_quality_total")
        # The audio itself is never stored. Only the (editable) transcript reaches the conversation.
        self.repo.audit("audio_transcribed", conversation_id=conv.id, request_id=request_id,
                        detail={"bytes": info.size_bytes, "container": info.container, "low_confidence": transcript.low_confidence})
        return Transcript(transcript.text, transcript.language, transcript.confidence,
                          transcript.low_confidence or info.very_quiet, tuple(warnings)), info

    def speak(self, conv: Conversation) -> AudioClip:
        from app.ai.base import ProviderError

        if self.providers.tts is None:
            raise ProviderUnavailable("Voice playback is not available right now.")
        last = self.repo.last_assistant_message(conv.id)
        if last is None:
            raise ValidationFailed("There is nothing to read aloud yet.")
        try:
            return self.providers.tts.synthesize(last.content, language=conv.language)
        except ProviderError as exc:
            metrics.inc("tts_failures_total", reason=exc.reason)
            raise ProviderUnavailable("Voice playback is not available right now.") from exc

    # ---- turns -----------------------------------------------------------
    def preview_extraction(self, text: str) -> dict:
        cleaned = self._clean(text)
        ex = extract(cleaned)
        return ex.model_dump(mode="json", exclude={"residual_tokens"})

    def _clean(self, text: str) -> str:
        try:
            return sanitize_text(text, self.settings.max_text_chars)
        except ValueError as exc:
            if str(exc) == "too_long":
                raise ValidationFailed(f"Please keep the message under {self.settings.max_text_chars} characters.") from exc
            raise ValidationFailed("Please enter or record a message.") from exc

    def process_turn(self, conv: Conversation, text: str, *, source: str, question_id: str | None,
                     language_hint: str | None, request_id: str | None) -> TurnOutcome:
        if self.repo.message_count(conv.id) >= self.settings.max_messages_per_conversation:
            raise ConversationLimit()
        cleaned = self._clean(text)
        state = self.load_state(conv)
        pending = get_question(state.pending_question_id) if state.pending_question_id else None
        if question_id and (pending is None or pending.question_id != question_id):
            raise ValidationFailed("That question is no longer active. Please answer the latest question.")

        injection = looks_like_prompt_injection(cleaned)
        ex = extract(cleaned, language_hint=language_hint)
        llm_used = False
        extractor = self.providers.extractor
        if injection:
            metrics.inc("prompt_injection_suspected_total")
            self.repo.audit("prompt_injection_suspected", conversation_id=conv.id, request_id=request_id)
        elif extractor is not None and self.settings.llm_extraction_enabled:
            before = len(ex.symptoms)
            ex = extractor.merge(cleaned, ex)
            llm_used = True
            if len(ex.symptoms) > before:
                metrics.inc("llm_added_symptoms_total")

        self._update_language(state, ex.detected_language, ex.language_confidence, language_hint)
        state.turn_count += 1
        observations = merge_extraction(state, ex)
        if pending is not None:
            observations += apply_answer(state, pending, cleaned, ex)
            state.pending_question_id = None
        refresh_derived(state)

        self.repo.add_message(conv.id, "patient", cleaned, source=source if source in ("text", "voice") else "text",
                              language=state.detected_language)
        self.repo.add_observations(conv.id, observations)

        outcome = self._decide(conv, state, request_id=request_id, llm_used=llm_used, injection=injection)
        self.repo.save_state(conv, state)
        return outcome

    def evaluate_now(self, conv: Conversation, request_id: str | None) -> TurnOutcome:
        state = self.load_state(conv)
        state.pending_question_id = None
        outcome = self._finalize(conv, state, request_id=request_id, llm_used=False, injection=False)
        self.repo.save_state(conv, state)
        return outcome

    def latest_final(self, conv: Conversation) -> tuple[TriageAssessment, ClinicalState]:
        state = self.load_state(conv)
        row = self.repo.latest_assessment(conv.id, final_only=True)
        if row is None:
            raise TriageNotReady()
        return row, state

    # ---- internals -------------------------------------------------------
    def _update_language(self, state: ClinicalState, detected: str | None, confidence: float, hint: str | None) -> None:
        if hint and hint in self.settings.translation_language_list:
            state.language = hint
            return
        if detected and detected != "und" and confidence >= 0.6:
            state.detected_language = detected
            state.language = resolve_language(detected)

    def _decide(self, conv: Conversation, state: ClinicalState, *, request_id: str | None, llm_used: bool,
                injection: bool) -> TurnOutcome:
        outstanding = required_outstanding(state)
        state.missing_information = outstanding
        result = evaluate(state, required_outstanding=outstanding)

        if result.triage_level == TriageLevel.EMERGENCY:
            self.repo.audit("emergency_override", conversation_id=conv.id, request_id=request_id,
                            detail={"rules": result.rules_triggered})
            metrics.inc("triage_total", level="emergency")
            return self._finish(conv, state, result, request_id, llm_used, injection)

        nxt = next_question(state) if state.followup_count < self.settings.max_followup_questions else None
        if nxt is None:
            return self._finalize(conv, state, request_id=request_id, llm_used=llm_used, injection=injection)

        state.triage_status = TriageStatus.INFORMATION_GATHERING
        state.pending_question_id = nxt.question_id
        asks = state.asked_questions.get(nxt.question_id, 0) + 1
        state.asked_questions[nxt.question_id] = asks
        state.followup_count += 1
        lang = state.language if state.language in ("hi", "hi-Latn", "en") else "hi"
        message = (self.localizer.reask_prefix(lang) if asks > 1 else "") + nxt.text(lang)
        self.repo.add_message(conv.id, "assistant", message, source="system", language=state.language)
        assessment = self.repo.add_assessment(conv.id, result, is_final=False)
        self._audit_turn(conv, state, result, request_id, llm_used, injection)
        return TurnOutcome(state, message, nxt, None, None, assessment.id)

    def _finalize(self, conv: Conversation, state: ClinicalState, *, request_id: str | None, llm_used: bool,
                  injection: bool) -> TurnOutcome:
        outstanding = required_outstanding(state)
        state.missing_information = outstanding
        result = evaluate(state, required_outstanding=outstanding, finalize=True)
        metrics.inc("triage_total", level=result.triage_level.value)
        return self._finish(conv, state, result, request_id, llm_used, injection)

    def _finish(self, conv: Conversation, state: ClinicalState, result: TriageResult, request_id: str | None,
                llm_used: bool, injection: bool) -> TurnOutcome:
        state.pending_question_id = None
        state.triage_status = TriageStatus.EMERGENCY if result.triage_level == TriageLevel.EMERGENCY else TriageStatus.COMPLETE
        if state.max_level_reached is None or _RANK[result.triage_level] > _RANK[state.max_level_reached]:
            state.max_level_reached = result.triage_level
        patient_result = self.localizer.render_result(result, state.language)
        message = f"{patient_result.headline}. {patient_result.message}"
        self.repo.add_message(conv.id, "assistant", message, source="system", language=patient_result.language)
        assessment = self.repo.add_assessment(conv.id, result, is_final=True)
        self._audit_turn(conv, state, result, request_id, llm_used, injection)
        return TurnOutcome(state, message, None, result, patient_result, assessment.id)

    def _audit_turn(self, conv: Conversation, state: ClinicalState, result: TriageResult, request_id: str | None,
                    llm_used: bool, injection: bool) -> None:
        self.repo.audit("turn_processed", conversation_id=conv.id, request_id=request_id, detail={
            "turn": state.turn_count, "level": result.triage_level.value, "rules": result.rules_triggered,
            "llm_used": llm_used, "injection_suspected": injection, "outstanding": state.missing_information,
        })
