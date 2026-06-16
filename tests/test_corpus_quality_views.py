"""source_freshness + corpus_quality_report views work and expose required columns (order §14)."""
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


def test_source_freshness_runs_with_required_columns():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT source_name, source_type, jurisdiction_code, rows_count,
                                  oldest_verified_at, newest_verified_at, stale_rows_count,
                                  last_ingestion_status, last_ingestion_finished_at
                           FROM source_freshness""")
            rows = cur.fetchall()
            assert rows is not None and len(rows) >= 1
    finally:
        conn.close()


def test_corpus_quality_report_runs_with_required_columns():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT source_type, domain, claim_type, jurisdiction_code,
                                  total_chunks, chunks_with_embedding, chunks_without_embedding,
                                  chunks_with_source_url, chunks_without_source_url,
                                  avg_quality_score, unverified_rules_count,
                                  prospective_rows_count, duplicate_hash_count
                           FROM corpus_quality_report""")
            rows = cur.fetchall()
            assert rows is not None and len(rows) >= 1
            cur.execute("SELECT COALESCE(sum(duplicate_hash_count),0) FROM corpus_quality_report")
            assert cur.fetchone()[0] == 0, "duplicate chunk hashes present"
    finally:
        conn.close()
