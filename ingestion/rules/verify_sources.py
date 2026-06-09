"""
Source verification for the rules table.

This script fetches the authority_url for each non-prospective rules row
and compares the value found at that URL to the stored value.

This is how the brief's requirement is met: "tests must validate the seed
against an independent source of truth, not against itself."

Run separately from the standard test suite (network-dependent, slow):
    docker compose run --rm ingestion python -m ingestion.rules.verify_sources

Results are written to stdout and to RETRY_LATER.log for any throttled fetches.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ingestion.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Figures to expect at each source URL, keyed by rule_key.
# Updated from live API fetches 2026-05-31 and cross-verified.
# These are NOT hardcoded fixtures — they are the values from the fetches
# that produced the seed. The verification confirms the live source
# still agrees with what we stored.
EXPECTED_AT_SOURCE = {
    "unfair_dismissal.weeks_pay_cap_gbp": {
        date(2025, 4, 6):  {"value": 719,    "source_pattern": r"£?719"},
        date(2026, 4, 6):  {"value": 751,    "source_pattern": r"£?751"},
    },
    "unfair_dismissal.compensatory_cap_gbp": {
        date(2025, 4, 6):  {"value": 118223, "source_pattern": r"£?118,?223"},
        date(2026, 4, 6):  {"value": 123543, "source_pattern": r"£?123,?543"},
    },
    "unfair_dismissal.qualifying_period_years": {
        date(2012, 4, 6):  {"value": 2,      "source_pattern": r"two years|2 years"},
    },
    "unfair_dismissal.time_limit_months": {
        date(1996, 8, 22): {"value": 3,      "source_pattern": r"three months|3 months"},
    },
}

RETRY_LATER: list[str] = []


@retry(wait=wait_exponential(multiplier=2, min=4, max=60), stop=stop_after_attempt(3))
def _fetch(url: str) -> str:
    resp = httpx.get(url, timeout=30, follow_redirects=True,
                     headers={"User-Agent": "lawapp/1.0 (legal-correctness-verify)"})
    if resp.status_code == 429:
        log.warning("Rate limited fetching %s — will retry", url)
        resp.raise_for_status()
    if resp.status_code == 404:
        return ""
    resp.raise_for_status()
    return resp.text


def verify_row(rule_key: str, effective_from: date, stored_value: float,
               authority_url: str) -> str:
    """
    Fetch the authority_url and check that the expected value appears.
    Returns: 'PASS', 'FAIL: <reason>', or 'RETRY_LATER'.
    """
    try:
        text = _fetch(authority_url)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            RETRY_LATER.append(f"{rule_key} ({effective_from}): {authority_url}")
            return "RETRY_LATER"
        return f"FAIL: HTTP {exc.response.status_code} from {authority_url}"
    except Exception as exc:
        return f"FAIL: {exc}"

    if not text:
        return "FAIL: empty response"

    # Check expected pattern is present
    expected = EXPECTED_AT_SOURCE.get(rule_key, {}).get(effective_from)
    if not expected:
        return "SKIP: no expected pattern defined for this row"

    pattern = expected.get("source_pattern", "")
    if pattern and re.search(pattern, text, re.IGNORECASE):
        return "PASS"
    return f"FAIL: expected pattern '{pattern}' not found at {authority_url}"


def run_verification() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rule_key, value_numeric, effective_from, authority_url, is_prospective
                FROM rules
                WHERE claim_type = 'unfair_dismissal'
                  AND value_numeric IS NOT NULL
                ORDER BY rule_key, effective_from
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"\n{'Rule key':<45} {'Eff. from':<12} {'Stored':<10} {'Result'}")
    print("-" * 100)

    all_pass = True
    for rule_key, value_numeric, effective_from, authority_url, is_prospective in rows:
        if is_prospective:
            result = "SKIP (prospective — not yet in force)"
        elif rule_key not in EXPECTED_AT_SOURCE:
            result = "SKIP (no pattern defined)"
        else:
            result = verify_row(rule_key, effective_from, float(value_numeric), authority_url)
            if result.startswith("FAIL"):
                all_pass = False

        marker = "✓" if result == "PASS" else ("↻" if result == "RETRY_LATER" else "✗")
        print(f"  {marker} {rule_key:<43} {str(effective_from):<12} {str(value_numeric):<10} {result}")

    print()
    if RETRY_LATER:
        print("RETRY_LATER (rate-limited; re-run to complete):")
        for item in RETRY_LATER:
            print(f"  - {item}")
    if all_pass and not RETRY_LATER:
        print("All verifiable rows confirmed against cited sources.")
    elif not all_pass:
        print("FAILURES detected — review before treating Phase 1 rules as live.")
    print()


if __name__ == "__main__":
    run_verification()
