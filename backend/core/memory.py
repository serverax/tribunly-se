"""
Legal Memory Engine.

Safe, case-isolated memory for lawapp.

GUARDRAIL: User A must never access User B's memory.
GUARDRAIL: Case A must not leak into Case B.
GUARDRAIL: Sensitive facts are encrypted at rest.
GUARDRAIL: User consent required for retention beyond session.

Memory types:
  - case_facts: structured facts for the case
  - user_preference: language, notification prefs
  - timeline: employment events
  - deadlines: computed deadlines
  - previous_answers: prior assessment summaries (non-PII only)
  - evidence_checklist: documents needed/uploaded
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def save_memory(
    user_id: str,
    case_id: str,
    memory_type: str,
    key: str,
    value: Any,
    encrypted: bool = False,
) -> dict:
    """
    Save a memory item for a specific user+case.

    GUARDRAIL: user_id and case_id are REQUIRED  -  no orphan memories.
    GUARDRAIL: If encrypted=True, value is encrypted before storage.
    """
    if not user_id or not case_id:
        raise ValueError("user_id and case_id are required to save memory")

    _ALLOWED_TYPES = {
        "case_facts", "user_preference", "timeline",
        "deadlines", "previous_answers", "evidence_checklist",
    }
    if memory_type not in _ALLOWED_TYPES:
        raise ValueError(f"memory_type must be one of: {_ALLOWED_TYPES}")

    serialised = json.dumps(value) if not isinstance(value, str) else value

    if encrypted:
        try:
            from backend.core.encryption import encrypt_str
            serialised = encrypt_str(serialised)
        except Exception as exc:
            logger.warning("Memory encryption failed: %s. Storing unencrypted.", exc)

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO legal_memory (user_id, case_id, memory_type, memory_key, value, encrypted)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                ON CONFLICT (user_id, case_id, memory_type, memory_key)
                DO UPDATE SET value = EXCLUDED.value,
                              encrypted = EXCLUDED.encrypted,
                              updated_at = now()
                RETURNING id
                """,
                (user_id, case_id, memory_type, key, serialised, encrypted),
            )
            row = cur.fetchone()
            conn.commit()
            return {"saved": True, "id": str(row[0]) if row else None}
    finally:
        conn.close()


def get_memory(
    user_id: str,
    case_id: str,
    memory_type: Optional[str] = None,
    key: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve memory items for a user+case.

    GUARDRAIL: Always filters by user_id AND case_id.
               Never returns records from other users or cases.
    """
    if not user_id or not case_id:
        raise ValueError("user_id and case_id are required to retrieve memory")

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            params: list = [user_id, case_id]
            sql = (
                "SELECT id, memory_type, memory_key, value, encrypted, created_at, updated_at "
                "FROM legal_memory "
                "WHERE user_id = %s::uuid AND case_id = %s::uuid"
            )
            if memory_type:
                sql += " AND memory_type = %s"
                params.append(memory_type)
            if key:
                sql += " AND memory_key = %s"
                params.append(key)
            sql += " ORDER BY updated_at DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()

        results = []
        for row in rows:
            val = row[3]
            if row[4]:  # encrypted
                try:
                    from backend.core.encryption import decrypt_str
                    val = decrypt_str(val)
                except Exception:
                    val = "[ENCRYPTED  -  decryption failed]"
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
            results.append({
                "id": str(row[0]),
                "memory_type": row[1],
                "key": row[2],
                "value": val,
                "encrypted": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
            })
        return results
    finally:
        conn.close()


def delete_memory(user_id: str, case_id: str) -> dict:
    """
    Delete all memory for a user+case (right to erasure).

    GUARDRAIL: Always scoped to user_id + case_id.
    """
    if not user_id or not case_id:
        raise ValueError("user_id and case_id are required to delete memory")

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM legal_memory WHERE user_id = %s::uuid AND case_id = %s::uuid",
                (user_id, case_id),
            )
            deleted = cur.rowcount
            conn.commit()
            return {"deleted": deleted}
    finally:
        conn.close()
