"""
security/scoring.py — combines detector output + IP signals into a final 0–100 score.
"""
from __future__ import annotations
from .config import IP_VELOCITY_MAX, IP_VELOCITY_WINDOW_SEC


def compute_score(
    detector_score: float,       # 0–100 from detectors.run_all()
    ip_risk:        float,       # 0–100 from ip_store.get_ip_risk()
    ip_velocity:    int,         # requests in the sliding window
) -> float:
    text_component     = detector_score * 0.70
    history_component  = ip_risk        * 0.20

    velocity_ratio     = max(0.0, (ip_velocity - IP_VELOCITY_MAX) / IP_VELOCITY_MAX)
    velocity_component = min(velocity_ratio * 10.0, 10.0)

    return min(text_component + history_component + velocity_component, 100.0)