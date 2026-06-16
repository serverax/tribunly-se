"""mv_current_employment_legal_chunks excludes unsupported/unprovenanced rows (order §14)."""
from __future__ import annotations

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


def test_matview_exists_and_queryable():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM mv_current_employment_legal_chunks")
            assert cur.fetchone()[0] >= 0
    finally:
        conn.close()


def test_matview_excludes_ni_and_missing_provenance():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM mv_current_employment_legal_chunks WHERE jurisdiction_code='NI'")
            assert cur.fetchone()[0] == 0, "matview leaked unsupported NI rows"
            cur.execute("SELECT count(*) FROM mv_current_employment_legal_chunks WHERE source_url IS NULL OR source_url=''")
            assert cur.fetchone()[0] == 0, "matview has rows missing source_url"
            cur.execute("SELECT count(*) FROM mv_current_employment_legal_chunks WHERE chunk_hash IS NULL")
            assert cur.fetchone()[0] == 0, "matview has rows missing chunk_hash"
    finally:
        conn.close()
