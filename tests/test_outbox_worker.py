"""
Outbox WORKER lifecycle tests (order §17).

Proves the consumer side against the REAL database:
  * claim_batch() transitions pending → processing, sets worker_id, preserves trace_id
  * successful dispatch → processed, with processed_at set and last_error cleared
  * a failing handler increments retry_count, records last_error, returns to pending
  * after max_retries the event moves to dead_letter
  * trace_id is preserved through every transition

Requires a reachable Postgres (compose db). On the host set:
  POSTGRES_HOST=localhost POSTGRES_PORT=5435 POSTGRES_USER=lawapp
  POSTGRES_PASSWORD=lawapp POSTGRES_DB=lawapp
"""

from __future__ import annotations

import uuid

import pytest

from backend.core import outbox, outbox_worker


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
    not _db_available(), reason="Postgres not reachable for outbox worker test"
)


@pytest.fixture
def trace_id():
    tid = str(uuid.uuid4())
    yield tid
    try:
        conn = _conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM outbox_events WHERE trace_id = %s", (tid,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _row(event_id: str):
    """Return (status, retry_count, trace_id, worker_id, processed_at, last_error)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, retry_count, trace_id, worker_id, processed_at, last_error "
                "FROM outbox_events WHERE event_id = %s",
                (event_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _publish(trace_id: str) -> str:
    key = f"wtest:{trace_id}"
    outbox.publish(
        "assessment_complete",
        {"trace_id": trace_id, "claim_type": "unfair_dismissal"},
        trace_id=trace_id,
        idempotency_key=key,
    )
    return key


def test_claim_sets_processing_and_preserves_trace(trace_id):
    key = _publish(trace_id)
    claimed = outbox.claim_batch("test-worker", limit=50)
    assert key in [e["event_id"] for e in claimed]
    status, _retry, stored_trace, worker_id, _proc, _err = _row(key)
    assert status == "processing"
    assert str(stored_trace) == trace_id     # trace preserved on claim
    assert worker_id == "test-worker"
    outbox.mark_processed(key)               # leave queue clean


def test_dispatch_success_marks_processed_with_timestamp(trace_id):
    key = _publish(trace_id)
    outbox_worker.run_once()
    status, _retry, stored_trace, _worker, processed_at, last_error = _row(key)
    assert status == "processed"
    assert processed_at is not None          # processed_at written
    assert last_error is None
    assert str(stored_trace) == trace_id


def test_failure_increments_retry_and_records_error(trace_id, monkeypatch):
    key = _publish(trace_id)

    def _boom(_payload, _trace_id):
        raise RuntimeError("forced handler failure")

    monkeypatch.setitem(outbox_worker.HANDLERS, "assessment_complete", _boom)
    outbox_worker.run_once()                  # exactly one failed attempt

    status, retry_count, stored_trace, _worker, _proc, last_error = _row(key)
    assert retry_count == 1
    assert status == "pending"                # returned to pending for re-claim
    assert last_error and "RuntimeError" in last_error
    assert str(stored_trace) == trace_id      # trace preserved through failure


def test_dead_letter_after_max_retries(trace_id, monkeypatch):
    key = _publish(trace_id)

    def _boom(_payload, _trace_id):
        raise RuntimeError("permanent failure")

    monkeypatch.setitem(outbox_worker.HANDLERS, "assessment_complete", _boom)

    for _ in range(6):
        if _row(key)[0] == "dead_letter":
            break
        outbox_worker.run_once()

    status, retry_count, stored_trace, _worker, _proc, last_error = _row(key)
    assert status == "dead_letter"            # exhausted retries
    assert retry_count >= 3
    assert last_error is not None
    assert str(stored_trace) == trace_id      # trace preserved into dead-letter
