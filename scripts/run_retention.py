#!/usr/bin/env python3
"""
Retention policy runner  -  Phase 6.

Soft-deletes cases and clears PII from handoff leads older than the
configured retention period. Does NOT hard-delete rows  -  audit metadata
is preserved for legal and compliance purposes.

Retention periods (configurable via env vars):
  RETENTION_CASES_DAYS        -  default 90 days
  RETENTION_HANDOFF_DAYS      -  default 30 days

Usage:
    docker compose run --rm ingestion python scripts/run_retention.py
    docker compose run --rm ingestion python scripts/run_retention.py --dry-run
    docker compose run --rm ingestion python scripts/run_retention.py --days-cases 60

GUARDRAIL: Dry run by default  -  use --apply to actually delete.
GUARDRAIL: Only soft-deletes; audit rows preserved.
GUARDRAIL: Reports counts before and after.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_retention(
    days_cases:   int  = 90,
    days_handoff: int  = 30,
    dry_run:      bool = True,
) -> dict:
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Count eligible cases
            cur.execute(
                "SELECT count(*) FROM cases "
                "WHERE created_at < now() - interval '%s days' AND deleted_at IS NULL",
                (days_cases,),
            )
            cases_eligible = cur.fetchone()[0]

            # Count eligible handoff leads
            cur.execute(
                "SELECT count(*) FROM handoff_leads "
                "WHERE created_at < now() - interval '%s days' AND deleted_at IS NULL",
                (days_handoff,),
            )
            leads_eligible = cur.fetchone()[0]

            if dry_run:
                return {
                    "dry_run":         True,
                    "cases_eligible":  cases_eligible,
                    "leads_eligible":  leads_eligible,
                    "cases_deleted":   0,
                    "leads_cleared":   0,
                    "note":            "Dry run  -  pass --apply to execute.",
                }

            # Apply: soft-delete cases
            cur.execute(
                "UPDATE cases SET deleted_at = now() "
                "WHERE created_at < now() - interval '%s days' AND deleted_at IS NULL",
                (days_cases,),
            )
            cases_deleted = cur.rowcount

            # Apply: clear PII from handoff leads
            cur.execute(
                """
                UPDATE handoff_leads
                SET name='[deleted]', email='[deleted]', phone=NULL,
                    case_summary=NULL, name_encrypted=NULL,
                    email_encrypted=NULL, phone_encrypted=NULL,
                    deleted_at=now()
                WHERE created_at < now() - interval '%s days' AND deleted_at IS NULL
                """,
                (days_handoff,),
            )
            leads_cleared = cur.rowcount

            # Record retention run
            cur.execute(
                """
                INSERT INTO retention_runs
                    (records_processed, records_deleted, policy_days, notes)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    cases_eligible + leads_eligible,
                    cases_deleted + leads_cleared,
                    min(days_cases, days_handoff),
                    f"cases_days={days_cases} leads_days={days_handoff}",
                ),
            )

        conn.commit()
        return {
            "dry_run":         False,
            "cases_eligible":  cases_eligible,
            "leads_eligible":  leads_eligible,
            "cases_deleted":   cases_deleted,
            "leads_cleared":   leads_cleared,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Lawapp retention policy runner")
    parser.add_argument("--apply",       action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--days-cases",  type=int, default=int(os.getenv("RETENTION_CASES_DAYS", "90")))
    parser.add_argument("--days-handoff",type=int, default=int(os.getenv("RETENTION_HANDOFF_DAYS", "30")))
    args = parser.parse_args()

    dry_run = not args.apply
    print("=" * 60)
    print(f"LAWAPP RETENTION RUNNER  -  {'DRY RUN' if dry_run else 'LIVE RUN'}")
    print(f"Cases retention: {args.days_cases} days")
    print(f"Handoff leads retention: {args.days_handoff} days")
    print("=" * 60)

    result = run_retention(
        days_cases=args.days_cases,
        days_handoff=args.days_handoff,
        dry_run=dry_run,
    )

    print(f"Cases eligible for deletion: {result['cases_eligible']}")
    print(f"Handoff leads eligible:      {result['leads_eligible']}")
    if not dry_run:
        print(f"Cases soft-deleted:          {result['cases_deleted']}")
        print(f"Handoff leads PII cleared:   {result['leads_cleared']}")
    print()
    print(result.get("note", "✓ Retention applied."))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
