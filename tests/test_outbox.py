"""
Outbox end-to-end lifecycle tests (order §17 Event Bus / Queue / Outbox).

Proves against the REAL database:
  * publish() writes a pending event carrying its trace_id
  * duplicate idempotency_key does NOT create a second row
  * the worker drains pending → processed
  * a failing handler retries and finally moves to dead_letter at max_retries

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
    not _db_available(), reason="Postgres not reachable for outbox lifecycle test"
)


@pytest.fixture
def trace_id():
    tid = str(uuid.uuid4())
    yield tid
    # Cleanup: remove any rows this test created.
    try:
        conn = _conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM outbox_events WHERE trace_id = %s", (tid,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _row(event_id: str):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, retry_count, trace_id FROM outbox_events WHERE event_id = %s",
                (event_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def test_publish_creates_pending_event_with_trace(trace_id):
    key = f"test:{trace_id}"
    eid = outbox.publish(
        "assessment_complete", {"trace_id": trace_id}, trace_id=trace_id, idempotency_key=key
    )
    assert eid == key
    status, retry_count, stored_trace = _row(key)
    assert status == "pending"
    assert retry_count == 0
    assert str(stored_trace) == trace_id


def test_duplicate_idempotency_key_is_noop(trace_id):
    key = f"test:{trace_id}"
    first = outbox.publish(
        "assessment_complete", {"trace_id": trace_id}, trace_id=trace_id, idempotency_key=key
    )
    second = outbox.publish(
        "assessment_complete", {"trace_id": trace_id}, trace_id=trace_id, idempotency_key=key
    )
    assert first == key
    assert second is None  # ON CONFLICT DO NOTHING → no row returned
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM outbox_events WHERE event_id = %s", (key,))
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_worker_drains_pending_to_processed(trace_id):
    key = f"test:{trace_id}"
    outbox.publish(
        "assessment_complete", {"trace_id": trace_id}, trace_id=trace_id, idempotency_key=key
    )
    drained = outbox_worker.run_once()
    assert drained >= 1
    status, _retry, _trace = _row(key)
    assert status == "processed"


def test_failing_handler_retries_then_dead_letters(trace_id, monkeypatch):
    key = f"test:{trace_id}"
    outbox.publish(
        "assessment_complete", {"trace_id": trace_id}, trace_id=trace_id, idempotency_key=key
    )

    def _boom(_payload, _trace_id):
        raise RuntimeError("forced handler failure")

    monkeypatch.setitem(outbox_worker.HANDLERS, "assessment_complete", _boom)

    # max_retries defaults to 3; each failed run increments retry_count and
    # returns the event to pending until retry_count+1 >= max_retries.
    for _ in range(5):
        status, _retry, _trace = _row(key)
        if status == "dead_letter":
            break
        outbox_worker.run_once()

    status, retry_count, _trace = _row(key)
    assert status == "dead_letter"
    assert retry_count >= 3
