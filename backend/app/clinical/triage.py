"""Deterministic, safety first triage engine.

Pure function of the clinical state. No network, no randomness, no LLM, so the
same input always yields the same output and every decision can be audited.
"""

from pydantic import BaseModel

from app.core.versions import ENGINE_VERSION, RULES_VERSION
from app.domain.clinical import ClinicalState, TriageLevel

from .rules import EMERGENCY_RULES, INSUFFICIENT_INFORMATION, URGENT_RULES, Facts, Rule

_ACTIONS = {
    TriageLevel.EMERGENCY: "seek_emergency_care_now",
    TriageLevel.URGENT: "seek_medical_evaluation_promptly",
    TriageLevel.NON_URGENT: "routine_consultation_and_monitoring",
}
_RANK = {TriageLevel.NON_URGENT: 0, TriageLevel.URGENT: 1, TriageLevel.EMERGENCY: 2}


class TriageResult(BaseModel):
    triage_level: TriageLevel
    reason_codes: list[str]
    rules_triggered: list[str]
    red_flags: list[str]
    recommended_action: str
    confidence: float | None = None  # intentionally null: no calibrated probability exists
    requires_human_review: bool
    information_complete: bool
    information_used: list[str]
    engine_version: str = ENGINE_VERSION
    rules_version: str = RULES_VERSION


def _fired(rules: list[Rule], facts: Facts) -> list[Rule]:
    return [r for r in rules if r.predicate(facts)]


def evaluate(state: ClinicalState, *, required_outstanding: list[str], finalize: bool = False) -> TriageResult:
    """Evaluate the state.

    required_outstanding lists safety questions that are still unanswered. When
    finalize is true and some remain, the result defaults to urgent because the
    system must not give reassurance without the information it needs.
    """
    facts = Facts(state)
    emergency = _fired(EMERGENCY_RULES, facts)
    urgent = _fired(URGENT_RULES, facts)

    fired: list[Rule]
    if emergency:
        level, fired = TriageLevel.EMERGENCY, emergency
    elif urgent:
        level, fired = TriageLevel.URGENT, urgent
    elif finalize and required_outstanding:
        level, fired = TriageLevel.URGENT, [INSUFFICIENT_INFORMATION]
    else:
        level, fired = TriageLevel.NON_URGENT, []

    reasons = [r.reason_code for r in fired]
    # A level once reached never drops within a conversation.
    if state.max_level_reached and _RANK[state.max_level_reached] > _RANK[level]:
        level = state.max_level_reached
        reasons.append("level_retained_from_earlier_turn")
    information_used = sorted(
        {c for c, st in state.findings.items() if st.value != "unknown"}
        | ({"age"} if state.patient.age_years is not None else set())
        | ({"temperature"} if state.temperature_c is not None else set())
        | ({"pregnancy"} if state.patient.pregnant is not None else set())
    )
    return TriageResult(
        triage_level=level,
        reason_codes=reasons,
        rules_triggered=[r.id for r in fired],
        red_flags=list(state.red_flags),
        recommended_action=_ACTIONS[level],
        requires_human_review=bool(state.conflicts) or (finalize and bool(required_outstanding)),
        information_complete=not required_outstanding,
        information_used=information_used,
    )
