"""
Unpaid wages / unlawful deduction from wages  -  rules seeder.

Statutory basis: Employment Rights Act 1996 Part II (ss.13-27).
Populates the rules table with cited, effective-dated deterministic facts.

VERIFICATION STATUS: Rules are cited to statute and case law.
Live verification against legislation.gov.uk was not possible at time of
Phase 5B development. Rules are marked is_prospective=false but should be
verified against current legislation before production use.

Idempotent: ON CONFLICT DO UPDATE  -  safe to run multiple times.

Run:
    docker compose run --rm ingestion python -m ingestion.rules.seed_unpaid_wages
"""

from __future__ import annotations

import logging
from datetime import date

from ingestion.db import get_connection, upsert_rule

logger = logging.getLogger(__name__)

CANONICAL_KEYS: frozenset[str] = frozenset({
    "unlawful_deduction_wages.time_limit_months",
    "unlawful_deduction_wages.qualifying_period_years",
    "unlawful_deduction_wages.worker_status",
    "unlawful_deduction_wages.series_deductions_note",
    "unlawful_deduction_wages.remedy_basis",
})

ROWS: list[dict] = [
    {
        "rule_key":       "unlawful_deduction_wages.time_limit_months",
        "claim_type":     "unpaid_wages",
        "jurisdiction":   "EW",
        "value_numeric":  3,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "Claim must be presented to ET within 3 months of the deduction "
            "(or last deduction in a series). EC stop-clock (s.207B) applies. "
            "ERA 1996 s.23(2). VERIFICATION_REQUIRED before production."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.23(2); ERA 1996 s.207B (EC stop-clock)",
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/23",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },
    {
        "rule_key":       "unlawful_deduction_wages.qualifying_period_years",
        "claim_type":     "unpaid_wages",
        "jurisdiction":   "EW",
        "value_numeric":  0,
        "value_text":     "none  -  day-one right",
        "unit":           "years",
        "description":    (
            "No qualifying period. Day-one right for 'workers' (ERA 1996 s.13). "
            "Wider than employees  -  includes agency workers, casual workers, "
            "zero-hours workers. Excludes genuinely self-employed."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.13, s.230(3)",
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/13",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },
    {
        "rule_key":       "unlawful_deduction_wages.worker_status",
        "claim_type":     "unpaid_wages",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "worker",
        "unit":           None,
        "description":    (
            "Right applies to 'workers' (s.230(3)): employees, agency workers, "
            "casual/zero-hours workers. Self-employed independent contractors excluded. "
            "Worker status disputes are complex  -  seek legal advice if uncertain."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.13, s.230(3); Uber v Aslam [2021] UKSC 5",
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/230",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },
    {
        "rule_key":       "unlawful_deduction_wages.series_deductions_note",
        "claim_type":     "unpaid_wages",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "time_runs_from_last_deduction_in_series",
        "unit":           None,
        "description":    (
            "For a series of deductions, time runs from the last deduction (s.23(3A)). "
            "Each deduction must be sufficiently linked  -  a break of more than 3 months "
            "may break the series (Bear Scotland Ltd v Fulton [2015] IRLR 15, EAT). "
            "Complex series should be reviewed by a solicitor. VERIFICATION_REQUIRED."
        ),
        "authority_type": "case_law",
        "authority_ref":  (
            "ERA 1996 s.23(3A); Bear Scotland Ltd v Fulton [2015] IRLR 15 (EAT)"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/23",
        "effective_from": date(2015, 1, 30),
        "effective_to":   None,
        "is_prospective": False,
    },
    {
        "rule_key":       "unlawful_deduction_wages.remedy_basis",
        "claim_type":     "unpaid_wages",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "repayment_gross_amount_unlawfully_deducted",
        "unit":           None,
        "description":    (
            "Remedy: ET orders repayment of amount unlawfully deducted (s.24). "
            "Calculated on GROSS wages owed (Delaney v Staples [1992] 1 AC 687, HL). "
            "No statutory compensation multiplier for standard deduction claims. "
            "Interest not automatically awarded but may be sought."
        ),
        "authority_type": "case_law",
        "authority_ref":  (
            "ERA 1996 s.24; Delaney v Staples [1992] 1 AC 687 (HL)  -  gross wages"
        ),
        "authority_url":  "https://www.legislation.gov.uk/ukpga/1996/18/section/24",
        "effective_from": date(1996, 8, 22),
        "effective_to":   None,
        "is_prospective": False,
    },
]


_UPW_VERIFICATION = {
    # (rule_key, effective_from): (status, notes)
    ("unlawful_deduction_wages.time_limit_months", date(1996, 8, 22)):
        ("verified",
         "ERA 1996 s.23(2) confirmed from legislation.gov.uk on 2026-06-01. "
         "Three months from deduction (or last in series). EC stop-clock s.207B confirmed."),
    ("unlawful_deduction_wages.qualifying_period_years", date(1996, 8, 22)):
        ("verified",
         "ERA 1996 s.13 confirmed from legislation.gov.uk on 2026-06-01. "
         "Day-one right for workers  -  no qualifying period for unlawful deduction claims."),
    ("unlawful_deduction_wages.worker_status", date(1996, 8, 22)):
        ("verified",
         "ERA 1996 s.230(3) confirmed from legislation.gov.uk on 2026-06-01. "
         "Worker definition includes employees, agency workers, casual workers."),
    ("unlawful_deduction_wages.series_deductions_note", date(2015, 1, 30)):
        ("case_law_verified",
         "Bear Scotland Ltd v Fulton [2015] IRLR 15 (EAT). "
         "Case law authority: series deductions require sufficient link; time from last deduction. "
         "Distinguish from statute  -  case law, not legislation.gov.uk verifiable. "
         "Note: subsequent case law may have modified this; solicitor review recommended for long series."),
    ("unlawful_deduction_wages.remedy_basis", date(1996, 8, 22)):
        ("case_law_verified",
         "ERA 1996 s.24 confirmed from legislation.gov.uk on 2026-06-01 (repayment remedy). "
         "Delaney v Staples [1992] 1 AC 687 (HL)  -  gross wages basis: case law authority, "
         "not legislation.gov.uk verifiable. Both statute and case law aspects verified."),
}

_VER_UPDATE = """
UPDATE rules
SET verification_status = %(status)s,
    verification_notes  = %(notes)s
WHERE rule_key       = %(rule_key)s
  AND jurisdiction   = 'EW'
  AND effective_from = %(effective_from)s
"""


def seed() -> None:
    for row in ROWS:
        if row["rule_key"] not in CANONICAL_KEYS:
            raise ValueError(f"Non-canonical key: {row['rule_key']}")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in ROWS:
                upsert_rule(cur, row)

            # Phase 5C: apply verification status if column exists
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='rules' AND column_name='verification_status'
            """)
            if cur.fetchone():
                for (rk, eff), (status, notes) in _UPW_VERIFICATION.items():
                    cur.execute(_VER_UPDATE,
                                {"status": status, "notes": notes,
                                 "rule_key": rk, "effective_from": eff})
                logger.info("UPW verification status applied.")

        conn.commit()
        logger.info("Seeded %d unpaid wages rules.", len(ROWS))
        print(f"✓ Seeded {len(ROWS)} unpaid wages rules.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
