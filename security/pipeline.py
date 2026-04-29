"""
security/pipeline.py — thin orchestrator.

Runs: validate → sanitize → detect → score → policy → update IP state.
Wraps everything in a timeout so a contended ip_store lock or unexpectedly
slow detector never blocks a Flask worker indefinitely.
"""
from __future__ import annotations
import logging
import concurrent.futures
import time

from .config   import PIPELINE_TIMEOUT_SEC
from .models   import Decision, SecurityResult
from .validation import validate_input, sanitize_query
from .detectors  import run_all as run_detectors
from .ip_store   import get_ip_risk, get_ip_velocity, record_ip_request
from .scoring    import compute_score
from .policy     import evaluate

log = logging.getLogger(__name__)

# Single-thread executor: we use submit/result purely for the timeout; there
# is no parallelism here (the GIL and a single thread are fine for this).
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="sec-pipeline")


def _run_pipeline(query: str, ip: str) -> SecurityResult:
    # 1. Validate (may raise ValueError — caller re-raises to Flask)
    validate_input(query)

    # 2. Sanitize
    clean = sanitize_query(query)

    # 3. Detect
    detector_score, triggers = run_detectors(clean)

    # 4. Score
    ip_risk     = get_ip_risk(ip)
    ip_velocity = get_ip_velocity(ip)
    final_score = compute_score(detector_score, ip_risk, ip_velocity)

    # 5. Policy
    decision, penalty = evaluate(final_score)

    # 6. Update IP state (fire-and-forget style; lock has its own timeout)
    record_ip_request(ip, risk_delta=penalty)

    log.info(
        "security decision=%s score=%.1f ip_risk=%.1f velocity=%d triggers=%s",
        decision, final_score, ip_risk, ip_velocity, triggers,
    )

    return SecurityResult(
        decision=decision,
        score=final_score,
        triggers=tuple(triggers),
        sanitized_query=clean,
    )


def analyze_query(query: str, ip: str = "0.0.0.0") -> SecurityResult:
    """
    Public entry point.  Raises ValueError for user-visible validation errors.
    Returns a safe BLOCK result if the pipeline times out or raises unexpectedly.
    """
    future = _executor.submit(_run_pipeline, query, ip)
    try:
        return future.result(timeout=PIPELINE_TIMEOUT_SEC)
    except ValueError:
        raise                              # re-raise for app.py to surface to user
    except concurrent.futures.TimeoutError:
        log.error("security pipeline timeout for ip=%s", ip)
        return SecurityResult(
            decision=Decision.BLOCK,
            score=100.0,
            triggers=("pipeline_timeout",),
            sanitized_query="",
        )
    except Exception as exc:
        log.exception("security pipeline unexpected error: %s", exc)
        return SecurityResult(
            decision=Decision.BLOCK,
            score=100.0,
            triggers=("pipeline_error",),
            sanitized_query="",
        )