import pytest

from app.clinical.concepts import SCREEN_A, SCREEN_B
from app.clinical.questions import QUESTION_BANK, next_question, required_outstanding
from app.clinical.state import merge_extraction
from app.clinical.triage import evaluate
from app.domain.clinical import ClinicalState, Duration, ExtractedSymptom, ExtractionResult, FindingStatus, Severity, TriageLevel


def state_with(*present: str, age: float | None = 30, **kw) -> ClinicalState:
    s = ClinicalState(conversation_id="c")
    s.patient.age_years = age
    for c in present:
        s.findings[c] = FindingStatus.PRESENT
        from app.domain.clinical import Symptom
        s.symptoms.append(Symptom(concept=c, name=c, original_text=c, normalized_concept=c, confidence=0.9,
                                  duration=kw.get("duration")))
    for c in SCREEN_A + SCREEN_B:
        s.findings.setdefault(c, FindingStatus.ABSENT)
    s.findings.setdefault("dehydration_signs", FindingStatus.ABSENT)
    for k in ("temperature_c", "progression"):
        if k in kw:
            setattr(s, k, kw[k])
    return s


def level(s: ClinicalState, finalize=False) -> TriageLevel:
    return evaluate(s, required_outstanding=required_outstanding(s), finalize=finalize).triage_level


@pytest.mark.parametrize("concept", ["chest_pain", "loss_of_consciousness", "confusion", "stroke_signs", "severe_bleeding",
                                     "gi_bleeding_severe", "allergic_severe", "seizure", "snakebite", "poisoning", "self_harm",
                                     "unspecified_critical_symptom", "worst_headache", "breathlessness"])
def test_every_red_flag_concept_is_emergency(concept):
    assert level(state_with(concept)) == TriageLevel.EMERGENCY


def test_mild_breathing_difficulty_is_urgent_not_reassuring():
    s = state_with("breathlessness")
    s.symptom("breathlessness").severity = Severity.MILD
    assert level(s) == TriageLevel.URGENT


def test_fever_rules():
    d = lambda n: Duration(value=n, unit="days")  # noqa: E731
    assert level(state_with("fever", duration=d(1))) == TriageLevel.NON_URGENT
    assert level(state_with("fever", duration=d(3))) == TriageLevel.URGENT
    assert level(state_with("fever", duration=d(1), temperature_c=39.6)) == TriageLevel.URGENT
    assert level(state_with("fever", duration=d(1), temperature_c=41.2)) == TriageLevel.EMERGENCY
    assert level(state_with("fever", age=70, duration=d(1))) == TriageLevel.URGENT
    assert level(state_with("fever", "neck_stiffness", duration=d(1))) == TriageLevel.EMERGENCY
    assert level(state_with("fever", age=0.1, duration=d(1))) == TriageLevel.EMERGENCY


def test_pregnancy_bleeding_is_emergency():
    s = state_with("bleeding")
    s.patient.pregnant = True
    assert level(s) == TriageLevel.EMERGENCY


def test_dehydration_rules():
    s = state_with("vomiting", "dehydration_signs", age=3)
    assert level(s) == TriageLevel.EMERGENCY
    assert level(state_with("diarrhea", "dehydration_signs", age=30)) == TriageLevel.URGENT


def test_level_never_drops_once_reached():
    s = state_with("chest_pain")
    s.max_level_reached = TriageLevel.EMERGENCY
    s.findings["chest_pain"] = FindingStatus.ABSENT
    assert level(s) == TriageLevel.EMERGENCY


def test_finalize_with_missing_required_information_is_urgent():
    s = ClinicalState(conversation_id="c")
    s.findings["fever"] = FindingStatus.PRESENT
    assert level(s, finalize=True) == TriageLevel.URGENT


def test_engine_is_deterministic_and_has_no_confidence_claim():
    s = state_with("fever")
    a = evaluate(s, required_outstanding=[]).model_dump()
    b = evaluate(s, required_outstanding=[]).model_dump()
    assert a == b and a["confidence"] is None


def test_present_red_flag_survives_later_negation():
    s = state_with("chest_pain")
    merge_extraction(s, ExtractionResult(negated=["chest_pain"]))
    assert s.present("chest_pain") and "chest_pain:negated_after_present" in s.conflicts


def test_absent_can_become_present():
    s = ClinicalState(conversation_id="c")
    s.findings["fever"] = FindingStatus.ABSENT
    merge_extraction(s, ExtractionResult(symptoms=[ExtractedSymptom(concept="fever", original_text="bukhar", confidence=0.9)]))
    assert s.present("fever")


# ---- question engine -----------------------------------------------------
def test_critical_screen_comes_first():
    s = ClinicalState(conversation_id="c")
    merge_extraction(s, ExtractionResult(symptoms=[ExtractedSymptom(concept="fever", original_text="bukhar", confidence=0.9)]))
    assert next_question(s).question_id == "screen_critical_a"


def test_chief_complaint_before_anything():
    assert next_question(ClinicalState(conversation_id="c")).question_id == "chief_complaint"


def test_no_questions_when_nothing_matters():
    s = state_with("cough", duration=Duration(value=1, unit="days"))
    assert next_question(s) is None


def test_age_asked_when_missing():
    s = state_with("cough", age=None, duration=Duration(value=1, unit="days"))
    assert next_question(s).question_id == "age"


def test_optional_questions_are_capped():
    s = state_with("fever", duration=Duration(value=1, unit="days"))
    s.asked_questions = {"fever_temperature": 1, "chronic_conditions": 1}
    s.answered_questions = ["fever_temperature", "chronic_conditions"]
    assert next_question(s) is None


def test_question_metadata_is_complete():
    ids = [q.question_id for q in QUESTION_BANK]
    assert len(ids) == len(set(ids))
    for q in QUESTION_BANK:
        assert {"hi", "hi-Latn", "en"} <= set(q.language_templates)
        assert q.priority in (0, 1, 2, 3)
