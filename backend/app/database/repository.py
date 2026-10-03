"""Persistence operations. Keeps SQL concerns out of the services."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.clinical.state import Observation
from app.clinical.triage import TriageResult
from app.domain.clinical import ClinicalState
from app.models.orm import (
    AuditEvent,
    ClinicalObservation,
    Conversation,
    ConversationMessage,
    TriageAssessment,
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, state: ClinicalState, token_hash: str, retention_hours: int) -> Conversation:
        now = datetime.now(UTC)
        conv = Conversation(
            id=state.conversation_id,
            token_hash=token_hash,
            language=state.language,
            triage_status=state.triage_status.value,
            state_json=state.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(hours=retention_hours),
        )
        self.db.add(conv)
        self.db.flush()
        return conv

    def get_active(self, conversation_id: str) -> Conversation | None:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None or _aware(conv.expires_at) <= datetime.now(UTC):
            return None
        return conv

    def save_state(self, conv: Conversation, state: ClinicalState) -> None:
        conv.state_json = state.model_dump(mode="json")
        conv.language = state.language
        conv.triage_status = state.triage_status.value
        conv.updated_at = datetime.now(UTC)
        self.db.add(conv)

    def add_message(self, conversation_id: str, role: str, content: str, *, source: str = "text", language: str | None = None) -> None:
        self.db.add(ConversationMessage(conversation_id=conversation_id, role=role, content=content, source=source, language=language))

    def messages(self, conversation_id: str) -> list[ConversationMessage]:
        stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.id)
        return list(self.db.scalars(stmt))

    def last_assistant_message(self, conversation_id: str) -> ConversationMessage | None:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id, ConversationMessage.role == "assistant")
            .order_by(ConversationMessage.id.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def message_count(self, conversation_id: str) -> int:
        return len(self.messages(conversation_id))

    def add_observations(self, conversation_id: str, observations: list[Observation]) -> None:
        for o in observations:
            self.db.add(ClinicalObservation(conversation_id=conversation_id, kind=o.kind, concept=o.concept,
                                            status=o.status, source=o.source, confidence=o.confidence))

    def add_assessment(self, conversation_id: str, result: TriageResult, *, is_final: bool) -> TriageAssessment:
        row = TriageAssessment(
            id=str(uuid.uuid4()), conversation_id=conversation_id, level=result.triage_level.value,
            reason_codes=result.reason_codes, rules_triggered=result.rules_triggered, red_flags=result.red_flags,
            information_used=result.information_used, engine_version=result.engine_version,
            rules_version=result.rules_version, is_final=is_final, requires_human_review=result.requires_human_review,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def latest_assessment(self, conversation_id: str, *, final_only: bool = False) -> TriageAssessment | None:
        stmt = select(TriageAssessment).where(TriageAssessment.conversation_id == conversation_id)
        if final_only:
            stmt = stmt.where(TriageAssessment.is_final.is_(True))
        stmt = stmt.order_by(TriageAssessment.created_at.desc(), TriageAssessment.id.desc()).limit(1)
        return self.db.scalars(stmt).first()

    def audit(self, event_type: str, *, conversation_id: str | None, request_id: str | None, detail: dict | None = None) -> None:
        self.db.add(AuditEvent(event_type=event_type, conversation_id=conversation_id, request_id=request_id, detail=detail or {}))

    def delete(self, conversation_id: str) -> bool:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None:
            return False
        # Detach audit rows so they stay useful for operations but no longer point at a person.
        self.db.execute(update(AuditEvent).where(AuditEvent.conversation_id == conversation_id).values(conversation_id=None))
        self.db.delete(conv)
        self.db.flush()
        return True

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        ids = list(self.db.scalars(select(Conversation.id).where(Conversation.expires_at <= now)))
        for cid in ids:
            self.delete(cid)
        self.db.execute(delete(AuditEvent).where(AuditEvent.created_at <= now - timedelta(days=90)))
        return len(ids)
