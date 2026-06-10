"""
Phase 5B — Unpaid wages / unlawful deduction integration tests.

Tests:
  Classification:
   1.  Unpaid wages query classifies as unpaid_wages
   2.  Unfair dismissal query still classifies as unfair_dismissal
   3.  OOS query still returns not_supported

  Rules:
   4.  GET /rules/unpaid_wages returns expected rules
   5.  time_limit_months = 3
   6.  qualifying_period_years = 0 (day-one right)
   7.  authority_ref contains ERA 1996

  Assessment:
   8.  Unpaid wages assessment returns structured output
   9.  Deadline uses wages_due_date, not EDT
  10.  No qualifying period applied to unpaid wages
  11.  Missing wages_due_date → missing_wages_date status
  12.  Self-employed → has_viable_claim='no'

  Document generation:
  13.  Letter before action generates
  14.  ET1 support notes (wages) generates
  15.  Generated documents include legal boundary notice
  16.  Generated documents do not include prohibited phrases

  Saved case:
  17.  Unpaid wages case can be saved and retrieved

  Safety:
  18.  Assessment contains no prohibited phrases
  19.  Assessment boundary_log proves de-identification

  Regressions:
  20.  Legal accuracy CI gate still passes
  21.  Unfair dismissal still works
  22.  Static routes still serve
  23.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase5b_unpaid_wages.py -v -s
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.classify import classify
from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel
from tests.integration.payment_helpers import mark_case_paid

client = TestClient(app, raise_server_exceptions=True)
STUB = StubReasoningModel()

_UPW_FACTS = {
    "wages_due_date": "2026-03-31",
    "unpaid_amount":  2500.0,
    "pay_frequency":  "monthly",
    "worker_status":  "employee",
    "jurisdiction":   "EW",
}

_UPW_ASSESSMENT = {
    "status": "ok",
    "claim_type": "unpaid_wages",
    "has_viable_claim": "yes",
    "strength": "medium",
    "reasoning_summary": "Employer has not paid final month's salary.",
    "key_weaknesses": [],
    "employer_arguments": ["Employer may dispute amount owed."],
    "deadline_info": {
        "limitation_date": "2026-06-30",
        "source": "rules",
        "authority": "ERA 1996 s.23(2)",
        "ec_applied": False,
    },
    "value_range": {"low": 2500.0, "high": 2500.0, "currency": "GBP",
                    "basis": "Gross wages unlawfully deducted (ERA 1996 s.24)."},
    "recommended_next_step": "prepare_documents",
    "citations": [{"cite": "ERA 1996 s.13", "url": "https://legislation.gov.uk/ukpga/1996/18/section/13"}],
    "grounding_score": 0.85, "confidence_score": 0.75, "insufficient_grounding": False,
    "boundary_log": {"fields_passed": ["wages_due_date", "unpaid_amount"], "fields_stripped": [], "pii_in_output": []},
}

_PROHIBITED = [
    "we will file", "we will submit", "we will represent",
    "guaranteed to win", "guaranteed outcome", "guaranteed success",
    "you will win", "as your solicitor",
]   # "guaranteed" alone is NOT prohibited — the legal notice says "No outcome is guaranteed"


def _make_paid_wages_case() -> str:
    resp = client.post("/cases", json={
        "claim_type": "unpaid_wages",
        "jurisdiction": "EW",
        "assessment": _UPW_ASSESSMENT,
        "key_dates": {"wages_due_date": "2026-03-31", "deadline_date": "2026-06-30"},
    })
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]
    mark_case_paid(case_id)
    return case_id


def _generate_paid_wages_document(doc_type: str):
    return client.post("/documents/generate", json={
        "document_type": doc_type,
        "assessment": _UPW_ASSESSMENT,
        "facts": _UPW_FACTS,
        "case_id": _make_paid_wages_case(),
    })


# ── 1-3. Classification ────────────────────────────────────────────────────────

def test_unpaid_wages_classification():
    result = classify("My employer hasn't paid my wages — final salary missing", {})
    assert result.matter_type == "unpaid_wages", \
        f"Expected unpaid_wages, got {result.matter_type}"
    assert result.in_scope is True


def test_unpaid_wages_various_queries():
    queries = [
        "I wasn't paid my final salary",
        "Unlawful deduction from wages",
        "My employer underpaid me",
    ]
    for q in queries:
        r = classify(q, {})
        assert r.matter_type == "unpaid_wages", f"Expected unpaid_wages for: {q}"


def test_unfair_dismissal_still_classifies():
    result = classify("I was unfairly dismissed without a hearing", {})
    assert result.matter_type == "unfair_dismissal"


def test_oos_still_rejected():
    result = classify("My landlord wants to evict me", {})
    assert result.in_scope is False


# ── 4-7. Rules API ────────────────────────────────────────────────────────────

def test_unpaid_wages_rules_returned():
    resp = client.get("/rules/unpaid_wages")
    assert resp.status_code == 200
    data = resp.json()
    keys = [r["rule_key"] for r in data["rules"]]
    assert "unlawful_deduction_wages.time_limit_months" in keys, \
        f"time_limit_months rule not found. Keys: {keys}"


def test_unpaid_wages_time_limit_is_3():
    resp = client.get("/rules/unpaid_wages")
    data = resp.json()
    tl = next(r for r in data["rules"] if r["rule_key"] == "unlawful_deduction_wages.time_limit_months")
    assert int(tl["value_numeric"]) == 3


def test_unpaid_wages_qualifying_period_is_zero():
    resp = client.get("/rules/unpaid_wages")
    data = resp.json()
    qp = next((r for r in data["rules"] if r["rule_key"] == "unlawful_deduction_wages.qualifying_period_years"), None)
    assert qp is not None
    assert int(qp["value_numeric"]) == 0


def test_unpaid_wages_rules_have_authority_ref():
    resp = client.get("/rules/unpaid_wages")
    data = resp.json()
    for rule in data["rules"]:
        assert rule.get("authority_ref"), f"Rule {rule['rule_key']} missing authority_ref"
        assert "ERA 1996" in rule["authority_ref"] or "Bear Scotland" in rule["authority_ref"], \
            f"authority_ref should reference ERA 1996: {rule['authority_ref']}"


# ── 8-12. Assessment ──────────────────────────────────────────────────────────

def test_unpaid_wages_assessment_returns_structured_output():
    result = assess("I haven't been paid my wages", _UPW_FACTS, model=STUB)
    assert "status" in result
    assert "boundary_log" in result
    if result.get("status") == "ok":
        assert result.get("claim_type") == "unpaid_wages"


def test_unpaid_wages_deadline_uses_wages_due_date():
    # wages_due_date 2026-03-31: anniversary=2026-06-30 (clamped), deadline=2026-06-29
    result = assess("My employer hasn't paid my wages", _UPW_FACTS, model=STUB)
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-06-29", \
        f"Deadline should be 2026-06-29 (3mo from 2026-03-31 with clamping), got {dl.get('limitation_date')}"
    assert dl.get("source") == "rules"


def test_unpaid_wages_no_qualifying_period_applied():
    result = assess("I wasn't paid", _UPW_FACTS, model=STUB)
    assert result.get("qualifying_check") is None, \
        "Unpaid wages must not have qualifying_check (day-one right)"


def test_unpaid_wages_missing_wages_date_status():
    result = assess("I haven't been paid", {"jurisdiction": "EW", "unpaid_amount": 500}, model=STUB)
    assert result.get("status") == "missing_wages_date", \
        f"Expected missing_wages_date, got {result.get('status')}"


def test_unpaid_wages_self_employed_no_viable():
    facts = {**_UPW_FACTS, "worker_status": "self_employed"}
    result = assess("I haven't been paid as a contractor", facts, model=STUB)
    if result.get("status") == "ok":
        assert result.get("has_viable_claim") == "no", \
            "Self-employed claimant must not have viable wages claim (ERA s.13)"


# ── 13-16. Document generation ────────────────────────────────────────────────

def test_letter_before_action_generates():
    resp = _generate_paid_wages_document("letter_before_action")
    assert resp.status_code == 200
    data = resp.json()
    assert data["safety_check"]["passed"] is True
    assert "letter_before_action" in data["document_type"]


def test_et1_support_notes_wages_generates():
    resp = _generate_paid_wages_document("et1_support_notes_wages")
    assert resp.status_code == 200
    assert resp.json()["safety_check"]["passed"] is True


def test_wages_documents_include_legal_boundary():
    for doc_type in ["letter_before_action", "et1_support_notes_wages"]:
        resp = _generate_paid_wages_document(doc_type)
        content = resp.json()["content"]
        assert "NOT legal advice" in content, f"Legal boundary missing from {doc_type}"
        assert "not a solicitor or law firm" in content.lower()


def test_wages_documents_no_prohibited_phrases():
    for doc_type in ["letter_before_action", "et1_support_notes_wages"]:
        resp = _generate_paid_wages_document(doc_type)
        content = resp.json()["content"].lower()
        for phrase in _PROHIBITED:
            assert phrase.lower() not in content, \
                f"Prohibited phrase '{phrase}' in {doc_type}"


def test_letter_before_action_includes_amount():
    resp = _generate_paid_wages_document("letter_before_action")
    content = resp.json()["content"]
    assert "2,500" in content or "2500" in content, "Letter must include unpaid amount"


def test_et1_notes_wages_do_not_say_we_will_file():
    resp = _generate_paid_wages_document("et1_support_notes_wages")
    content = resp.json()["content"].lower()
    assert "we will file" not in content
    assert "we will submit" not in content
    assert "we will represent" not in content


# ── 17. Saved case ─────────────────────────────────────────────────────────────

def test_unpaid_wages_case_saved_and_retrieved():
    save_resp = client.post("/cases", json={
        "claim_type": "unpaid_wages",
        "jurisdiction": "EW",
        "assessment": _UPW_ASSESSMENT,
        "key_dates": {"wages_due_date": "2026-03-31", "deadline_date": "2026-06-30"},
    })
    assert save_resp.status_code == 201
    case_id = save_resp.json()["case_id"]

    get_resp = client.get(f"/cases/{case_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["claim_type"] == "unpaid_wages"
    assert data["status"] == "diagnosis"


# ── 18-19. Safety ─────────────────────────────────────────────────────────────

def test_assessment_no_prohibited_phrases():
    result = assess("I wasn't paid my salary", _UPW_FACTS, model=STUB)
    result_str = str(result).lower()
    for phrase in _PROHIBITED:
        assert phrase.lower() not in result_str, \
            f"Prohibited phrase '{phrase}' in wages assessment"


def test_assessment_boundary_log_proves_deidentification():
    pii_facts = {
        **_UPW_FACTS,
        "claimant_name": "Test Person",
        "employer_name": "Test Corp Ltd",
        "email": "test@test.invalid",
    }
    result = assess("Unpaid wages", pii_facts, model=STUB)
    bl = result.get("boundary_log", {})
    assert bl is not None
    pii_keys = {"claimant_name", "employer_name", "email"}
    passed = set(bl.get("fields_passed", []))
    for key in pii_keys:
        assert key not in passed, f"PII key '{key}' passed to model"


# ── 20-23. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_ci_gate_passes():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, \
        f"CI gate failed. Output:\n{result.stdout}\n{result.stderr}"


def test_unfair_dismissal_still_works():
    result = assess("I was unfairly dismissed", {
        "edt": "2026-04-01", "service_start_date": "2023-04-01",
        "reason_for_dismissal": "conduct", "weekly_pay": 600,
        "jurisdiction": "EW",
    }, model=STUB)
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-06-30"
    assert dl.get("source") == "rules"


def test_static_routes_regression():
    for path in ["/", "/pages/intake.html", "/pages/assessment.html", "/pages/saved_case.html"]:
        assert client.get(path).status_code == 200


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
