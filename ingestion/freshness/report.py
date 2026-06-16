"""
Phase 1  -  Source freshness report.

Queries the `source_freshness` view and prints a table showing every source
with its row count and oldest `last_verified_at`. Flags any source where the
oldest verification is more than STALE_DAYS old.

Acceptance criterion: "Freshness report runs and lists all sources with verification dates."

Usage:
    python -m ingestion.freshness.report
    python -m ingestion.freshness.report --stale-days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from ingestion.db import get_connection

STALE_DAYS_DEFAULT = 30

console = Console()


def run_report(stale_days: int = STALE_DAYS_DEFAULT) -> bool:
    """
    Print the freshness report. Returns True if all sources are fresh, False otherwise.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source, rows, oldest_verified
                FROM source_freshness
                ORDER BY source
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        console.print("[red]No data in source_freshness view  -  has ingestion run?[/red]")
        return False

    now = datetime.now(tz=timezone.utc)
    stale_threshold_days = stale_days

    table = Table(title=f"Source Freshness Report  -  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    table.add_column("Source", style="bold")
    table.add_column("Rows", justify="right")
    table.add_column("Oldest verified_at")
    table.add_column("Age (days)", justify="right")
    table.add_column("Status")

    all_fresh = True
    for source, row_count, oldest_verified in rows:
        if oldest_verified is None:
            age_str = " - "
            status = "[yellow]NO DATA[/yellow]"
            all_fresh = False
        else:
            # oldest_verified may be timezone-aware or naive
            if hasattr(oldest_verified, "tzinfo") and oldest_verified.tzinfo is None:
                oldest_verified = oldest_verified.replace(tzinfo=timezone.utc)
            age_days = (now - oldest_verified).days
            age_str = str(age_days)
            if age_days > stale_threshold_days:
                status = f"[red]STALE (>{stale_threshold_days}d)[/red]"
                all_fresh = False
            else:
                status = "[green]OK[/green]"

        table.add_row(
            source,
            str(row_count or 0),
            str(oldest_verified)[:19] if oldest_verified else " - ",
            age_str,
            status,
        )

    console.print(table)

    if all_fresh:
        console.print("\n[bold green]All sources fresh.[/bold green]")
    else:
        console.print(
            f"\n[bold yellow]Warning: one or more sources are stale or empty. "
            f"Re-run ingestion for flagged sources.[/bold yellow]"
        )

    return all_fresh


def main() -> None:
    parser = argparse.ArgumentParser(description="Source freshness report")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT,
                        help=f"Flag sources older than this many days (default: {STALE_DAYS_DEFAULT})")
    parser.add_argument("--fail-if-stale", action="store_true",
                        help="Exit with code 1 if any source is stale (for CI use)")
    args = parser.parse_args()

    fresh = run_report(stale_days=args.stale_days)
    if args.fail_if_stale and not fresh:
        sys.exit(1)


if __name__ == "__main__":
    main()
