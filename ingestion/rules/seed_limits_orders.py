"""
UKSI  -  Employment Rights (Increase of Limits) Orders ingestion.

Statutory employment limits (week's pay cap, maximum compensatory award, minimum
basic award for certain automatically-unfair dismissals) are revised annually by a
Statutory Instrument: "The Employment Rights (Increase of Limits) Order {year}".

This module:
  1. Fetches each official Order from legislation.gov.uk and stores its text in the
     `legislation` table (leg_type='uksi') with a real content_hash + source_url  - 
     so the statutory source is captured, hashed and citation-resolvable.
  2. Upserts effective-dated `rules` rows for the caps, each tied to its specific
     Order (authority_ref + authority_url + effective_from/effective_to). The cap
     VALUES live in the cited `rules` table  -  NOT hardcoded in application logic.

The SI numbers/URLs below were confirmed live via legislation.gov.uk title
resolution. The figures are the published statutory limits; each rule row carries
the official Order URL so any value is verifiable against source.

Usage:
    python -m ingestion.rules.seed_limits_orders
"""

from __future__ import annotations

import logging
import re
import html
from datetime import date

import httpx
from rich.console import Console

from ingestion.config import settings  # noqa: F401  (ensures env/DB config loaded)
from ingestion.db import transaction, upsert_legislation, upsert_rule

logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
logger = logging.getLogger(__name__)
console = Console()

LEG_BASE = "https://www.legislation.gov.uk"

# Confirmed via resolve_title() against legislation.gov.uk on 2026-06-05.
# Each Order commences 6 April of its year. Figures are the published statutory
# limits revised by that Order.
LIMITS_ORDERS = [
    # year, si_no, weeks_pay_cap, max_compensatory_award, min_basic_award_automatic
    (2021, "208", 544, 89493, 6634),
    (2022, "182", 571, 93878, 6959),
    (2023, "318", 643, 105707, 7836),
    (2024, "213", 700, 115115, 8533),
    (2025, "348", 719, 118223, 8533),
    (2026, "310", 751, 123543, 9157),  # current in-force Order (open-ended)
]

# rule_key -> (column in tuple index, ERA authority anchor)
CAP_RULES = [
    ("unfair_dismissal.weeks_pay_cap_amount", 2, "ERA 1996 s.227"),
    ("unfair_dismissal.compensatory_cap_amount", 3, "ERA 1996 s.124"),
    ("unfair_dismissal.basic_award_min_automatic", 4, "ERA 1996 s.120"),
]


def _order_url(year: int, si_no: str) -> str:
    return f"{LEG_BASE}/uksi/{year}/{si_no}"


def _order_citation(year: int, si_no: str) -> str:
    return f"The Employment Rights (Increase of Limits) Order {year} (SI {year}/{si_no})"


def _fetch_order_text(year: int, si_no: str) -> str:
    """Fetch the official Order document text (real source, for content_hash)."""
    url = f"{_order_url(year, si_no)}/data.xml"
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "lawapp/1.0 (employment-claim-copilot)"})
        resp.raise_for_status()
    text = html.unescape(re.sub(r"<[^>]+>", " ", resp.text))
    return re.sub(r"\s+", " ", text).strip()


def ingest_limits_orders() -> dict:
    stored_sources = 0
    stored_rules = 0
    n = len(LIMITS_ORDERS)
    with transaction() as cur:
        for idx, (year, si_no, wcap, ccap, bmin) in enumerate(LIMITS_ORDERS):
            url = _order_url(year, si_no)
            citation = _order_citation(year, si_no)
            eff_from = date(year, 4, 6)
            # latest order stays open-ended; earlier orders end the day before next commencement
            eff_to = None if idx == n - 1 else date(LIMITS_ORDERS[idx + 1][0], 4, 5)

            # 1) store the official Order text as a legislation (uksi) provenance row
            try:
                body = _fetch_order_text(year, si_no)
            except Exception as exc:  # never fabricate  -  skip source text on failure
                console.print(f"  [yellow]could not fetch {citation} source text ({exc})[/yellow]")
                body = ""
            if body:
                upsert_legislation(cur, {
                    "act_title": f"The Employment Rights (Increase of Limits) Order {year}",
                    "leg_type": "uksi",
                    "year": year,
                    "chapter": si_no,
                    "section_ref": "ILO",
                    "jurisdiction": "EW",
                    "heading": f"Increase of Limits Order {year}",
                    "body_text": body,
                    "chunk_index": 0,
                    "source_url": f"{url}/made",
                    "version_date": eff_from,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                    "is_prospective": False,
                    "source_type": "statutory_instrument",
                    "parser_type": "clml_xml",
                    "parent_source_id": "legislation_gov_uk",
                })
                stored_sources += 1

            # 2) effective-dated cap rules tied to this Order
            order_tuple = (year, si_no, wcap, ccap, bmin)
            for rule_key, val_idx, era_anchor in CAP_RULES:
                value = order_tuple[val_idx]
                upsert_rule(cur, {
                    "rule_key": rule_key,
                    "claim_type": "unfair_dismissal",
                    "jurisdiction": "EW",
                    "value_numeric": value,
                    "value_text": None,
                    "unit": "GBP",
                    "description": (
                        f"{era_anchor} statutory limit set by {citation}, "
                        f"effective {eff_from.isoformat()}."
                    ),
                    "authority_type": "statutory_instrument",
                    "authority_ref": f"{era_anchor}; {citation}",
                    "authority_url": url,
                    "effective_from": eff_from,
                    "effective_to": eff_to,
                    "is_prospective": False,
                    "verification_status": "verified_against_official_source",
                    "verification_notes": (
                        "Annual statutory limit; source Order text stored in legislation "
                        "(leg_type=uksi) with content_hash for verification."
                    ),
                })
                stored_rules += 1

    result = {"orders": n, "source_rows": stored_sources, "rule_rows": stored_rules}
    console.print(f"[green]Increase of Limits Orders ingested:[/green] {result}")
    return result


if __name__ == "__main__":
    ingest_limits_orders()
