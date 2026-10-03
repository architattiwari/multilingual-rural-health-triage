"""Medically reviewed triage ruleset, expressed as data plus small predicates.

Rules are deliberately conservative: when in doubt they escalate. Every rule
has a stable id and reason code that is stored in the audit trail.

REVIEW REQUIRED: these rules are an engineering baseline derived from widely
used symptom red flags. They have NOT been clinically validated. A qualified
clinician must review and sign off before any patient facing use. Bump
RULES_VERSION in core/versions.py after every change.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.clinical import ClinicalState, FindingStatus, Severity, TriageLevel

from .concepts import HIGH_RISK_CONTEXT, NON_SYMPTOM


class Facts:
    """Read only view over the clinical state used by rule predicates."""

    def __init__(self, state: ClinicalState) -> None:
        self.s = state

    def has(self, *concepts: str) -> bool:
        return any(self.s.status(c) == FindingStatus.PRESENT for c in concepts)

    @property
    def age(self) -> float | None:
        return self.s.patient.age_years

    @property
    def temp(self) -> float | None:
        return self.s.temperature_c

    @property
    def pregnant(self) -> bool:
        return self.s.patient.pregnant is True

    def severity(self, concept: str) -> Severity:
        sym = self.s.symptom(concept)
        return sym.severity if sym else Severity.UNKNOWN

    def duration_days(self, concept: str) -> float | None:
        sym = self.s.symptom(concept)
        return sym.duration.days if sym and sym.duration else None

    def max_duration_days(self) -> float:
        values = [sym.duration.days for sym in self.s.symptoms if sym.duration and self.has(sym.concept)]
        return max(values, default=0.0)

    def any_symptom(self) -> bool:
        return any(self.has(sym.concept) for sym in self.s.symptoms if sym.concept not in NON_SYMPTOM)

    def any_severe(self) -> bool:
        return any(sym.severity == Severity.SEVERE and self.has(sym.concept) for sym in self.s.symptoms)

    def high_risk_context(self) -> bool:
        return bool(HIGH_RISK_CONTEXT & set(self.s.medical_context))

    def young_or_old(self) -> bool:
        return self.age is not None and (self.age < 5 or self.age >= 65)


@dataclass(frozen=True)
class Rule:
    id: str
    level: TriageLevel
    reason_code: str
    description: str
    predicate: Callable[[Facts], bool]


E, U = TriageLevel.EMERGENCY, TriageLevel.URGENT

EMERGENCY_RULES: list[Rule] = [
    Rule("E01", E, "breathing_difficulty", "Difficulty breathing not described as mild",
         lambda f: f.has("breathlessness") and f.severity("breathlessness") != Severity.MILD),
    Rule("E02", E, "chest_pain", "Chest pain of any severity", lambda f: f.has("chest_pain")),
    Rule("E03", E, "loss_of_consciousness", "Fainting or unconsciousness", lambda f: f.has("loss_of_consciousness")),
    Rule("E04", E, "new_confusion", "Confusion", lambda f: f.has("confusion")),
    Rule("E05", E, "stroke_signs", "Face droop, one sided weakness or speech difficulty", lambda f: f.has("stroke_signs")),
    Rule("E06", E, "heavy_bleeding", "Heavy or uncontrolled bleeding", lambda f: f.has("severe_bleeding")),
    Rule("E07", E, "gi_bleeding", "Vomiting blood or black stool", lambda f: f.has("gi_bleeding_severe")),
    Rule("E08", E, "severe_allergic_reaction", "Swelling of face, lips, tongue or throat", lambda f: f.has("allergic_severe")),
    Rule("E09", E, "seizure", "Seizure or convulsions", lambda f: f.has("seizure")),
    Rule("E10", E, "snakebite", "Snake bite", lambda f: f.has("snakebite")),
    Rule("E11", E, "poisoning_or_overdose", "Poison, pesticide or overdose", lambda f: f.has("poisoning")),
    Rule("E12", E, "critical_symptom_reported", "Patient confirmed breathing, chest or fainting problem",
         lambda f: f.has("unspecified_critical_symptom")),
    Rule("E13", E, "mental_health_crisis", "Thoughts of self harm", lambda f: f.has("self_harm")),
    Rule("E14", E, "fever_with_stiff_neck", "Fever with stiff neck", lambda f: f.has("fever") and f.has("neck_stiffness")),
    Rule("E15", E, "very_high_fever", "Temperature at or above 41 C", lambda f: f.temp is not None and f.temp >= 41.0),
    Rule("E16", E, "infant_fever", "Fever in a baby under 3 months", lambda f: f.has("fever") and f.age is not None and f.age < 0.25),
    Rule("E17", E, "dehydration_high_risk", "Dehydration signs with vomiting or diarrhoea in a high risk person",
         lambda f: f.has("dehydration_signs") and f.has("vomiting", "diarrhea")
         and (f.young_or_old() or f.severity("weakness") == Severity.SEVERE or f.has("dizziness"))),
    Rule("E18", E, "pregnancy_bleeding_or_severe_pain", "Bleeding or severe abdominal pain in pregnancy",
         lambda f: f.pregnant and (f.has("bleeding") or (f.has("abdominal_pain") and f.severity("abdominal_pain") == Severity.SEVERE))),
    Rule("E19", E, "worst_headache", "Sudden severe headache", lambda f: f.has("worst_headache")),
    Rule("E20", E, "head_injury_with_vomiting", "Head injury with vomiting", lambda f: f.has("head_injury") and f.has("vomiting")),
    Rule("E21", E, "severe_burn", "Severe burn", lambda f: f.has("burn") and f.severity("burn") == Severity.SEVERE),
]

URGENT_RULES: list[Rule] = [
    Rule("U01", U, "high_fever", "Temperature at or above 39.5 C", lambda f: f.has("fever") and f.temp is not None and f.temp >= 39.5),
    Rule("U02", U, "persistent_fever", "Fever for 3 days or more",
         lambda f: f.has("fever") and (f.duration_days("fever") or 0) >= 3),
    Rule("U03", U, "fever_young_or_old", "Fever in a child under 5 or adult 65 and over", lambda f: f.has("fever") and f.young_or_old()),
    Rule("U04", U, "fever_in_pregnancy", "Fever during pregnancy", lambda f: f.has("fever") and f.pregnant),
    Rule("U05", U, "fever_with_chronic_condition", "Fever with a chronic condition", lambda f: f.has("fever") and f.high_risk_context()),
    Rule("U06", U, "dehydration_signs", "Dehydration signs with vomiting or diarrhoea",
         lambda f: f.has("dehydration_signs") and f.has("vomiting", "diarrhea")),
    Rule("U07", U, "persistent_vomiting_or_diarrhea", "Vomiting or loose stools for 2 days or more, or in a young or old person",
         lambda f: f.has("vomiting", "diarrhea") and (f.max_duration_days() >= 2 or f.young_or_old())),
    Rule("U08", U, "blood_in_stool_or_urine", "Blood in stool or urine", lambda f: f.has("blood_in_stool", "blood_in_urine")),
    Rule("U09", U, "bleeding", "Bleeding that is not clearly minor", lambda f: f.has("bleeding")),
    Rule("U10", U, "severe_symptom", "A symptom described as severe", lambda f: f.any_severe()),
    Rule("U11", U, "abdominal_pain_with_fever_or_vomiting", "Abdominal pain with fever or vomiting",
         lambda f: f.has("abdominal_pain") and f.has("fever", "vomiting")),
    Rule("U12", U, "persistent_cough", "Cough for 14 days or more", lambda f: f.has("cough") and (f.duration_days("cough") or 0) >= 14),
    Rule("U13", U, "prolonged_symptoms", "Any symptom for 7 days or more", lambda f: f.max_duration_days() >= 7),
    Rule("U14", U, "worsening", "Symptoms are getting worse", lambda f: f.any_symptom() and f.s.progression == "worsening"),
    Rule("U15", U, "stiff_neck", "Stiff neck", lambda f: f.has("neck_stiffness")),
    Rule("U16", U, "injury", "Injury or burn", lambda f: f.has("injury", "head_injury", "burn")),
    Rule("U17", U, "jaundice_or_vision_change", "Yellow eyes or vision change", lambda f: f.has("jaundice", "vision_change")),
    Rule("U18", U, "mild_breathing_difficulty", "Breathing difficulty described as mild",
         lambda f: f.has("breathlessness") and f.severity("breathlessness") == Severity.MILD),
    Rule("U19", U, "palpitations_high_risk", "Fast heartbeat in an older person or with heart disease",
         lambda f: f.has("palpitations") and ((f.age or 0) >= 60 or "heart_disease" in f.s.medical_context)),
    Rule("U20", U, "symptoms_in_pregnancy", "Fever, vomiting, pain, dizziness or headache in pregnancy",
         lambda f: f.pregnant and f.has("vomiting", "abdominal_pain", "dizziness", "headache")),
    Rule("U21", U, "infant_unwell", "Any symptom in a child under 1 year", lambda f: f.age is not None and f.age < 1 and f.any_symptom()),
]

INSUFFICIENT_INFORMATION = Rule(
    "U99", U, "insufficient_information", "Required safety information is missing", lambda f: True
)
