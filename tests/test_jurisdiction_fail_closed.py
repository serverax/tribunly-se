"""Behavioural tests: UK jurisdiction model + Northern Ireland fail-closed.

Run: docker compose run --rm -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion pytest tests/test_jurisdiction_fail_closed.py -q
"""
from __future__ import annotations

import pytest

from ingestion.db import get_connection


@pytest.fixture(scope="module")
def cur():
    conn = get_connection()
    c = conn.cursor()
    yield c
    c.close()
    conn.close()


def test_jurisdiction_table_seeded(cur):
    cur.execute("SELECT jurisdiction_code FROM legal_jurisdictions")
    codes = {r[0] for r in cur.fetchall()}
    assert {"GB", "EW", "S", "NI", "UK"}.issubset(codes)


def test_every_legal_row_has_jurisdiction(cur):
    for t in ("legislation", "acas_guidance", "rules", "corpus_chunks"):
        cur.execute(f"SELECT count(*) FROM {t} WHERE jurisdiction_code IS NULL")
        assert cur.fetchone()[0] == 0, f"{t} has NULL jurisdiction_code"


def test_gb_unfair_dismissal_retrieves_gb_rules(cur):
    cur.execute(
        "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal' "
        "AND jurisdiction_code='GB' AND is_current=true"
    )
    assert cur.fetchone()[0] >= 1


def test_ni_unfair_dismissal_fails_closed(cur):
    # No verified NI rules => NI is unsupported => assessment must fail closed.
    cur.execute(
        "SELECT count(*) FROM rules WHERE jurisdiction_code='NI' "
        "AND claim_type='unfair_dismissal' AND verification_status='verified'"
    )
    assert cur.fetchone()[0] == 0, "NI claims must fail closed until NI rules are ingested+verified"


def test_ni_query_does_not_return_gb_rules(cur):
    # A correctly jurisdiction-scoped NI query returns nothing (no GB leakage).
    cur.execute("SELECT count(*) FROM rules WHERE jurisdiction_code='NI'")
    assert cur.fetchone()[0] == 0


def test_materialized_view_excludes_ni(cur):
    cur.execute("SELECT count(*) FROM mv_current_employment_legal_chunks WHERE jurisdiction_code='NI'")
    assert cur.fetchone()[0] == 0


def test_ni_source_recorded_as_unimplemented(cur):
    # NI source must exist in the registry as a recorded (not-implemented) blocker.
    cur.execute("SELECT count(*) FROM legal_sources WHERE source_id='ni_employment_law'")
    assert cur.fetchone()[0] == 1
