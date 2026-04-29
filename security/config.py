"""
security/config.py — security-specific constants only.
Nothing from this module is imported by app.py directly.
"""
import os

# ── Input validation ───────────────────────────────────────────────────────
QUERY_MIN_LEN  = int(os.environ.get("QUERY_MIN_LEN", "3"))
QUERY_MAX_LEN  = int(os.environ.get("QUERY_MAX_LEN", "2000"))

# ── Detector weights (0–100 contribution each) ────────────────────────────
INJECTION_WEIGHT   = float(os.environ.get("INJECTION_WEIGHT",   "40"))
OBFUSCATION_WEIGHT = float(os.environ.get("OBFUSCATION_WEIGHT", "25"))
ENCODING_WEIGHT    = float(os.environ.get("ENCODING_WEIGHT",    "20"))
ANOMALY_WEIGHT     = float(os.environ.get("ANOMALY_WEIGHT",     "15"))

# ── IP scoring ─────────────────────────────────────────────────────────────
IP_RISK_DECAY_FACTOR   = float(os.environ.get("IP_RISK_DECAY_FACTOR",   "0.95"))
IP_MAX_RISK_SCORE      = float(os.environ.get("IP_MAX_RISK_SCORE",      "100.0"))
IP_VELOCITY_WINDOW_SEC = int(os.environ.get("IP_VELOCITY_WINDOW_SEC",   "60"))     # sliding window
IP_VELOCITY_MAX        = int(os.environ.get("IP_VELOCITY_MAX",          "20"))     # requests / window
IP_TTL_SECONDS         = int(os.environ.get("IP_TTL_SECONDS",           "3600"))   # evict after 1 h idle
IP_STORE_MAX_ENTRIES   = int(os.environ.get("IP_STORE_MAX_ENTRIES",     "50000"))  # hard cap on store size

# ── Policy thresholds ──────────────────────────────────────────────────────
SCORE_BLOCK     = float(os.environ.get("SCORE_BLOCK",     "75"))
SCORE_LIMIT     = float(os.environ.get("SCORE_LIMIT",     "50"))
SCORE_CHALLENGE = float(os.environ.get("SCORE_CHALLENGE", "30"))

# ── Policy penalties added to future requests ─────────────────────────────
PENALTY_BLOCK     = float(os.environ.get("PENALTY_BLOCK",     "30"))
PENALTY_LIMIT     = float(os.environ.get("PENALTY_LIMIT",     "15"))
PENALTY_CHALLENGE = float(os.environ.get("PENALTY_CHALLENGE", "5"))

# ── Pipeline circuit-breaker ───────────────────────────────────────────────
PIPELINE_TIMEOUT_SEC = float(os.environ.get("PIPELINE_TIMEOUT_SEC", "2.0"))