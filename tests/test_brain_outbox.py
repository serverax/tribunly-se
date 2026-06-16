"""
Brain → Outbox integration proof (order §2 Brain wiring + §17 Outbox).

Proves that run_brain() Step 18b publishes a REAL ``assessment_complete`` event
to the REAL outbox when the assessment status is 'ok', and that the REAL worker
then drains it pending → processed.

Only ``backend.core.pipeline.assess`` is substituted  -  that is the
corpus/LLM-dependent stage which is gated on owner blocker #13 (legal corpus
ingestion). Everything else is real: the full brain pipeline, the audit write,
Step 18b publish, the worker claim (FOR UPDATE SKIP LOCKED), and the database.

Requires a reachable Postgres (compose db). On the host set:
  POSTGRES_HOST=localhost POSTGRES_PORT=5435 POSTGRES_USER=lawapp
  POSTGRES_PASSWORD=lawapp POSTGRES_DB=lawapp
"""

from __future__ import annotations

import pytest

from backend.core import brain as brain_mod
from backend.core import outbox_worker


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_available() -> bool:
    try:
        c = _conn()
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(), reason="Postgres not reachable for brain→outbox test"
)

_UD_FACTS = {
    "edt": "2025-10-01",
    "service_start_date": "2019-01-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": False,
    "weekly_pay": 700,
    "jurisdiction": "EW",
}


@pytest.fixture
def db_isolation():
    """Hermetic DB state (db_setup / db_teardown) for the brain->outbox proof.

    Cross-test bleed vector: ``outbox_worker.run_once()`` drains the GLOBAL pending
    queue, so a stale non-terminal event left by another test could be claimed
    (and a malformed one could abort the drain) before THIS test's event is
    processed  -  making the test pass alone but flake in a batch. db_setup gives the
    worker a deterministic clean queue; db_teardown removes whatever this test
    created. Safe: the compose ``db`` is a disposable test database, and we only
    delete non-``processed`` (stale) rows, never terminal audit history.
    """
    created: list[str] = []

    def _clear_pending():
        try:
            conn = _conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM outbox_events WHERE status <> 'processed'")
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── db_setup: deterministic clean queue ──
    _clear_pending()
    yield created
    # ── db_teardown: remove this test's rows + any pending it left behind ──
    try:
        conn = _conn()
        with conn.cursor() as cur:
            for tid in created:
                cur.execute("DELETE FROM outbox_events WHERE trace_id = %s", (tid,))
        conn.commit()
        conn.close()
    except Exception:
        pass
    _clear_pending()


def _event_for(trace_id: str):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_type, status, trace_id, processed_at "
                "FROM outbox_events WHERE trace_id = %s",
                (trace_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def test_brain_publishes_assessment_complete_then_worker_processes(monkeypatch, db_isolation):
    # Substitute ONLY the corpus/LLM-dependent assessment with the grounded 'ok'
    # result production returns once the legal corpus is ingested (owner #13).
    def _fake_assess(message, facts, model=None, jurisdiction="EW", graph_context=None, **kwargs):
        return {
            "status": "ok",
            "assessment": {
                "verdict": "likely_eligible",
                "citations": [
                    {"source_id": "ERA1996_s94", "quote": "right not to be unfairly dismissed"}
                ],
            },
        }

    monkeypatch.setattr("backend.core.pipeline.assess", _fake_assess)

    result = brain_mod.run_brain(
        message="I was dismissed after 6 years with no appeal.",
        facts=_UD_FACTS,
        user_id=None,
        case_id=None,
        jurisdiction="EW",
    )
    trace_id = result["trace"]["trace_id"]
    db_isolation.append(trace_id)

    assert result["assessment"]["status"] == "ok"

    # Step 18b must have published a real pending event carrying this trace_id.
    row = _event_for(trace_id)
    assert row is not None, "Brain Step 18b did not publish an outbox event for an 'ok' assessment"
    event_type, status, stored_trace, processed_at = row
    assert event_type == "assessment_complete"
    assert status == "pending"
    assert str(stored_trace) == trace_id
    assert processed_at is None

    # The real worker drains pending → processed.
    outbox_worker.run_once()
    event_type, status, stored_trace, processed_at = _event_for(trace_id)
    assert status == "processed"
    assert processed_at is not None
    assert str(stored_trace) == trace_id   # trace preserved end-to-end
