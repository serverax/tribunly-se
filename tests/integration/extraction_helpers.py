"""Helpers for tests that exercise extracted-fact review states."""

from __future__ import annotations

import json

from ingestion.db import get_connection


def seed_extracted_facts(upload_id: str, facts: dict) -> None:
    """Seed the document.extracted_facts JSON used by review/bundle tests."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                   SET extracted_facts = %s::jsonb,
                       extraction_status = 'extracted'
                 WHERE id = %s::uuid
                """,
                (json.dumps(facts), str(upload_id)),
            )
            if cur.rowcount != 1:
                raise AssertionError(f"Could not seed extracted facts for upload: {upload_id}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
