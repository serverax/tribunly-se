"""
Deterministic deadline arithmetic for unfair dismissal claims.

GUARDRAIL: This module computes dates in Python from values retrieved from the
`rules` table. The LLM never sees raw date arithmetic and never generates or
recalls a deadline. The `source` field in the returned dict is always "rules".

All logic is derived from ERA 1996 s.111(2) and s.207B as verified in Phase 1.
The 03a_UNFAIR_DISMISSAL_SEED_SPEC.md has the worked examples used as tests.

Statutory mechanic (s.111(2)):
  "before the end of the period of N months beginning with the effective date
  of termination" → last valid day = same calendar date N months later, minus
  one day. Month-end clamped (e.g. 31 Jan + 3 months → 30 Apr → 29 Apr).

EC stop-clock (s.207B):
  Day A = date claimant first contacted ACAS
  Day B = date EC certificate received
  Pause = (Day B - Day A).days  [Day A+1 to Day B inclusive]
  Floor = one calendar month after Day B
  Final = max(base_limit + pause_days, floor)

WARNING on the 6-month time limit: the prospective row (is_prospective=True)
is NEVER returned by the rules query. This module uses whatever time_limit_months
is passed in. The caller is responsible for querying rules with is_prospective=false.
If the commencement SI is published and the prospective row is promoted, the
arithmetic here is identical — only the value changes, not the code.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional


def _add_months(d: date, months: int) -> date:
    """Add N calendar months to a date, clamping to month-end if needed."""
    total_month = d.month + months
    year = d.year + (total_month - 1) // 12
    month = (total_month - 1) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_limitation_date(
    edt: date,
    time_limit_months: int,
    ec_day_a: Optional[date] = None,
    ec_day_b: Optional[date] = None,
) -> dict:
    """
    Compute the ET claim limitation date.

    Returns a dict matching the `deadline` field of StructuredAssessment:
        {
            "limitation_date": "YYYY-MM-DD",
            "source": "rules",
            "authority": "ERA 1996 s.111(2)",
            "ec_applied": bool,
            "base_limit": "YYYY-MM-DD",
            "notes": str,
        }

    DOES NOT compute the 'not reasonably practicable' extension — that is a
    merits judgement routed to the honesty/uncertainty path, never asserted.
    """
    # Step 1 — base limit: N months "beginning with" EDT → last day = anniversary - 1
    anniversary = _add_months(edt, time_limit_months)
    base_limit = anniversary - timedelta(days=1)

    if ec_day_a is None or ec_day_b is None:
        return {
            "limitation_date": base_limit.isoformat(),
            "source": "rules",
            "authority": "ERA 1996 s.111(2)",
            "ec_applied": False,
            "base_limit": base_limit.isoformat(),
            "notes": (
                f"3-month-less-1-day rule: {time_limit_months} months from EDT {edt} "
                f"= anniversary {anniversary}, deadline {base_limit}."
            ),
        }

    # Step 2 — EC stop-clock (s.207B)
    # Pause = days from Day A+1 to Day B inclusive = Day B - Day A (in days)
    pause_days = (ec_day_b - ec_day_a).days
    adjusted = base_limit + timedelta(days=pause_days)

    # Step 3 — floor: one calendar month after Day B
    floor = _add_months(ec_day_b, 1)

    final = max(adjusted, floor)
    floor_applied = final == floor and floor > adjusted

    return {
        "limitation_date": final.isoformat(),
        "source": "rules",
        "authority": "ERA 1996 s.111(2) + s.207B",
        "ec_applied": True,
        "base_limit": base_limit.isoformat(),
        "pause_days": pause_days,
        "adjusted_limit": adjusted.isoformat(),
        "ec_floor": floor.isoformat(),
        "floor_applied": floor_applied,
        "notes": (
            f"Base {base_limit} + {pause_days} EC pause days = {adjusted}. "
            f"Floor (1 month after Day B {ec_day_b}) = {floor}. "
            f"Final = {final} ({'floor applied' if floor_applied else 'adjusted limit'})."
        ),
    }


def check_qualifying_period(
    service_start_date: date,
    edt: date,
    qualifying_period_value: float,
    qualifying_period_unit: str,
) -> dict:
    """
    Check whether the claimant meets the qualifying period for ordinary unfair dismissal.

    Returns {meets_qualifying_period: bool, service_months: float, required: str}
    Day-one exceptions (discrimination, whistleblowing, health & safety, TU) are
    separate rules not handled here — they have qualifying_period=0.
    """
    service_days = (edt - service_start_date).days
    service_months = service_days / 30.44  # approximate

    if qualifying_period_unit == "years":
        required_days = qualifying_period_value * 365.25
        required_str = f"{qualifying_period_value} year(s)"
    elif qualifying_period_unit == "months":
        required_days = qualifying_period_value * 30.44
        required_str = f"{qualifying_period_value} month(s)"
    else:
        required_days = 0
        required_str = "unknown"

    meets = service_days >= required_days

    return {
        "meets_qualifying_period": meets,
        "service_days": service_days,
        "service_months_approx": round(service_months, 1),
        "required": required_str,
        "required_days_approx": round(required_days),
    }
