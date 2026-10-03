"""Deterministic rule based medical entity extractor.

It always runs, with or without an LLM. Its output is the trusted baseline:
LLM suggestions are only ever merged on top of it (see ai.extraction).

Design points:
* Longest phrase match wins and consumes tokens, so "saans lene mein dikkat"
  is one finding, not several.
* Negation is scoped to a clause fragment. "bukhar hai lekin saans ki dikkat
  nahi" negates breathing only.
* Original wording is kept for every finding.
"""

import re
from difflib import get_close_matches

from app.domain.clinical import (
    Duration,
    ExtractedSymptom,
    ExtractionResult,
    Severity,
)

from .concepts import CONCEPTS
from .language import detect_language
from .lexicon import (
    AMBIGUOUS_CONFIDENCE,
    DEFAULT_CONFIDENCE,
    FUZZY_CANDIDATES,
    PHRASE_INDEX,
)
from .text import CONJUNCTIONS, NUMBER_WORDS, Clause, fold_devanagari, fold_phrase, fold_token, tokenize


def _fold_set(words: str) -> set[str]:
    return {fold_token(fold_devanagari(w)) for w in words.split()}


NEG_AFTER = _fold_set("nahi nahin nhi nai koni not no नहीं नही कोनी नाही नहि")
NEG_BEFORE = _fold_set("no without bina बिना nahi नहीं")
POS_STRONG = _fold_set("haan han ha haa ji jee yes yeah yep haanji hanji bilkul हां हाँ जी हांजी हा बिल्कुल")
POS_WEAK = _fold_set("hai ho raha rahi rahe hota hoti hain lagta lagti hu hoon है हो रहा रही रहे होता होती")
SEVERE_WORDS = _fold_set(
    "bahut bohot bahot jyada zyada tez bhayankar ghano ghani ghana asahniya severe very extreme unbearable "
    "bardasht sakht behad "
    "बहुत ज्यादा तेज भयंकर घणो घणी असहनीय बर्दाश्त बेहद"
)
MILD_WORDS = _fold_set("thoda thodi halka halki mamuli mild slight little थोडा थोडी हल्का हल्की मामूली")
SUDDEN_WORDS = _fold_set("achanak ekdum sudden suddenly अचानक एकदम")
WORSENING = _fold_set("badh badhta badhti badhne bigad bigadna worse worsening increasing बढ बढ़ता बढ़ती बिगड़")
IMPROVING = _fold_set("kam ghat theek better improving sudhar कम घट ठीक सुधार")
FEMALE_WORDS = _fold_set("aurat mahila ladki bachchi patni woman female girl lady औरत महिला लड़की बच्ची पत्नी")
MALE_WORDS = _fold_set("aadmi purush ladka pati man male boy आदमी पुरुष लड़का पति")
TEMP_CONTEXT = _fold_set("temperature tapman bukhar taav fever degree digri thermometer thermameter तापमान बुखार ताव डिग्री")
AGE_CONTEXT = _fold_set("umar umra age aayu उम्र आयु उमर")
# Intensifiers that may sit inside a phrase: "sar mein bahut tez dard".
SKIPPABLE = _fold_set(
    "achanak bahut bohot bahot jyada zyada tez thoda thodi halka halki bhayankar ghano ghani sakht behad kafi ekdum "
    "very severe sudden अचानक बहुत ज्यादा तेज थोडा थोडी हल्का हल्की भयंकर घणो घणी बेहद एकदम"
)

UNIT_WORDS: dict[str, str] = {}
for _unit, _words in {
    "days": "din dino divas day days दिन दिनों दिवस",
    "weeks": "hafte hafta haftey hafton week weeks हफ्ते हफ्ता हफ़्ते सप्ताह",
    "months": "mahine mahina mahino month months महीने महीना महीनों",
    "hours": "ghante ghanta ghanton hour hours hr hrs घंटे घंटा घंटों",
    "years": "saal sal saalon year years yr yrs varsh साल सालों वर्ष",
}.items():
    for _w in _words.split():
        UNIT_WORDS[fold_token(fold_devanagari(_w))] = _unit

APPROX_WORDS = _fold_set("kuch kai few several कुछ कई")
SINCE_YESTERDAY = {fold_phrase("kal se"), fold_phrase("कल से"), fold_phrase("kal raat se"), fold_phrase("कल रात से")}
SINCE_DAY_BEFORE = {fold_phrase("parson se"), fold_phrase("parso se"), fold_phrase("परसों से")}
AGE_SUFFIX = _fold_set("ka ki ke old का की के")
AGE_PRONOUN_END = _fold_set("hoon hu hun hai he हूं हूँ है")

_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _number(raw: str) -> float | None:
    if _NUM_RE.match(raw):
        return float(raw)
    return NUMBER_WORDS.get(fold_devanagari(raw))


def _confidence(concept: str, fuzzy: bool) -> float:
    base = AMBIGUOUS_CONFIDENCE if CONCEPTS[concept].ambiguous else DEFAULT_CONFIDENCE
    return round(base * (0.8 if fuzzy else 1.0), 2)


def _fragment_bounds(clause: Clause, start: int, end: int) -> tuple[int, int]:
    """Limit a match to the fragment between conjunctions for negation and severity scope."""
    lo = start
    while lo > 0 and clause.raw[lo - 1] not in CONJUNCTIONS:
        lo -= 1
    hi = end
    while hi < len(clause) and clause.raw[hi] not in CONJUNCTIONS:
        hi += 1
    return lo, hi


class _Match:
    __slots__ = ("concept", "start", "end", "original", "fuzzy")

    def __init__(self, concept: str, start: int, end: int, original: str, fuzzy: bool) -> None:
        self.concept, self.start, self.end, self.original, self.fuzzy = concept, start, end, original, fuzzy


def _match_at(clause: Clause, i: int, phrase: tuple[str, ...], used: list[bool]) -> int | None:
    """Match a phrase starting at i, tolerating up to three intensifier words inside it."""
    j, k, gaps = i, 0, 0
    while k < len(phrase):
        if j >= len(clause) or used[j]:
            return None
        if clause.folded[j] == phrase[k]:
            j += 1
            k += 1
        elif k > 0 and gaps < 3 and clause.folded[j] in SKIPPABLE:
            j += 1
            gaps += 1
        else:
            return None
    return j


def _find_matches(clause: Clause) -> list[_Match]:
    matches: list[_Match] = []
    used = [False] * len(clause)
    for i, token in enumerate(clause.folded):
        if used[i]:
            continue
        for phrase in PHRASE_INDEX.get(token, []):
            end = _match_at(clause, i, phrase.tokens, used)
            if end is not None:
                matches.append(_Match(phrase.concept, i, end, " ".join(clause.raw[i:end]), False))
                for j in range(i, end):
                    used[j] = True
                break
    # Typo tolerant pass for single long Latin words that matched nothing.
    for i, token in enumerate(clause.folded):
        if used[i] or len(token) < 6 or not token.isascii() or token.isdigit():
            continue
        close = get_close_matches(token, FUZZY_CANDIDATES.keys(), n=1, cutoff=0.86)
        if close:
            matches.append(_Match(FUZZY_CANDIDATES[close[0]], i, i + 1, clause.raw[i], True))
            used[i] = True
    matches.sort(key=lambda m: m.start)
    return matches


def _extract_durations(clause: Clause, consumed: set[int]) -> tuple[Duration | None, tuple[float, str] | None]:
    """Return (duration, age) found in a clause. Age is (years or fractional years, source unit)."""
    duration: Duration | None = None
    age: tuple[float, str] | None = None
    n = len(clause)
    folded = clause.folded

    for phrase in SINCE_YESTERDAY:
        if tuple(folded[:len(phrase)]) == phrase or _contains(folded, phrase):
            duration = Duration(value=1, unit="days")
    for phrase in SINCE_DAY_BEFORE:
        if _contains(folded, phrase):
            duration = Duration(value=2, unit="days")

    for i, token in enumerate(folded):
        unit = UNIT_WORDS.get(token)
        if not unit:
            continue
        value: float | None = None
        j = i - 1
        if j >= 0:
            value = _number(clause.raw[j])
            if value is None and folded[j] in APPROX_WORDS:
                value = 3.0
            # "do teen din": a range. Use the larger number, which is the cautious reading.
            if value is not None and j - 1 >= 0 and folded[j - 1] not in APPROX_WORDS:
                earlier = _number(clause.raw[j - 1])
                if earlier is not None and earlier < value and unit in ("days", "weeks", "hours"):
                    j -= 1
        if value is None or value <= 0:
            continue
        number_index = j
        # Age patterns: "45 saal ka", "6 mahine ki", "umar 45 saal"
        followed_by_age_suffix = i + 1 < n and folded[i + 1] in AGE_SUFFIX
        preceded_by_age_word = any(folded[k] in AGE_CONTEXT for k in range(max(0, number_index - 2), number_index))
        if (followed_by_age_suffix and not _followed_by_since(folded, i)) or preceded_by_age_word:
            age = (value, unit)
            consumed.update(range(number_index, i + 1))
            continue
        if _followed_by_since(folded, i) or unit in ("hours", "days", "weeks", "months") or (
            unit == "years" and i + 1 < n
        ):
            duration = Duration(value=value, unit=unit)  # type: ignore[arg-type]
            consumed.update(range(number_index, i + 1))
    # "age 45" / "45 year old" without unit handled by age words
    for i, token in enumerate(folded):
        if token in AGE_CONTEXT and i + 1 < n:
            value = _number(clause.raw[i + 1])
            if value is not None and 0 < value <= 110 and age is None:
                age = (value, "years")
    # "main 45 ka hoon"
    for i in range(n - 2):
        value = _number(clause.raw[i]) if _NUM_RE.match(clause.raw[i]) else None
        if value and 1 <= value <= 110 and folded[i + 1] in AGE_SUFFIX and folded[i + 2] in AGE_PRONOUN_END and age is None:
            age = (value, "years")
    return duration, age


def _contains(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    return any(tuple(tokens[i : i + n]) == phrase for i in range(len(tokens) - n + 1))


def _followed_by_since(folded: list[str], i: int) -> bool:
    return i + 1 < len(folded) and folded[i + 1] in {"se", "से"}


def age_to_years(value: float, unit: str) -> float:
    factor = {"years": 1.0, "months": 1 / 12, "weeks": 7 / 365, "days": 1 / 365, "hours": 1 / 8760}[unit]
    return round(value * factor, 3)


def _extract_temperature(clause: Clause) -> float | None:
    has_context = any(t in TEMP_CONTEXT for t in clause.folded)
    has_age_word = any(t in AGE_CONTEXT or t in UNIT_WORDS for t in clause.folded)
    for i, raw in enumerate(clause.raw):
        if not _NUM_RE.match(raw):
            continue
        value = float(raw)
        next_tok = clause.folded[i + 1] if i + 1 < len(clause) else ""
        unit_hint = next_tok in {"degree", "digri", "dig", "डिग्री", "c", "celsius", "f", "fahrenheit"}
        if 34 <= value <= 43 and (unit_hint or (has_context and not has_age_word)):
            return round(value, 1)
        if 93 <= value <= 109 and (unit_hint or has_context):
            return round((value - 32) * 5 / 9, 1)
    return None


def _severity(clause: Clause, lo: int, hi: int, start: int, end: int) -> Severity:
    window = clause.folded[max(lo, start - 3) : min(hi, end + 3)]
    if any(t in SEVERE_WORDS for t in window):
        return Severity.SEVERE
    if any(t in MILD_WORDS for t in window):
        return Severity.MILD
    return Severity.UNKNOWN


def _negated(clause: Clause, lo: int, hi: int, start: int, end: int) -> bool:
    after = clause.folded[end : min(hi, end + 4)]
    if any(t in NEG_AFTER for t in after):
        return True
    before = clause.folded[max(lo, start - 2) : start]
    if any(t in NEG_BEFORE for t in before):
        return True
    # "na bukhar hai na khansi": neither ... nor
    return bool(start > 0 and clause.folded[start - 1] in {"na", "ना"} and clause.folded.count("na") + clause.folded.count("ना") >= 2)


def extract(text: str, *, language_hint: str | None = None) -> ExtractionResult:
    """Extract structured entities from one patient utterance."""
    clauses = tokenize(text)
    result = ExtractionResult()
    lang = detect_language(text)
    result.detected_language = lang.code if lang.code != "und" else language_hint
    result.language_confidence = lang.confidence
    result.code_mixed = lang.code_mixed

    per_clause_symptoms: list[tuple[int, ExtractedSymptom]] = []
    durations: list[Duration] = []
    seen_present: set[str] = set()
    residual: list[str] = []

    for ci, clause in enumerate(clauses):
        consumed: set[int] = set()
        matches = _find_matches(clause)
        duration, age = _extract_durations(clause, consumed)
        if duration:
            durations.append(duration)
        if age and result.age_years is None:
            result.age_years = age_to_years(*age)
        temp = _extract_temperature(clause)
        if temp is not None:
            result.temperature_c = temp
        sudden = any(t in SUDDEN_WORDS for t in clause.folded)

        for m in matches:
            consumed.update(range(m.start, m.end))
            lo, hi = _fragment_bounds(clause, m.start, m.end)
            negated = _negated(clause, lo, hi, m.start, m.end)
            if negated:
                for k in range(m.end, min(hi, m.end + 4)):
                    if clause.folded[k] in NEG_AFTER:
                        consumed.add(k)
                if m.concept.startswith("ctx:"):
                    if m.concept == "ctx:pregnant":
                        result.pregnant = False
                else:
                    result.negated.append(m.concept)
                continue
            if m.concept.startswith("ctx:"):
                tag = m.concept[4:]
                if tag == "pregnant":
                    result.pregnant = True
                elif tag not in result.context:
                    result.context.append(tag)
                continue
            if m.concept in seen_present:
                continue
            seen_present.add(m.concept)
            symptom = ExtractedSymptom(
                concept=m.concept,
                original_text=m.original[:120],
                confidence=_confidence(m.concept, m.fuzzy),
                severity=_severity(clause, lo, hi, m.start, m.end),
                sudden_onset=sudden,
                source="rules",
            )
            per_clause_symptoms.append((ci, symptom))

        for token in clause.folded:
            if token in FEMALE_WORDS and result.sex is None:
                result.sex = "female"
            elif token in MALE_WORDS and result.sex is None:
                result.sex = "male"
        has_neg = any(t in NEG_AFTER for t in clause.folded)
        if any(t in WORSENING for t in clause.folded) and not has_neg:
            result.progression = "worsening"
        elif any(t in IMPROVING for t in clause.folded) and result.progression is None:
            result.progression = "stable" if has_neg else "improving"
        residual.extend(t for k, t in enumerate(clause.folded) if k not in consumed)

    # Sudden severe headache is a recognised emergency pattern, so promote it explicitly.
    for _, s in per_clause_symptoms:
        if s.concept == "headache" and s.sudden_onset and s.severity == Severity.SEVERE and "worst_headache" not in seen_present:
            seen_present.add("worst_headache")
            result.symptoms.append(
                ExtractedSymptom(concept="worst_headache", original_text=s.original_text,
                                 confidence=0.8, severity=Severity.SEVERE, sudden_onset=True))

    # Attach durations. Prefer the duration in the same clause, else a single global one.
    clause_duration: dict[int, Duration] = {}
    for ci, clause in enumerate(clauses):
        d, _ = _extract_durations(clause, set())
        if d:
            clause_duration[ci] = d
    for ci, symptom in per_clause_symptoms:
        if ci in clause_duration:
            symptom.duration = clause_duration[ci]
        elif len(set((d.value, d.unit) for d in durations)) == 1:
            symptom.duration = durations[0]
        result.symptoms.append(symptom)
    if durations:
        result.duration = max(durations, key=lambda d: d.days)
    result.residual_tokens = residual
    return result


def polarity(result: ExtractionResult) -> str:
    """Interpret a short answer such as "haan" or "nahi" as yes, no, mixed or none."""
    tokens = result.residual_tokens
    strong_yes = any(t in POS_STRONG for t in tokens)
    weak_yes = any(t in POS_WEAK for t in tokens)
    no = any(t in NEG_AFTER for t in tokens)
    if strong_yes and no:
        return "mixed"
    if no:
        return "no"
    if strong_yes or weak_yes:
        return "yes"
    return "none"
