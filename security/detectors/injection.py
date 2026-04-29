"""
security/detectors/injection.py — prompt-injection pattern detector.

Norwegian-context aware: patterns are scoped with word boundaries and
phrasing that avoids false positives on common Norwegian compound words
(e.g. "prisoverride", "systemoppdatering").
"""
from __future__ import annotations
import re

# Each entry: (compiled_pattern, human-readable trigger label, score contribution 0–1)
_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # --- Role/persona hijacking ---
    (re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\b", re.I),
     "ignore_previous", 1.0),
    (re.compile(r"\bforget\s+(everything|all|your\s+instructions)\b", re.I),
     "forget_instructions", 1.0),
    (re.compile(r"\bact\s+as\b(?!\s+a?\s*(?:an?\s+)?normal)", re.I),
     "act_as", 0.8),
    (re.compile(r"\bpretend\s+(to\s+be|you\s+are)\b", re.I),
     "pretend_to_be", 0.9),
    (re.compile(r"\b(new|different)\s+(role|persona|character|identity)\b", re.I),
     "new_persona", 0.9),
    (re.compile(r"\byou\s+are\s+now\b", re.I),
     "you_are_now", 0.8),
    (re.compile(r"\bswitch\s+(to\s+)?(developer|admin|root|god|jailbreak)\s+mode\b", re.I),
     "mode_switch", 1.0),

    # --- System prompt extraction ---
    (re.compile(r"\b(reveal|repeat|print|output|show|display)\s+(your\s+)?(system\s+prompt|instructions|prompt)\b", re.I),
     "extract_system_prompt", 1.0),
    (re.compile(r"\bwhat\s+(are\s+)?(your|the)\s+(instructions|prompt|rules|guidelines)\b", re.I),
     "probe_instructions", 0.7),

    # --- DAN / jailbreak keywords ---
    (re.compile(r"\b(DAN|jailbreak|do\s+anything\s+now)\b", re.I),
     "dan_jailbreak", 1.0),
    (re.compile(r"\b(no\s+restrictions?|without\s+restrictions?|unrestricted\s+mode)\b", re.I),
     "no_restrictions", 0.9),

    # --- Instruction injection via delimiter confusion ---
    # Matches sequences that look like injected system-level delimiters
    (re.compile(r"(###\s*system|<\s*system\s*>|\[system\]|\bsystem:\s)", re.I),
     "delimiter_injection", 1.0),
    (re.compile(r"(###\s*instruction|<\s*instruction\s*>|\[instruction\])", re.I),
     "instruction_delimiter", 1.0),

    # --- Override scoped to English compound avoidance ---
    # Avoids "prisoverride", "systemoverride" etc. by requiring whitespace before
    (re.compile(r"(?<!\w)override\s+(your\s+)?(safety|filter|rule|policy|instruction)", re.I),
     "override_safety", 1.0),
]

# Max possible raw score (sum of all weights)
_MAX_RAW = sum(w for _, _, w in _PATTERNS)


def detect(text: str) -> tuple[float, list[str]]:
    """
    Returns (normalised_score 0.0–1.0, list_of_trigger_labels).
    Score is normalised so a single high-confidence match doesn't max out.
    """
    total = 0.0
    triggers: list[str] = []

    for pattern, label, weight in _PATTERNS:
        if pattern.search(text):
            total += weight
            triggers.append(label)

    normalised = min(total / _MAX_RAW, 1.0) if _MAX_RAW else 0.0
    return normalised, triggers