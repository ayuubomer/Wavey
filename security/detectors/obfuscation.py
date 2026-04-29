"""
security/detectors/obfuscation.py — Unicode obfuscation detector.

Catches:
  • Zero-width / invisible characters
  • RTL override and embedding characters
  • Mixed-script confusable attacks (Cyrillic/Greek lookalikes in Latin text)
  • Excessive homoglyph density
"""
from __future__ import annotations
import re
import unicodedata

# Zero-width and invisible characters
_ZERO_WIDTH_RE = re.compile(
    r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]"
)

# RTL/LTR embedding and override characters
_BIDI_OVERRIDE_RE = re.compile(
    r"[\u202a-\u202e\u2066-\u2069\u200e\u200f]"
)

# Scripts that are commonly used in confusable attacks against Latin text
_CONFUSABLE_SCRIPTS = frozenset({"Cyrillic", "Greek", "Armenian", "Georgian"})

# Minimum ratio of confusable chars to trigger (avoids false positives on genuine multilingual text)
_CONFUSABLE_RATIO_THRESHOLD = 0.25


def _script_of(char: str) -> str:
    """Return the Unicode script name for a character (simplified)."""
    try:
        name = unicodedata.name(char, "")
    except (ValueError, TypeError):
        return "Unknown"
    for part in name.split():
        if part in ("LATIN", "CYRILLIC", "GREEK", "ARMENIAN", "GEORGIAN",
                    "ARABIC", "HEBREW", "HANGUL", "HIRAGANA", "KATAKANA",
                    "CJK", "DEVANAGARI"):
            return part
    return "Other"


def detect(text: str) -> tuple[float, list[str]]:
    score = 0.0
    triggers: list[str] = []

    # Zero-width characters
    zw_count = len(_ZERO_WIDTH_RE.findall(text))
    if zw_count > 0:
        score += min(zw_count * 0.3, 1.0)
        triggers.append(f"zero_width_chars:{zw_count}")

    # BIDI overrides
    bidi_count = len(_BIDI_OVERRIDE_RE.findall(text))
    if bidi_count > 0:
        score += min(bidi_count * 0.5, 1.0)
        triggers.append(f"bidi_override:{bidi_count}")

    # Mixed-script confusable check — only for texts that look primarily Latin
    latin_chars    = [c for c in text if _script_of(c) == "LATIN" and c.isalpha()]
    confusable     = [c for c in text if _script_of(c) in _CONFUSABLE_SCRIPTS and c.isalpha()]
    total_alpha    = len(latin_chars) + len(confusable)

    if total_alpha > 10 and confusable:
        ratio = len(confusable) / total_alpha
        if ratio >= _CONFUSABLE_RATIO_THRESHOLD:
            score += min(ratio * 2, 1.0)
            triggers.append(f"mixed_script_confusable:{ratio:.2f}")

    return min(score, 1.0), triggers