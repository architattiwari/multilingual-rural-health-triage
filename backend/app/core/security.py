"""Security helpers: token handling, text sanitisation, rate limiting, prompt injection screening."""

import hashlib
import hmac
import re
import secrets
import threading
import time
import unicodedata
from collections import defaultdict, deque

# Zero width, bidi override and other invisible characters that can hide instructions
# or break downstream rendering.
_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t]+")


def new_conversation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str, secret: bytes) -> str:
    # Tokens carry 256 bits of entropy, so a keyed fast hash is sufficient and avoids a
    # per request password hashing cost.
    return hmac.new(secret or b"dev-only", token.encode(), hashlib.sha256).hexdigest()


def verify_token(token: str, expected_hash: str, secret: bytes) -> bool:
    return hmac.compare_digest(hash_token(token, secret), expected_hash)


def sanitize_text(text: str, max_chars: int) -> str:
    """Normalise untrusted patient text. Raises ValueError when it is unusable."""
    cleaned = unicodedata.normalize("NFC", text)
    cleaned = _INVISIBLE.sub("", cleaned)
    cleaned = _CONTROL.sub(" ", cleaned)
    cleaned = _SPACES.sub(" ", cleaned).strip()
    if not cleaned:
        raise ValueError("empty")
    if len(cleaned) > max_chars:
        raise ValueError("too_long")
    return cleaned


_INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above)",
    r"(reveal|show|print|repeat) (your|the) (system )?(prompt|instructions)",
    r"you are now\b",
    r"\bact as\b.{0,40}\b(doctor|admin|developer|dan)\b",
    r"system prompt",
    r"developer mode",
    r"jailbreak",
    r"</?(system|assistant|instructions?)>",
    r"triage[_ ]level\s*[:=]",
    r"mark (this|me|it) as (non[- ]?urgent|safe)",
    r"पिछले निर्देश|पहले के निर्देश|निर्देशों को अनदेखा",
    r"pichhle nirdesh|pehle ke nirdesh",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def looks_like_prompt_injection(text: str) -> bool:
    """Heuristic screen. A hit never blocks the patient, it only keeps the text away from the LLM."""
    return bool(_INJECTION_RE.search(text))


class SlidingWindowLimiter:
    """Per key sliding window limiter held in memory.

    Suitable for a single process. Behind multiple replicas use a shared store
    (for example Redis) or enforce limits at the gateway as well.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 20000:
                self._evict(now, window_seconds)
            return True

    def _evict(self, now: float, window: int) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
