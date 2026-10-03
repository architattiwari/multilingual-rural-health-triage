"""HTTP routes under /api/v1."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import text

from app import __version__
from app.clinical.questions import get_question
from app.core.errors import AppError, PayloadTooLarge
from app.core.versions import API_VERSION, ENGINE_VERSION, RULES_VERSION
from app.domain.clinical import ClinicalState
from app.services.conversation_service import TriageNotReady, TurnOutcome, result_from_assessment
from app.services.localization import DISCLAIMER, TEMPLATE_LANGUAGES, emergency_contact

from .deps import ConversationDep, DbDep, ServiceDep, SettingsDep, heavy_rate_limit, rate_limit
from .schemas import (
    AnswerIn,
    ConversationCreate,
    ConversationCreated,
    ConversationOut,
    ErrorResponse,
    ExtractIn,
    HealthOut,
    MessageIn,
    MessageOut,
    MetaOut,
    QuestionOut,
    StateSummary,
    SymptomOut,
    TranscriptOut,
    TriageOut,
    TurnResponse,
)

router = APIRouter(prefix=f"/api/{API_VERSION}", dependencies=[Depends(rate_limit)])

_ERR = {401: {"model": ErrorResponse, "description": "Missing or invalid conversation token"},
        422: {"model": ErrorResponse, "description": "Validation failed"},
        429: {"model": ErrorResponse, "description": "Rate limited"}}


class TriageNotReadyError(AppError):
    status_code = 409
    code = "triage_not_ready"
    public_message = "A final triage result is not available yet. Please finish answering the questions."


def _state_summary(state: ClinicalState) -> StateSummary:
    symptoms = [
        SymptomOut(name=s.name, original_text=s.original_text, normalized_concept=s.normalized_concept, confidence=s.confidence,
                   requires_clarification=s.requires_clarification, duration_days=s.duration.days if s.duration else None,
                   severity=s.severity.value)
        for s in state.symptoms if state.present(s.concept) and s.concept != "unspecified_critical_symptom"
    ]
    return StateSummary(language=state.language, detected_language=state.detected_language, age_years=state.patient.age_years,
                        symptoms=symptoms, missing_information=state.missing_information, red_flags=state.red_flags,
                        followup_count=state.followup_count)


def _question_out(question, lang: str) -> QuestionOut:  # type: ignore[no-untyped-def]
    return QuestionOut(question_id=question.question_id, kind=question.kind, required_for_triage=question.required_for_triage,
                       text=question.text(lang if lang in TEMPLATE_LANGUAGES else "hi"))


def _turn_response(conv_id: str, outcome: TurnOutcome, service: ServiceDep) -> TurnResponse:
    triage = None
    if outcome.result and outcome.patient_result and outcome.assessment_id:
        r = outcome.result
        triage = TriageOut(assessment_id=outcome.assessment_id, triage_level=r.triage_level, reason_codes=r.reason_codes,
                           recommended_action=r.recommended_action, confidence=r.confidence,
                           requires_human_review=r.requires_human_review, engine_version=r.engine_version,
                           rules_version=r.rules_version, patient=outcome.patient_result)
    lang = outcome.state.language
    return TurnResponse(
        conversation_id=conv_id, triage_status=outcome.state.triage_status, assistant_message=outcome.assistant_message,
        question=_question_out(outcome.question, lang) if outcome.question else None, triage=triage,
        state=_state_summary(outcome.state), disclaimer=service.localizer.disclaimer(lang),
    )


@router.get("/health", response_model=HealthOut, tags=["system"], summary="Liveness and dependency check")
def health(request: Request, db: DbDep) -> HealthOut:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    checks = {"database": db_ok, **request.app.state.providers.status()}
    return HealthOut(status="ok" if db_ok else "degraded", version=__version__, checks=checks)


@router.get("/meta", response_model=MetaOut, tags=["system"], summary="Client configuration")
def meta(request: Request, settings: SettingsDep) -> MetaOut:
    return MetaOut(
        api_version=API_VERSION, engine_version=ENGINE_VERSION, rules_version=RULES_VERSION,
        languages=list(TEMPLATE_LANGUAGES) + settings.translation_language_list,
        limits={"max_text_chars": settings.max_text_chars, "max_audio_bytes": settings.max_audio_bytes,
                "max_audio_seconds": settings.max_audio_seconds},
        providers=request.app.state.providers.status(), emergency_contact=emergency_contact(settings),
        disclaimers=dict(DISCLAIMER),
    )


@router.post("/conversations", response_model=ConversationCreated, status_code=201, tags=["conversation"],
             responses={429: _ERR[429]}, summary="Start a conversation")
def create_conversation(body: ConversationCreate, request: Request, service: ServiceDep, settings: SettingsDep) -> ConversationCreated:
    conv, token, message = service.create(body.language, request.state.request_id)
    return ConversationCreated(
        conversation_id=conv.id, access_token=token, language=conv.language, assistant_message=message,
        disclaimer=service.localizer.disclaimer(conv.language), expires_in_hours=settings.conversation_retention_hours,
        emergency_contact=emergency_contact(settings),
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut, tags=["conversation"],
            responses={401: _ERR[401]}, summary="Retrieve a conversation")
def get_conversation(conv: ConversationDep, service: ServiceDep) -> ConversationOut:
    state = service.load_state(conv)
    messages = [MessageOut(role=m.role, text=m.content, source=m.source, created_at=m.created_at.isoformat())  # type: ignore[arg-type]
                for m in service.repo.messages(conv.id)]
    pending = get_question(state.pending_question_id) if state.pending_question_id else None
    return ConversationOut(conversation_id=conv.id, triage_status=state.triage_status, messages=messages,
                           state=_state_summary(state), pending_question=_question_out(pending, state.language) if pending else None,
                           disclaimer=service.localizer.disclaimer(state.language))


@router.delete("/conversations/{conversation_id}", status_code=204, tags=["conversation"], responses={401: _ERR[401]},
               summary="Delete a conversation and all its stored messages")
def delete_conversation(conv: ConversationDep, service: ServiceDep, request: Request) -> Response:
    service.delete(conv, request.state.request_id)
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/audio/transcribe", response_model=TranscriptOut, tags=["voice"],
             dependencies=[Depends(heavy_rate_limit)], responses={401: _ERR[401], 413: {}, 415: {}, 503: {}},
             summary="Convert a voice recording to text")
async def transcribe(conv: ConversationDep, service: ServiceDep, settings: SettingsDep, request: Request,
                     audio: Annotated[UploadFile, File(description="webm, ogg, wav, mp3 or m4a, max 5 MB")],
                     language_hint: Annotated[str | None, Form(max_length=10)] = None) -> TranscriptOut:
    data = await audio.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise PayloadTooLarge()
    # Provider call is blocking, so run it off the event loop.
    from starlette.concurrency import run_in_threadpool

    transcript, info = await run_in_threadpool(service.transcribe, conv, data, audio.content_type, language_hint,
                                               request.state.request_id)
    usable = bool(transcript.text.strip()) and not transcript.low_confidence
    return TranscriptOut(text=transcript.text, language=transcript.language, confidence=transcript.confidence,
                         low_confidence=transcript.low_confidence, usable=usable, warnings=list(transcript.warnings),
                         duration_seconds=info.duration_seconds)


@router.post("/conversations/{conversation_id}/extract", tags=["analysis"], responses={401: _ERR[401], 422: _ERR[422]},
             summary="Preview entity extraction for a text without changing the conversation")
def extract_preview(body: ExtractIn, conv: ConversationDep, service: ServiceDep) -> dict:
    return service.preview_extraction(body.text)


@router.post("/conversations/{conversation_id}/messages", response_model=TurnResponse, tags=["conversation"],
             dependencies=[Depends(heavy_rate_limit)], responses={401: _ERR[401], 409: {}, 422: _ERR[422]},
             summary="Submit a patient message")
def post_message(body: MessageIn, conv: ConversationDep, service: ServiceDep, request: Request) -> TurnResponse:
    outcome = service.process_turn(conv, body.text, source=body.source, question_id=None, language_hint=body.language_hint,
                                   request_id=request.state.request_id)
    return _turn_response(conv.id, outcome, service)


@router.post("/conversations/{conversation_id}/answers", response_model=TurnResponse, tags=["conversation"],
             dependencies=[Depends(heavy_rate_limit)], responses={401: _ERR[401], 422: _ERR[422]},
             summary="Answer the current follow up question")
def post_answer(body: AnswerIn, conv: ConversationDep, service: ServiceDep, request: Request) -> TurnResponse:
    outcome = service.process_turn(conv, body.text, source=body.source, question_id=body.question_id,
                                   language_hint=body.language_hint, request_id=request.state.request_id)
    return _turn_response(conv.id, outcome, service)


@router.get("/conversations/{conversation_id}/next-question", response_model=QuestionOut | None, tags=["conversation"],
            responses={401: _ERR[401]}, summary="The question currently waiting for an answer, if any")
def next_question_route(conv: ConversationDep, service: ServiceDep) -> QuestionOut | None:
    state = service.load_state(conv)
    pending = get_question(state.pending_question_id) if state.pending_question_id else None
    return _question_out(pending, state.language) if pending else None


@router.post("/conversations/{conversation_id}/triage", response_model=TurnResponse, tags=["triage"],
             responses={401: _ERR[401]}, summary="Evaluate triage now with the information collected so far")
def evaluate_triage(conv: ConversationDep, service: ServiceDep, request: Request) -> TurnResponse:
    outcome = service.evaluate_now(conv, request.state.request_id)
    return _turn_response(conv.id, outcome, service)


@router.get("/conversations/{conversation_id}/triage", response_model=TriageOut, tags=["triage"],
            responses={401: _ERR[401], 409: {"model": ErrorResponse}}, summary="Latest final triage result")
def get_triage(conv: ConversationDep, service: ServiceDep) -> TriageOut:
    try:
        row, state = service.latest_final(conv)
    except TriageNotReady as exc:
        raise TriageNotReadyError() from exc
    result = result_from_assessment(row, state)
    return TriageOut(assessment_id=row.id, triage_level=result.triage_level, reason_codes=result.reason_codes,
                     recommended_action=result.recommended_action, confidence=None,
                     requires_human_review=result.requires_human_review, engine_version=result.engine_version,
                     rules_version=result.rules_version, patient=service.localizer.render_result(result, state.language))


@router.post("/conversations/{conversation_id}/speech", tags=["voice"], dependencies=[Depends(heavy_rate_limit)],
             responses={200: {"content": {"audio/mpeg": {}}}, 401: _ERR[401], 503: {}},
             summary="Read the latest assistant message aloud")
def speech(conv: ConversationDep, service: ServiceDep) -> Response:
    clip = service.speak(conv)
    return Response(content=clip.data, media_type=clip.content_type, headers={"Cache-Control": "no-store"})
