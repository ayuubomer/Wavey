import re
import unicodedata
import time
import logging
import hashlib
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

# ==================================================
# IN-MEMORY STORAGE (Redis replacement)
# ==================================================

_ip_risk_store = {}
_ip_last_seen = {}
_ip_request_count = {}
_store_lock = Lock()

RISK_TTL_SECONDS = 3600  # 1 hour expiry
DECAY_INTERVAL = 60
DECAY_AMOUNT = 2
MAX_IP_RISK = 80

# ==================================================
# CONFIG
# ==================================================

MAX_QUERY_LENGTH = 1500
MIN_QUERY_LENGTH = 2
MAX_QUERY_TOKENS = 300

BLOCK_THRESHOLD = 70
LIMIT_THRESHOLD = 40
CHALLENGE_THRESHOLD = 25

PENALTY_INJECTION = 35
PENALTY_OBFUSCATION = 25
PENALTY_ANOMALY = 15
PENALTY_ENCODING = 20

CAP_INJECTION = 100
CAP_OBFUSCATION = 50
CAP_ENCODING = 50
CAP_ANOMALY = 50
CAP_VELOCITY = 50

IP_PENALTY_BLOCK = 5
IP_PENALTY_LIMIT = 2
IP_PENALTY_CHALLENGE = 1

# ==================================================
# DATA STRUCTURE
# ==================================================

@dataclass
class SecurityResult:
    clean_query: str
    risk_score: int
    decision: str
    injection_score: int = 0
    obfuscation_score: int = 0
    encoding_score: int = 0
    anomaly_score: int = 0
    ip_risk: int = 0
    velocity_score: int = 0
    triggers: list = field(default_factory=list)
    ip_hash: str = ""

# ==================================================
# UTIL
# ==================================================

def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

# ==================================================
# INPUT VALIDATION
# ==================================================

def validate_input(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Input must be string")

    if "\x00" in text:
        raise ValueError("Null byte detected")

    text = text.strip()

    if len(text) < MIN_QUERY_LENGTH:
        raise ValueError("Too short")
    if len(text) > MAX_QUERY_LENGTH:
        raise ValueError("Too long")

    return text

# ==================================================
# SANITISATION
# ==================================================

def _sanitize_query(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"<[^>]{0,500}>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ==================================================
# DETECTION (same logic as before)
# ==================================================

def detect_injection(text: str):
    score = 0
    triggers = []

    patterns = [
        r"ignore.*instructions",
        r"disregard.*instructions",
        r"you are now",
        r"developer mode",
        r"jailbreak",
        r"override",
    ]

    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            score += PENALTY_INJECTION
            triggers.append(f"injection:{p}")

    return min(score, CAP_INJECTION), triggers


def detect_obfuscation(text: str):
    score = 0
    triggers = []

    if re.search(r"[\u200b-\u200f\u2060-\u2064\ufeff]", text):
        score += PENALTY_OBFUSCATION
        triggers.append("obfuscation:invisible_chars")

    return min(score, CAP_OBFUSCATION), triggers


def detect_encoding_tricks(text: str):
    score = 0
    triggers = []

    if re.search(r"[A-Za-z0-9+/]{30,}={0,2}", text):
        score += PENALTY_ENCODING
        triggers.append("encoding:base64")

    return min(score, CAP_ENCODING), triggers


def detect_structure_anomaly(text: str):
    score = 0
    triggers = []

    if len(text.split()) > MAX_QUERY_TOKENS:
        score += PENALTY_ANOMALY
        triggers.append("anomaly:too_long")

    if text.count("?") > 4:
        score += PENALTY_ANOMALY
        triggers.append("anomaly:spam_questions")

    return min(score, CAP_ANOMALY), triggers

# ==================================================
# IN-MEMORY IP SYSTEM (Redis replacement)
# ==================================================

def _cleanup(ip: str):
    now = time.time()

    # cleanup risk expiry
    if ip in _ip_last_seen:
        if now - _ip_last_seen[ip] > RISK_TTL_SECONDS:
            _ip_risk_store.pop(ip, None)
            _ip_last_seen.pop(ip, None)
            _ip_request_count.pop(ip, None)


def get_ip_risk(ip: str) -> int:
    with _store_lock:
        _cleanup(ip)
        return _ip_risk_store.get(ip, 0)


def increase_ip_risk(ip: str, amount: int):
    with _store_lock:
        _cleanup(ip)
        _ip_risk_store[ip] = min(
            MAX_IP_RISK,
            _ip_risk_store.get(ip, 0) + amount
        )
        _ip_last_seen[ip] = time.time()


def record_request(ip: str):
    with _store_lock:
        _cleanup(ip)
        _ip_request_count[ip] = _ip_request_count.get(ip, 0) + 1
        _ip_last_seen[ip] = time.time()


def get_velocity(ip: str) -> int:
    with _store_lock:
        _cleanup(ip)
        return _ip_request_count.get(ip, 0)


def decay_ip_risk(ip: str):
    with _store_lock:
        _cleanup(ip)

        if ip not in _ip_last_seen:
            return

        elapsed = time.time() - _ip_last_seen[ip]
        intervals = int(elapsed / DECAY_INTERVAL)

        if intervals > 0:
            _ip_risk_store[ip] = max(
                0,
                _ip_risk_store.get(ip, 0) - intervals * DECAY_AMOUNT
            )
            _ip_last_seen[ip] = time.time()

# ==================================================
# RISK ENGINE
# ==================================================

def compute_risk(text: str, ip: str):
    inj, t1 = detect_injection(text)
    obf, t2 = detect_obfuscation(text)
    enc, t3 = detect_encoding_tricks(text)
    anm, t4 = detect_structure_anomaly(text)

    ip_risk = get_ip_risk(ip)
    velocity = min(get_velocity(ip) // 10, CAP_VELOCITY)

    total = inj + obf + enc + anm + ip_risk + velocity

    return min(total, 100), {
        "injection": inj,
        "obfuscation": obf,
        "encoding": enc,
        "anomaly": anm,
        "ip_risk": ip_risk,
        "velocity": velocity,
        "triggers": t1 + t2 + t3 + t4
    }

# ==================================================
# POLICY
# ==================================================

def apply_policy(score: int) -> str:
    if score >= BLOCK_THRESHOLD:
        return "BLOCK"
    if score >= LIMIT_THRESHOLD:
        return "LIMIT"
    if score >= CHALLENGE_THRESHOLD:
        return "CHALLENGE"
    return "ALLOW"

# ==================================================
# MAIN ENTRY
# ==================================================

def analyze_query(text: str, ip: str) -> SecurityResult:
    ip_hash = _hash_ip(ip)

    validated = validate_input(text)
    clean = _sanitize_query(validated)

    decay_ip_risk(ip)
    record_request(ip)

    score, breakdown = compute_risk(clean, ip)
    decision = apply_policy(score)

    if decision == "BLOCK":
        increase_ip_risk(ip, IP_PENALTY_BLOCK)
    elif decision == "LIMIT":
        increase_ip_risk(ip, IP_PENALTY_LIMIT)
    elif decision == "CHALLENGE":
        increase_ip_risk(ip, IP_PENALTY_CHALLENGE)

    return SecurityResult(
        clean_query=clean,
        risk_score=score,
        decision=decision,
        injection_score=breakdown["injection"],
        obfuscation_score=breakdown["obfuscation"],
        encoding_score=breakdown["encoding"],
        anomaly_score=breakdown["anomaly"],
        ip_risk=breakdown["ip_risk"],
        velocity_score=breakdown["velocity"],
        triggers=breakdown["triggers"],
        ip_hash=ip_hash
    )