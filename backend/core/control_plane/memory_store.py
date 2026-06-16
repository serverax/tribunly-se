"""
Memory store  -  case outcome feedback and agent memory (consent-gated).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _case_ref_hash(case_id: str) -> str:
    return hashlib.sha256(case_id.encode()).hexdigest()[:32]


class MemoryStore:
    """Read/write masked case and agent memory."""

    def write_agent_memory(
        self,
        *,
        user_id: str,
        case_id: Optional[str],
        memory_key: str,
        memory_value: dict,
        masked_value: dict,
        memory_type: str = "reasoning",
        consent_given: bool = False,
    ) -> Optional[str]:
        if not consent_given or not user_id:
            return None
        mem_id = str(uuid.uuid4())
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO agent_memory (
                            id, user_id, case_id, memory_key, memory_value,
                            masked_value, memory_type, consent_given
                        ) VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s, %s::jsonb,
                            %s::jsonb, %s, %s
                        )
                        """,
                        (
                            mem_id,
                            user_id,
                            case_id,
                            memory_key,
                            json.dumps(memory_value),
                            json.dumps(masked_value),
                            memory_type,
                            consent_given,
                        ),
                    )
                conn.commit()
                return mem_id
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("agent_memory write skipped: %s", exc)
            return None

    def read_agent_memory(
        self,
        user_id: str,
        case_id: Optional[str] = None,
        memory_key: Optional[str] = None,
    ) -> list[dict]:
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    q = "SELECT memory_key, masked_value, memory_type FROM agent_memory WHERE user_id = %s::uuid AND consent_given = true"
                    params: list[Any] = [user_id]
                    if case_id:
                        q += " AND case_id = %s::uuid"
                        params.append(case_id)
                    if memory_key:
                        q += " AND memory_key = %s"
                        params.append(memory_key)
                    cur.execute(q, params)
                    rows = cur.fetchall()
                return [
                    {"memory_key": r[0], "masked_value": r[1], "memory_type": r[2]}
                    for r in rows
                ]
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("agent_memory read skipped: %s", exc)
            return []

    def write_case_outcome_feedback(
        self,
        *,
        user_id: str,
        case_id: str,
        actual_outcome: str,
        predicted_outcome: Optional[str] = None,
        reasoning_gaps: Optional[list] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[str]:
        """Persist outcome feedback to case_outcome_feedback (082)."""
        fb_id = str(uuid.uuid4())
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO case_outcome_feedback (
                            id, user_id, case_id, trace_id,
                            predicted_outcome, actual_outcome, reasoning_gaps
                        ) VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb
                        )
                        RETURNING id
                        """,
                        (
                            fb_id,
                            user_id,
                            case_id,
                            trace_id,
                            predicted_outcome,
                            actual_outcome,
                            json.dumps(reasoning_gaps or []),
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
                return str(row[0]) if row else None
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("case_outcome_feedback write skipped: %s", exc)
            # Fallback: feedback_registry when case_outcome_feedback not migrated
            try:
                from ingestion.db import get_connection

                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO feedback_registry (
                                id, case_ref_hash, outcome_label, strategy_snapshot, pii_stripped, source
                            ) VALUES (%s::uuid, %s, %s, %s::jsonb, true, 'agent_outcome')
                            RETURNING id
                            """,
                            (
                                fb_id,
                                _case_ref_hash(case_id),
                                actual_outcome,
                                json.dumps({"predicted": predicted_outcome, "gaps": reasoning_gaps or []}),
                            ),
                        )
                        row = cur.fetchone()
                    conn.commit()
                    return str(row[0]) if row else None
                finally:
                    conn.close()
            except Exception:
                return None
