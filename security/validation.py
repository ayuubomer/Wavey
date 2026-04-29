"""
security/validation.py — input validation and sanitization.

Raises ValueError with a safe, user-visible message on bad input.
No knowledge of detectors, IP state, or Flask.
"""
from __future__ import annotations
import re
import unicodedata
from .config import QUERY_MIN_LEN, QUERY_MAX_LEN

# ── Dangerous control-character ranges ────────────────────────────────────
# C0 controls (0x00–0x1f) except tab (0x09), LF (0x0a), CR (0x0d)
# DEL (0x7f)
# C1 controls (0x80–0x9f)
# Unicode control block (0x200b–0x200f, 0x2028–0x202f, 0x2060–0x206f, 0xfff0–0xffff)
_CONTROL_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f"
    r"\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufff0-\uffff]"
)

# RTL/LTR embedding or override characters
_BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069\u200e\u200f]")


def validate_input(query: str | None) -> None:
    """
    Raise ValueError with a safe message if the query fails any hard rule.
    The caller may surface this message directly to the user.
    """
    if query is None:
        raise ValueError("Query is required.")
    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    stripped = query.strip()

    if len(stripped) < QUERY_MIN_LEN:
        raise ValueError(f"Query is too short (minimum {QUERY_MIN_LEN} characters).")
    if len(stripped) > QUERY_MAX_LEN:
        raise ValueError(f"Query is too long (maximum {QUERY_MAX_LEN} characters).")

    if _CONTROL_RE.search(query):
        raise ValueError("Query contains disallowed control characters.")

    # NFC-normalise: reject strings that can't be normalised (malformed surrogates etc.)
    try:
        unicodedata.normalize("NFC", query)
    except (UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise ValueError("Query contains invalid Unicode sequences.") from exc


def sanitize_query(query: str) -> str:
    """
    Return a cleaned copy of the query suitable for passing to detectors and the LLM.
    Does not raise — call validate_input first.
    """
    # Strip BIDI override/embedding characters
    cleaned = _BIDI_RE.sub("", query)
    # Collapse runs of whitespace (preserves single spaces / newlines)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # NFC normalise
    cleaned = unicodedata.normalize("NFC", cleaned)
    return cleaned.strip()