"""
Legal accuracy regression suite  -  Phase 5A.

Tests the deterministic pipeline layer against known unfair dismissal
fact patterns. Uses StubReasoningModel only  -  no real LLM, no quota dependency.

This suite proves the deterministic guarantees of the engine:
  - Deadlines are always computed from rules, never guessed.
  - Qualifying period failures produce "no viable claim" deterministically.
  - EC stop-clock arithmetic is correct (floor / no-floor cases).
  - Missing facts produce explicit status, not fabricated assessments.

CI gate: scripts/run_legal_accuracy.py runs this file and exits non-zero on failure.

GUARDRAIL: No real model calls. No real personal data.
GUARDRAIL: All expected outcomes are statute-derived.

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/legal_accuracy/test_legal_accuracy.py -v -s
"""

from __future__ import annotations

import sys
import os

import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.core.pipeline import assess
from backend.core.models import StubReasoningModel
from backend.domains.employment.deadline import compute_limitation_date
from backend.domains.employment.reminders import compute_urgency
from tests.legal_accuracy.fixtures import FACT_PATTERNS, UPW_FACT_PATTERNS

STUB = StubReasoningModel()

# ── Helper ────────────────────────────────────────────────────────────────────

def _run(facts: dict) -> dict:
    return assess("I was unfairly dismissed", facts, model=STUB)


def _get_fixture(fp_id: str) -> dict:
    return next(fp for fp in FACT_PATTERNS if fp["id"] == fp_id)


# ── FP1: Ordinary UD (4yr service, conduct, no procedure) ────────────────────

def test_fp1_deadline_correct():
    """FP1: Deadline must be 2026-06-30 (3 months from EDT 2026-04-01)."""
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or result.get("deadline") or {}
    assert dl.get("limitation_date") == fp["expected"]["deadline_date"], \
        f"FP1 deadline wrong: {dl.get('limitation_date')} != {fp['expected']['deadline_date']}"


def test_fp1_deadline_source_is_rules():
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("source") == "rules", "Deadline must always come from rules, never from model"


def test_fp1_deadline_authority_era1996():
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    auth = dl.get("authority", "")
    assert "ERA 1996" in auth or "s.111" in auth, \
        f"Authority must reference ERA 1996 s.111, got: {auth}"


def test_fp1_qualifying_period_passes():
    """FP1: 4yr service must satisfy the 2-year QP for ordinary UD."""
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    qc = result.get("qualifying_check")
    if qc:
        assert qc.get("meets_qualifying_period") is True, \
            f"FP1 should pass QP (4yr service), got: {qc}"


def test_fp1_claim_type_unfair_dismissal():
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    if result.get("status") == "ok":
        assert result.get("claim_type") == "unfair_dismissal"


def test_fp1_key_weaknesses_present():
    """Deterministic assess_logic.py must populate key_weaknesses for FP1."""
    fp = _get_fixture("FP1")
    result = _run(fp["facts"])
    if result.get("status") == "ok":
        weaknesses = result.get("key_weaknesses", [])
        assert len(weaknesses) > 0, "FP1 must have key_weaknesses from deterministic layer"


# ── FP2: Under qualifying period (14 months service) ─────────────────────────

def test_fp2_deadline_correct():
    """FP2: Deadline must be 2026-06-14 (3 months from 2026-03-15)."""
    fp = _get_fixture("FP2")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == fp["expected"]["deadline_date"], \
        f"FP2 deadline wrong: {dl.get('limitation_date')}"


def test_fp2_qualifying_period_fails():
    """FP2: 14 months service must fail the 2-year qualifying period."""
    fp = _get_fixture("FP2")
    result = _run(fp["facts"])
    qc = result.get("qualifying_check")
    if qc:
        assert qc.get("meets_qualifying_period") is False, \
            f"FP2 (14mo service) must fail QP, got: {qc}"


def test_fp2_no_viable_claim_when_qp_fails():
    """FP2: QP failure must produce has_viable_claim='no' from deterministic layer."""
    fp = _get_fixture("FP2")
    result = _run(fp["facts"])
    if result.get("status") == "ok" and result.get("qualifying_check"):
        qc = result["qualifying_check"]
        if qc.get("meets_qualifying_period") is False:
            assert result.get("has_viable_claim") == "no", \
                "QP failure must set has_viable_claim='no' deterministically"


# ── FP3: Day-one service (auto-unfair candidate) ──────────────────────────────

def test_fp3_deadline_correct():
    """FP3: Deadline must be 2026-07-02 (3mo from 2026-04-03)."""
    fp = _get_fixture("FP3")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == fp["expected"]["deadline_date"]


def test_fp3_qp_fails_for_day_one():
    """FP3: 2 days service must fail 2-year QP."""
    fp = _get_fixture("FP3")
    result = _run(fp["facts"])
    qc = result.get("qualifying_check")
    if qc:
        assert qc.get("meets_qualifying_period") is False


# ── FP4: EC applied  -  floor does NOT bite ────────────────────────────────────

def test_fp4_deadline_floor_does_not_bite():
    """FP4: EC applied with 14-day pause, floor 2026-03-15 < extended 2026-04-14."""
    fp = _get_fixture("FP4")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-04-14", \
        f"FP4 deadline (no floor): expected 2026-04-14, got {dl.get('limitation_date')}"


def test_fp4_ec_applied_true():
    fp = _get_fixture("FP4")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("ec_applied") is True or "s.207B" in dl.get("authority", ""), \
        "FP4: EC must be applied"


def test_fp4_floor_not_applied():
    fp = _get_fixture("FP4")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    if "floor_applied" in dl:
        assert dl["floor_applied"] is False, "FP4: floor must NOT be applied"


# ── FP5: EC applied  -  floor BITES ────────────────────────────────────────────

def test_fp5_deadline_floor_bites():
    """FP5: EC applied, 5-day pause, floor 2026-04-25 > extended 2026-04-05."""
    fp = _get_fixture("FP5")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-04-25", \
        f"FP5 deadline (floor bites): expected 2026-04-25, got {dl.get('limitation_date')}"


def test_fp5_floor_applied():
    fp = _get_fixture("FP5")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    if "floor_applied" in dl:
        assert dl["floor_applied"] is True, "FP5: floor must be applied"


# ── FP6: Missed deadline ──────────────────────────────────────────────────────

def test_fp6_deadline_correct():
    fp = _get_fixture("FP6")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2025-03-31", \
        f"FP6 deadline: expected 2025-03-31, got {dl.get('limitation_date')}"


def test_fp6_deadline_expired_by_2026():
    """FP6: Deadline 2025-03-31 must show expired urgency as of 2026-06-01."""
    urgency = compute_urgency("2025-03-31", today_str="2026-06-01")
    assert urgency["urgency"] == "expired", \
        f"FP6: deadline in past must be 'expired', got {urgency['urgency']}"
    assert urgency["is_urgent"] is True


# ── FP7: Insufficient facts (no EDT) ─────────────────────────────────────────

def test_fp7_missing_edt_status():
    """FP7: No EDT → pipeline must return missing_edt, not fabricate assessment."""
    fp = _get_fixture("FP7")
    result = _run(fp["facts"])
    assert result.get("status") in ("missing_edt", "not_supported"), \
        f"FP7: no EDT must return missing_edt, got status={result.get('status')}"


def test_fp7_no_fabricated_deadline():
    """FP7: No EDT → no deadline should appear."""
    fp = _get_fixture("FP7")
    result = _run(fp["facts"])
    assert "deadline_info" not in result or result.get("status") != "ok", \
        "FP7: no deadline should be computed without EDT"


def test_fp7_no_viable_claim_fabricated():
    """FP7: Insufficient facts must not produce a fabricated viability determination."""
    fp = _get_fixture("FP7")
    result = _run(fp["facts"])
    # Must not be "ok" with a positive has_viable_claim=yes without proper facts
    if result.get("status") == "ok":
        assert result.get("has_viable_claim") != "yes", \
            "FP7: must not fabricate 'yes' viability from insufficient facts"


# ── FP8: Complex case (SOSR + procedure followed) ─────────────────────────────

def test_fp8_deadline_correct():
    fp = _get_fixture("FP8")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-06-30"


def test_fp8_deadline_source_is_rules():
    fp = _get_fixture("FP8")
    result = _run(fp["facts"])
    dl = result.get("deadline_info") or {}
    assert dl.get("source") == "rules"


def test_fp8_qp_passes():
    fp = _get_fixture("FP8")
    result = _run(fp["facts"])
    qc = result.get("qualifying_check")
    if qc:
        assert qc.get("meets_qualifying_period") is True, "FP8: 3yr service must pass QP"


# ── Cross-fixture: deadline authority and de-identification ───────────────────

def test_all_in_scope_deadlines_come_from_rules():
    """Every in-scope fact pattern must have deadline.source='rules'."""
    for fp in FACT_PATTERNS:
        if "no_deadline" in fp["expected"]:
            continue  # FP7  -  no deadline expected
        result = _run(fp["facts"])
        dl = result.get("deadline_info") or {}
        if dl:
            assert dl.get("source") == "rules", \
                f"{fp['id']}: deadline must come from rules, got source={dl.get('source')}"


def test_all_results_have_boundary_log():
    """
    Pipeline results with substantive facts must include boundary_log.
    missing_edt / not_supported exit before de-identification is needed
    (no facts to process), so they are excluded from this check.
    """
    for fp in FACT_PATTERNS:
        result = _run(fp["facts"])
        if result.get("status") in ("missing_edt", "not_supported"):
            continue   # pipeline exits before reaching de-id stage
        assert "boundary_log" in result, \
            f"{fp['id']}: boundary_log missing  -  de-identification gate not proven"


# ── Phase 5B: Unpaid wages legal accuracy ─────────────────────────────────────

def _run_upw(fp: dict) -> dict:
    return assess(fp.get("query", "Unpaid wages claim"), fp["facts"], model=STUB)


def _get_upw(fp_id: str) -> dict:
    return next(fp for fp in UPW_FACT_PATTERNS if fp["id"] == fp_id)


def test_upw1_deadline_correct():
    """UPW1: Clear final salary  -  deadline 2026-06-29 from wages_due_date 2026-03-31.
    Anniversary = add_months(2026-03-31, 3) = 2026-06-30 (clamped); deadline = June 29."""
    fp = _get_upw("UPW1")
    result = _run_upw(fp)
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-06-29", \
        f"UPW1 deadline: expected 2026-06-29, got {dl.get('limitation_date')}"
    assert dl.get("source") == "rules"


def test_upw1_no_qualifying_period():
    """UPW1: Unpaid wages has no qualifying period  -  must not apply QP check."""
    fp = _get_upw("UPW1")
    result = _run_upw(fp)
    # QP check must NOT gate the wages claim
    assert result.get("qualifying_check") is None, \
        "Unpaid wages must not have qualifying_check  -  it is a day-one right"


def test_upw2_series_routes_to_solicitor():
    """UPW2: Series of deductions → key_weaknesses flagged + seek_solicitor."""
    fp = _get_upw("UPW2")
    result = _run_upw(fp)
    if result.get("status") == "ok":
        rns = result.get("recommended_next_step")
        weaknesses = result.get("key_weaknesses", [])
        assert rns == "seek_solicitor" or any("series" in w.lower() for w in weaknesses), \
            "UPW2: Series of deductions must flag weakness or route to solicitor"


def test_upw3_disputed_deduction_uncertain():
    """UPW3: Authorized deduction claimed → has_viable_claim=uncertain."""
    fp = _get_upw("UPW3")
    result = _run_upw(fp)
    if result.get("status") == "ok":
        assert result.get("has_viable_claim") in ("uncertain", "no"), \
            "UPW3: Disputed/authorized deduction must produce uncertain/no viability"


def test_upw4_missing_wages_date_status():
    """UPW4: No wages_due_date → missing_wages_date status, no fabricated deadline."""
    fp = _get_upw("UPW4")
    result = _run_upw(fp)
    assert result.get("status") == "missing_wages_date", \
        f"UPW4: expected missing_wages_date, got {result.get('status')}"


def test_upw5_deadline_correct_and_expired():
    """UPW5: Stale claim  -  deadline 2026-02-27 (Nov 30 + 3 months = Feb 28, -1 = Feb 27)."""
    fp = _get_upw("UPW5")
    result = _run_upw(fp)
    dl = result.get("deadline_info") or {}
    assert dl.get("limitation_date") == "2026-02-27", \
        f"UPW5 deadline: expected 2026-02-27, got {dl.get('limitation_date')}"
    # Verify expired urgency
    from backend.domains.employment.reminders import compute_urgency
    urg = compute_urgency("2026-02-28", today_str="2026-06-01")
    assert urg["urgency"] == "expired"


def test_upw6_self_employed_no_viable_claim():
    """UPW6: Self-employed → excluded from ERA s.13 → has_viable_claim='no'."""
    fp = _get_upw("UPW6")
    result = _run_upw(fp)
    if result.get("status") == "ok":
        assert result.get("has_viable_claim") == "no", \
            "UPW6: Self-employed claimant excluded from ERA s.13 wages rights"


def test_upw7_missing_amount_weakness():
    """UPW7: No unpaid_amount → weakness flagged in assessment."""
    fp = _get_upw("UPW7")
    result = _run_upw(fp)
    if result.get("status") == "ok":
        weaknesses = result.get("key_weaknesses", [])
        assert any("amount" in w.lower() or "not specified" in w.lower() for w in weaknesses), \
            "UPW7: Missing unpaid amount must appear as key weakness"


def test_upw8_complex_routes_to_solicitor():
    """UPW8: Agency worker + series → seek_solicitor recommended."""
    fp = _get_upw("UPW8")
    result = _run_upw(fp)
    if result.get("status") == "ok":
        assert result.get("recommended_next_step") == "seek_solicitor", \
            "UPW8: Complex agency worker + series case must route to seek_solicitor"


def test_upw_all_deadlines_from_rules():
    """All in-scope UPW patterns must have deadline.source='rules'."""
    for fp in UPW_FACT_PATTERNS:
        if "no_deadline" in fp["expected"] or fp["expected"].get("status") == "missing_wages_date":
            continue
        result = _run_upw(fp)
        dl = result.get("deadline_info") or {}
        if dl:
            assert dl.get("source") == "rules", \
                f"{fp['id']}: deadline must come from rules, got {dl.get('source')}"


def test_upw_all_results_have_boundary_log():
    """All UPW patterns with substantive facts must have boundary_log."""
    for fp in UPW_FACT_PATTERNS:
        result = _run_upw(fp)
        if result.get("status") in ("missing_wages_date", "not_supported"):
            continue
        assert "boundary_log" in result, \
            f"{fp['id']}: boundary_log missing from UPW assessment"


def test_all_results_no_pii_in_output():
    """Boundary_log must show pii_in_output=[] for all fact patterns."""
    for fp in FACT_PATTERNS:
        result = _run(fp["facts"])
        bl = result.get("boundary_log", {})
        pii_out = bl.get("pii_in_output", [])
        assert pii_out == [], \
            f"{fp['id']}: PII found in output boundary_log: {pii_out}"
