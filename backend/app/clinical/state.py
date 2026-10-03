"""Merging extraction results into the persisted clinical state.

Safety asymmetry: information can move toward "present" freely, but a present
red flag is never cleared by a later negation. A contradiction is recorded as
a conflict and flagged for human review instead.
"""

from dataclasses import dataclass

from app.domain.clinical import (
    ClinicalState,
    ExtractedSymptom,
    ExtractionResult,
    FindingStatus,
    Severity,
    Symptom,
)

from .concepts import CONCEPTS, NON_SYMPTOM, is_red_flag

_SEVERITY_ORDER = {Severity.UNKNOWN: 0, Severity.MILD: 1, Severity.MODERATE: 2, Severity.SEVERE: 3}


@dataclass(frozen=True)
class Observation:
    """Append only record written to the ClinicalObservation table. Holds no free text."""

    kind: str
    concept: str
    status: str
    source: str
    confidence: float | None = None


def _add_conflict(state: ClinicalState, tag: str) -> None:
    if tag not in state.conflicts:
        state.conflicts.append(tag)


def _merge_symptom(state: ClinicalState, ex: ExtractedSymptom) -> Observation | None:
    concept = CONCEPTS.get(ex.concept)
    if concept is None:
        return None
    previous_status = state.status(ex.concept)
    state.findings[ex.concept] = FindingStatus.PRESENT
    existing = state.symptom(ex.concept)
    clarified = f"clarify_{ex.concept}" in state.answered_questions
    if existing is None:
        state.symptoms.append(
            Symptom(
                concept=ex.concept,
                name=concept.label,
                original_text=ex.original_text,
                normalized_concept=concept.label,
                confidence=ex.confidence,
                requires_clarification=concept.ambiguous and not clarified,
                body_location=concept.location,
                duration=ex.duration,
                severity=ex.severity,
                sudden_onset=ex.sudden_onset,
                source=ex.source,
            )
        )
    else:
        if _SEVERITY_ORDER[ex.severity] > _SEVERITY_ORDER[existing.severity]:
            existing.severity = ex.severity
        if existing.duration is None and ex.duration is not None:
            existing.duration = ex.duration
        existing.sudden_onset = existing.sudden_onset or ex.sudden_onset
        existing.confidence = max(existing.confidence, ex.confidence)
    if previous_status == FindingStatus.PRESENT:
        return None
    return Observation("symptom", ex.concept, "present", ex.source, ex.confidence)


def merge_extraction(state: ClinicalState, ex: ExtractionResult) -> list[Observation]:
    """Apply an extraction to the state in place and return new observations."""
    changes: list[Observation] = []

    for symptom in ex.symptoms:
        obs = _merge_symptom(state, symptom)
        if obs:
            changes.append(obs)

    for concept in ex.negated:
        current = state.status(concept)
        if current == FindingStatus.PRESENT:
            _add_conflict(state, f"{concept}:negated_after_present")
        elif current == FindingStatus.UNKNOWN:
            state.findings[concept] = FindingStatus.ABSENT
            changes.append(Observation("finding", concept, "absent", "rules"))

    patient = state.patient
    if ex.age_years is not None:
        if patient.age_years is not None and abs(patient.age_years - ex.age_years) > 0.01:
            _add_conflict(state, "age:conflicting_values")
        patient.age_years = ex.age_years
        changes.append(Observation("patient", "age", "present", "rules"))
    if ex.sex and patient.sex is None:
        patient.sex = ex.sex
        changes.append(Observation("patient", "sex", "present", "rules"))
    if ex.pregnant is not None:
        if patient.pregnant is True and ex.pregnant is False:
            _add_conflict(state, "pregnancy:conflicting_values")
        else:
            patient.pregnant = ex.pregnant
            changes.append(Observation("patient", "pregnancy", "present", "rules"))
    if ex.temperature_c is not None:
        state.temperature_c = max(ex.temperature_c, state.temperature_c or 0)
        changes.append(Observation("measurement", "temperature", "present", "rules"))
    for tag in ex.context:
        if tag not in state.medical_context:
            state.medical_context.append(tag)
            changes.append(Observation("context", tag, "present", "rules"))
    if ex.progression and state.progression != "worsening":
        state.progression = ex.progression
        for s in state.symptoms:
            s.progression = state.progression

    refresh_derived(state)
    return changes


def refresh_derived(state: ClinicalState) -> None:
    state.red_flags = sorted(c for c, s in state.findings.items() if s == FindingStatus.PRESENT and is_red_flag(c))
    state.risk_factors = sorted(state.medical_context)


def present_symptoms(state: ClinicalState) -> list[Symptom]:
    return [s for s in state.symptoms if s.concept not in NON_SYMPTOM and state.present(s.concept)]
