"""
Integration tests for the structured rules retrieval leg.

REQUIRES: running DB with seeded rules (docker compose up -d db, then seed).
Run inside the ingestion container:
  docker compose run --rm ingestion pytest tests/integration/test_retrieve_rules.py -v

These tests prove:
1. is_prospective=false gate works  -  prospective rows are NEVER returned
2. Effective-dating works  -  correct row returned based on EDT date
3. Current-in-force values are correct (verified against SI 2026/310 in Phase 1)
4. The compensatory cap at two EDT dates (proving the £118,223 / £123,543 split)
"""

from datetime import date
import pytest

from backend.core.retrieve import retrieve_rules


# ── Guardrail: is_prospective=false gate ──────────────────────────────────────

def test_prospective_rows_never_returned():
    """
    The 6-month time limit, 6-month qualifying period, and uncapped compensatory
    award are all is_prospective=True rows. They must NEVER be returned, regardless
    of what date is passed.
    """
    # Use a future EDT that would be in the prospective window
    future_edt = date(2027, 6, 1)
    rules = retrieve_rules("unfair_dismissal", "EW", future_edt)
    rule_map = {r["rule_key"]: r for r in rules}

    # is_prospective filter confirmed: all returned rows must be False
    for rule in rules:
        assert rule["is_prospective"] is False, \
            f"Prospective row leaked through: {rule['rule_key']} effective_from={rule['effective_from']}"


def test_time_limit_is_3_months_not_6():
    """
    The 6-month time limit (ERA 2025 s.152) is not yet commenced.
    is_prospective=True row must not be returned. Current value must be 3.
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    assert "unfair_dismissal.time_limit_months" in rule_map
    tl = rule_map["unfair_dismissal.time_limit_months"]
    assert int(tl["value_numeric"]) == 3, \
        f"Got {tl['value_numeric']}  -  prospective 6-month row must not be returned"
    assert tl["is_prospective"] is False


def test_qualifying_period_is_2_years_not_6_months():
    """
    The 6-month qualifying period (ERA 2025 s.25) is not yet commenced.
    Current value must be 2 years.
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    assert "unfair_dismissal.qualifying_period" in rule_map
    qp = rule_map["unfair_dismissal.qualifying_period"]
    assert float(qp["value_numeric"]) == 2.0
    assert qp["unit"] == "years"
    assert qp["is_prospective"] is False


def test_compensatory_cap_is_not_uncapped():
    """
    The 'uncapped' compensatory award (ERA 2025 s.25) is prospective.
    Current rules must return a £ figure, not 'uncapped'.
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    assert "unfair_dismissal.compensatory_cap_amount" in rule_map
    cap = rule_map["unfair_dismissal.compensatory_cap_amount"]
    assert cap["value_text"] != "uncapped", \
        "Prospective uncapped cap row must not be returned while is_prospective=True"
    assert cap["value_numeric"] is not None


# ── Effective-dating: correct cap for EDT date ────────────────────────────────

def test_cap_for_edt_before_6_apr_2026():
    """
    EDT 2025-06-01 → cap £118,223 (SI 2025/348, effective 2025-04-06 to 2026-04-05).
    Proves effective-dating selects the row in force at the EDT date.
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    cap = rule_map.get("unfair_dismissal.compensatory_cap_amount")
    assert cap is not None, "No compensatory cap rule returned for 2025-06-01"
    assert int(cap["value_numeric"]) == 118223, \
        f"Expected £118,223 for EDT 2025-06-01, got {cap['value_numeric']}"
    assert "SI 2025/348" in cap["authority_ref"]


def test_cap_for_edt_on_or_after_6_apr_2026():
    """
    EDT 2026-05-01 → cap £123,543 (SI 2026/310, effective 2026-04-06).
    Verified against live SI schedule in Phase 1.
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    cap = rule_map.get("unfair_dismissal.compensatory_cap_amount")
    assert cap is not None, "No compensatory cap rule returned for 2026-05-01"
    assert int(cap["value_numeric"]) == 123543, \
        f"Expected £123,543 for EDT 2026-05-01, got {cap['value_numeric']}"
    assert "SI 2026/310" in cap["authority_ref"]


def test_weeks_pay_cap_for_2026():
    """
    EDT 2026-05-01 → week's pay cap £751 (SI 2026/310, effective 2026-04-06).
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    wpc = rule_map.get("unfair_dismissal.weeks_pay_cap_amount")
    assert wpc is not None
    assert int(wpc["value_numeric"]) == 751
    assert wpc["unit"] == "GBP"


def test_weeks_pay_cap_for_2025():
    """
    EDT 2025-06-01 → week's pay cap £719 (SI 2025/348).
    """
    rules = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    wpc = rule_map.get("unfair_dismissal.weeks_pay_cap_amount")
    assert wpc is not None
    assert int(wpc["value_numeric"]) == 719


# ── Citations present on every returned rule ──────────────────────────────────

def test_all_rules_have_citations():
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    for rule in rules:
        assert rule.get("authority_ref"), \
            f"Rule {rule['rule_key']} missing authority_ref"
        assert rule.get("authority_url"), \
            f"Rule {rule['rule_key']} missing authority_url"


# ── EC requirement is returned ────────────────────────────────────────────────

def test_ec_requirement_returned():
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    rule_map = {r["rule_key"]: r for r in rules}

    ec = rule_map.get("unfair_dismissal.early_conciliation_required")
    assert ec is not None
    assert ec["value_text"] == "true"
    assert "ETA" in ec["authority_ref"] or "Employment Tribunals" in ec["authority_ref"]
