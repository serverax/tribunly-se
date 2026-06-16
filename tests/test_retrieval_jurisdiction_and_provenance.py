"""Retrieval is jurisdiction-filtered and provenance-bound (order §16)."""
from __future__ import annotations

from datetime import date

import pytest


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up():
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  DB not accessible")


def test_gb_unfair_dismissal_retrieves_gb_rules():
    # GB retrieves rules; jurisdiction filtering is enforced in retrieve_rules' WHERE
    # clause and proven by test_ni_does_not_retrieve_gb_rules (NI -> []).
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules("unfair_dismissal", "EW", date.today())
    assert len(rules) > 0, "no GB unfair dismissal rules retrieved"
    assert all(r.get("rule_key") for r in rules)


def test_ni_fails_closed():
    from backend.core.retrieve import jurisdiction_supported
    assert jurisdiction_supported("NI") is False, "NI must be unsupported (fail closed)"


def test_ni_does_not_retrieve_gb_rules():
    from backend.core.retrieve import retrieve_rules
    rules = retrieve_rules("unfair_dismissal", "NI", date.today())
    assert rules == [], "NI retrieved rules  -  must not inherit GB law"


def test_retrieved_bundle_has_provenance():
    from backend.core.retrieve import retrieve
    bundle = retrieve("unfair dismissal time limit", "unfair_dismissal", "EW", date.today())
    for r in bundle.exact_rules:
        assert r.get("authority_ref") or r.get("authority") or r.get("source_url"), \
            "retrieved rule lacks authority/provenance"
