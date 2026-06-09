"""
Phase 1 — Unfair Dismissal rules seed (verified 2026-05-31).

CANONICAL RULE KEYS — the single authoritative series.
Every key here must match what the Phase 2 retrieval code looks up.
Do not introduce new keys without updating the retrieval code and the
no-duplicate guard test (test_no_duplicate_rule_key_series).

Canonical keys:
    unfair_dismissal.time_limit_months
    unfair_dismissal.early_conciliation_required
    unfair_dismissal.qualifying_period
    unfair_dismissal.weeks_pay_cap_amount
    unfair_dismissal.compensatory_cap_amount
    unfair_dismissal.compensatory_cap_weeks_pay
    unfair_dismissal.basic_award_formula
    unfair_dismissal.basic_award_min_automatic
    unfair_dismissal.ec_max_duration_weeks

All values confirmed from live legislation.gov.uk API fetches 2026-05-31.
All effective_from dates confirmed from primary sources.
Haque UKEAT/0180/17/JOJ para 17 and para 26 as s.207B authority.

Run:
    docker compose run --rm ingestion python -m ingestion.rules.seed_unfair_dismissal

Guardrail 3: these values enter the rules table from cited primary sources only.
No value is from model memory.
"""

from __future__ import annotations
import logging
from datetime import date
from ingestion.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# The single canonical set of rule_key strings for unfair_dismissal.
# If a key is not in this set, it has no business in the rules table.
# The no-duplicate guard test asserts every DB row's rule_key is in here.
CANONICAL_KEYS = frozenset({
    "unfair_dismissal.time_limit_months",
    "unfair_dismissal.early_conciliation_required",
    "unfair_dismissal.qualifying_period",
    "unfair_dismissal.weeks_pay_cap_amount",
    "unfair_dismissal.compensatory_cap_amount",
    "unfair_dismissal.compensatory_cap_weeks_pay",
    "unfair_dismissal.basic_award_formula",
    "unfair_dismissal.basic_award_min_automatic",
    "unfair_dismissal.ec_max_duration_weeks",
    # added intentionally (migration 033): ACAS Code uplift (TULRCA s.207A) and the
    # not-reasonably-practicable extension (ERA 1996 s.111(2)(b)).
    "unfair_dismissal.acas_code_adjustment_percent",
    "unfair_dismissal.not_reasonably_practicable_extension",
})


ROWS = [

    # ── 1a. Limitation period (current: 3 months) ────────────────────────────
    # s.111(2) ERA 1996: "before the end of the period of three months
    # beginning with the effective date of termination."
    # Text confirmed 2026-05-31.
    # ERA 1996: Royal Assent 22 May 1996; commencement 22 August 1996 (s.243).
    # s.207B (EC stop-the-clock) inserted by ERRA 2013; in force 6 April 2014.
    # Pre-2014-04-06 EDTs: 3-month limit applies but s.207B does NOT apply.
    # Sequential (3)/(4) method: Luton BC v Haque para 17 and para 26.
    {
        "rule_key":       "unfair_dismissal.time_limit_months",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  3,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "Primary limitation period: claim presented before the end of 3 months "
            "beginning with the EDT (ERA 1996 s.111(2); in force 1996-08-22). "
            "EC stop-the-clock (s.207B) in force 2014-04-06: (3) always runs first "
            "(may be no-op if Day A=Day B); (4) tested against the (3) result per "
            "Haque para 17 and para 26. "
            "WASM must not apply s.207B to EDTs before 2014-04-06. "
            "Not-reasonably-practicable extension is a merits question; never computed."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "ERA 1996 s.111(2) (commencement 1996-08-22); "
            "ERA 1996 s.207B (in force 2014-04-06, inserted by ERRA 2013); "
            "Luton Borough Council v Haque UKEAT/0180/17/JOJ "
            "[2018] UKEAT 0180_17_1204 para 17 (ratio) and para 26 (no-op (3) case)"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/111",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 1b. Limitation period (prospective: 6 months, ERA 2025 s.152) ─────────
    # ERA 2025 s.152 + Schedule 12 para 4(25): extends to 6 months.
    # Confirmed from ERA 2025 s.152 enacted text 2026-05-31.
    # NOT YET IN FORCE. effective_from = 2026-10-01 PROVISIONAL.
    # When commencement SI is published, only this row changes; no code change.
    {
        "rule_key":       "unfair_dismissal.time_limit_months",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  6,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "PROSPECTIVE — NOT IN FORCE. ERA 2025 s.152 + Schedule 12 para 4(25) "
            "extends the time limit to 6 months. Confirmed from ERA 2025 enacted text "
            "2026-05-31. No commencement SI published as of that date. "
            "effective_from 2026-10-01 PROVISIONAL ('no earlier than Oct 2026'). "
            "DO NOT use until is_prospective=false and effective_from confirmed from SI."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "Employment Rights Act 2025 s.152 and Schedule 12 para 4(25) "
            "(amending ERA 1996 s.111(2)); commencement SI pending — "
            "effective_from is PROVISIONAL from government statements"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/2025/36/section/152",
        "effective_from": date(2026, 10, 1),
        "effective_to":   None,
        "is_prospective": True,
    },

    # ── 2. EC mandatory requirement ─────────────────────────────────────────
    # ETA 1996 s.18A inserted by ERRA 2013 s.7.
    # s.18A in force 2014-04-06 (confirmed Haque para 30).
    # Mandatory pre-claim requirement from 2014-05-06 (SI 2014/253 transitional).
    {
        "rule_key":       "unfair_dismissal.early_conciliation_required",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "true",
        "unit":           None,
        "description":    (
            "Prospective claimant must notify ACAS and obtain an EC certificate "
            "before presenting a claim (ETA 1996 s.18A). "
            "s.18A in force 2014-04-06 (confirmed Haque para 30; inserted by ERRA 2013 s.7). "
            "Mandatory pre-claim requirement (claim inadmissible without certificate) "
            "applies to claims presented on or after 2014-05-06 (SI 2014/253 transitional). "
            "Claimants using EC in the voluntary window 2014-04-06 to 2014-05-05 "
            "still benefit from s.207B stop-the-clock extension."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "Employment Tribunals Act 1996 s.18A (in force 2014-04-06 per Haque para 30; "
            "inserted by ERRA 2013 s.7); SI 2014/253 (mandatory requirement from 2014-05-06)"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/17/section/18A",
        "effective_from": date(2014, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 3a. Qualifying period (current: 2 years from 6 April 2012) ──────────
    # s.108(1) ERA 1996: "not less than two years ending with the EDT."
    # 2-year period introduced by SI 2012/989 in force 6 April 2012.
    {
        "rule_key":       "unfair_dismissal.qualifying_period",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  2,
        "value_text":     None,
        "unit":           "years",
        "description":    (
            "Continuous employment of not less than 2 years ending with the EDT "
            "(ERA 1996 s.108(1)). Introduced by SI 2012/989, in force 6 April 2012. "
            "Day-one exceptions (whistleblowing, trade union, health & safety) carry "
            "no qualifying period and are Phase 5 scope."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "ERA 1996 s.108(1); SI 2012/989 "
            "(Unfair Dismissal and Statement of Reasons for Dismissal "
            "(Variation of Qualifying Period) Order 2012)"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/108",
        "effective_from": date(2012, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 3b. Qualifying period (prospective: 6 months, ERA 2025 s.25) ────────
    # ERA 2025 s.25(2): "for 'two years' substitute 'six months'."
    # Verified from ERA 2025 enacted text 2026-05-31.
    # NOT YET IN FORCE. effective_from = 2027-01-01 PROVISIONAL.
    {
        "rule_key":       "unfair_dismissal.qualifying_period",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  6,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "PROSPECTIVE — NOT IN FORCE. ERA 2025 s.25(2) substitutes 'six months' "
            "for 'two years' in ERA 1996 s.108(1) and (2). Verified from ERA 2025 "
            "enacted text 2026-05-31. No commencement SI as of that date. "
            "effective_from 2027-01-01 PROVISIONAL. DO NOT use until is_prospective=false."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "Employment Rights Act 2025 s.25(2) (amending ERA 1996 s.108(1) and (2)); "
            "commencement SI pending — effective_from is PROVISIONAL"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/2025/36/section/25",
        "effective_from": date(2027, 1, 1),
        "effective_to":   None,
        "is_prospective": True,
    },

    # ── 4a. Week's pay cap — prior year (£719, to 5 April 2026) ────────────
    {
        "rule_key":       "unfair_dismissal.weeks_pay_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  719,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Maximum week's pay for basic award (ERA 1996 s.227(1)), SI 2025/348. "
            "Applies where EDT is on or after 6 April 2025 and before 6 April 2026. "
            "Does NOT apply to the 52-week Limb B comparator in the compensatory cap."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.227(1) + SI 2025/348",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2025/348/schedule/made",
        "effective_from": date(2025, 4, 6),
        "effective_to":   date(2026, 4, 5),
        "is_prospective": False,
    },

    # ── 4b. Week's pay cap — current (£751, from 6 April 2026) ──────────────
    # SI 2026/310 schedule: s.227(1) £719 -> £751. Confirmed 2026-05-31.
    {
        "rule_key":       "unfair_dismissal.weeks_pay_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  751,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Maximum week's pay for basic award (ERA 1996 s.227(1)), SI 2026/310. "
            "Applies where EDT is on or after 6 April 2026. "
            "Does NOT apply to the 52-week Limb B comparator in the compensatory cap. "
            "Uprated annually each April."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.227(1) + SI 2026/310",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2026/310/schedule/made",
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 5a. Compensatory cap — prior year (£118,223, to 5 April 2026) ───────
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  118223,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Limb A statutory compensatory cap (ERA 1996 s.124(1ZA)(a)), SI 2025/348. "
            "Applies where EDT is on or after 6 April 2025 and before 6 April 2026. "
            "Award = min(Limb A, Limb B). Limb B = 52 x actual gross weekly pay "
            "(NOT s.227-capped). Cap disapplied for certain auto-unfair categories."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA)(a) + SI 2025/348",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2025/348/schedule/made",
        "effective_from": date(2025, 4, 6),
        "effective_to":   date(2026, 4, 5),
        "is_prospective": False,
    },

    # ── 5b. Compensatory cap — current (£123,543, from 6 April 2026) ────────
    # SI 2026/310 schedule: s.124(1ZA)(a) £118,223 -> £123,543. Confirmed 2026-05-31.
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  123543,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Limb A statutory compensatory cap (ERA 1996 s.124(1ZA)(a)), SI 2026/310. "
            "Applies where EDT is on or after 6 April 2026. "
            "Award = min(Limb A=£123,543, Limb B=52 x actual gross weekly pay). "
            "s.227 cap (£751) does NOT apply to Limb B. "
            "Cap disapplied for auto-unfair categories (Phase 5 scope)."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA)(a) + SI 2026/310",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2026/310/schedule/made",
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 5c. Compensatory cap — prospective removal (ERA 2025 s.25) ──────────
    # ERA 2025 s.25(3): "Omit section 124." Verified from enacted text 2026-05-31.
    # NOT YET IN FORCE. effective_from = 2027-01-01 PROVISIONAL.
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "s124_omitted_by_era2025_s25",
        "unit":           "GBP",
        "description":    (
            "PROSPECTIVE — NOT IN FORCE. ERA 2025 s.25(3): 'Omit section 124'. "
            "Verified from ERA 2025 enacted text 2026-05-31. The entire ERA 1996 s.124 "
            "is deleted; no statutory cap once commenced. Act says Omit, not uncapped. "
            "Limb B (52 x actual gross weekly pay) survival must be verified when SI "
            "is published. effective_from 2027-01-01 PROVISIONAL. "
            "DO NOT use until is_prospective=false."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "Employment Rights Act 2025 s.25(3) (omitting ERA 1996 s.124); "
            "commencement SI pending — effective_from is PROVISIONAL"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/2025/36/section/25",
        "effective_from": date(2027, 1, 1),
        "effective_to":   None,
        "is_prospective": True,
    },

    # ── 6. 52-week alternative cap ───────────────────────────────────────────
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_weeks_pay",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  52,
        "value_text":     None,
        "unit":           "weeks_gross_pay",
        "description":    (
            "Alternative compensatory cap: 52 x actual gross weekly pay. "
            "Applied if lower than the statutory cap in compensatory_cap_amount. "
            "Uses ACTUAL gross pay, not the s.227-capped week's pay figure."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA)(b)",
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/124",
        "effective_from": date(2013, 7, 29),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 7. Basic award formula (reference row) ───────────────────────────────
    {
        "rule_key":       "unfair_dismissal.basic_award_formula",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     (
            "Per complete year of service (max 20 years): "
            "1.5 x week's pay for each year while aged 41+; "
            "1.0 x week's pay for each year while aged 22-40; "
            "0.5 x week's pay for each year while under 22. "
            "Week's pay capped at weeks_pay_cap_amount (s.227). "
            "Computed in application code. Do not hard-code the cap value. "
            "NOTE: s.227 cap applies to the basic award; it does NOT apply to "
            "the 52-week Limb B in the compensatory cap."
        ),
        "unit":           None,
        "description":    (
            "Reference row for the statutory basic award formula (ERA 1996 s.119). "
            "The monetary cap is in weeks_pay_cap_amount. "
            "Multipliers are statutory constants; date sensitivity is in the cap row."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.119",
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/119",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 8. Minimum basic award for specific auto-unfair categories ──────────
    # s.120 ERA 1996. Applies only to specified automatically-unfair dismissals.
    # NOT a general unfair dismissal rule — Phase 5 scope.
    # Included for completeness; retrieval code must scope to s.120 categories.
    {
        "rule_key":       "unfair_dismissal.basic_award_min_automatic",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  9157,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Minimum basic award where dismissal is automatically unfair on specified "
            "grounds (ERA 1996 s.120): health & safety reps, working time, trade union, "
            "employee reps. £9,157 from SI 2026/310 (effective 2026-04-06). "
            "DOES NOT APPLY to ordinary unfair dismissal. Phase 5 scope for auto-unfair."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.120(1) + SI 2026/310",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2026/310/schedule/made",
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── 9. EC max duration (12 weeks from 1 December 2025) ──────────────────
    # SI 2025/1153: substitutes "12" for "six" in Schedule rule 6(1).
    # Verified from SI 2025/1153 text 2026-05-31.
    {
        "rule_key":       "unfair_dismissal.ec_max_duration_weeks",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  12,
        "value_text":     None,
        "unit":           "weeks",
        "description":    (
            "Maximum duration of ACAS Early Conciliation: up to 12 weeks for EC "
            "notifications on or after 1 December 2025 (extended from 6 weeks). "
            "The s.207B stop-the-clock arithmetic is unchanged; the actual EC period "
            "is whatever Day A to Day B turns out to be, up to this maximum."
        ),
        "authority_type": "legislation",
        "authority_ref":  (
            "Employment Tribunals (Early Conciliation: Exemptions and Rules of Procedure) "
            "(Amendment) Regulations 2025 (SI 2025/1153), Schedule rule 6(1)"
        ),
        "authority_url":  "https://www.legislation.gov.uk/uksi/2025/1153/made",
        "effective_from": date(2025, 12, 1),
        "effective_to":   None,
        "is_prospective": False,
    },
]


UPSERT = """
INSERT INTO rules (
    rule_key, claim_type, jurisdiction, value_numeric, value_text, unit,
    description, authority_type, authority_ref, authority_url,
    effective_from, effective_to, is_prospective, last_verified_at
) VALUES (
    %(rule_key)s, %(claim_type)s, %(jurisdiction)s, %(value_numeric)s,
    %(value_text)s, %(unit)s, %(description)s, %(authority_type)s,
    %(authority_ref)s, %(authority_url)s,
    %(effective_from)s, %(effective_to)s, %(is_prospective)s, now()
)
ON CONFLICT (rule_key, jurisdiction, effective_from) DO UPDATE SET
    value_numeric    = EXCLUDED.value_numeric,
    value_text       = EXCLUDED.value_text,
    description      = EXCLUDED.description,
    authority_ref    = EXCLUDED.authority_ref,
    authority_url    = EXCLUDED.authority_url,
    effective_to     = EXCLUDED.effective_to,
    is_prospective   = EXCLUDED.is_prospective,
    last_verified_at = now()
"""

# Phase 5C: verification status per rule_key + effective_from.
# Applied as a separate UPDATE after UPSERT so the column may not exist on first run.
VERIFICATION_STATUSES = {
    # (rule_key, effective_from): (status, notes)
    ("unfair_dismissal.time_limit_months", date(1996, 8, 22)):
        ("verified", "Confirmed from legislation.gov.uk/ukpga/1996/18/section/111 on 2026-05-31."),
    ("unfair_dismissal.time_limit_months", date(2026, 10, 1)):
        ("prospective", "ERA 2025 s.152. No commencement SI as of 2026-05-31."),
    ("unfair_dismissal.early_conciliation_required", date(2014, 4, 6)):
        ("verified", "Confirmed from legislation.gov.uk/ukpga/1996/17/section/18A on 2026-05-31."),
    ("unfair_dismissal.qualifying_period", date(2012, 4, 6)):
        ("verified", "Confirmed from legislation.gov.uk/ukpga/1996/18/section/108 on 2026-05-31. SI 2012/989 text confirmed."),
    ("unfair_dismissal.qualifying_period", date(2027, 1, 1)):
        ("prospective", "ERA 2025 s.25(2). No commencement SI as of 2026-05-31."),
    ("unfair_dismissal.weeks_pay_cap_amount", date(2025, 4, 6)):
        ("verified", "SI 2025/348 schedule confirmed from legislation.gov.uk on 2026-05-31."),
    ("unfair_dismissal.weeks_pay_cap_amount", date(2026, 4, 6)):
        ("verified", "SI 2026/310 schedule confirmed from legislation.gov.uk on 2026-05-31."),
    ("unfair_dismissal.compensatory_cap_amount", date(2025, 4, 6)):
        ("verified", "SI 2025/348 schedule confirmed from legislation.gov.uk on 2026-05-31."),
    ("unfair_dismissal.compensatory_cap_amount", date(2026, 4, 6)):
        ("verified", "SI 2026/310 schedule confirmed from legislation.gov.uk on 2026-05-31."),
    ("unfair_dismissal.compensatory_cap_amount", date(2027, 1, 1)):
        ("prospective", "ERA 2025 s.25(3). No commencement SI as of 2026-05-31."),
    ("unfair_dismissal.compensatory_cap_weeks_pay", date(2013, 7, 29)):
        ("verified", "Confirmed from legislation.gov.uk/ukpga/1996/18/section/124 on 2026-05-31."),
    ("unfair_dismissal.basic_award_formula", date(1996, 8, 22)):
        ("verified", "Confirmed from legislation.gov.uk/ukpga/1996/18/section/119 on 2026-05-31."),
    ("unfair_dismissal.basic_award_min_automatic", date(2026, 4, 6)):
        ("verified", "SI 2026/310 schedule confirmed from legislation.gov.uk on 2026-05-31."),
    ("unfair_dismissal.ec_max_duration_weeks", date(2025, 12, 1)):
        ("verified", "SI 2025/1153 text confirmed from legislation.gov.uk on 2026-05-31."),
}

VERIFICATION_UPDATE = """
UPDATE rules
SET verification_status = %(status)s,
    verification_notes  = %(notes)s
WHERE rule_key       = %(rule_key)s
  AND jurisdiction   = 'EW'
  AND effective_from = %(effective_from)s
"""


def seed() -> None:
    # Guard: every row must use a canonical key
    for row in ROWS:
        if row["rule_key"] not in CANONICAL_KEYS:
            raise ValueError(
                f"Non-canonical rule_key '{row['rule_key']}' in ROWS. "
                f"Add it to CANONICAL_KEYS or use an existing key."
            )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in ROWS:
                cur.execute(UPSERT, row)
                log.info(
                    "upserted %s effective_from=%s is_prospective=%s",
                    row["rule_key"], row["effective_from"], row["is_prospective"],
                )

            # Phase 5C: apply verification status if column exists
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='rules' AND column_name='verification_status'
            """)
            if cur.fetchone():
                for (rk, eff), (status, notes) in VERIFICATION_STATUSES.items():
                    cur.execute(VERIFICATION_UPDATE,
                                {"status": status, "notes": notes,
                                 "rule_key": rk, "effective_from": eff})
                log.info("Verification status applied to %d rule rows.", len(VERIFICATION_STATUSES))

        conn.commit()
        log.info("Seed complete: %d rows", len(ROWS))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
