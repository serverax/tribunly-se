#!/usr/bin/env python3
"""
Production readiness check  -  Phase 6A.

Calls the /admin/production-readiness endpoint and prints the result.
Requires ADMIN_API_KEY env var to be set (same as the running server).

Usage:
    docker compose run --rm ingestion python scripts/run_production_readiness.py
    # or, if backend is running locally:
    python scripts/run_production_readiness.py --url http://localhost:8000
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()

    import httpx

    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key:
        print("ERROR: ADMIN_API_KEY environment variable is not set.")
        print("Set it to the same value as the running server's ADMIN_API_KEY.")
        return 1

    try:
        resp = httpx.get(
            f"{args.url}/admin/production-readiness",
            headers={"X-Admin-Key": admin_key},
            timeout=15,
        )
    except Exception as exc:
        print(f"ERROR: Could not connect to {args.url}: {exc}")
        return 1

    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code}  -  {resp.text[:200]}")
        return 1

    data = resp.json()
    print("=" * 70)
    print("LAWAPP  -  PRODUCTION READINESS REPORT")
    print("=" * 70)
    print(json.dumps(data, indent=2))
    print()
    status = data.get("overall_status", "UNKNOWN")
    if status == "NOT_PRODUCTION_READY":
        print(f"Status: {status}")
        print("Blockers:")
        for b in data.get("overall_blockers", []):
            print(f"  ✗ {b}")
    else:
        print(f"Status: {status}")
    print("=" * 70)
    return 0 if status not in ("NOT_PRODUCTION_READY",) else 0


if __name__ == "__main__":
    sys.exit(main())
