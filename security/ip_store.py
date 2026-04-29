"""
security/ip_store.py — thread-safe, bounded, windowed IP risk state.

Key improvements over the previous version:
    • Velocity is a sliding window (deque of timestamps), not a raw counter.
    • _cleanup() is called on every mutating operation and evicts ALL stale entries,
    not just the one being looked up — prevents unbounded store growth.
    • Hard cap: when the store exceeds IP_STORE_MAX_ENTRIES, the lowest-risk half
    is evicted so memory is bounded even under sustained attack.
    • Lock acquire uses a timeout so a contended lock never blocks a Flask worker
    indefinitely (pairs with the circuit-breaker in pipeline.py).
"""
from __future__ import annotations
import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from typing import NamedTuple

from .config import (
    IP_MAX_RISK_SCORE,
    IP_RISK_DECAY_FACTOR,
    IP_STORE_MAX_ENTRIES,
    IP_TTL_SECONDS,
    IP_VELOCITY_MAX,
    IP_VELOCITY_WINDOW_SEC,
)

log = logging.getLogger(__name__)


class IPState(NamedTuple):
    risk_score:  float
    timestamps:  deque   # deque of float (epoch seconds) — the sliding window
    last_seen:   float


class IPStore:
    """Singleton-style store; instantiate once at module level."""

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._store: dict[str, IPState] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def get_risk_score(self, ip_hash: str) -> float:
        with self._lock:
            state = self._store.get(ip_hash)
            if state is None:
                return 0.0
            return self._decayed_score(state)

    def get_velocity(self, ip_hash: str) -> int:
        """Return number of requests in the current sliding window."""
        with self._lock:
            state = self._store.get(ip_hash)
            if state is None:
                return 0
            now = time.time()
            self._trim_window(state.timestamps, now)
            return len(state.timestamps)

    def record_request(self, ip_hash: str, risk_delta: float = 0.0) -> None:
        """
        Record one request for ip_hash and optionally add risk_delta to its score.
        Triggers a full cleanup pass every call.
        """
        now = time.time()
        acquired = self._lock.acquire(timeout=0.1)
        if not acquired:
            log.warning("ip_store lock contention: skipping record for %s", ip_hash)
            return

        try:
            self._cleanup(now)
            state = self._store.get(ip_hash)

            if state is None:
                ts: deque = deque()
                ts.append(now)
                self._store[ip_hash] = IPState(
                    risk_score=min(risk_delta, IP_MAX_RISK_SCORE),
                    timestamps=ts,
                    last_seen=now,
                )
            else:
                self._trim_window(state.timestamps, now)
                state.timestamps.append(now)
                new_score = min(
                    self._decayed_score(state) + risk_delta,
                    IP_MAX_RISK_SCORE,
                )
                self._store[ip_hash] = IPState(
                    risk_score=new_score,
                    timestamps=state.timestamps,
                    last_seen=now,
                )

            self._enforce_size_cap()
        finally:
            self._lock.release()

    def is_velocity_exceeded(self, ip_hash: str) -> bool:
        return self.get_velocity(ip_hash) > IP_VELOCITY_MAX

    # ── Internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _decayed_score(state: IPState) -> float:
        idle = time.time() - state.last_seen
        decays = idle / 60.0                         # one decay tick per minute
        return state.risk_score * (IP_RISK_DECAY_FACTOR ** decays)

    @staticmethod
    def _trim_window(timestamps: deque, now: float) -> None:
        cutoff = now - IP_VELOCITY_WINDOW_SEC
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _cleanup(self, now: float) -> None:
        """Evict ALL entries whose last_seen is beyond TTL."""
        cutoff = now - IP_TTL_SECONDS
        stale = [k for k, v in self._store.items() if v.last_seen < cutoff]
        for k in stale:
            del self._store[k]
        if stale:
            log.debug("ip_store: evicted %d stale entries", len(stale))

    def _enforce_size_cap(self) -> None:
        if len(self._store) <= IP_STORE_MAX_ENTRIES:
            return
        # Evict the lowest-risk half to make room
        sorted_keys = sorted(self._store, key=lambda k: self._store[k].risk_score)
        evict_count = len(self._store) // 2
        for k in sorted_keys[:evict_count]:
            del self._store[k]
        log.warning("ip_store: size cap hit, evicted %d low-risk entries", evict_count)


# ── Module-level singleton ─────────────────────────────────────────────────
_store = IPStore()


def hash_ip(ip: str) -> str:
    """One-way hash so raw IPs are never stored."""
    return hashlib.blake2b(ip.encode(), digest_size=16).hexdigest()


def get_ip_risk(ip: str) -> float:
    return _store.get_risk_score(hash_ip(ip))


def get_ip_velocity(ip: str) -> int:
    return _store.get_velocity(hash_ip(ip))


def record_ip_request(ip: str, risk_delta: float = 0.0) -> None:
    _store.record_request(hash_ip(ip), risk_delta)


def is_velocity_exceeded(ip: str) -> bool:
    return _store.is_velocity_exceeded(hash_ip(ip))