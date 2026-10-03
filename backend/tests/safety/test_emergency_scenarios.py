"""Clinical safety scenarios. These must never regress."""

import pytest

from app.providers import Providers
from tests.conftest import EMERGENCY_NUMBER, Chat
from tests.fakes import FakeLLM

pytestmark = pytest.mark.safety

EMERGENCY_UTTERANCES = [
    ("severe breathing difficulty hindi roman", "saans lene mein bahut dikkat hai"),
    ("breathing devanagari", "मुझे साँस लेने में बहुत तकलीफ है"),
    ("breathing english", "I cannot breathe properly, difficulty breathing"),
    ("chest pain roman", "seene mein tez dard ho raha hai"),
    ("chest pain devanagari", "छाती में दर्द है"),
    ("loss of consciousness", "mere pita behosh ho gaye"),
    ("stroke signs", "munh tedha ho gaya hai aur bolne mein dikkat hai"),
    ("stroke devanagari", "एक तरफ कमजोरी है और चेहरा टेढ़ा हो गया"),
    ("severe bleeding", "bahut khoon beh raha hai band nahi ho raha"),
    ("allergic reaction", "chehre par sujan aa gayi hai"),
    ("seizure", "bachche ko daura pad raha hai"),
    ("snake bite", "saanp ne kata hai"),
    ("poisoning", "usne zehar kha liya"),
    ("vomiting blood", "khoon ki ulti hui hai"),
    ("marwari influenced breathing", "म्हने साँस लेणे में घणी तकलीफ छै, सांस फूल रही है"),
    ("self harm", "main khudkushi karna chahta hoon"),
    ("sudden worst headache", "achanak bahut tez sar mein dard hua, aisa kabhi nahi hua"),
]


@pytest.mark.parametrize("label,text", EMERGENCY_UTTERANCES, ids=[e[0] for e in EMERGENCY_UTTERANCES])
def test_red_flag_utterance_escalates_immediately(client, label, text):
    chat = Chat(client)
    result = chat.say(text)
    assert chat.level == "emergency", f"{label}: {result.get('assistant_message')}"
    assert result["question"] is None, "no further questions after an emergency"
    assert result["triage_status"] == "emergency"


def test_emergency_guidance_uses_configured_number_only(client, make_client):
    chat = Chat(client)
    chat.say("seene mein dard hai")
    steps = " ".join(chat.last["triage"]["patient"]["next_steps"])
    assert EMERGENCY_NUMBER in steps
    # Without configuration the guidance must not invent a number.
    bare = make_client(emergency_contact_number="")
    c2 = Chat(bare)
    c2.say("seene mein dard hai")
    text = " ".join(c2.last["triage"]["patient"]["next_steps"])
    assert not any(ch.isdigit() for ch in text)
    assert c2.last["triage"]["patient"]["emergency_contact"] is None


def test_emergency_cannot_be_downgraded_by_later_reassurance(client):
    chat = Chat(client)
    chat.say("saans lene mein bahut dikkat hai")
    for reassurance in ["nahi ab theek hoon, koi dikkat nahi", "saans lene mein koi dikkat nahi hai", "no I am fine"]:
        chat.say(reassurance)
        assert chat.level == "emergency"
    state = client.get(f"/api/v1/conversations/{chat.id}", headers=chat.headers).json()["state"]
    assert "breathlessness" in state["red_flags"]


def test_fever_without_red_flags_is_not_emergency(client):
    chat = Chat(client)
    chat.say("Do din se bukhar hai aur sar bhaari lag raha hai.")
    chat.answer_until_final({"age": "30", "fever_temperature": "nahi"})
    assert chat.level == "non_urgent"
    message = chat.last["triage"]["patient"]["message"].lower()
    for forbidden in ("you are safe", "nothing to worry", "aap surakshit", "koi chinta nahi"):
        assert forbidden not in message


def test_persistent_fever_is_urgent(client):
    chat = Chat(client)
    chat.say("chaar din se bukhar hai")
    chat.answer_until_final({"age": "30", "fever_temperature": "nahi"})
    assert chat.level == "urgent"


def test_infant_fever_is_emergency(client):
    chat = Chat(client)
    chat.say("meri bachchi 2 mahine ki hai aur use bukhar hai")
    chat.answer_until_final({})
    assert chat.level == "emergency"


def test_screening_no_answers_are_required_before_reassurance(client):
    """A mild looking complaint must still pass the breathing / chest / fainting screen."""
    chat = Chat(client)
    chat.say("halka sa khansi hai 1 din se")
    assert chat.last["question"]["question_id"] == "screen_critical_a"
    assert chat.last["triage"] is None


def test_yes_to_critical_screen_is_emergency(client):
    chat = Chat(client)
    chat.say("bukhar hai")
    assert chat.last["question"]["question_id"] == "screen_critical_a"
    chat.say("haan")
    assert chat.level == "emergency"


def test_unclear_answers_never_end_in_reassurance(client):
    """If safety questions stay unanswered the result must be urgent, never non urgent."""
    chat = Chat(client)
    chat.say("bukhar hai 1 din se")
    for _ in range(20):
        if chat.last.get("triage"):
            break
        chat.say("hmm pata nahi kya")
    assert chat.level == "urgent"
    assert "insufficient_information" in chat.last["triage"]["reason_codes"]
    assert chat.last["triage"]["requires_human_review"] is True


def test_ambiguous_colloquial_phrase_triggers_clarification(client):
    chat = Chat(client)
    chat.say("sar bhaari lag raha hai")
    state = chat.last["state"]
    sym = next(s for s in state["symptoms"] if s["normalized_concept"] == "head heaviness")
    assert sym["requires_clarification"] is True
    assert sym["original_text"] == "sar bhaari"
    ids = []
    for _ in range(8):
        if chat.last.get("triage"):
            break
        ids.append(chat.last["question"]["question_id"])
        chat.say("nahi" if chat.last["question"]["kind"] == "yes_no" else "30")
    assert "clarify_head_heaviness" in ids


def test_conflicting_age_is_flagged_for_review(client):
    chat = Chat(client)
    chat.say("meri umar 30 saal hai, bukhar hai")
    chat.say("nahi")
    chat.say("nahi")
    chat.say("meri umar 60 saal hai")
    chat.answer_until_final({})
    assert chat.last["triage"]["requires_human_review"] is True


@pytest.mark.parametrize("llm_output", [
    "not json at all",
    '{"symptoms": [{"concept": "made_up", "evidence": "x y", "confidence": 1}]}',
    '{"triage_level": "non_urgent", "symptoms": "yes"}',
    '{"symptoms": [{"concept": "fever", "evidence": "words the patient never said", "confidence": 0.9}]}',
])
def test_malformed_or_ungrounded_llm_output_is_ignored(make_client, llm_output):
    llm = FakeLLM(llm_output)
    client = make_client(Providers(llm=llm))
    chat = Chat(client)
    chat.say("kuch nahi bas pet mein halka dard hai")
    assert llm.calls == 1
    names = [s["name"] for s in chat.last["state"]["symptoms"]]
    assert "fever" not in names and "made_up" not in names


def test_llm_cannot_override_emergency_or_set_level(make_client):
    llm = FakeLLM('{"triage_level": "non_urgent", "symptoms": []}')
    client = make_client(Providers(llm=llm))
    chat = Chat(client)
    chat.say("seene mein dard hai")
    assert chat.level == "emergency"


def test_llm_may_escalate_with_grounded_evidence(make_client):
    llm = FakeLLM('{"symptoms": [{"concept": "chest_pain", "evidence": "dil par pathar", "severity": "severe", "confidence": 0.9}]}')
    client = make_client(Providers(llm=llm))
    chat = Chat(client)
    chat.say("mere dil par pathar rakha hai jaisa lagta hai")
    assert chat.level == "emergency"


def test_llm_failure_falls_back_to_rules(make_client):
    from app.ai.base import ProviderError

    client = make_client(Providers(llm=FakeLLM(ProviderError("fake", "timeout", retryable=True))))
    chat = Chat(client)
    chat.say("saans lene mein dikkat hai")
    assert chat.level == "emergency"
