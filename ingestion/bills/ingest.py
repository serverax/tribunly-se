"""
UK Parliament Bills API ingestion.

Source: https://bills-api.parliament.uk/api/v1/Bills
Stores in: bills, legal_change_watch

GUARDRAIL: Bills are NOT active law until commenced.
           is_in_force=False until explicitly verified and updated.
           Never use a Bill as an active rule.

Usage:
    python -m ingestion.bills.ingest
"""

from __future__ import annotations

import logging

import httpx
from rich.console import Console

from ingestion.db import transaction

console = Console()
logger  = logging.getLogger(__name__)

BILLS_API = "https://bills-api.parliament.uk/api/v1"

# Employment-relevant bill title keywords
EMPLOYMENT_KEYWORDS = [
    "employment", "worker", "labour", "trade union", "redundancy",
    "tribunal", "dismissal", "wages", "pay", "equality", "discrimination",
]


def _is_employment_relevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in EMPLOYMENT_KEYWORDS)


def ingest_recent_bills(pages: int = 3) -> None:
    """Fetch recent bills from Parliament API and store employment-relevant ones."""
    console.print("[bold green]Parliament Bills ingestion starting[/bold green]")
    ingested = 0

    for page in range(1, pages + 1):
        try:
            resp = httpx.get(
                f"{BILLS_API}/Bills",
                params={"currentHouse": "Commons", "page": page, "itemsPerPage": 25},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Bills API fetch failed page %d: %s", page, e)
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for bill in items:
            title = bill.get("shortTitle") or bill.get("longTitle", "")
            if not _is_employment_relevant(title):
                continue

            bill_id    = bill.get("billId")
            bill_type  = bill.get("billType", {}).get("name", "")
            stage      = bill.get("currentStage", {}).get("stageName", "")
            source_url = f"https://bills.parliament.uk/bills/{bill_id}"

            sql = """
                INSERT INTO bills
                    (bill_id, title, short_title, bill_type, stage,
                     house_origin, jurisdiction, source_url,
                     is_in_force, last_verified_at)
                VALUES
                    (%(bill_id)s, %(title)s, %(short_title)s, %(bill_type)s, %(stage)s,
                     'Commons', 'UK', %(url)s, false, now())
                ON CONFLICT (source_url) DO UPDATE SET
                    stage            = EXCLUDED.stage,
                    last_verified_at = now()
            """
            with transaction() as cur:
                cur.execute(sql, {
                    "bill_id":    bill_id,
                    "title":      title[:500],
                    "short_title": (bill.get("shortTitle") or "")[:200],
                    "bill_type":  bill_type[:100],
                    "stage":      stage[:200],
                    "url":        source_url,
                })
            console.print(f"  [green]✓[/green] {title[:80]}  -  stage: {stage}")
            ingested += 1

    console.print(f"[bold]Done: {ingested} employment-relevant bills stored[/bold]")
    console.print("[yellow]NOTE: Bills are NOT active law until commenced. is_in_force=False.[/yellow]")


if __name__ == "__main__":
    ingest_recent_bills()
