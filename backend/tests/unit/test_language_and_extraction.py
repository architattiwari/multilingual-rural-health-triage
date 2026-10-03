import pytest

from app.clinical.extractor import extract, polarity
from app.clinical.language import detect_language
from app.clinical.text import fold_token, tokenize


@pytest.mark.parametrize("text,code", [
    ("मुझे दो दिन से बुखार है", "hi"),
    ("Do din se bukhar hai aur sar bhaari lag raha hai", "hi-Latn"),
    ("I have had fever and a headache since two days", "en"),
    ("म्हने ताव छै अर माथो दुखै", "mwr"),
    ("mhane bukhar koni", "mwr"),
])
def test_language_detection(text, code):
    assert detect_language(text).code == code


def test_code_mixing_detected():
    result = detect_language("मुझे fever है और headache भी")
    assert result.code == "hi" and result.code_mixed


def test_empty_or_symbols_are_undetermined():
    assert detect_language("???").code == "und"


@pytest.mark.parametrize("a,b", [("bukhar", "bukhaar"), ("dikkat", "dikat"), ("zukam", "jukam")])
def test_roman_spelling_variants_fold_together(a, b):
    assert fold_token(a) == fold_token(b)


def test_devanagari_variants_fold():
    assert tokenize("साँस")[0].folded == tokenize("सांस")[0].folded


def test_spec_example_extraction():
    r = extract("Do din se bukhar hai aur sar bhaari lag raha hai.")
    by = {s.concept: s for s in r.symptoms}
    assert by["fever"].original_text == "bukhar"
    assert by["head_heaviness"].original_text == "sar bhaari"
    assert by["fever"].duration.value == 2 and by["fever"].duration.unit == "days"
    assert by["head_heaviness"].duration.days == 2
    assert 0.8 <= by["head_heaviness"].confidence < 0.9  # ambiguous concepts are less certain


@pytest.mark.parametrize("text,days", [
    ("3 din se bukhar", 3), ("teen din se bukhar", 3), ("एक हफ्ते से खांसी", 7), ("kal se bukhar hai", 1),
    ("do teen din se dast", 3), ("2 mahine se khansi", 60), ("kuch din se bukhar", 3),
])
def test_duration_extraction(text, days):
    r = extract(text)
    assert r.duration is not None and r.duration.days == pytest.approx(days)


@pytest.mark.parametrize("text,negated,present", [
    ("bukhar hai lekin saans ki dikkat nahi hai", "breathlessness", "fever"),
    ("mujhe na bukhar hai na khansi", "fever", None),
    ("सीने में दर्द नहीं है", "chest_pain", None),
    ("no fever", "fever", None),
])
def test_negation_is_scoped(text, negated, present):
    r = extract(text)
    assert negated in r.negated
    assert negated not in {s.concept for s in r.symptoms}
    if present:
        assert present in {s.concept for s in r.symptoms}


@pytest.mark.parametrize("text,years", [("meri umar 45 saal hai", 45), ("45 saal ka hoon", 45), ("6 mahine ki bachchi", 0.5),
                                        ("age 30", 30)])
def test_age_extraction(text, years):
    assert extract(text).age_years == pytest.approx(years, abs=0.01)


def test_duration_in_years_is_not_mistaken_for_age():
    r = extract("2 saal se sugar ki bimari hai aur bukhar")
    assert r.age_years is None and "diabetes" in r.context


@pytest.mark.parametrize("text,celsius", [("bukhar 102 degree", 38.9), ("temperature 39 C", 39.0), ("bukhar 101.5 hai", 38.6)])
def test_temperature_normalised_to_celsius(text, celsius):
    assert extract(text).temperature_c == pytest.approx(celsius, abs=0.1)


def test_misspelling_matched_with_lower_confidence():
    r = extract("bukharr hai aur khasii")
    assert {"fever", "cough"} <= {s.concept for s in r.symptoms}


def test_severity_and_sudden_onset():
    r = extract("achanak bahut tez sar dard")
    assert any(s.concept == "worst_headache" for s in r.symptoms)


def test_pregnancy_and_context():
    r = extract("main garbhvati hoon aur sugar ki bimari hai")
    assert r.pregnant is True and "diabetes" in r.context


@pytest.mark.parametrize("text,expected", [("haan", "yes"), ("nahi", "no"), ("हाँ जी", "yes"), ("nahi haan", "mixed"), ("hmm", "none")])
def test_answer_polarity(text, expected):
    assert polarity(extract(text)) == expected


@pytest.mark.parametrize("text,concept", [
    ("सीने मे दर्द हे", "chest_pain"),            # typical ASR output: nasal mark dropped, ै written as े
    ("साँस लेने मे दिक्कत है", "breathlessness"),
    ("बुखार हे", "fever"),
])
def test_asr_style_devanagari_variants_still_match(text, concept):
    assert concept in {s.concept for s in extract(text).symptoms}
