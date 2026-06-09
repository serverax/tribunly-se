"""legal_sources provenance + FCL-blocked integrity (order §5)."""
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


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN — DB not accessible")


def test_sources_present_with_provenance():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM legal_sources")
            assert cur.fetchone()[0] >= 6
            cur.execute("""SELECT count(*) FROM legal_sources
                           WHERE source_id IS NULL OR source_name IS NULL
                              OR base_url IS NULL OR licence_status IS NULL""")
            assert cur.fetchone()[0] == 0, "legal_sources rows missing provenance"
    finally:
        conn.close()


def test_find_case_law_bulk_blocked_unless_granted():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT count(*) FROM legal_sources
                           WHERE source_type='case_law' OR source_id ILIKE '%case%'
                              OR source_name ILIKE '%case law%'""")
            assert cur.fetchone()[0] >= 1, "no Find Case Law source registered"
            cur.execute("""SELECT count(*) FROM legal_sources
                           WHERE (source_type='case_law' OR source_id ILIKE '%case%'
                                  OR source_name ILIKE '%case law%')
                             AND COALESCE(application_status,'unknown') <> 'granted'
                             AND COALESCE(bulk_allowed,false) = true""")
            assert cur.fetchone()[0] == 0, "FCL bulk allowed without a granted licence"
    finally:
        conn.close()
