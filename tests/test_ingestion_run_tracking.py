"""corpus_ingestion_runs tracking + blocker recording (order §6, §8)."""
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


def test_ingestion_runs_recorded():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM corpus_ingestion_runs")
            assert cur.fetchone()[0] >= 1, "no ingestion runs tracked"
    finally:
        conn.close()


def test_fcl_blocker_recorded():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT count(*) FROM corpus_ingestion_runs
                           WHERE source_id='find_case_law' AND status='blocked'""")
            assert cur.fetchone()[0] >= 1, "Find Case Law blocker not recorded in corpus_ingestion_runs"
    finally:
        conn.close()


def test_run_has_status_and_validation_columns():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT column_name FROM information_schema.columns
                           WHERE table_name='corpus_ingestion_runs'""")
            cols = {r[0] for r in cur.fetchall()}
            assert {"status", "validation_passed", "rows_ingested"}.issubset(cols)
    finally:
        conn.close()
