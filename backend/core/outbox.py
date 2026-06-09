"""
Event Outbox — transactional outbox pattern for async event delivery.
Events written atomically with DB transactions, processed by a background worker.

Event types: legal_source_reindex, assessment_complete, payment_received,
             account_delete_request, evaluation_job, audit_export, human_review_created

Tables: outbox_events
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

_VALID_TYPES = {
    "legal_source_reindex", "assessment_complete", "payment_received",
    "account_delete_request", "evaluation_job", "audit_export", "human_review_created",
    "evidence_parsed",
}


def publish(
    event_type: str,
    payload: dict[str, Any],
    trace_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    conn=None,
) -> Optional[str]:
    """Write event to outbox. Pass conn to write inside existing transaction."""
    if event_type not in _VALID_TYPES:
        logger.warning("outbox.publish unknown event_type=%s", event_type)
        return None
    event_id = idempotency_key or str(uuid.uuid4())
    own_conn = conn is None
    try:
        if own_conn:
            from ingestion.db import get_connection
            conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO outbox_events (event_id,event_type,payload,trace_id,status,retry_count,max_retries)
                    VALUES (%s,%s,%s::jsonb,%s,'pending',0,3)
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING event_id
                    """,
                    (event_id, event_type, json.dumps(payload), trace_id),
                )
                row = cur.fetchone()
                if own_conn:
                    conn.commit()
                return event_id if row else None
        finally:
            if own_conn:
                conn.close()
    except Exception as exc:
        logger.warning("outbox.publish failed type=%s: %s", event_type, exc)
        return None


def mark_processed(event_id: str) -> None:
    """Mark a claimed event processed (processing → processed)."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE outbox_events
                    SET status='processed', processed_at=now(),
                        last_error=NULL, updated_at=now()
                    WHERE event_id=%s
                    """,
                    (event_id,),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("outbox.mark_processed error: %s", exc)


def mark_failed(event_id: str, error: Optional[str] = None) -> None:
    """Record a failed delivery attempt. Increments retry_count and returns the
    event to 'pending' for re-claim, or moves it to 'dead_letter' once
    retry_count+1 >= max_retries. ``error`` is truncated and never contains PII
    (handlers pass exception class/message only)."""
    safe_error = (error or "")[:500] or None
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE outbox_events
                    SET retry_count=retry_count+1,
                        status=CASE WHEN retry_count+1>=max_retries THEN 'dead_letter' ELSE 'pending' END,
                        last_error=%s,
                        updated_at=now()
                    WHERE event_id=%s
                    """,
                    (safe_error, event_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("outbox.mark_failed error: %s", exc)


def claim_batch(worker_id: str, limit: int = 10) -> list[dict]:
    """Atomically claim pending events (pending → processing) in a single
    statement using FOR UPDATE SKIP LOCKED, so concurrent workers never
    double-process the same event. Returns the events claimed by this worker.
    trace_id is preserved on every claimed row."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE outbox_events o
                    SET status='processing', worker_id=%s, updated_at=now()
                    FROM (
                        SELECT event_id FROM outbox_events
                        WHERE status='pending' AND retry_count < max_retries
                        ORDER BY created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    ) c
                    WHERE o.event_id = c.event_id
                    RETURNING o.event_id, o.event_type, o.payload, o.trace_id, o.retry_count
                    """,
                    (worker_id, limit),
                )
                rows = cur.fetchall()
            conn.commit()
            return [{"event_id": r[0], "event_type": r[1], "payload": r[2],
                     "trace_id": r[3], "retry_count": r[4]} for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("outbox.claim_batch error: %s", exc)
        return []


def poll_pending(limit: int = 10) -> list[dict]:
    """Fetch pending events for background worker processing."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id,event_type,payload,trace_id,retry_count
                    FROM outbox_events WHERE status='pending'
                    ORDER BY created_at ASC LIMIT %s FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
                return [{"event_id": r[0], "event_type": r[1], "payload": r[2],
                         "trace_id": r[3], "retry_count": r[4]} for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("outbox.poll_pending error: %s", exc)
        return []


def _set_status(event_id: str, status: str) -> None:
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE outbox_events SET status=%s,updated_at=now() WHERE event_id=%s",
                    (status, event_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("outbox status update skipped: %s", exc)
