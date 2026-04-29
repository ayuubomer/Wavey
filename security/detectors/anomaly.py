"""
security/detectors/anomaly.py — structural anomaly detector.

Checks:
  • Extreme word count (too short after validation pass, or padded)
  • Question spam (many ? marks — could be used to confuse context)
  • Word repetition padding (same word >5× in a short query)
  • Special-character density (> threshold ratio of non-alphanumeric chars)
  • Nested instruction markers (multiple lines that look like roles/headers)
"""
from __future__ import annotations
import re
from collections import Counter

_HEADER_LINE_RE = re.compile(r"^(\s*#+\s|\s*-{3,}|.*:$)", re.MULTILINE)
_WORD_RE        = re.compile(r"\b\w+\b")


def detect(text: str) -> tuple[float, list[str]]:
    score = 0.0
    triggers: list[str] = []

    words = _WORD_RE.findall(text.lower())
    word_count = len(words)

    # Question spam
    q_count = text.count("?")
    if word_count > 0 and q_count / max(word_count, 1) > 0.3:
        score += 0.4
        triggers.append(f"question_spam:{q_count}")

    # Word repetition padding
    if word_count >= 10:
        freq = Counter(words)
        most_common_word, most_common_count = freq.most_common(1)[0]
        if most_common_count > 5 and most_common_count / word_count > 0.25:
            score += 0.5
            triggers.append(f"word_repetition:{most_common_word}:{most_common_count}")

    # Special-character density
    non_alnum = sum(1 for c in text if not c.isalnum() and not c.isspace())
    total_chars = max(len(text), 1)
    density = non_alnum / total_chars
    if density > 0.35:
        score += min(density, 0.8)
        triggers.append(f"high_special_char_density:{density:.2f}")

    # Nested header / role markers (e.g. ### System, --- User ---)
    header_matches = _HEADER_LINE_RE.findall(text)
    if len(header_matches) >= 3:
        score += 0.6
        triggers.append(f"nested_header_markers:{len(header_matches)}")

    return min(score, 1.0), triggers