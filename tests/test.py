import pytest

from security.validation import validate_input, sanitize_query
from security.scoring import compute_score
from security.policy import evaluate
from security.models import Decision


def test_validate_input_accepts_valid_query():
    validate_input("Hva er AI?")


def test_validate_input_rejects_none():
    with pytest.raises(ValueError):
        validate_input(None)


def test_validate_input_rejects_short():
    with pytest.raises(ValueError):
        validate_input("hi")


def test_sanitize_query():
    assert sanitize_query("  Hei   verden ") == "Hei verden"


def test_compute_score():
    assert compute_score(50, 20, 0) == 39.0


def test_policy_allow():
    decision, penalty = evaluate(10)
    assert decision == Decision.ALLOW


def test_policy_block():
    decision, penalty = evaluate(100)
    assert decision == Decision.BLOCK


def test_sanitize_query_handles_empty_string():
    assert sanitize_query("") == ""


def test_compute_score_with_zero_values():
    assert compute_score(0, 0, 0) == 0.0


def test_policy_block_has_penalty():
    decision, penalty = evaluate(100)
    assert decision == Decision.BLOCK
    assert penalty > 0

# Additioonal advanced tests:
# - Mocking the LLM response to test how the system handles different outputs.

from security.pipeline import _run_pipeline


def test_security_pipeline_with_mocked_dependencies(monkeypatch):
    monkeypatch.setattr("security.pipeline.run_detectors", lambda query: (80, ["test_trigger"]))
    monkeypatch.setattr("security.pipeline.get_ip_risk", lambda ip: 10)
    monkeypatch.setattr("security.pipeline.get_ip_velocity", lambda ip: 0)
    monkeypatch.setattr("security.pipeline.record_ip_request", lambda ip, risk_delta: None)

    result = _run_pipeline("  Dette er en testspørring  ", "127.0.0.1")

    assert result.sanitized_query == "Dette er en testspørring"
    assert result.score == 58.0
    assert "test_trigger" in result.triggers
    assert result.decision in [
        Decision.ALLOW,
        Decision.CHALLENGE,
        Decision.LIMIT,
        Decision.BLOCK,
    ]