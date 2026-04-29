"""
security/detectors/__init__.py — detector registry.

To add a new detector:
  1. Create security/detectors/mydetector.py with a detect(text) -> (score, triggers) function.
  2. Import it here and append it to _DETECTORS.
  That's all — nothing else changes.
"""
from __future__ import annotations
from . import injection, obfuscation, encoding, anomaly
from ..config import (
    INJECTION_WEIGHT,
    OBFUSCATION_WEIGHT,
    ENCODING_WEIGHT,
    ANOMALY_WEIGHT,
)
from typing import Callable

# (module, weight) — weight is the maximum contribution to the overall score
_DETECTORS: list[tuple[Callable, float]] = [
    (injection.detect,   INJECTION_WEIGHT),
    (obfuscation.detect, OBFUSCATION_WEIGHT),
    (encoding.detect,    ENCODING_WEIGHT),
    (anomaly.detect,     ANOMALY_WEIGHT),
]


def run_all(text: str) -> tuple[float, list[str]]:
    """
    Run every registered detector and return:
        (combined_weighted_score 0–100, flat_list_of_all_triggers)
    """
    total_score  = 0.0
    all_triggers: list[str] = []

    for detect_fn, weight in _DETECTORS:
        normalised, triggers = detect_fn(text)   # normalised ∈ [0, 1]
        total_score += normalised * weight
        all_triggers.extend(triggers)

    # Cap at 100
    return min(total_score, 100.0), all_triggers