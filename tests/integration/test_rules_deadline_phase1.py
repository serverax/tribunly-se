"""
Phase 1 proof  -  rules table effective-dating and deadline arithmetic.

Tests:
1. Rules resolve correctly for current EDT (post-2026-04-06)
2. Rules resolve correctly for older EDT (pre-2026-04-06) - different cap
3. Prospective rows are never returned by the live query
4. Deadline: no EC
5. Deadline: EC stop-the-clock, floor does NOT bite
6. Deadline: EC stop-the-clock, floor BITES

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_rules_deadline_phase1.py -v -s
"""

from datetime import date, timedelta
import pytest

from backend.core.retrieve import retrieve_rules
from backend.domains.employment.deadline import (
    compute_limitation_date,
    check_qualifying_period,
)


# ── Rules table: effective-dating ────────────────────────────────────────────

def test_current_edt_returns_2026_cap():
    """EDT 2026-05-01 -> compensatory cap must be £123,543 (SI 2026/310)."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    caps = {r["rule_key"]: r for r in rules
            if r["rule_key"] == "unfair_dismissal.compensatory_cap_amount"}
    assert caps, "No compensatory_cap_amount row returned"
    cap = caps["unfair_dismissal.compensatory_cap_amount"]
    assert int(cap["value_numeric"]) == 123543, \
        f"Expected £123,543 for EDT 2026-05-01, got {cap['value_numeric']}"
    assert cap["is_prospective"] is False


def test_older_edt_returns_prior_cap():
    """EDT 2025-06-01 -> compensatory cap must be £118,223 (SI 2025/348)."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
    caps = {r["rule_key"]: r for r in rules
            if r["rule_key"] == "unfair_dismissal.compensatory_cap_amount"}
    assert caps, "No compensatory_cap_amount row for 2025-06-01"
    cap = caps["unfair_dismissal.compensatory_cap_amount"]
    assert int(cap["value_numeric"]) == 118223, \
        f"Expected £118,223 for EDT 2025-06-01, got {cap['value_numeric']}"


def test_current_edt_weeks_pay_751():
    """EDT 2026-05-01 -> week's pay cap £751."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    row = next((r for r in rules if r["rule_key"] == "unfair_dismissal.weeks_pay_cap_amount"), None)
    assert row is not None
    assert int(row["value_numeric"]) == 751


def test_older_edt_weeks_pay_719():
    """EDT 2025-06-01 -> week's pay cap £719."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2025, 6, 1))
    row = next((r for r in rules if r["rule_key"] == "unfair_dismissal.weeks_pay_cap_amount"), None)
    assert row is not None
    assert int(row["value_numeric"]) == 719


def test_prospective_rows_never_returned():
    """Prospective (ERA 2025) rows must never appear in the live rules query."""
    for edt in [date(2026, 5, 1), date(2027, 6, 1), date(2030, 1, 1)]:
        rules = retrieve_rules("unfair_dismissal", "EW", edt)
        for row in rules:
            assert row["is_prospective"] is False, \
                f"Prospective row leaked: {row['rule_key']} edt={edt}"


def test_time_limit_is_3_months():
    """time_limit_months must be 3 for any current EDT."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    tl = next((r for r in rules if r["rule_key"] == "unfair_dismissal.time_limit_months"), None)
    assert tl is not None
    assert int(tl["value_numeric"]) == 3


def test_qualifying_period_is_2_years():
    """Qualifying period must be 2 years for current EDTs."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    qp = next((r for r in rules if r["rule_key"] == "unfair_dismissal.qualifying_period"), None)
    assert qp is not None
    assert int(qp["value_numeric"]) == 2


def test_ec_required_returned():
    """early_conciliation_required must be 'true' for current EDTs."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    ec = next((r for r in rules if r["rule_key"] == "unfair_dismissal.early_conciliation_required"), None)
    assert ec is not None
    assert ec["value_text"] == "true"  # canonical series stores "true", not "required"


def test_all_rules_have_citations():
    """Every returned rule must have authority_ref and authority_url."""
    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    assert len(rules) >= 5, f"Expected at least 5 rules, got {len(rules)}"
    for r in rules:
        assert r.get("authority_ref"), f"Missing authority_ref: {r['rule_key']}"
        assert r.get("authority_url"), f"Missing authority_url: {r['rule_key']}"


# ── Deadline arithmetic ───────────────────────────────────────────────────────

def test_deadline_no_ec():
    """Test 1: No EC. EDT 2026-03-14 -> deadline 2026-06-13."""
    result = compute_limitation_date(date(2026, 3, 14), 3)
    assert result["limitation_date"] == "2026-06-13", \
        f"Expected 2026-06-13, got {result['limitation_date']}"
    assert result["source"] == "rules"
    assert result["ec_applied"] is False


def test_deadline_ec_floor_does_not_bite():
    """
    Test 2: EC used; floor does NOT bite.
    EDT 2026-03-14, Day A 2026-04-01, Day B 2026-04-20.
    conciliation_days = 19. extended = 2026-07-02.
    one_month_after_B = 2026-05-20. 2 Jul > 20 May -> floor doesn't bite.
    Final = 2026-07-02.
    """
    result = compute_limitation_date(
        date(2026, 3, 14), 3,
        ec_day_a=date(2026, 4, 1),
        ec_day_b=date(2026, 4, 20),
    )
    assert result["limitation_date"] == "2026-07-02", \
        f"Expected 2026-07-02, got {result['limitation_date']}"
    assert result["ec_applied"] is True
    assert result["floor_applied"] is False


def test_deadline_ec_floor_bites():
    """
    Test 3: EC used; floor BITES.
    EDT 2026-01-10, base = 2026-04-09.
    Day A 2026-04-05, Day B 2026-04-25.
    conciliation_days = 20. extended = 2026-04-29.
    one_month_after_B = 2026-05-25. 29 Apr < 25 May -> floor bites.
    Final = 2026-05-25.
    """
    result = compute_limitation_date(
        date(2026, 1, 10), 3,
        ec_day_a=date(2026, 4, 5),
        ec_day_b=date(2026, 4, 25),
    )
    assert result["limitation_date"] == "2026-05-25", \
        f"Expected 2026-05-25, got {result['limitation_date']}"
    assert result["floor_applied"] is True


def test_deadline_haque_worked_example():
    """
    Test 4: Haque facts (para 17 authority check).
    EDT 20 Jun 2016, Day A 22 Jul, Day B 22 Aug.
    base = 19 Sep 2016. conciliation_days = 31. extended = 20 Oct.
    one_month_after_B = 22 Sep. 20 Oct > 22 Sep -> floor doesn't bite.
    Final = 20 Oct 2016. Claim on 18 Oct -> IN TIME.
    """
    result = compute_limitation_date(
        date(2016, 6, 20), 3,
        ec_day_a=date(2016, 7, 22),
        ec_day_b=date(2016, 8, 22),
    )
    assert result["limitation_date"] == "2016-10-20", \
        f"Expected 2016-10-20 (Haque facts), got {result['limitation_date']}"
    assert result["floor_applied"] is False
    # Claimant presented 18 Oct 2016  -  confirm this is before the deadline
    assert date.fromisoformat(result["limitation_date"]) >= date(2016, 10, 18)


def test_deadline_para26_no_op_ec_floor_fires():
    """
    Para 26 regression: (3) is a no-op (Day A = Day B), (4) still fires.
    EDT 2026-03-14 -> base 2026-06-13.
    Day A = Day B = 2026-06-13. conciliation_days = 0. date_under_3 = 2026-06-13.
    one_month_after_B = 2026-07-13.
    date_under_3 (13 Jun) in [13 Jun, 13 Jul] -> (4) triggered.
    Final = max(13 Jun, 13 Jul) = 2026-07-13.
    Claimant contacts ACAS and receives certificate on the very last day of the
    primary limit. (3) extends nothing. (4) still grants one month. Haque para 26.
    """
    result = compute_limitation_date(
        date(2026, 3, 14), 3,
        ec_day_a=date(2026, 6, 13),
        ec_day_b=date(2026, 6, 13),   # same day as Day A: conciliation_days = 0
    )
    assert result["limitation_date"] == "2026-07-13", \
        f"Para 26 no-op (3) case: expected 2026-07-13, got {result['limitation_date']}"
    assert result["floor_applied"] is True, "Para 26: (4) must fire even when (3) is a no-op"


def test_month_end_clamping():
    """Test 5: Month-end EDT clamping. EDT 31 Jan, +3 months -> 30 Apr -> deadline 29 Apr."""
    result = compute_limitation_date(date(2026, 1, 31), 3)
    assert result["limitation_date"] == "2026-04-29", \
        f"Expected 2026-04-29 (month-end clamp), got {result['limitation_date']}"


def test_qualifying_period_not_met_18_months():
    """Test 6: 18 months service in 2026 -> does NOT meet 2-year qualifying period."""
    qp = check_qualifying_period(date(2025, 1, 1), date(2026, 7, 1), 2, "years")
    assert qp["meets_qualifying_period"] is False
    assert qp["service_days"] < 730


def test_qualifying_period_met_3_years():
    """Test 7: 3 years service -> MEETS 2-year qualifying period."""
    qp = check_qualifying_period(date(2023, 1, 1), date(2026, 5, 1), 2, "years")
    assert qp["meets_qualifying_period"] is True
