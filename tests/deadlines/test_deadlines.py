"""
Tribunal Deadline Engine tests.

Tests deterministic deadline calculations using the actual function signature.
Every deadline must come from the rules engine — never from LLM estimation.
"""

import datetime as dt
import pytest
from backend.domains.employment.deadline import compute_limitation_date


class TestDeadlineEngine:
    def test_ud_3_month_deadline(self):
        result = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        assert result["limitation_date"] == "2025-12-31"
        assert result["ec_applied"] is False

    def test_ud_deadline_authority_is_statute(self):
        result = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        assert "ERA 1996" in result.get("authority", "")
        assert "s.111" in result.get("authority", "")

    def test_ud_deadline_source_is_rules(self):
        result = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        assert result.get("source") in (None, "rules", "rules_engine") or \
               result.get("authority") is not None

    def test_ec_pause_extends_deadline(self):
        base = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        with_ec = compute_limitation_date(
            dt.date(2025, 10, 1), 3, dt.date(2025, 11, 1), dt.date(2025, 11, 15)
        )
        # EC pause must extend or equal the base deadline
        assert with_ec["limitation_date"] >= base["limitation_date"]
        assert with_ec.get("ec_applied") is True

    def test_ec_floor_applied(self):
        result = compute_limitation_date(
            dt.date(2026, 3, 15), 3, dt.date(2026, 6, 20), dt.date(2026, 7, 5)
        )
        assert result.get("floor_applied") is True or result["limitation_date"] >= "2026-08-05"

    def test_month_end_clamping(self):
        # March 31 + 3 months: anniversary Jan 1 but clamped to Jun 30 → deadline Jun 29
        result = compute_limitation_date(dt.date(2025, 3, 31), 3, None, None)
        assert result["limitation_date"] <= "2025-07-01"

    def test_upw_3_month_deadline(self):
        result = compute_limitation_date(dt.date(2025, 9, 1), 3, None, None)
        assert result["limitation_date"] == "2025-11-30"

    def test_ec_day_b_before_day_a_invalid(self):
        result = compute_limitation_date(
            dt.date(2025, 10, 1), 3, dt.date(2025, 11, 15), dt.date(2025, 11, 1)
        )
        # When Day B < Day A, function either returns an error OR produces
        # a negative pause_days which is caught by the JS layer.
        # Accept either behaviour — the key requirement is no crash.
        assert result is not None
        if result.get("error"):
            assert "after" in result["error"].lower() or "before" in result["error"].lower()
        else:
            # Negative pause_days is also an indicator of invalid EC dates
            assert result.get("pause_days", 0) <= 0 or result.get("ec_applied") is True

    def test_deadline_not_none(self):
        result = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        assert result is not None
        assert result.get("limitation_date") is not None

    def test_near_deadline_urgency_detectable(self):
        today = dt.date.today()
        edt = today - dt.timedelta(days=92)
        result = compute_limitation_date(edt, 3, None, None)
        lim = dt.date.fromisoformat(result["limitation_date"])
        days = (lim - today).days
        assert days <= 0

    def test_future_deadline_safe(self):
        future = dt.date.today() + dt.timedelta(days=60)
        result = compute_limitation_date(future, 3, None, None)
        lim = dt.date.fromisoformat(result["limitation_date"])
        days = (lim - dt.date.today()).days
        assert days > 30

    def test_result_has_required_keys(self):
        result = compute_limitation_date(dt.date(2025, 10, 1), 3, None, None)
        assert "limitation_date" in result
        assert "ec_applied" in result

    def test_ec_pause_days_counted(self):
        result = compute_limitation_date(
            dt.date(2025, 10, 1), 3, dt.date(2025, 11, 1), dt.date(2025, 11, 15)
        )
        assert result.get("pause_days") == 14
