"""Follow up question engine.

Questions are described by metadata (priority, trigger, templates). The next
question is derived from the current clinical state instead of a fixed script,
but critical emergency screening questions always come first.

Question wording here is approved text, not LLM output. A reviewer can read
every sentence a patient may be asked.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Literal

from app.domain.clinical import ClinicalState, Duration, ExtractionResult, FindingStatus

from .concepts import CONCEPTS, SCREEN_A, SCREEN_B
from .extractor import polarity
from .state import Observation
from .text import NUMBER_WORDS, fold_devanagari, tokenize

CRITICAL, HIGH, MEDIUM, LOW = 0, 1, 2, 3
MAX_ASKS = 2  # one ask plus one rephrase when the answer was unclear
MAX_OPTIONAL_QUESTIONS = 2  # keeps the conversation short when nothing safety critical is missing

Kind = Literal["yes_no", "number", "free_text", "duration"]

_B_TRIGGERS = ("headache", "head_heaviness", "dizziness", "weakness", "injury", "head_injury", "bleeding",
               "vomiting", "fever", "neck_stiffness", "abdominal_pain")
_PREGNANCY_TRIGGERS = ("abdominal_pain", "bleeding", "vomiting", "dizziness")


def _unknown_any(state: ClinicalState, concepts: tuple[str, ...]) -> bool:
    return any(state.status(c) == FindingStatus.UNKNOWN for c in concepts)


def _has_any(state: ClinicalState, concepts: tuple[str, ...]) -> bool:
    return any(state.present(c) for c in concepts)


def _childbearing_age(state: ClinicalState) -> bool:
    age = state.patient.age_years
    return age is not None and 12 <= age <= 50


@dataclass(frozen=True)
class Question:
    question_id: str
    clinical_field: str
    priority: int
    required_for_triage: bool
    kind: Kind
    trigger: Callable[[ClinicalState], bool]
    language_templates: dict[str, str]
    trigger_conditions: str = ""
    group: tuple[str, ...] = field(default_factory=tuple)

    def text(self, language: str) -> str:
        return self.language_templates.get(language) or self.language_templates.get("hi") or self.language_templates["en"]


def _clarify_trigger(concept: str, state: ClinicalState) -> bool:
    symptom = state.symptom(concept)
    return bool(state.present(concept) and symptom and symptom.requires_clarification)


def _clarify(concept_id: str, hi: str, hl: str, en: str) -> Question:
    return Question(
        question_id=f"clarify_{concept_id}", clinical_field=concept_id, priority=MEDIUM, required_for_triage=False,
        kind="free_text",
        trigger=partial(_clarify_trigger, concept_id),
        language_templates={"hi": hi, "hi-Latn": hl, "en": en}, trigger_conditions=f"{concept_id} present and ambiguous",
    )


QUESTION_BANK: list[Question] = [
    Question(
        "chief_complaint", "symptoms", CRITICAL, True, "free_text",
        lambda s: not any(s.present(x.concept) for x in s.symptoms),
        {"hi": "आपको क्या तकलीफ है? कृपया अपनी बात बताइए।",
         "hi-Latn": "Aapko kya takleef hai? Kripya apni baat bataiye.",
         "en": "What problem are you having? Please tell me in your own words."},
        "no symptom recorded yet",
    ),
    Question(
        "screen_critical_a", "breathing_chest_consciousness", CRITICAL, True, "yes_no",
        lambda s: _unknown_any(s, SCREEN_A),
        {"hi": "क्या अभी सांस लेने में दिक्कत, सीने में दर्द, या बेहोशी जैसा कुछ हो रहा है?",
         "hi-Latn": "Kya abhi saans lene mein dikkat, seene mein dard, ya behoshi jaisa kuch ho raha hai?",
         "en": "Right now, do you have trouble breathing, chest pain, or fainting?"},
        "always until answered", group=SCREEN_A,
    ),
    Question(
        "screen_critical_b", "stroke_seizure_bleeding_confusion", CRITICAL, True, "yes_no",
        lambda s: _unknown_any(s, SCREEN_B) and (_has_any(s, _B_TRIGGERS) or s.patient.pregnant is True),
        {"hi": "क्या अचानक उलझन, एक तरफ कमजोरी या मुंह टेढ़ा होना, दौरा (झटके), या बहुत ज्यादा खून बहना जैसा कुछ है?",
         "hi-Latn": "Kya achanak uljhan, ek taraf kamzori ya munh tedha hona, daura (jhatke), ya bahut zyada khoon behna jaisa kuch hai?",
         "en": "Is there sudden confusion, weakness on one side or a drooping face, a seizure, or very heavy bleeding?"},
        "headache, dizziness, weakness, injury, bleeding, vomiting, fever, neck stiffness or abdominal pain", group=SCREEN_B,
    ),
    Question(
        "age", "patient.age", HIGH, True, "number",
        lambda s: s.patient.age_years is None,
        {"hi": "मरीज की उम्र कितनी है?", "hi-Latn": "Mareez ki umar kitni hai?", "en": "How old is the patient?"},
        "age unknown",
    ),
    Question(
        "dehydration_check", "dehydration_signs", HIGH, True, "yes_no",
        lambda s: (s.present("vomiting") or s.present("diarrhea")) and s.status("dehydration_signs") == FindingStatus.UNKNOWN,
        {"hi": "क्या पेशाब बहुत कम हो गया है, मुंह बहुत सूख रहा है, या पानी पीते ही उल्टी हो जाती है?",
         "hi-Latn": "Kya peshab bahut kam ho gaya hai, munh bahut sookh raha hai, ya paani peete hi ulti ho jaati hai?",
         "en": "Has urine become very little, is the mouth very dry, or does vomiting start as soon as water is taken?"},
        "vomiting or diarrhoea present",
    ),
    Question(
        "sex", "patient.sex", MEDIUM, True, "yes_no",
        lambda s: s.patient.sex is None and _childbearing_age(s) and _has_any(s, _PREGNANCY_TRIGGERS),
        {"hi": "क्या मरीज महिला हैं?", "hi-Latn": "Kya mareez mahila hain?", "en": "Is the patient a woman?"},
        "age 12 to 50 with abdominal pain, bleeding, vomiting or dizziness",
    ),
    Question(
        "pregnancy", "patient.pregnancy", MEDIUM, True, "yes_no",
        lambda s: s.patient.sex == "female" and s.patient.pregnant is None and _childbearing_age(s) and _has_any(s, _PREGNANCY_TRIGGERS),
        {"hi": "क्या वे गर्भवती हैं या गर्भवती होने की संभावना है?",
         "hi-Latn": "Kya woh garbhvati hain ya garbhvati hone ki sambhavna hai?",
         "en": "Is she pregnant, or could she be pregnant?"},
        "female, age 12 to 50, relevant symptom",
    ),
    Question(
        "symptom_duration", "symptoms.duration", MEDIUM, True, "duration",
        lambda s: any(sym.duration is None and s.present(sym.concept) and sym.concept != "unspecified_critical_symptom"
                      for sym in s.symptoms),
        {"hi": "यह तकलीफ कितने दिन से है?", "hi-Latn": "Yeh takleef kitne din se hai?", "en": "For how many days has this been going on?"},
        "a symptom has no duration",
    ),
    Question(
        "fever_temperature", "temperature", LOW, False, "number",
        lambda s: s.present("fever") and s.temperature_c is None,
        {"hi": "अगर आपने बुखार नापा है, तो कितना है? (नहीं नापा तो 'नहीं' बोलें)",
         "hi-Latn": "Agar aapne bukhar naapa hai, to kitna hai? (Nahi naapa to 'nahi' bolein)",
         "en": "If you have measured the fever, what is it? (Say 'no' if not measured)"},
        "fever present and temperature unknown",
    ),
    Question(
        "chronic_conditions", "medical_context", LOW, False, "yes_no",
        lambda s: s.present("fever") and not s.medical_context,
        {"hi": "क्या आपको शुगर, बीपी, दिल, दमा या किडनी की कोई पुरानी बीमारी है?",
         "hi-Latn": "Kya aapko sugar, BP, dil, dama ya kidney ki koi purani bimari hai?",
         "en": "Do you have any long term illness such as diabetes, blood pressure, heart, asthma or kidney problems?"},
        "fever present and no known conditions recorded",
    ),
    _clarify("head_heaviness", "क्या सिर में दर्द है, या सिर्फ भारी लग रहा है?",
             "Kya sar mein dard hai, ya sirf bhaari lag raha hai?", "Is there pain in the head, or does it only feel heavy?"),
    _clarify("dizziness", "चक्कर आने पर क्या आप गिर पड़ते हैं या बेहोश जैसा लगता है?",
             "Chakkar aane par kya aap gir padte hain ya behosh jaisa lagta hai?", "When you feel dizzy, do you fall or feel like fainting?"),
    _clarify("weakness", "कमजोरी कितनी है? क्या आप खड़े होकर चल पा रहे हैं?",
             "Kamzori kitni hai? Kya aap khade hokar chal pa rahe hain?", "How weak do you feel? Are you able to stand and walk?"),
    _clarify("palpitations", "क्या दिल की धड़कन तेज लग रही है, या सिर्फ घबराहट है?",
             "Kya dil ki dhadkan tez lag rahi hai, ya sirf ghabrahat hai?", "Does the heart feel like it is beating fast, or is it only nervousness?"),
    _clarify("stomach_upset", "पेट खराब में क्या दस्त हैं, उल्टी है, या पेट में दर्द है?",
             "Pet kharab mein kya dast hain, ulti hai, ya pet mein dard hai?", "With the upset stomach, is there loose stool, vomiting, or pain?"),
]
_BY_ID = {q.question_id: q for q in QUESTION_BANK}


def get_question(question_id: str) -> Question | None:
    return _BY_ID.get(question_id)


def required_outstanding(state: ClinicalState) -> list[str]:
    """Required questions that apply now and are not yet resolved."""
    return [q.question_id for q in QUESTION_BANK
            if q.required_for_triage and q.question_id not in state.answered_questions and q.trigger(state)]


def next_question(state: ClinicalState) -> Question | None:
    """Highest priority applicable question that has not been asked too often."""
    optional_asked = sum(1 for qid in state.asked_questions if (b := _BY_ID.get(qid)) and not b.required_for_triage)
    candidates = [
        (q.priority, i, q) for i, q in enumerate(QUESTION_BANK)
        if q.question_id not in state.answered_questions
        and (q.required_for_triage or optional_asked < MAX_OPTIONAL_QUESTIONS or q.question_id in state.asked_questions)
        and q.trigger(state) and state.asked_questions.get(q.question_id, 0) < MAX_ASKS
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


# ----- answer interpretation -------------------------------------------------

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _bare_number(text: str) -> float | None:
    m = _NUMBER.search(text.translate(str.maketrans("०१२३४५६७८९", "0123456789")))
    if m:
        return float(m.group())
    for clause in tokenize(text):
        for raw in clause.raw:
            value = NUMBER_WORDS.get(fold_devanagari(raw))
            if value is not None:
                return value
    return None


def apply_answer(state: ClinicalState, question: Question, text: str, ex: ExtractionResult) -> list[Observation]:
    """Update the state from a patient's answer to a specific question.

    Extraction has already been merged. This adds the question specific meaning
    of short replies like "haan", "nahi" or a bare number.
    """
    changes: list[Observation] = []
    qid, kind = question.question_id, question.kind
    resolved = False

    if kind == "yes_no":
        answer = polarity(ex)
        members_present = any(state.present(c) for c in question.group)
        if question.group:
            if answer == "yes" and not members_present:
                state.findings["unspecified_critical_symptom"] = FindingStatus.PRESENT
                changes.append(Observation("finding", "unspecified_critical_symptom", "present", "answer"))
                resolved = True
            elif members_present:
                resolved = True
            elif answer == "no":
                for c in question.group:
                    if state.status(c) == FindingStatus.UNKNOWN:
                        state.findings[c] = FindingStatus.ABSENT
                        changes.append(Observation("finding", c, "absent", "answer"))
                resolved = True
        elif qid == "dehydration_check" and answer in ("yes", "no"):
            status = FindingStatus.PRESENT if answer == "yes" else FindingStatus.ABSENT
            state.findings["dehydration_signs"] = status
            changes.append(Observation("finding", "dehydration_signs", status.value, "answer"))
            resolved = True
        elif qid == "sex" and answer in ("yes", "no"):
            state.patient.sex = "female" if answer == "yes" else "male"
            changes.append(Observation("patient", "sex", "present", "answer"))
            resolved = True
        elif qid == "pregnancy" and answer in ("yes", "no"):
            state.patient.pregnant = answer == "yes"
            changes.append(Observation("patient", "pregnancy", "present", "answer"))
            resolved = True
        elif qid == "chronic_conditions" and answer in ("yes", "no"):
            if answer == "yes" and not ex.context:
                state.medical_context.append("chronic_condition")
                changes.append(Observation("context", "chronic_condition", "present", "answer"))
            resolved = True
    elif kind == "number":
        number = _bare_number(text)
        if qid == "age":
            if state.patient.age_years is not None or (number is not None and 0 < number <= 120):
                if state.patient.age_years is None and number is not None:
                    state.patient.age_years = number
                    changes.append(Observation("patient", "age", "present", "answer"))
                resolved = True
        elif qid == "fever_temperature":
            if state.temperature_c is not None:
                resolved = True
            elif number is not None and (34 <= number <= 43 or 93 <= number <= 109):
                state.temperature_c = round(number if number < 50 else (number - 32) * 5 / 9, 1)
                changes.append(Observation("measurement", "temperature", "present", "answer"))
                resolved = True
            elif polarity(ex) == "no":
                resolved = True  # not measured, which is acceptable
    elif kind == "duration":
        duration = ex.duration
        if duration is None:
            number = _bare_number(text)
            if number and 0 < number <= 365:
                duration = Duration(value=number, unit="days")
        if duration is not None:
            for sym in state.symptoms:
                if sym.duration is None and state.present(sym.concept):
                    sym.duration = duration
            resolved = True
            changes.append(Observation("symptom", "duration", "present", "answer"))
    elif kind == "free_text":
        if qid.startswith("clarify_"):
            concept = qid.removeprefix("clarify_")
            clarified = state.symptom(concept)
            if clarified:
                clarified.requires_clarification = False
            resolved = True
        else:
            resolved = bool(ex.symptoms or ex.negated)

    if resolved and qid not in state.answered_questions:
        state.answered_questions.append(qid)
    return changes


def ambiguous_concepts() -> list[str]:
    return [c.id for c in CONCEPTS.values() if c.ambiguous]
