from sqlalchemy import select, text

from app.ai.base import ProviderError
from app.models.orm import AuditEvent, ClinicalObservation, Conversation, ConversationMessage, TriageAssessment
from app.providers import Providers
from app.speech.base import Transcript
from tests.conftest import Chat, wav_bytes
from tests.fakes import FakeSTT, FakeTTS


def test_health_and_meta(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["checks"]["database"] is True and h["checks"]["llm"] is False
    m = client.get("/api/v1/meta").json()
    assert m["languages"][:3] == ["hi", "hi-Latn", "en"] and m["rules_version"]


def test_create_conversation(client):
    r = client.post("/api/v1/conversations", json={"language": "en"})
    body = r.json()
    assert r.status_code == 201 and len(body["access_token"]) >= 40 and "not a doctor" in body["assistant_message"]
    assert "does not diagnose" in body["disclaimer"]
    assert r.headers["x-request-id"] and r.headers["x-content-type-options"] == "nosniff"


def test_full_followup_flow_and_retrieval(client):
    chat = Chat(client)
    chat.say("Do din se bukhar hai aur sar bhaari lag raha hai.")
    assert chat.last["question"]["question_id"] == "screen_critical_a"
    r = client.get(f"/api/v1/conversations/{chat.id}/next-question", headers=chat.headers)
    assert r.json()["question_id"] == "screen_critical_a"
    # explicit answer endpoint validates the question id
    bad = client.post(f"/api/v1/conversations/{chat.id}/answers", headers=chat.headers,
                      json={"question_id": "age", "text": "30"})
    assert bad.status_code == 422
    ok = client.post(f"/api/v1/conversations/{chat.id}/answers", headers=chat.headers,
                     json={"question_id": "screen_critical_a", "text": "nahi"})
    assert ok.status_code == 200
    chat.last = ok.json()
    chat.answer_until_final({"age": "35", "fever_temperature": "102"})
    assert chat.level == "non_urgent"
    got = client.get(f"/api/v1/conversations/{chat.id}", headers=chat.headers).json()
    assert got["triage_status"] == "complete" and len(got["messages"]) >= 8
    tri = client.get(f"/api/v1/conversations/{chat.id}/triage", headers=chat.headers).json()
    assert tri["triage_level"] == "non_urgent" and tri["confidence"] is None and tri["engine_version"]
    assert "does not diagnose" in chat.last["disclaimer"] or "nahi karta" in chat.last["disclaimer"]


def test_triage_not_ready_then_forced_evaluation(client):
    chat = Chat(client)
    r = client.get(f"/api/v1/conversations/{chat.id}/triage", headers=chat.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "triage_not_ready"
    chat.say("bukhar hai")
    forced = client.post(f"/api/v1/conversations/{chat.id}/triage", headers=chat.headers).json()
    assert forced["triage"]["triage_level"] == "urgent"  # required safety questions still missing


def test_language_follows_patient(client):
    chat = Chat(client, "hi")
    chat.say("I have fever since two days and headache")
    assert chat.last["state"]["language"] == "en" and chat.last["question"]["text"].startswith("Right now")
    chat2 = Chat(client, "en")
    chat2.say("म्हने ताव छै अर माथो दुखै")
    assert chat2.last["state"]["detected_language"] == "mwr" and chat2.last["state"]["language"] == "hi"


def test_extract_preview_does_not_change_state(client):
    chat = Chat(client)
    r = client.post(f"/api/v1/conversations/{chat.id}/extract", headers=chat.headers, json={"text": "bukhar 3 din se"})
    assert r.status_code == 200 and r.json()["symptoms"][0]["concept"] == "fever"
    state = client.get(f"/api/v1/conversations/{chat.id}", headers=chat.headers).json()["state"]
    assert state["symptoms"] == []


def test_persistence_in_database(client, settings):
    chat = Chat(client)
    chat.say("seene mein dard hai")
    session = client.app.state.session_factory()
    try:
        conv = session.get(Conversation, chat.id)
        assert conv.triage_status == "emergency" and conv.state_json["red_flags"] == ["chest_pain"]
        assert session.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == chat.id)).all()
        assessment = session.scalars(select(TriageAssessment).where(TriageAssessment.is_final.is_(True))).one()
        assert assessment.level == "emergency" and assessment.rules_triggered == ["E02"] and assessment.rules_version
        obs = session.scalars(select(ClinicalObservation)).all()
        assert any(o.concept == "chest_pain" for o in obs)
        events = {e.event_type for e in session.scalars(select(AuditEvent))}
        assert {"conversation_created", "emergency_override", "turn_processed"} <= events
        # Assessment and audit rows must hold codes only, never the patient's words.
        dump = " ".join(str(v) for e in session.scalars(select(AuditEvent)) for v in e.detail.values())
        assert "seene" not in dump
    finally:
        session.close()


def test_delete_removes_everything(client):
    chat = Chat(client)
    chat.say("bukhar hai")
    assert client.delete(f"/api/v1/conversations/{chat.id}", headers=chat.headers).status_code == 204
    assert client.get(f"/api/v1/conversations/{chat.id}", headers=chat.headers).status_code == 401
    session = client.app.state.session_factory()
    try:
        for model in (Conversation, ConversationMessage, ClinicalObservation, TriageAssessment):
            assert session.scalars(select(model)).all() == []
        assert all(e.conversation_id is None for e in session.scalars(select(AuditEvent)))
    finally:
        session.close()


def test_expired_conversations_are_rejected_and_purged(client):
    from datetime import UTC, datetime, timedelta

    from app.database.repository import ConversationRepository

    chat = Chat(client)
    session = client.app.state.session_factory()
    conv = session.get(Conversation, chat.id)
    conv.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()
    assert client.get(f"/api/v1/conversations/{chat.id}", headers=chat.headers).status_code == 401
    assert ConversationRepository(session).purge_expired() == 1
    session.commit()
    assert session.get(Conversation, chat.id) is None
    session.close()


def test_conversation_message_limit(make_client):
    client = make_client(max_messages_per_conversation=5)
    chat = Chat(client)
    codes = [client.post(f"/api/v1/conversations/{chat.id}/messages", headers=chat.headers, json={"text": "hmm"}).status_code
             for _ in range(5)]
    assert 409 in codes


# ---- voice pipeline -------------------------------------------------------
def test_voice_pipeline_end_to_end(make_client):
    stt = FakeSTT(Transcript("Do din se bukhar hai", "hi", 0.9, False))
    client = make_client(Providers(stt=stt, tts=FakeTTS()))
    chat = Chat(client)
    files = {"audio": ("a.wav", wav_bytes(1.0), "audio/wav")}
    r = client.post(f"/api/v1/conversations/{chat.id}/audio/transcribe", headers=chat.headers, files=files, data={"language_hint": "hi"})
    body = r.json()
    assert r.status_code == 200 and body["text"] == "Do din se bukhar hai" and body["usable"] and stt.last_hint == "hi"
    chat.say(body["text"], source="voice")
    assert chat.last["state"]["symptoms"][0]["name"] == "fever"
    sp = client.post(f"/api/v1/conversations/{chat.id}/speech", headers=chat.headers)
    assert sp.status_code == 200 and sp.headers["content-type"] == "audio/mpeg"


def test_low_confidence_and_quiet_audio_are_flagged(make_client):
    stt = FakeSTT(Transcript("", None, 0.1, True, ("empty_transcript",)))
    client = make_client(Providers(stt=stt))
    chat = Chat(client)
    r = client.post(f"/api/v1/conversations/{chat.id}/audio/transcribe", headers=chat.headers,
                    files={"audio": ("a.wav", wav_bytes(1.0, amplitude=5), "audio/wav")})
    body = r.json()
    assert r.status_code == 200 and body["usable"] is False and "very_quiet_audio" in body["warnings"]


def test_provider_failures_degrade_gracefully(make_client):
    stt = FakeSTT(ProviderError("fake", "timeout", retryable=True))
    client = make_client(Providers(stt=stt, tts=FakeTTS(fail=True)))
    chat = Chat(client)
    r = client.post(f"/api/v1/conversations/{chat.id}/audio/transcribe", headers=chat.headers,
                    files={"audio": ("a.wav", wav_bytes(1.0), "audio/wav")})
    assert r.status_code == 503 and "type your message" in r.json()["error"]["message"]
    assert client.post(f"/api/v1/conversations/{chat.id}/speech", headers=chat.headers).status_code == 503
    # text path still works
    assert client.post(f"/api/v1/conversations/{chat.id}/messages", headers=chat.headers, json={"text": "bukhar hai"}).status_code == 200


def test_voice_unavailable_without_provider(client):
    chat = Chat(client)
    r = client.post(f"/api/v1/conversations/{chat.id}/audio/transcribe", headers=chat.headers,
                    files={"audio": ("a.wav", wav_bytes(1.0), "audio/wav")})
    assert r.status_code == 503


def test_migrations_match_models(settings):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    from app.models.orm import Base

    with create_engine(settings.database_url).connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
