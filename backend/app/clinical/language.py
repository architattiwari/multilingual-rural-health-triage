"""Lightweight language and code mixing detection for short symptom utterances.

Returned codes:
  hi        Hindi in Devanagari
  hi-Latn   romanised Hindi (Hinglish)
  en        English
  mwr       Marwari influenced Hindi (either script)
  und       not enough evidence

This is a heuristic tuned for short health phrases, not a general language
identifier. Speech providers also report a language; callers combine both.
"""

import re
from dataclasses import dataclass

from .text import fold_devanagari, fold_token

_DEV = re.compile(r"[\u0900-\u097F]")
_LATIN_WORD = re.compile(r"[a-zA-Z']+")
_DEV_WORD = re.compile(r"[\u0900-\u097F]+")

_HINDI_ROMAN = {fold_token(w) for w in ["hai", "hain", "hu", "hoon", "hun", "mujhe", "mujhko", "mera", "meri", "mere", "se", "ko", "ka", "ki", "ke", "mein", "raha", "rahi", "rahe", "lag", "laga", "lagta", "lagti", "aur", "bahut", "kya", "kuch", "hota", "hoti", "tha", "thi", "din", "bhi", "par", "toh", "dard", "bukhar", "sar", "sir", "pet", "saans", "khansi", "thoda", "bahot", "bohot", "jyada", "zyada", "kab", "kaise", "abhi", "kal", "nahi", "nahin", "hamare", "unko", "unki", "unka", "bachcha", "bachchi", "aadmi", "aurat"]}
_ENGLISH = {fold_token(w) for w in ["i", "have", "has", "am", "the", "my", "since", "with", "pain", "days", "day", "feel", "feeling", "been", "very", "also", "and", "cant", "dont", "not", "is", "are", "she", "he", "they", "it", "from", "for", "ache", "headache", "vomiting", "cough", "since", "last", "two", "three", "week", "weeks", "hours"]}
_MWR_ROMAN = {fold_token(w) for w in ["mhane", "mhare", "mharo", "mhari", "mharai", "thane", "tharo", "thari", "koni", "ghano", "ghani", "taav", "matho", "maatho"]}
_MWR_DEV = {fold_devanagari(w) for w in ["म्हने", "म्हारो", "म्हारी", "म्हारे", "थने", "थारो", "कोनी", "घणो", "घणी", "ताव", "माथो", "दुखै"]}


@dataclass(frozen=True)
class LanguageResult:
    code: str
    confidence: float
    code_mixed: bool = False


def detect_language(text: str) -> LanguageResult:
    dev_chars = len(_DEV.findall(text))
    latin_words = [fold_token(w.lower()) for w in _LATIN_WORD.findall(text)]
    dev_words = [fold_devanagari(w) for w in _DEV_WORD.findall(text)]
    latin_chars = sum(len(w) for w in latin_words)

    if dev_chars + latin_chars == 0:
        return LanguageResult("und", 0.0)

    mwr_hits = sum(1 for w in latin_words if w in _MWR_ROMAN) + sum(1 for w in dev_words if w in _MWR_DEV)
    hi_roman = sum(1 for w in latin_words if w in _HINDI_ROMAN)
    en_hits = sum(1 for w in latin_words if w in _ENGLISH)

    # Compare word counts, not characters: long English words would otherwise outweigh short Hindi ones.
    if dev_words and len(dev_words) >= len(latin_words):
        mixed = en_hits >= 1
        if mwr_hits:
            return LanguageResult("mwr", min(0.9, 0.55 + 0.15 * mwr_hits), mixed)
        return LanguageResult("hi", 0.9 if not mixed else 0.8, mixed)

    if mwr_hits:
        return LanguageResult("mwr", min(0.85, 0.5 + 0.15 * mwr_hits), en_hits > 0)
    if hi_roman >= 2 or (hi_roman >= 1 and en_hits == 0):
        mixed = en_hits >= 1
        return LanguageResult("hi-Latn", min(0.9, 0.55 + 0.08 * hi_roman), mixed)
    if en_hits >= 1 and hi_roman == 0:
        return LanguageResult("en", min(0.9, 0.5 + 0.1 * en_hits))
    return LanguageResult("und", 0.3)
