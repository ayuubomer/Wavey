"""
security/policy.py — maps a numeric score to a Decision + IP penalty.

No I/O.  No Flask.  Pure function.
"""
from __future__ import annotations
from .config import (
    SCORE_BLOCK, SCORE_LIMIT, SCORE_CHALLENGE,
    PENALTY_BLOCK, PENALTY_LIMIT, PENALTY_CHALLENGE,
)
from .models import Decision


def evaluate(score: float) -> tuple[Decision, float]:
    """
    Returns (Decision, penalty_to_add_to_ip_risk_score).
    """
    if score >= SCORE_BLOCK:
        return Decision.BLOCK,     PENALTY_BLOCK
    if score >= SCORE_LIMIT:
        return Decision.LIMIT,     PENALTY_LIMIT
    if score >= SCORE_CHALLENGE:
        return Decision.CHALLENGE, PENALTY_CHALLENGE
    return Decision.ALLOW,         0.0