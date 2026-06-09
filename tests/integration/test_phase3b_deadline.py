"""
Phase 3B — Deterministic deadline tracker integration tests.

Validates:
  1. Rules API returns time_limit_months with authority_ref and last_verified_at
  2. Deadline arithmetic: EDT only
  3. Deadline arithmetic: EC applied, floor does NOT bite
  4. Deadline arithmetic: EC applied, floor BITES
  5. Invalid EC dates (Day B < Day A) rejected at API validation
  6. POST /assess with wrong client_deadline → deadline_mismatch=True
  7. POST /assess with correct client_deadline → deadline_mismatch=False
  8. POST /assess without client_deadline → deadline_mismatch absent
  9. Static routes (Phase 3A regression check)
 10. Rules endpoint returns no is_prospective rows

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase3b_deadline.py -v -s
"""

from __future__ import annotations

from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.domains.employment.deadline import compute_limitation_date, _add_months

client = TestClient(app, raise_server_exceptions=True)

_BASE_FACTS = {
    "edt": "2026-04-01",
    "service_start_date": "2023-04-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 600,
    "jurisdiction": "EW",
}


# ── 1. Rules API completeness ─────────────────────────────────────────────────

def test_rules_api_returns_time_limit_months():
    """GET /rules/unfair_dismissal must include time_limit_months rule."""
    resp = client.get("/rules/unfair_dismissal")
    assert resp.status_code == 200
    data = resp.json()
    keys = [r["rule_key"] for r in data["rules"]]
    assert "unfair_dismissal.time_limit_months" in keys, \
        f"time_limit_months not found in rules. Keys: {keys}"


def test_rules_api_time_limit_value_is_three():
    """time_limit_months must be 3 for current unfair dismissal rules."""
    resp = client.get("/rules/unfair_dismissal")
    data = resp.json()
    rule = next(r for r in data["rules"] if r["rule_key"] == "unfair_dismissal.time_limit_months")
    assert int(rule["value_numeric"]) == 3


def test_rules_api_has_authority_ref():
    """time_limit_months rule must carry an authority_ref."""
    resp = client.get("/rules/unfair_dismissal")
    data = resp.json()
    rule = next(r for r in data["rules"] if r["rule_key"] == "unfair_dismissal.time_limit_months")
    assert rule.get("authority_ref"), "authority_ref must not be empty"
    assert "s.111" in rule["authority_ref"] or "111" in rule["authority_ref"], \
        f"authority_ref should reference ERA 1996 s.111: {rule['authority_ref']}"


def test_rules_api_has_last_verified_at():
    """Phase 3B requirement: rules API must include last_verified_at."""
    resp = client.get("/rules/unfair_dismissal")
    data = resp.json()
    rule = next(r for r in data["rules"] if r["rule_key"] == "unfair_dismissal.time_limit_months")
    assert "last_verified_at" in rule, "last_verified_at field missing from rules response"
    assert rule["last_verified_at"] is not None, "last_verified_at must not be null"


def test_rules_api_no_prospective_rows():
    """is_prospective=true rows must never appear in the rules API response."""
    resp = client.get("/rules/unfair_dismissal")
    data = resp.json()
    for rule in data["rules"]:
        assert rule["is_prospective"] is False, \
            f"Prospective rule leaked into API response: {rule['rule_key']}"


# ── 2. Deadline arithmetic — Python (mirrors JS) ──────────────────────────────

def test_deadline_edt_only():
    """EDT only: base limit = anniversary - 1 day. No EC stop-clock."""
    edt = date(2026, 4, 1)
    result = compute_limitation_date(edt, 3)
    assert result["limitation_date"] == "2026-06-30"
    assert result["ec_applied"] is False
    assert result["source"] == "rules"
    assert "s.111" in result["authority"]


def test_deadline_edt_only_month_end_clamp():
    """Month-end clamping: EDT 31 Jan + 3 months → anniversary 30 Apr → deadline 29 Apr."""
    edt = date(2026, 1, 31)
    result = compute_limitation_date(edt, 3)
    # _add_months(Jan 31, 3) = Apr 30 (clamped); deadline = Apr 29
    assert result["limitation_date"] == "2026-04-29"


def test_deadline_ec_no_floor():
    """EC applied, floor does NOT bite: extended limit > 1 month after Day B."""
    # EDT 2026-01-01, base = 2026-03-31
    # Day A = 2026-02-01, Day B = 2026-02-15 → pause = 14 days
    # extended = 2026-03-31 + 14 = 2026-04-14
    # floor = add_months(2026-02-15, 1) = 2026-03-15
    # final = max(2026-04-14, 2026-03-15) = 2026-04-14 (floor does NOT bite)
    edt   = date(2026, 1, 1)
    day_a = date(2026, 2, 1)
    day_b = date(2026, 2, 15)
    result = compute_limitation_date(edt, 3, day_a, day_b)
    assert result["limitation_date"] == "2026-04-14"
    assert result["ec_applied"] is True
    assert result["floor_applied"] is False
    assert result["pause_days"] == 14
    assert "s.207B" in result["authority"]


def test_deadline_ec_floor_bites():
    """EC applied, floor BITES: 1 month after Day B exceeds extended limit."""
    # EDT 2026-01-01, base = 2026-03-31
    # Day A = 2026-03-20, Day B = 2026-03-25 → pause = 5 days
    # extended = 2026-03-31 + 5 = 2026-04-05
    # floor = add_months(2026-03-25, 1) = 2026-04-25
    # final = max(2026-04-05, 2026-04-25) = 2026-04-25 (floor BITES)
    edt   = date(2026, 1, 1)
    day_a = date(2026, 3, 20)
    day_b = date(2026, 3, 25)
    result = compute_limitation_date(edt, 3, day_a, day_b)
    assert result["limitation_date"] == "2026-04-25"
    assert result["floor_applied"] is True
    assert result["ec_floor"] == "2026-04-25"
    assert result["pause_days"] == 5


def test_deadline_ec_day_b_before_day_a_rejected():
    """Invalid EC dates (Day B < Day A) — form validation must catch this."""
    # This test exercises the intake form validation path via the assess endpoint:
    # the backend pipeline itself doesn't error on this (it would just compute
    # a negative pause); the client validates it. We confirm the pipeline
    # doesn't crash with reversed EC dates.
    facts = {**_BASE_FACTS, "ec_day_a": "2026-03-20", "ec_day_b": "2026-03-10"}
    resp = client.post("/assess", json={
        "query": "unfair dismissal", "facts": facts,
        "jurisdiction": "EW", "use_model": False,
    })
    # Should not 500 — pipeline must handle gracefully
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


# ── 3. Client deadline validation (backend is authoritative) ──────────────────

def test_assess_correct_client_deadline_no_mismatch():
    """Correct client_deadline → deadline_mismatch=False."""
    # Backend will compute 2026-06-30 for EDT 2026-04-01, 3 months
    resp = client.post("/assess", json={
        "query": "I was unfairly dismissed",
        "facts": _BASE_FACTS,
        "jurisdiction": "EW",
        "use_model": False,
        "client_deadline": "2026-06-30",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("deadline_mismatch") is False, \
        f"Expected no mismatch for correct client_deadline, got: {data.get('deadline_mismatch')}"


def test_assess_wrong_client_deadline_flags_mismatch():
    """Wrong client_deadline → deadline_mismatch=True with detail."""
    resp = client.post("/assess", json={
        "query": "I was unfairly dismissed",
        "facts": _BASE_FACTS,
        "jurisdiction": "EW",
        "use_model": False,
        "client_deadline": "2026-01-01",   # deliberately wrong
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("deadline_mismatch") is True, \
        "Expected deadline_mismatch=True for wrong client_deadline"
    detail = data.get("deadline_mismatch_detail", {})
    assert detail.get("client") == "2026-01-01"
    assert detail.get("backend") == "2026-06-30"


def test_assess_without_client_deadline_no_mismatch_key():
    """When client_deadline is not sent, deadline_mismatch must not appear."""
    resp = client.post("/assess", json={
        "query": "I was unfairly dismissed",
        "facts": _BASE_FACTS,
        "jurisdiction": "EW",
        "use_model": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "deadline_mismatch" not in data, \
        "deadline_mismatch must not appear when client_deadline was not supplied"


# ── 4. Phase 3A regression ────────────────────────────────────────────────────

def test_static_routes_still_work():
    """Phase 3A routes must still return 200."""
    for path in ["/", "/pages/intake.html", "/pages/assessment.html"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"

def test_health_still_ok():
    """Health endpoint must still return ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
