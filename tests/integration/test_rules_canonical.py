"""
Guard test: rules table must contain only canonical rule_key series.

This test FAILS if a duplicate or orphan series ever reappears.
It is the regression guard against the correctness bug where two rule_key
series existed simultaneously (e.g. compensatory_cap_amount AND
compensatory_cap_gbp), causing retrieval to silently select from an
unverified duplicate rather than the authoritative row.

The canonical set is defined in seed_unfair_dismissal.CANONICAL_KEYS.
Any row in the DB with a rule_key not in that set is a bug.

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_rules_canonical.py -v
"""

import pytest
from ingestion.db import get_connection
from ingestion.rules.seed_unfair_dismissal import CANONICAL_KEYS


def test_no_duplicate_or_unknown_rule_key_series():
    """
    Every rule_key in the rules table must be in the canonical set.
    Fails immediately if a second series is introduced — no silent doubling.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT rule_key FROM rules WHERE claim_type = 'unfair_dismissal'"
            )
            db_keys = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    unknown = db_keys - CANONICAL_KEYS
    assert not unknown, (
        f"Non-canonical rule_key(s) found in the rules table: {sorted(unknown)}. "
        f"This means a second series was introduced. "
        f"Delete the orphaned rows and update CANONICAL_KEYS if the new key is intentional."
    )


def test_all_canonical_keys_present():
    """
    Every canonical key must exist in the DB with at least one current row.
    Catches accidental deletion of an entire rule series.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT rule_key FROM rules
                WHERE claim_type = 'unfair_dismissal'
                  AND is_prospective = false
                """
            )
            current_keys = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    missing = CANONICAL_KEYS - current_keys
    assert not missing, (
        f"Canonical rule_key(s) have no current (non-prospective) row in the DB: "
        f"{sorted(missing)}. Either re-seed or remove the key from CANONICAL_KEYS."
    )


def test_no_prospective_rows_returned_by_live_query():
    """
    The live retrieval query must never return a prospective row.
    Regression against the bug where is_prospective=True rows could have
    leaked through if the query filter was accidentally removed.
    """
    from backend.core.retrieve import retrieve_rules
    from datetime import date

    for edt in [date(2026, 5, 1), date(2026, 12, 31), date(2027, 6, 1)]:
        rules = retrieve_rules("unfair_dismissal", "EW", edt)
        prospective_leaked = [r for r in rules if r.get("is_prospective")]
        assert not prospective_leaked, (
            f"Prospective rows leaked into live retrieval for EDT {edt}: "
            f"{[r['rule_key'] for r in prospective_leaked]}"
        )


def test_each_monetary_rule_has_exactly_one_current_row_per_edt():
    """
    For a given EDT, each monetary rule_key must resolve to exactly ONE row.
    If there are two series, DISTINCT ON (rule_key) may silently pick either.
    This test confirms a specific EDT gets one value, not two.
    """
    from backend.core.retrieve import retrieve_rules
    from datetime import date

    rules = retrieve_rules("unfair_dismissal", "EW", date(2026, 5, 1))
    key_counts: dict[str, int] = {}
    for r in rules:
        key_counts[r["rule_key"]] = key_counts.get(r["rule_key"], 0) + 1

    duplicates = {k: v for k, v in key_counts.items() if v > 1}
    assert not duplicates, (
        f"Duplicate rule_keys returned by retrieve_rules for EDT 2026-05-01: "
        f"{duplicates}. This means the DISTINCT ON query is not deduplicating correctly."
    )
