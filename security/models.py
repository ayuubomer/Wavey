"""
security/models.py — shared data types.  No logic, no side-effects.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    ALLOW     = "ALLOW"
    CHALLENGE = "CHALLENGE"
    LIMIT     = "LIMIT"
    BLOCK     = "BLOCK"


@dataclass(frozen=True, slots=True)
class SecurityResult:
    decision:       Decision
    score:          float
    triggers:       tuple[str, ...] = field(default_factory=tuple)
    sanitized_query: str            = ""

    # Convenience helpers ────────────────────────────────────────────────────
    @property
    def allowed(self) -> bool:
        return self.decision in (Decision.ALLOW, Decision.CHALLENGE)

    @property
    def blocked(self) -> bool:
        return self.decision == Decision.BLOCK

    @property
    def limited(self) -> bool:
        return self.decision == Decision.LIMIT