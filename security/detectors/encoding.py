"""
security/detectors/encoding.py — encoding-trick detector.

Catches:
  • Base64-encoded payloads
  • URL percent-encoding (multiple consecutive %XX sequences)
  • Hex string blobs (\x41\x42 or 0x41 0x42 style)
  • Unicode escape sequences (\u0041 style outside of legitimate source code)
"""
from __future__ import annotations
import re

_BASE64_RE = re.compile(
    r"(?:[A-Za-z0-9+/]{4}){4,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?"
)

_PERCENT_RE = re.compile(r"(?:%[0-9A-Fa-f]{2}){4,}")

_HEX_ESCAPE_RE = re.compile(r"(?:\\x[0-9A-Fa-f]{2}){3,}")

_HEX_LITERAL_RE = re.compile(r"(?:0x[0-9A-Fa-f]{2}\s*){4,}")

_UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9A-Fa-f]{4}){3,}")


def detect(text: str) -> tuple[float, list[str]]:
    score = 0.0
    triggers: list[str] = []

    if _BASE64_RE.search(text):
        score += 0.7
        triggers.append("base64_blob")

    if _PERCENT_RE.search(text):
        score += 0.6
        triggers.append("percent_encoding")

    if _HEX_ESCAPE_RE.search(text):
        score += 0.8
        triggers.append("hex_escape_sequence")

    if _HEX_LITERAL_RE.search(text):
        score += 0.7
        triggers.append("hex_literal_sequence")

    if _UNICODE_ESCAPE_RE.search(text):
        score += 0.5
        triggers.append("unicode_escape_sequence")

    return min(score, 1.0), triggers