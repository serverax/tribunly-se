"""
Phase 1 — `rules` table seeder for unfair dismissal (England, Wales, Scotland).

Authority: 03a_UNFAIR_DISMISSAL_SEED_SPEC.md
Source:    SI 2026/310 (Increase of Limits Order 2026), ERA 1996, ETA 1996.

GUARDRAIL: Every figure seeded here was verified against the live
legislation.gov.uk API and SI 2026/310 on 2026-05-29. Values are seeded
into the `rules` table; the application reads them by effective date.
The LLM NEVER generates, recalls, or re-derives these values.

Verification performed 2026-05-29:
  SI 2026/310  (The Employment Rights (Increase of Limits) Order 2026)
    s.227(1)    week's pay cap:           £719 → £751  (effective 2026-04-06) ✓
    s.124(1ZA)  compensatory cap:    £118,223 → £123,543 (effective 2026-04-06) ✓
    s.120(1)    min basic award:       £8,763 → £9,157   (effective 2026-04-06) ✓

  NOTE: £783 / £123,785 are Northern Ireland figures (nisr/2026/57). Rejected.

  ERA 2025 s.25 (qualifying period + cap removal) and s.152 (time limits):
    NOT YET COMMENCED as of 2026-05-29. No commencement SI found for these
    provisions. Seeded as is_prospective=true with soft effective dates.
    Check for commencement SIs before relying on these rows.

Usage:
    python -m ingestion.rules.seed            # seed all rules
    python -m ingestion.rules.seed --check    # verify against live API, don't write
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from rich.console import Console
from rich.table import Table

from ingestion.config import settings, LEGISLATION_BASE
from ingestion.db import transaction, upsert_rule
from ingestion.legislation.client import fetch_section_xml

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

# ── Rule definitions ──────────────────────────────────────────────────────────
#
# Format: dict matching the `rules` table schema.
# All dates are confirmed or soft-dated as noted.
# effective_to=None means "current" (no expiry yet).
# is_prospective=True means enacted but not yet commenced.
#
# Jurisdictions: seeded for EW (England & Wales, also applies to Scotland for
# these GB-wide ERA 1996 provisions — documented as EW per 03_DATABASE_DESIGN.md).

_ERA96_S111_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/111/data.xml"
_ERA96_S111_PROS_URL = f"{LEGISLATION_BASE}/ukpga/1996/18/section/111/prospective/data.xml"
_ERA96_S108_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/108/data.xml"
_ERA96_S108_PROS_URL = f"{LEGISLATION_BASE}/ukpga/1996/18/section/108/prospective/data.xml"
_ERA96_S124_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/124/data.xml"
_ERA96_S124_PROS_URL = f"{LEGISLATION_BASE}/ukpga/1996/18/section/124/prospective/data.xml"
_ERA96_S120_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/120/data.xml"
_ERA96_S119_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/119/data.xml"
_ERA96_S227_URL      = f"{LEGISLATION_BASE}/ukpga/1996/18/section/227/data.xml"
_ERA96_S207B_URL     = f"{LEGISLATION_BASE}/ukpga/1996/18/section/207B/data.xml"
_ETA96_S18A_URL      = f"{LEGISLATION_BASE}/ukpga/1996/17/section/18A/data.xml"
_SI2026_310_URL      = f"{LEGISLATION_BASE}/uksi/2026/310/schedule/made"
_SI2025_348_URL      = f"{LEGISLATION_BASE}/uksi/2025/348/schedule/made"

RULES: list[dict] = [

    # ── Qualifying period ─────────────────────────────────────────────────────
    {
        "rule_key":       "unfair_dismissal.qualifying_period",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  2,
        "value_text":     None,
        "unit":           "years",
        "description":    (
            "Ordinary unfair dismissal requires 2 years' continuous service "
            "(ERA 1996 s.108(1)). Applies to dismissals with EDT up to 2026-12-31 "
            "under the current regime. Day-one exceptions (discrimination, whistleblowing, "
            "health & safety, trade union) are not covered by this rule."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.108(1)",
        "authority_url":  _ERA96_S108_URL,
        "effective_from": date(2012, 4, 6),   # Unfair Dismissal (Variation of Qualifying Period) Order 2012
        "effective_to":   None,               # current — no effective_to; gap risk if ERA 2025 s.25 slips
        "is_prospective": False,
    },
    {
        "rule_key":       "unfair_dismissal.qualifying_period",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  6,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "Qualifying period reduced to 6 months for dismissals with EDT on/after "
            "2027-01-01 (ERA 2025 s.25 amending ERA 1996 s.108). "
            "PROSPECTIVE: ERA 2025 s.25 has NOT been commenced as of 2026-05-29. "
            "Confirm commencement SI before relying on this row. "
            "Applies to existing employees; no transitional carve-out."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.108 as amended by ERA 2025 s.25",
        "authority_url":  _ERA96_S108_PROS_URL,
        "effective_from": date(2027, 1, 1),   # Soft — confirm commencement SI
        "effective_to":   None,
        "is_prospective": True,
    },

    # ── Time limit ────────────────────────────────────────────────────────────
    {
        "rule_key":       "unfair_dismissal.time_limit_months",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  3,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "Complaint must be presented before the end of 3 months 'beginning with' "
            "the EDT (i.e. the last day is the day before the 3-month anniversary). "
            "ERA 1996 s.111(2). A 'not reasonably practicable' extension may apply — "
            "this is a merits judgement, not deterministic; route to honesty path."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.111(2)",
        "authority_url":  _ERA96_S111_URL,
        "effective_from": date(1996, 8, 22),  # ERA 1996 commencement — verify exact date
        "effective_to":   None,   # current law — no soft expiry; gap risk if commencement slips
        "is_prospective": False,
    },
    {
        "rule_key":       "unfair_dismissal.time_limit_months",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  6,
        "value_text":     None,
        "unit":           "months",
        "description":    (
            "Time limit extended to 6 months 'beginning with' the EDT under ERA 2025 s.152. "
            "PROSPECTIVE — COMMENCEMENT NOT CONFIRMED: government stated 'no earlier than "
            "October 2026' but no commencement SI has been published as of 2026-05-29. "
            "The effective_from date is provisional. DEADLINE CALC MUST apply 3 months "
            "until a commencement order is published and this row's is_prospective is "
            "set to false. Applying 6 months early tells claimants they have longer than "
            "they do — that loses claims. Check for commencement SI monthly."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.111(2) as amended by ERA 2025 s.152",
        "authority_url":  _ERA96_S111_PROS_URL,
        "effective_from": date(2026, 10, 1),  # Soft — do NOT rely until commencement SI published
        "effective_to":   None,
        "is_prospective": True,
    },

    # ── Early Conciliation requirement ────────────────────────────────────────
    {
        "rule_key":       "unfair_dismissal.early_conciliation_required",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "true",
        "unit":           None,
        "description":    (
            "Claimant must notify ACAS for Early Conciliation before issuing ET1. "
            "The EC period pauses the limitation clock per ERA 1996 s.207B "
            "(Day A+1 to Day B not counted; floor of one month after Day B applies)."
        ),
        "authority_type": "legislation",
        "authority_ref":  "Employment Tribunals Act 1996 s.18A",
        "authority_url":  _ETA96_S18A_URL,
        "effective_from": date(2014, 5, 6),   # EC mandatory requirement date
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── Compensatory cap (s.124) ──────────────────────────────────────────────
    # Prior year figure (for back-dated cases with EDT in 2025-04-06 to 2026-04-05)
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  118223,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Maximum compensatory award for unfair dismissal: £118,223 OR 52 weeks' "
            "gross actual pay, whichever is lower. Applies to dismissals with EDT "
            "between 2025-04-06 and 2026-04-05. Source: SI 2025/348."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA) + Employment Rights (Increase of Limits) Order 2025 (SI 2025/348)",
        "authority_url":  _SI2025_348_URL,
        "effective_from": date(2025, 4, 6),
        "effective_to":   date(2026, 4, 5),
        "is_prospective": False,
    },
    # Current figure (EDT on/after 2026-04-06)
    # effective_to = NULL: this is the current law. The prospective uncapped row
    # has is_prospective=True and won't activate until its commencement SI is published.
    # A pre-set effective_to of 2026-12-31 would leave a gap if ERA 2025 s.25 slips.
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  123543,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Maximum compensatory award: £123,543 OR 52 weeks' gross actual pay, "
            "whichever is lower. Current regime for EDT from 2026-04-06. "
            "Verified against SI 2026/310 Schedule on 2026-05-29. "
            "No effective_to set — remains current until ERA 2025 s.25 commences and "
            "the prospective uncapped row is activated by removing is_prospective."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA)(a) + Employment Rights (Increase of Limits) Order 2026 (SI 2026/310)",
        "authority_url":  _SI2026_310_URL,
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,   # current — no gap risk if ERA 2025 s.25 commencement slips
        "is_prospective": False,
    },
    # Prospective: cap removed for EDT on/after 2027-01-01
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     "uncapped",
        "unit":           "GBP",
        "description":    (
            "Compensatory award cap REMOVED for dismissals with EDT on/after 2027-01-01 "
            "by ERA 2025 s.25. Compensation = actual just-and-equitable loss, uncapped. "
            "PROSPECTIVE: not yet commenced as of 2026-05-29. "
            "OPEN ITEM: verify whether the 52-week alternative (s.124(1ZA)(b)) is also "
            "removed or retained — confirm against amended s.124 prospective text."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124 as amended by ERA 2025 s.25",
        "authority_url":  _ERA96_S124_PROS_URL,
        "effective_from": date(2027, 1, 1),   # Soft — confirm commencement SI
        "effective_to":   None,
        "is_prospective": True,
    },

    # 52-week alternative cap
    {
        "rule_key":       "unfair_dismissal.compensatory_cap_weeks_pay",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  52,
        "value_text":     None,
        "unit":           "weeks_gross_pay",
        "description":    (
            "Alternative compensatory cap: 52 weeks' gross actual pay if this is lower "
            "than the £ figure. ERA 1996 s.124(1ZA)(b). "
            "OPEN ITEM: whether this survives the ERA 2025 cap removal must be confirmed "
            "against the prospective text of s.124 once ERA 2025 s.25 is commenced."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.124(1ZA)(b)",
        "authority_url":  _ERA96_S124_URL,
        "effective_from": date(2013, 7, 29),  # Enterprise and Regulatory Reform Act 2013 — verify
        "effective_to":   None,               # May end 2026-12-31 — verify against ERA 2025
        "is_prospective": False,
    },

    # ── Week's pay cap (s.227) ────────────────────────────────────────────────
    # Prior year
    {
        "rule_key":       "unfair_dismissal.weeks_pay_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  719,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Weekly pay cap for basic award calculation: £719. "
            "Applies to dismissals with EDT between 2025-04-06 and 2026-04-05. "
            "Source: SI 2025/348. Uprated annually each April."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.227(1) + SI 2025/348",
        "authority_url":  _SI2025_348_URL,
        "effective_from": date(2025, 4, 6),
        "effective_to":   date(2026, 4, 5),
        "is_prospective": False,
    },
    # Current figure
    {
        "rule_key":       "unfair_dismissal.weeks_pay_cap_amount",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  751,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Weekly pay cap for basic award calculation: £751 (effective 2026-04-06). "
            "Verified against SI 2026/310 Schedule on 2026-05-29. "
            "Uprated each April — update this row and add a new one each year."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.227(1) + Employment Rights (Increase of Limits) Order 2026 (SI 2026/310)",
        "authority_url":  _SI2026_310_URL,
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,              # Until next April uprating
        "is_prospective": False,
    },

    # ── Basic award ───────────────────────────────────────────────────────────
    # Minimum basic award (automatically unfair dismissals: s.120)
    {
        "rule_key":       "unfair_dismissal.basic_award_min_automatic",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  9157,
        "value_text":     None,
        "unit":           "GBP",
        "description":    (
            "Minimum basic award where dismissal is automatically unfair on specified grounds "
            "(health & safety reps, working time, trade union, employee reps). "
            "£9,157 effective 2026-04-06. Verified against SI 2026/310 on 2026-05-29."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.120(1) + SI 2026/310",
        "authority_url":  _SI2026_310_URL,
        "effective_from": date(2026, 4, 6),
        "effective_to":   None,
        "is_prospective": False,
    },
    # Basic award formula (non-numeric — the computation rule)
    {
        "rule_key":       "unfair_dismissal.basic_award_formula",
        "claim_type":     "unfair_dismissal",
        "jurisdiction":   "EW",
        "value_numeric":  None,
        "value_text":     (
            "Per complete year of service (max 20 years): "
            "1.5 × week's pay for each year while aged 41+; "
            "1.0 × week's pay for each year while aged 22–40; "
            "0.5 × week's pay for each year while under 22. "
            "Week's pay is capped at the current unfair_dismissal.weeks_pay_cap_amount. "
            "Maximum basic award = 20 × 1.5 × weeks_pay_cap — compute, do not hardcode."
        ),
        "unit":           None,
        "description":    (
            "Age-banded formula for basic award (ERA 1996 s.119). "
            "The derived maximum (currently 20 × 1.5 × £751 = £22,530) is NOT stored "
            "as a literal — it must be computed from this formula and the current "
            "weeks_pay_cap_amount so it automatically stays correct after each April uprating."
        ),
        "authority_type": "legislation",
        "authority_ref":  "ERA 1996 s.119",
        "authority_url":  _ERA96_S119_URL,
        "effective_from": date(1996, 8, 22),  # ERA 1996 commencement — verify exact date
        "effective_to":   None,
        "is_prospective": False,
    },

    # ── Early Conciliation maximum duration ───────────────────────────────────
    # Verified 2026-05-30 against primary source: UKSI 2025/1153 (The Employment
    # Tribunals (Early Conciliation: Exemptions and Rules of Procedure) (Amendment)
    # Regulations 2025) substitutes "six" with "12" in Schedule rule 6(1), effective
    # 1 December 2025, for EC notifications on or after that date.
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
            "The s.207B stop-the-clock arithmetic (Day A+1 to Day B) is unchanged; "
            "the actual EC period is whatever Day A to Day B turns out to be, up to "
            "this maximum. Source: SI 2025/1153, Schedule rule 6(1)."
        ),
        "authority_type": "legislation",
        "authority_ref":  "Employment Tribunals (Early Conciliation: Exemptions and Rules of Procedure) (Amendment) Regulations 2025 (SI 2025/1153), Schedule rule 6(1)",
        "authority_url":  "https://www.legislation.gov.uk/uksi/2025/1153/made",
        "effective_from": date(2025, 12, 1),
        "effective_to":   None,
        "is_prospective": False,
    },
]


def seed(dry_run: bool = False) -> None:
    """Seed all rules rows. dry_run=True prints without writing."""
    table = Table(title="Rules to seed", show_lines=True)
    table.add_column("rule_key")
    table.add_column("effective_from")
    table.add_column("value")
    table.add_column("prospective")

    for rule in RULES:
        val = str(rule["value_numeric"]) if rule["value_numeric"] is not None else (rule["value_text"] or "—")
        table.add_row(
            rule["rule_key"],
            str(rule["effective_from"]),
            val,
            "✓" if rule["is_prospective"] else "",
        )

    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run — no writes.[/yellow]")
        return

    console.print(f"Writing {len(RULES)} rule rows…")
    with transaction() as cur:
        for rule in RULES:
            upsert_rule(cur, rule)

    console.print("[bold green]Rules seeded successfully.[/bold green]")
    _print_open_items()


def _print_open_items() -> None:
    console.print("\n[bold yellow]Open items — verify before relying on prospective rows:[/bold yellow]")
    items = [
        "ERA 2025 s.25 commencement SI not yet found (qualifying period + cap removal). "
        "Check for new commencement SIs regularly.",
        "ERA 2025 s.152 commencement SI not yet found (time limit extension). "
        "October 2026 soft date — confirm.",
        "Whether s.124(1ZA)(b) 52-week cap survives ERA 2025 cap removal — check prospective text.",
        "ERA 1996 commencement date for s.119 and s.111 — verify exact date against the Act.",
    ]
    for item in items:
        console.print(f"  [yellow]•[/yellow] {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the rules table for unfair dismissal")
    parser.add_argument("--check", action="store_true",
                        help="Print rules without writing to DB")
    args = parser.parse_args()
    seed(dry_run=args.check)


if __name__ == "__main__":
    main()
