"""
Source freshness report + ERA 2025 commencement watch.

Queries the `source_freshness` view and prints a table showing every source
with its row count and oldest `last_verified_at`. Flags any source where the
oldest verification is more than STALE_DAYS old.

Also checks legislation.gov.uk for ERA 2025 commencement SIs and flags
when the provisional rules should transition to in-force.

Usage:
    python -m ingestion.freshness.report
    python -m ingestion.freshness.report --stale-days 30
    python -m ingestion.freshness.report --json  # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from ingestion.db import get_connection

STALE_DAYS_DEFAULT = 30

ERA_2025_COMMENCEMENT_URL = (
    "https://www.legislation.gov.uk/id?title="
    "Employment+Rights+Act+2025+%28Commencement%29"
)

console = Console()


def run_report(stale_days: int = STALE_DAYS_DEFAULT) -> dict:
    """
    Print the freshness report. Returns a result dict with keys:
    all_fresh, sources, stale_sources, era2025_commencement_found.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_name, source_type, jurisdiction_code,
                       rows_count, oldest_verified_at, newest_verified_at,
                       stale_rows_count
                FROM source_freshness
                ORDER BY source_name
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    result = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "stale_days_threshold": stale_days,
        "all_fresh": True,
        "sources": [],
        "stale_sources": [],
        "era2025_commencement_found": False,
        "era2025_commencement_detail": None,
    }

    if not rows:
        console.print("[red]No data in source_freshness view  -  has ingestion run?[/red]")
        result["all_fresh"] = False
        return result

    now = datetime.now(tz=timezone.utc)

    table = Table(title=f"Source Freshness Report  -  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    table.add_column("Source", style="bold")
    table.add_column("Type")
    table.add_column("Jurisdiction")
    table.add_column("Rows", justify="right")
    table.add_column("Stale", justify="right")
    table.add_column("Oldest verified")
    table.add_column("Age (days)", justify="right")
    table.add_column("Status")

    for source_name, source_type, jurisdiction, row_count, oldest_verified, newest_verified, stale_count in rows:
        entry = {
            "source_name": source_name,
            "source_type": source_type,
            "jurisdiction": jurisdiction,
            "rows": row_count or 0,
            "stale_rows": stale_count or 0,
        }

        if oldest_verified is None:
            age_str = " - "
            status = "[yellow]NO DATA[/yellow]"
            entry["status"] = "NO_DATA"
            entry["age_days"] = None
            result["all_fresh"] = False
            result["stale_sources"].append(source_name)
        else:
            if hasattr(oldest_verified, "tzinfo") and oldest_verified.tzinfo is None:
                oldest_verified = oldest_verified.replace(tzinfo=timezone.utc)
            age_days = (now - oldest_verified).days
            age_str = str(age_days)
            entry["age_days"] = age_days
            entry["oldest_verified"] = str(oldest_verified)[:19]

            if age_days > stale_days:
                status = f"[red]STALE (>{stale_days}d)[/red]"
                entry["status"] = "STALE"
                result["all_fresh"] = False
                result["stale_sources"].append(source_name)
            else:
                status = "[green]OK[/green]"
                entry["status"] = "OK"

        result["sources"].append(entry)
        table.add_row(
            source_name,
            source_type or "",
            jurisdiction or "",
            str(row_count or 0),
            str(stale_count or 0),
            str(oldest_verified)[:19] if oldest_verified else " - ",
            age_str,
            status,
        )

    console.print(table)

    if result["all_fresh"]:
        console.print("\n[bold green]All sources fresh.[/bold green]")
    else:
        console.print(
            f"\n[bold yellow]Warning: one or more sources are stale or empty. "
            f"Re-run ingestion for flagged sources.[/bold yellow]"
        )

    return result


def check_era2025_commencement() -> dict:
    """
    Check legislation.gov.uk for ERA 2025 commencement SIs.
    Returns dict with found (bool) and detail (str).
    """
    detail = {
        "found": False,
        "detail": "No commencement SI found — ERA 2025 provisional values remain suppressed.",
        "url_checked": ERA_2025_COMMENCEMENT_URL,
    }

    try:
        req = urllib.request.Request(
            ERA_2025_COMMENCEMENT_URL,
            headers={
                "Accept": "text/html",
                "User-Agent": "LawApp-Freshness/1.0 (OGL compliance)",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")

        if "Commencement" in body and ("No. " in body or "commencement" in body.lower()):
            if "section 25" in body.lower() or "section 152" in body.lower():
                detail["found"] = True
                detail["detail"] = (
                    "ERA 2025 commencement SI DETECTED on legislation.gov.uk. "
                    "Review whether s.25 (qualifying period) and/or s.152 (time limit) "
                    "are commenced. If so: set is_prospective=false on the relevant "
                    "rules rows and update effective_from to the commencement date."
                )
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        detail["detail"] = f"Could not check legislation.gov.uk: {e}"

    if detail["found"]:
        console.print(
            "\n[bold red]ERA 2025 COMMENCEMENT SI DETECTED[/bold red]"
        )
    else:
        console.print(
            "\n[dim]ERA 2025 commencement check: no commencement SI found — "
            "provisional values remain suppressed.[/dim]"
        )

    console.print(f"  URL checked: {detail['url_checked']}")
    console.print(f"  Detail: {detail['detail']}")

    return detail


def main() -> None:
    parser = argparse.ArgumentParser(description="Source freshness report")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT,
                        help=f"Flag sources older than this many days (default: {STALE_DAYS_DEFAULT})")
    parser.add_argument("--fail-if-stale", action="store_true",
                        help="Exit with code 1 if any source is stale (for CI use)")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON to stdout")
    parser.add_argument("--skip-era2025", action="store_true",
                        help="Skip ERA 2025 commencement SI check")
    args = parser.parse_args()

    result = run_report(stale_days=args.stale_days)

    if not args.skip_era2025:
        era = check_era2025_commencement()
        result["era2025_commencement_found"] = era["found"]
        result["era2025_commencement_detail"] = era["detail"]

    if args.json:
        print(json.dumps(result, indent=2, default=str))

    if args.fail_if_stale and not result["all_fresh"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
