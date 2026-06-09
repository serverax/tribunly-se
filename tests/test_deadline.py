"""
Tests for deterministic deadline arithmetic.

These are the 6 fact-patterns from 03a_UNFAIR_DISMISSAL_SEED_SPEC.md §5.
No DB, no model, no network. Pure Python.

Every test records the expected outcome as a comment so it serves as the
regression set entry — future changes that silently alter deadline output
will break these tests.
"""

from datetime import date
from backend.domains.employment.deadline import compute_limitation_date, _add_months


# ── _add_months edge cases ────────────────────────────────────────────────────

def test_add_months_standard():
    assert _add_months(date(2026, 5, 10), 3) == date(2026, 8, 10)

def test_add_months_month_end_clamped():
    # January 31 + 3 months: April has 30 days, clamp to 30
    assert _add_months(date(2026, 1, 31), 3) == date(2026, 4, 30)

def test_add_months_year_rollover():
    assert _add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


# ── Pattern 1: Straightforward EDT, no EC ────────────────────────────────────
# EDT = 10 May 2026, no EC
# 3 months from May 10 → Aug 10 anniversary → deadline Aug 9
def test_no_ec_standard():
    result = compute_limitation_date(date(2026, 5, 10), 3)
    assert result["limitation_date"] == "2026-08-09"
    assert result["source"] == "rules"
    assert result["ec_applied"] is False

def test_no_ec_boundary_last_valid_day():
    # Boundary: claim on Aug 9 is in time; Aug 10 is out of time
    edt = date(2026, 5, 10)
    result = compute_limitation_date(edt, 3)
    last_day = date.fromisoformat(result["limitation_date"])
    anniversary = _add_months(edt, 3)
    # last_day must be exactly one day before the anniversary
    assert (anniversary - last_day).days == 1


# ── Pattern 2: EC used, floor does not bite ───────────────────────────────────
# EDT = 10 May 2026 → base limit 9 Aug 2026
# Day A = 1 Jun, Day B = 20 Jun
# Pause = Day B - Day A = 19 days
# Adjusted = 9 Aug + 19 = 28 Aug
# Floor = 1 month after Day B = 20 Jul
# Final = 28 Aug (floor doesn't bite: 28 Aug > 20 Jul)
def test_ec_floor_does_not_bite():
    result = compute_limitation_date(
        date(2026, 5, 10), 3,
        ec_day_a=date(2026, 6, 1),
        ec_day_b=date(2026, 6, 20),
    )
    assert result["limitation_date"] == "2026-08-28"
    assert result["ec_applied"] is True
    assert result["pause_days"] == 19
    assert result["floor_applied"] is False


# ── Pattern 3: EC used, floor bites ──────────────────────────────────────────
# EDT = 10 May 2026 → base limit 9 Aug 2026
# Day A = 5 Aug, Day B = 25 Aug  (EC started very late)
# Pause = Day B - Day A = 20 days
# Adjusted = 9 Aug + 20 = 29 Aug
# Floor = 1 month after Day B = 25 Sep
# Final = 25 Sep (floor bites: 25 Sep > 29 Aug)
def test_ec_floor_bites():
    result = compute_limitation_date(
        date(2026, 5, 10), 3,
        ec_day_a=date(2026, 8, 5),
        ec_day_b=date(2026, 8, 25),
    )
    assert result["limitation_date"] == "2026-09-25"
    assert result["floor_applied"] is True
    assert result["pause_days"] == 20


# ── Pattern 4: Older cap figure applies (EDT before 6 Apr 2026) ──────────────
# This tests the rules table query, not the deadline arithmetic.
# Proves effective-dating works — tested in test_retrieve_rules.py (integration).
# Placeholder here so the pattern is documented in the unit test set.
def test_pattern_4_documented():
    """
    EDT 2025-06-01 → compensatory cap £118,223 (SI 2025/348, effective 2025-04-06).
    EDT 2026-05-01 → compensatory cap £123,543 (SI 2026/310, effective 2026-04-06).
    Verified in tests/integration/test_retrieve_rules.py against live DB.
    """
    # The deadline arithmetic itself is unaffected by which cap applies.
    result = compute_limitation_date(date(2025, 6, 1), 3)
    assert result["limitation_date"] == "2025-08-31"
    assert result["source"] == "rules"


# ── Pattern 5: Prospective 6-month time limit (not yet commenced) ─────────────
# The 6-month row has is_prospective=True and is NEVER returned by the rules query.
# When it is eventually commenced, the arithmetic is unchanged — only the value changes.
# Proved in test_retrieve_rules.py (integration) — is_prospective=False gate.
# Here we test the arithmetic with time_limit=6 to confirm the code handles it:
def test_arithmetic_with_6_month_limit():
    # EDT 1 Jan 2027, 6-month limit (prospective — not in DB yet)
    # 6 months from Jan 1 → Jul 1 → deadline Jun 30
    result = compute_limitation_date(date(2027, 1, 1), 6)
    assert result["limitation_date"] == "2027-06-30"
    assert result["source"] == "rules"


# ── Pattern 6: Qualifying period check ───────────────────────────────────────
from backend.domains.employment.deadline import check_qualifying_period

def test_qualifying_period_not_met():
    # 18 months service, 2-year required → no ordinary UD claim
    qp = check_qualifying_period(
        service_start_date=date(2025, 1, 1),
        edt=date(2026, 7, 1),   # ~18 months
        qualifying_period_value=2,
        qualifying_period_unit="years",
    )
    assert qp["meets_qualifying_period"] is False
    assert qp["service_days"] < 730  # 2 years

def test_qualifying_period_met():
    # 3 years service, 2-year required → qualifies
    qp = check_qualifying_period(
        service_start_date=date(2023, 1, 1),
        edt=date(2026, 5, 1),   # ~3.3 years
        qualifying_period_value=2,
        qualifying_period_unit="years",
    )
    assert qp["meets_qualifying_period"] is True

def test_qualifying_period_transition():
    # Same person (18 months service), EDT changes from 2026 to 2027
    # In 2026: 2-year rule → no claim
    # In 2027 (if ERA 2025 s.25 commences): 6-month rule → qualifies
    # This test proves the arithmetic is correct for both regimes.
    service_start = date(2025, 7, 1)

    qp_2026 = check_qualifying_period(service_start, date(2026, 12, 31), 2, "years")
    assert qp_2026["meets_qualifying_period"] is False  # ~17 months < 2 years

    qp_2027 = check_qualifying_period(service_start, date(2027, 1, 31), 6, "months")
    assert qp_2027["meets_qualifying_period"] is True   # ~18 months > 6 months
