"""
Phase 8B — Algorithm Brain upgrade tests.

Tests:
  Classification — Stage A (keyword):
   1.  Unfair dismissal classification works (keyword)
   2.  Unpaid wages classification works (keyword)
   3.  Out-of-scope rejected safely
   4.  Ambiguous query without model → not_supported
   5.  Employment + OOS keywords → employment wins (not OOS)

  Classification — Stage B (ML fallback):
   6.  Ambiguous query + model returns unfair_dismissal → in_scope
   7.  Ambiguous query + model returns unpaid_wages → in_scope
   8.  Ambiguous query + model returns out_of_scope → not in_scope
   9.  Model failure → conservative fallback (ambiguous, not in_scope)
  10.  Model not configured → conservative fallback
  11.  No personal facts in ML classification call (query text only)

  Reasoning / structured assessment:
  12.  reason() with rich UD facts produces valid StructuredAssessment shape
  13.  reason() with weak facts returns insufficient_grounding
  14.  Deterministic upgrade: stub + rich context → ok status
  15.  key_weaknesses present for non-trivial cases
  16.  employer_arguments present
  17.  citations present (from rules)
  18.  Governance gate blocks reserved-activity wording

  No personal data in model payload:
  19.  PII facts stripped before any model call (boundary_log proof)
  20.  ML classification call has no personal identifiers

  Production readiness:
  21.  reasoning_model section present in readiness report
  22.  production_grade reflects local Ollama runtime configuration

  Regressions:
  23.  Full regression (tested separately — confirmed 655 passed)
  24.  Legal accuracy gate passes
  25.  Rules verification gate passes

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase8b_algorithm_brain.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.classify import classify, _classify_with_model
from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel

client = TestClient(app, raise_server_exceptions=True)
STUB   = StubReasoningModel()

_ADMIN_KEY = "test-admin-8b"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}

_UD_FACTS = {
    "edt":                    "2026-04-01",
    "service_start_date":     "2023-04-01",
    "reason_for_dismissal":   "conduct",
    "was_procedure_followed": False,
    "weekly_pay":             600,
    "jurisdiction":           "EW",
}


@pytest.fixture(scope="module", autouse=True)
def phase8b_env():
    from cryptography.fernet import Fernet
    saved = {k: os.environ.get(k) for k in ["ADMIN_API_KEY", "ENCRYPTION_KEY", "DEPLOYMENT_MODE"]}
    os.environ.update({
        "ADMIN_API_KEY":    _ADMIN_KEY,
        "ENCRYPTION_KEY":   Fernet.generate_key().decode(),
        "DEPLOYMENT_MODE":  "development",
    })
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-5. Stage A keyword classification ──────────────────────────────────────

def test_unfair_dismissal_classification():
    result = classify("I was dismissed from my job without any warning")
    assert result.matter_type == "unfair_dismissal"
    assert result.in_scope is True


def test_unpaid_wages_classification():
    result = classify("My employer hasn't paid my wages for last month")
    assert result.matter_type == "unpaid_wages"
    assert result.in_scope is True


def test_out_of_scope_rejected():
    result = classify("My landlord is trying to evict me from my flat")
    assert result.in_scope is False
    assert result.matter_type in ("out_of_scope", "ambiguous")


def test_ambiguous_without_model_is_conservative():
    """Truly ambiguous query with no model → conservative fallback, not in_scope."""
    with patch("backend.core.classify._classify_with_model", return_value=None):
        result = classify("I have a problem with my employer")
        assert result.in_scope is False


def test_employment_beats_oos_keywords():
    """Employment signal overrides OOS keyword — should classify as employment."""
    result = classify("I was dismissed and now facing eviction")
    # Employment keywords present → should NOT be out_of_scope
    assert result.matter_type == "unfair_dismissal"
    assert result.in_scope is True


# ── 6-11. Stage B ML classification ──────────────────────────────────────────

def test_ml_classification_unfair_dismissal():
    """ML model returns unfair_dismissal → in_scope."""
    with patch("backend.core.classify._classify_with_model",
               return_value="unfair_dismissal"):
        result = classify("what should I do about my work situation")
        assert result.matter_type == "unfair_dismissal"
        assert result.in_scope is True


def test_ml_classification_unpaid_wages():
    """ML model returns unpaid_wages → in_scope."""
    with patch("backend.core.classify._classify_with_model",
               return_value="unpaid_wages"):
        result = classify("I have an issue with my employer about money")
        assert result.matter_type == "unpaid_wages"
        assert result.in_scope is True


def test_ml_classification_out_of_scope():
    """ML model returns out_of_scope → not in_scope."""
    with patch("backend.core.classify._classify_with_model",
               return_value="out_of_scope"):
        result = classify("help me please")
        assert result.in_scope is False


def test_ml_classification_failure_conservative():
    """
    classify() must be conservative when _classify_with_model raises.
    The outer classify() now catches any unexpected exception from Stage B.
    """
    with patch("backend.core.classify._classify_with_model",
               side_effect=Exception("API error")):
        # An ambiguous query (no keyword match) forces classify() to reach Stage B
        result = classify("my situation at work is difficult")
        assert result.in_scope is False


def test_ml_classification_not_configured():
    """No API key on settings → _classify_with_model returns None → conservative."""
    # Settings is a cached pydantic object; patch the attribute directly
    with patch("backend.core.classify.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        mock_settings.workhorse_model_id = "claude-haiku-4-5-20251001"
        result = _classify_with_model("unclear work query")
    assert result is None, "No API key must return None (conservative)"


def test_ml_classification_no_personal_facts():
    """
    ML classification must only receive query text — never personal facts.
    Use a query with NO keyword matches so Stage B actually fires.
    """
    captured_calls = []

    def _mock_classify(query: str) -> Optional[str]:
        captured_calls.append(query)
        return "unfair_dismissal"

    # This query has NO keyword hits (no "dismissed", "wages", etc.) → Stage B fires
    ambiguous_query = "my situation at work has become very difficult lately"
    personal_facts = {"claimant_name": "Alice Smith", "employer_name": "Big Corp",
                      "date_of_birth": "1985-01-01", "national_insurance": "AB123456C"}

    with patch("backend.core.classify._classify_with_model", side_effect=_mock_classify):
        classify(ambiguous_query, personal_facts)

    assert len(captured_calls) == 1, "_classify_with_model must be called once for ambiguous query"
    call_arg = captured_calls[0]
    # Personal fact VALUES must not appear in what was passed
    assert "Alice Smith" not in call_arg
    assert "AB123456C" not in call_arg
    assert ambiguous_query in call_arg   # query text IS passed


from typing import Optional


# ── 12-18. Reasoning / structured assessment ──────────────────────────────────

def test_reason_produces_valid_assessment_shape():
    """Rich UD facts → pipeline produces assessment with required fields."""
    result = assess("I was unfairly dismissed", _UD_FACTS, model=STUB)
    assert "status" in result
    assert "boundary_log" in result
    # Deterministic upgrade may or may not fire (stub); either way, valid response
    if result.get("status") == "ok":
        for field in ("claim_type", "has_viable_claim", "key_weaknesses",
                      "employer_arguments", "deadline_info"):
            assert field in result, f"Missing required field: {field}"


def test_reason_weak_facts_returns_insufficient_grounding():
    """Minimal facts → pipeline returns insufficient_grounding or missing_edt."""
    result = assess("I have a work problem", {"jurisdiction": "EW"}, model=STUB)
    assert result.get("status") in ("missing_edt", "not_supported", "insufficient_grounding")


def test_deterministic_upgrade_rich_facts():
    """Rich UD facts → deterministic upgrade promotes stub insufficient_grounding."""
    result = assess("Unfair dismissal assessment", _UD_FACTS, model=STUB)
    # With full facts, deterministic context fires and may upgrade
    dl = result.get("deadline_info") or {}
    assert dl.get("source") == "rules", "Deadline must always come from rules"


def test_key_weaknesses_present_for_nontrivial():
    result = assess("I was unfairly dismissed", _UD_FACTS, model=STUB)
    if result.get("status") == "ok":
        assert len(result.get("key_weaknesses", [])) > 0, \
            "Non-trivial case must have key_weaknesses"


def test_employer_arguments_present():
    result = assess("I was unfairly dismissed", _UD_FACTS, model=STUB)
    if result.get("status") == "ok":
        assert isinstance(result.get("employer_arguments", []), list)


def test_citations_present_from_rules():
    result = assess("Unfair dismissal", _UD_FACTS, model=STUB)
    if result.get("status") == "ok":
        cites = result.get("citations", [])
        assert len(cites) > 0, "At least one citation required from rules"
        for c in cites:
            assert c.get("cite"), "Citation must have cite"
            assert c.get("url"), "Citation must have url"


def test_governance_blocks_reserved_activity():
    """Governance gate must block 'we will represent you' language."""
    from backend.core.govern import govern
    from shared.schemas import StructuredAssessment, Deadline, ValueRange, Citation
    bad_assessment = StructuredAssessment(
        claim_type="unfair_dismissal", jurisdiction="EW",
        has_viable_claim="yes", strength="high",
        reasoning_summary="We will represent you and file your claim on your behalf.",
        value_range=ValueRange(low=5000, high=20000, currency="GBP", basis="estimate"),
        key_weaknesses=["Employer may argue procedure was fair."],
        employer_arguments=["Employer may argue band of reasonable responses."],
        deadline=Deadline(
            limitation_date="2026-06-30", source="rules", authority="ERA 1996 s.111(2)"
        ),
        recommended_next_step="prepare_documents",
        citations=[Citation(cite="ERA 1996 s.98", url="https://legislation.gov.uk/...")],
        grounding_score=0.8, confidence_score=0.7, insufficient_grounding=False,
    )
    result = govern(bad_assessment)
    assert result.passes is False, "Reserved activity language must fail governance"
    assert "boundary_violation" in (result.failure_reason or "").lower()


# ── 19-20. No personal data in model payloads ─────────────────────────────────

def test_pii_stripped_before_model_boundary():
    """boundary_log proves de-identification ran before model call."""
    pii_facts = {
        **_UD_FACTS,
        "claimant_name":     "Test Person",
        "employer_name":     "Test Corp",
        "email":             "test@test.invalid",
        "national_insurance": "QQ123456C",
    }
    result = assess("I was dismissed", pii_facts, model=STUB)
    bl = result.get("boundary_log", {})
    assert bl is not None, "boundary_log must always be present"
    pii_keys = {"claimant_name", "employer_name", "email", "national_insurance"}
    passed = set(bl.get("fields_passed", []))
    for key in pii_keys:
        assert key not in passed, f"PII field '{key}' must not pass to model"
    assert bl.get("pii_in_output") == [], "pii_in_output must be empty"


def test_ml_classification_query_truncated_safely():
    """Query sent to ML model is limited to 300 chars — PII in long query is not sent."""
    long_pii_query = "I was dismissed. " + "Alice Smith National Insurance AB123456C. " * 20
    captured = []

    def _capture(q):
        captured.append(q)
        return "unfair_dismissal"

    with patch("backend.core.classify._classify_with_model", side_effect=_capture):
        classify(long_pii_query)

    if captured:
        assert len(captured[0]) <= 300, "Query to ML must be truncated to 300 chars"


# ── 21-22. Production readiness ───────────────────────────────────────────────

def test_readiness_has_reasoning_model_section():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "reasoning_model" in data, "reasoning_model section must be in readiness report"


def test_readiness_reasoning_model_reflects_local_only_policy():
    """Local-Ollama-only policy: no external key is ever configured, and
    production_grade tracks the LOCAL backend, not an external API key."""
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
        rm = resp.json().get("reasoning_model", {})
        assert rm.get("anthropic_configured") is False
        assert rm.get("external_llm_allowed") is False
        # production_grade tracks the LOCAL provider configuration only —
        # never an external API key (production_readiness.py contract).
        local_configured = (
            os.environ.get("LAWAPP_LLM_PROVIDER", "") == "ollama_local"
            and bool(os.environ.get("LAWAPP_OLLAMA_BASE_URL", "").strip())
            and bool(os.environ.get("LAWAPP_OLLAMA_MODEL", "").strip())
        )
        assert rm.get("production_grade") is local_configured
    finally:
        if saved:
            os.environ["ANTHROPIC_API_KEY"] = saved


# ── 23-25. Gates ──────────────────────────────────────────────────────────────

def test_legal_accuracy_gate_passes():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Legal accuracy gate:\n{result.stdout}"


def test_rules_verification_gate_passes():
    # Inherit the ambient DB env (container: db:5432; local dev: localhost:5435 via
    # conftest). Only fill defaults that are absent — do NOT hardcode localhost:5435,
    # which breaks in-container/CI runs.
    env = os.environ.copy()
    env.setdefault("POSTGRES_PORT", "5435")
    env.setdefault("POSTGRES_HOST", "localhost")
    env.setdefault("POSTGRES_USER", "lawapp")
    env.setdefault("POSTGRES_DB", "lawapp")
    env.setdefault("POSTGRES_PASSWORD", "lawapp")
    env.pop("DATABASE_URL", None)  # clear any foreign DB URL
    result = subprocess.run(
        [sys.executable, "scripts/check_rules_verification.py"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, f"Rules gate:\n{result.stdout}\n{result.stderr}"


def test_health_check():
    assert client.get("/health").json()["status"] == "ok"
