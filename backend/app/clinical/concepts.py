"""Catalogue of clinical concepts the system understands.

Each concept has a stable id used by rules, questions and storage. Display
labels here are English and internal. Patient facing wording lives in
services.localization.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    red_flag: bool = False
    ambiguous: bool = False
    location: str | None = None


def _c(id_: str, label: str, **kw: object) -> Concept:
    return Concept(id_, label, **kw)  # type: ignore[arg-type]


CONCEPTS: dict[str, Concept] = {
    c.id: c
    for c in [
        _c("fever", "fever"),
        _c("headache", "headache", location="head"),
        _c("head_heaviness", "head heaviness", ambiguous=True, location="head"),
        _c("cough", "cough", location="chest"),
        _c("sore_throat", "sore throat", location="throat"),
        _c("cold_symptoms", "cold or runny nose"),
        _c("chills", "chills"),
        _c("body_pain", "body ache"),
        _c("weakness", "weakness or tiredness", ambiguous=True),
        _c("dizziness", "dizziness", ambiguous=True),
        _c("palpitations", "fast heartbeat or nervousness", ambiguous=True, location="chest"),
        _c("vomiting", "vomiting"),
        _c("nausea", "nausea"),
        _c("diarrhea", "loose stools"),
        _c("stomach_upset", "stomach upset", ambiguous=True, location="abdomen"),
        _c("abdominal_pain", "abdominal pain", location="abdomen"),
        _c("rash", "rash or itching"),
        _c("dysuria", "burning urination"),
        _c("blood_in_urine", "blood in urine"),
        _c("blood_in_stool", "blood in stool"),
        _c("jaundice", "yellow eyes or skin"),
        _c("vision_change", "vision change"),
        _c("bleeding", "bleeding"),
        _c("injury", "injury"),
        _c("burn", "burn"),
        _c("head_injury", "head injury", location="head"),
        _c("neck_stiffness", "stiff neck", location="neck"),
        _c("dehydration_signs", "signs of dehydration"),
        # Red flag concepts. Any of these present can trigger emergency rules.
        _c("breathlessness", "difficulty breathing", red_flag=True, location="chest"),
        _c("chest_pain", "chest pain", red_flag=True, location="chest"),
        _c("loss_of_consciousness", "fainting or unconsciousness", red_flag=True),
        _c("confusion", "confusion", red_flag=True),
        _c("stroke_signs", "possible stroke signs", red_flag=True),
        _c("severe_bleeding", "heavy bleeding", red_flag=True),
        _c("gi_bleeding_severe", "vomiting blood or black stool", red_flag=True),
        _c("allergic_severe", "swelling of face, lips or throat", red_flag=True),
        _c("seizure", "seizure", red_flag=True),
        _c("snakebite", "snake bite", red_flag=True),
        _c("poisoning", "possible poisoning or overdose", red_flag=True),
        _c("worst_headache", "worst headache of life", red_flag=True, location="head"),
        _c("self_harm", "thoughts of self harm", red_flag=True),
        _c("unspecified_critical_symptom", "unspecified critical symptom", red_flag=True),
    ]
}

# Yes/no screening groups. Answering "no" marks each member absent.
SCREEN_A = ("breathlessness", "chest_pain", "loss_of_consciousness")
SCREEN_B = ("stroke_signs", "seizure", "severe_bleeding", "confusion")

# Concepts that count as clinical symptoms for rules that say "any symptom".
NON_SYMPTOM = {"unspecified_critical_symptom"}

HIGH_RISK_CONTEXT = {"diabetes", "heart_disease", "kidney_disease", "cancer", "asthma", "chronic_condition"}


def is_red_flag(concept: str) -> bool:
    c = CONCEPTS.get(concept)
    return bool(c and c.red_flag)
