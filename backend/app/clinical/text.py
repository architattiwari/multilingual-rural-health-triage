"""Text normalisation for Devanagari, romanised Hindi and English.

Patients (and speech recognisers) spell the same Hindi word in many ways:
bukhar, bukhaar, bukar. Folding collapses repeated letters and a few common
substitutions so one lexicon entry matches many spellings. The same fold is
applied to lexicon entries and to patient text, so it only needs to be
consistent, not linguistically correct.
"""

import re
import unicodedata
from dataclasses import dataclass, field

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_CLAUSE_SPLIT = re.compile(r"[,;:!?।\n]+|(?<!\d)\.(?!\d)")
_TOKEN = re.compile(r"[\u0900-\u097F]+|[a-zA-Z]+|\d+(?:\.\d+)?")
_REPEAT = re.compile(r"(.)\1+")
_ROMAN_SUBSTITUTIONS = str.maketrans("zwq", "jvk")

# Words that split one sentence into independent statements for negation scope.
CONJUNCTIONS = {"aur", "lekin", "par", "magar", "but", "and", "jabki", "parantu", "या", "ya",
                "और", "लेकिन", "पर", "मगर", "परंतु", "जबकि", "toh", "तो"}


def fold_devanagari(text: str) -> str:
    """Canonical Devanagari comparison form.

    Speech recognisers and quick typists often drop nasal marks and confuse the
    vowel signs ै/े and ौ/ो (में becomes मे, है becomes हे). Folding removes the
    nukta and nasal marks and unifies those vowel signs. The cost is a few
    collisions (सांस and सास fold together), accepted because a missed red flag
    is worse than an extra match that a follow up question can resolve.
    """
    decomposed = unicodedata.normalize("NFD", text).replace("\u093c", "")
    for nasal in ("\u0901", "\u0902"):
        decomposed = decomposed.replace(nasal, "")
    decomposed = decomposed.replace("\u0948", "\u0947").replace("\u094c", "\u094b")
    return unicodedata.normalize("NFC", decomposed)


def fold_token(token: str) -> str:
    """Canonical comparison form of a single lowercase token."""
    if re.search(r"[\u0900-\u097F]", token):
        return fold_devanagari(token)
    if any(ch.isdigit() for ch in token):
        return token
    token = token.translate(_ROMAN_SUBSTITUTIONS)
    return _REPEAT.sub(r"\1", token)


@dataclass
class Clause:
    raw: list[str] = field(default_factory=list)
    folded: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.raw)


def tokenize(text: str) -> list[Clause]:
    prepared = unicodedata.normalize("NFC", text).translate(_DEVANAGARI_DIGITS).lower()
    prepared = fold_devanagari(prepared)
    clauses: list[Clause] = []
    for chunk in _CLAUSE_SPLIT.split(prepared):
        raw = _TOKEN.findall(chunk)
        if raw:
            clauses.append(Clause(raw=raw, folded=[fold_token(t) for t in raw]))
    return clauses


def fold_phrase(phrase: str) -> tuple[str, ...]:
    prepared = fold_devanagari(phrase.lower().translate(_DEVANAGARI_DIGITS))
    return tuple(fold_token(t) for t in _TOKEN.findall(prepared))


NUMBER_WORDS: dict[str, float] = {}
for _words, _value in [
    (("ek", "एक", "one", "ik"), 1), (("do", "दो", "two", "dono"), 2), (("teen", "तीन", "three"), 3),
    (("char", "chaar", "चार", "four"), 4), (("panch", "paanch", "पांच", "five", "paach"), 5),
    (("chhe", "chhah", "che", "छह", "छः", "छे", "six"), 6), (("saat", "सात", "seven"), 7),
    (("aath", "आठ", "eight"), 8), (("nau", "नौ", "nine"), 9), (("das", "दस", "ten"), 10),
    (("gyarah", "ग्यारह", "eleven"), 11), (("barah", "बारह", "twelve"), 12),
    (("pandrah", "पंद्रह", "fifteen"), 15), (("bees", "बीस", "twenty"), 20),
    (("dedh", "डेढ़", "डेढ"), 1.5), (("dhai", "ढाई"), 2.5), (("aadha", "adha", "आधा"), 0.5),
]:
    for _w in _words:
        NUMBER_WORDS[fold_devanagari(_w)] = _value
