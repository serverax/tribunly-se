"""Helpers for integration tests that need DB-backed paid access."""

from __future__ import annotations

from uuid import uuid4

from ingestion.db import get_connection


def mark_case_paid(case_id: str) -> None:
    """Simulate the verified webhook end-state for a saved case."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cases
                   SET payment_status = 'paid',
                       stripe_session_id = %s
                 WHERE id = %s::uuid
                """,
                (f"cs_test_{uuid4().hex}", str(case_id)),
            )
            if cur.rowcount != 1:
                raise AssertionError(f"Could not mark case paid: {case_id}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
