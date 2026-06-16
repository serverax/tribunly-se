"""
Legal accuracy regression fixtures  -  Phase 5A.

Eight known fact patterns for unfair dismissal (England & Wales).
Tests use StubReasoningModel  -  deterministic layer only, no real model.

Each fixture specifies:
  - facts: intake facts
  - expected: minimum expected outcomes from the deterministic pipeline

GUARDRAIL: These fixtures contain no real personal data.
GUARDRAIL: All expected outcomes are derived from statute and rules, not guesswork.
"""

from __future__ import annotations

from datetime import date

# ── Fact Pattern Fixtures ─────────────────────────────────────────────────────

FACT_PATTERNS: list[dict] = [

    # FP1: Ordinary unfair dismissal  -  4 years service, conduct, no procedure
    {
        "id": "FP1",
        "description": "Ordinary UD  -  4yr service, conduct, no hearing or procedure",
        "facts": {
            "edt":                    "2026-04-01",
            "service_start_date":     "2022-04-01",
            "reason_for_dismissal":   "conduct",
            "was_procedure_followed": False,
            "weekly_pay":             600,
            "jurisdiction":           "EW",
        },
        "expected": {
            "claim_type":            "unfair_dismissal",
            "deadline_date":         "2026-06-30",
            "deadline_source":       "rules",
            "deadline_authority":    "ERA 1996 s.111(2)",
            "qp_passes":             True,          # 4yr > 2yr threshold
            "key_weaknesses_present": True,          # deterministic layer populates
            "has_viable_claim_not": [""],             # any of yes/no/uncertain is acceptable
        },
    },

    # FP2: Under qualifying period  -  14 months service
    {
        "id": "FP2",
        "description": "Under 2-year qualifying period  -  14 months service",
        "facts": {
            "edt":                  "2026-03-15",
            "service_start_date":   "2025-01-01",
            "reason_for_dismissal": "conduct",
            "weekly_pay":           450,
            "jurisdiction":         "EW",
        },
        "expected": {
            "claim_type":     "unfair_dismissal",
            "deadline_date":  "2026-06-14",
            "deadline_source": "rules",
            "qp_passes":       False,    # ~14 months < 2 years
            "has_viable_claim": "no",    # deterministic: QP fails → no viable ordinary UD
            "key_weaknesses_present": True,  # QP weakness in list
        },
    },

    # FP3: Auto-unfair candidate  -  day-one service, unprotected category
    # (Dismissed on first day  -  might be protected characteristic; system flags for review)
    {
        "id": "FP3",
        "description": "Day-one service  -  auto-unfair candidate needing legal review",
        "facts": {
            "edt":                  "2026-04-03",
            "service_start_date":   "2026-04-01",
            "reason_for_dismissal": "unknown",
            "weekly_pay":           400,
            "jurisdiction":         "EW",
        },
        "expected": {
            "claim_type":      "unfair_dismissal",
            "deadline_date":   "2026-07-02",
            "deadline_source":  "rules",
            "qp_passes":        False,
            "has_viable_claim": "no",     # 2 days < 2yr QP for ordinary UD
            # System should not assert a positive viability without proper review
        },
    },

    # FP4: EC applied  -  floor does NOT bite
    {
        "id": "FP4",
        "description": "EC applied  -  pause days extend deadline, floor does not bite",
        "facts": {
            "edt":                  "2026-01-01",
            "service_start_date":   "2022-01-01",
            "reason_for_dismissal": "conduct",
            "weekly_pay":           500,
            "jurisdiction":         "EW",
            "ec_day_a":             "2026-02-01",
            "ec_day_b":             "2026-02-15",   # 14-day pause
        },
        "expected": {
            # Base limit: 2026-03-31 + 14 pause = 2026-04-14
            # Floor: add_months(2026-02-15, 1) = 2026-03-15  ← does NOT bite
            "claim_type":      "unfair_dismissal",
            "deadline_date":   "2026-04-14",
            "deadline_source":  "rules",
            "ec_applied":       True,
            "floor_applied":    False,
            "qp_passes":        True,
        },
    },

    # FP5: EC applied  -  floor BITES
    {
        "id": "FP5",
        "description": "EC applied  -  1-month-after-Day-B floor bites",
        "facts": {
            "edt":                  "2026-01-01",
            "service_start_date":   "2022-01-01",
            "reason_for_dismissal": "conduct",
            "weekly_pay":           500,
            "jurisdiction":         "EW",
            "ec_day_a":             "2026-03-20",
            "ec_day_b":             "2026-03-25",   # 5-day pause
        },
        "expected": {
            # Base limit: 2026-03-31 + 5 = 2026-04-05
            # Floor: add_months(2026-03-25, 1) = 2026-04-25  ← BITES
            "claim_type":      "unfair_dismissal",
            "deadline_date":   "2026-04-25",
            "deadline_source":  "rules",
            "ec_applied":       True,
            "floor_applied":    True,
            "qp_passes":        True,
        },
    },

    # FP6: Missed deadline  -  deadline in the past
    {
        "id": "FP6",
        "description": "Missed deadline  -  EDT was 2025-01-01, deadline long past",
        "facts": {
            "edt":                  "2025-01-01",
            "service_start_date":   "2022-01-01",
            "reason_for_dismissal": "conduct",
            "weekly_pay":           600,
            "jurisdiction":         "EW",
        },
        "expected": {
            "claim_type":     "unfair_dismissal",
            "deadline_date":  "2025-03-31",
            "deadline_source": "rules",
            "deadline_expired_by_2026_06_01": True,   # checked via urgency
        },
    },

    # FP7: Insufficient facts  -  no EDT provided
    {
        "id": "FP7",
        "description": "Insufficient facts  -  no EDT provided",
        "facts": {
            "jurisdiction": "EW",
            "reason_for_dismissal": "conduct",
        },
        "expected": {
            "status": "missing_edt",    # pipeline must return missing_edt
            "no_deadline": True,         # cannot compute deadline without EDT
        },
    },

    # FP8: Seek-solicitor / beyond self-help
    {
        "id": "FP8",
        "description": "Complex case  -  constructive dismissal with 3yr service",
        "facts": {
            "edt":                  "2026-04-01",
            "service_start_date":   "2023-04-01",
            "reason_for_dismissal": "some_other_substantial_reason",
            "was_procedure_followed": True,
            "weekly_pay":           800,
            "jurisdiction":         "EW",
        },
        "expected": {
            "claim_type":     "unfair_dismissal",
            "deadline_date":  "2026-06-30",
            "deadline_source": "rules",
            "qp_passes":       True,
            # With SOSR + procedure followed, outcome is uncertain → honesty gate
            "has_viable_claim_options": ("yes", "no", "uncertain"),
        },
    },
]

# ── Unpaid wages fact patterns (Phase 5B) ─────────────────────────────────────

UPW_FACT_PATTERNS: list[dict] = [

    # UPW1: Clear unpaid final salary
    {
        "id": "UPW1",
        "description": "Clear unpaid final salary  -  last month not paid",
        "query": "My employer hasn't paid my wages  -  final salary of £2,500 is missing",
        "facts": {
            "wages_due_date": "2026-03-31",
            "unpaid_amount":  2500.0,
            "pay_frequency":  "monthly",
            "worker_status":  "employee",
            "jurisdiction":   "EW",
        },
        "expected": {
            "claim_type":    "unpaid_wages",
            # 3 months from 2026-03-31: anniversary=2026-06-30 (clamped), deadline=2026-06-29
            "deadline_date": "2026-06-29",
            "deadline_source": "rules",
            "no_qp":          True,     # no qualifying period for wages claims
        },
    },

    # UPW2: Repeated underpayments (series of deductions)
    {
        "id": "UPW2",
        "description": "Repeated underpayments  -  series of monthly deductions",
        "query": "My employer has been deducting £100 per month without authorisation for 6 months",
        "facts": {
            "wages_due_date":          "2026-03-31",
            "unpaid_amount":           600.0,
            "pay_frequency":           "monthly",
            "worker_status":           "employee",
            "is_series_of_deductions": True,
            "jurisdiction":            "EW",
        },
        "expected": {
            "claim_type":        "unpaid_wages",
            "deadline_date":     "2026-06-30",
            "deadline_source":   "rules",
            "weaknesses_present": True,   # series complexity flagged
            "recommended_seek_solicitor": True,
        },
    },

    # UPW3: Disputed deduction (employer claims authorized)
    {
        "id": "UPW3",
        "description": "Disputed deduction  -  employer claims it was authorised by contract",
        "query": "Employer deducted £500 claiming it was in my contract",
        "facts": {
            "wages_due_date":      "2026-03-31",
            "unpaid_amount":       500.0,
            "worker_status":       "employee",
            "deduction_authorized": True,
            "jurisdiction":        "EW",
        },
        "expected": {
            "claim_type":        "unpaid_wages",
            "deadline_date":     "2026-06-30",
            "deadline_source":   "rules",
            "has_viable_claim":  "uncertain",    # disputed authorization
            "weaknesses_present": True,
        },
    },

    # UPW4: Missing wages_due_date
    {
        "id": "UPW4",
        "description": "Insufficient facts  -  no wages_due_date provided",
        "query": "My employer hasn't paid my wages",
        "facts": {
            "unpaid_amount": 1000.0,
            "jurisdiction":  "EW",
        },
        "expected": {
            "status":      "missing_wages_date",    # cannot compute deadline
            "no_deadline": True,
        },
    },

    # UPW5: Old/stale claim near or beyond limitation
    {
        "id": "UPW5",
        "description": "Stale claim  -  wages_due_date more than 3 months ago",
        "query": "My employer didn't pay my wages 6 months ago",
        "facts": {
            "wages_due_date": "2025-11-30",   # >3 months before 2026-06-01
            "unpaid_amount":  1500.0,
            "worker_status":  "employee",
            "jurisdiction":   "EW",
        },
        "expected": {
            "claim_type":              "unpaid_wages",
            # 3 months from 2025-11-30: anniversary=2026-02-28 (clamped), deadline=2026-02-27
            "deadline_date":           "2026-02-27",
            "deadline_source":         "rules",
            "deadline_expired_by_today": True,
        },
    },

    # UPW6: Uncertain worker status (self-employed)
    {
        "id": "UPW6",
        "description": "Uncertain worker status  -  claims to be self-employed",
        "query": "I'm a contractor and my client hasn't paid me",
        "facts": {
            "wages_due_date": "2026-03-31",
            "unpaid_amount":  3000.0,
            "worker_status":  "self_employed",
            "jurisdiction":   "EW",
        },
        "expected": {
            "claim_type":       "unpaid_wages",
            "deadline_date":    "2026-06-30",
            "deadline_source":  "rules",
            "has_viable_claim": "no",           # self-employed excluded from ERA s.13
            "weaknesses_present": True,
        },
    },

    # UPW7: Insufficient facts (no amount)
    {
        "id": "UPW7",
        "description": "Insufficient facts  -  no unpaid amount specified",
        "query": "Employer hasn't paid me correctly",
        "facts": {
            "wages_due_date": "2026-03-31",
            "worker_status":  "employee",
            "jurisdiction":   "EW",
        },
        "expected": {
            "claim_type":       "unpaid_wages",
            "deadline_date":    "2026-06-30",
            "deadline_source":  "rules",
            "weaknesses_present": True,   # "unpaid amount not specified" weakness
        },
    },

    # UPW8: Complex case  -  agency worker with unclear status
    {
        "id": "UPW8",
        "description": "Complex case  -  agency worker, series of deductions, status unclear",
        "query": "I work through an agency and they've been underpaying me for months",
        "facts": {
            "wages_due_date":          "2026-03-31",
            "unpaid_amount":           800.0,
            "worker_status":           "worker",
            "is_series_of_deductions": True,
            "jurisdiction":            "EW",
        },
        "expected": {
            "claim_type":       "unpaid_wages",
            "deadline_date":    "2026-06-30",
            "deadline_source":  "rules",
            "recommended_seek_solicitor": True,   # series + worker complexity
        },
    },
]

# Combined for cross-type tests
ALL_FACT_PATTERNS = FACT_PATTERNS + UPW_FACT_PATTERNS
