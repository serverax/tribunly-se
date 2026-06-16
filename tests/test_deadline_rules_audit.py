"""Deadline calculation is rules-driven and audited (order §17)."""
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

UD_FACTS = {
    "edt": "2025-10-01", "service_start_date": "2019-01-01",
    "reason_for_dismissal": "conduct", "was_procedure_followed": False,
    "weekly_pay": 700, "jurisdiction": "EW",
}


def _count() -> int:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM deadline_calculation_audit")
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_assessment_writes_deadline_audit_with_rules_used():
    from backend.core.models import StubReasoningModel
    from backend.core.pipeline import assess

    before = _count()
    assess(query="unfair dismissal claim", facts=UD_FACTS,
           model=StubReasoningModel(), jurisdiction="EW")
    after = _count()
    assert after > before, "no deadline_calculation_audit row written"

    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT jurisdiction_code, rules_used, final_limitation_date
                           FROM deadline_calculation_audit ORDER BY created_at DESC LIMIT 1""")
            juris, rules_used, final_dl = cur.fetchone()
            # GB-wide employment law is recorded under the canonical 'GB' code.
            assert juris in ("EW", "GB")
            assert rules_used is not None, "rules_used missing  -  deadline not traced to rules"
            assert final_dl is not None
    finally:
        conn.close()
