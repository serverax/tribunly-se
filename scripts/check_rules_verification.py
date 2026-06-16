#!/usr/bin/env python3
"""
CI quality gate  -  rules legal verification.

Reads all production-enabled rules (is_prospective=false) from the DB.
Exits with code 1 if any are unverified or failed.

Verification status rules:
  verified            -  passes gate
  case_law_verified   -  passes gate (case law authority)
  prospective         -  exempt from gate (is_prospective=true)
  verification_required  -  FAILS gate (production blocker)
  failed              -  FAILS gate (verification contradicts rule)

Usage (inside ingestion container):
    python scripts/check_rules_verification.py

Usage (via docker compose):
    docker compose run --rm ingestion python scripts/check_rules_verification.py
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_verification(rules: list[dict]) -> dict:
    """
    Check verification status for a list of rule dicts.
    Returns: {passed: bool, failures: list, summary: dict}
    """
    failures = []
    summary = {
        "verified": 0,
        "case_law_verified": 0,
        "prospective": 0,
        "verification_required": 0,
        "failed": 0,
        "column_missing": 0,
    }

    for rule in rules:
        # Skip prospective rules
        if rule.get("is_prospective"):
            summary["prospective"] += 1
            continue

        status = rule.get("verification_status", "COLUMN_MISSING")

        if status == "COLUMN_MISSING":
            summary["verification_required"] += 1
            failures.append({
                "rule_key":        rule.get("rule_key"),
                "effective_from":  str(rule.get("effective_from", "")),
                "issue":           "verification_status column missing  -  run migration 011",
            })
        elif status in ("verified", "case_law_verified"):
            summary[status] += 1
        elif status == "prospective":
            summary["prospective"] += 1
        elif status in ("verification_required", "failed", None):
            key = status or "verification_required"
            summary[key if key in summary else "verification_required"] += 1
            failures.append({
                "rule_key":        rule.get("rule_key"),
                "effective_from":  str(rule.get("effective_from", "")),
                "claim_type":      rule.get("claim_type"),
                "authority_ref":   rule.get("authority_ref"),
                "issue":           f"status={status}  -  production rule unverified",
                "notes":           rule.get("verification_notes") or "",
            })
        else:
            summary["verification_required"] += 1
            failures.append({
                "rule_key": rule.get("rule_key"),
                "issue":    f"Unknown verification_status: {status}",
            })

    passed = len(failures) == 0
    return {"passed": passed, "failures": failures, "summary": summary}


def main() -> int:
    from ingestion.db import get_connection

    print("=" * 70)
    print("LAWAPP  -  RULES LEGAL VERIFICATION GATE")
    print("=" * 70)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check if verification_status column exists
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='rules' AND column_name='verification_status'
            """)
            has_column = cur.fetchone() is not None

            if has_column:
                cur.execute("""
                    SELECT rule_key, claim_type, jurisdiction, effective_from,
                           is_prospective, authority_ref, verification_status,
                           verification_notes
                    FROM rules
                    ORDER BY claim_type, rule_key, effective_from
                """)
            else:
                cur.execute("""
                    SELECT rule_key, claim_type, jurisdiction, effective_from,
                           is_prospective, authority_ref
                    FROM rules
                    ORDER BY claim_type, rule_key, effective_from
                """)

            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()

    if not rows:
        print("⚠ No rules found in DB. Seed the rules first.")
        return 1

    result = check_verification(rows)
    s = result["summary"]

    print(f"\nRules checked: {len(rows)} total")
    print(f"  verified:          {s['verified']}")
    print(f"  case_law_verified: {s['case_law_verified']}")
    print(f"  prospective:       {s['prospective']} (exempt)")
    print(f"  verification_req:  {s['verification_required']}")
    print(f"  failed:            {s['failed']}")
    print()

    if result["failures"]:
        print("FAILURES:")
        for f in result["failures"]:
            print(f"  FAIL {f['rule_key']} (from {f.get('effective_from', '?')})")
            print(f"    {f['issue']}")
            if f.get("notes"):
                print(f"    Notes: {f['notes'][:100]}")
        print()

    if result["passed"]:
        print("PASS RULES VERIFICATION GATE: PASSED")
        print("  All production-enabled rules are verified.")
    else:
        print("FAIL RULES VERIFICATION GATE: FAILED")
        print("  Unverified production rules block deployment.")
    print("=" * 70)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
