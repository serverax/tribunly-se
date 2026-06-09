from __future__ import annotations

import json
from uuid import UUID


def record_conversation_event(
    *,
    conversation_id: UUID,
    user_id: str,
    case_id: UUID | None,
    role: str,
    message: str,
    intent: str | None,
    claim_type: str | None,
    pipeline_state: str,
    metadata: dict,
) -> None:
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_events (
                    conversation_id, user_id, case_id, role, message, intent,
                    claim_type, pipeline_state, metadata
                )
                VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(conversation_id),
                    user_id,
                    str(case_id) if case_id else None,
                    role,
                    message,
                    intent,
                    claim_type,
                    pipeline_state,
                    json.dumps(metadata),
                ),
            )
        conn.commit()
    finally:
        conn.close()
