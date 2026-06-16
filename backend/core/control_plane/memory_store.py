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
        case_id: str,
        outcome_label: str,
        claim_type: str,
        jurisdiction: str,
        strategy_snapshot: dict,
        fact_pattern_tags: Optional[list[str]] = None,
        law_refs: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Persist de-identified outcome to feedback_registry (case_outcome_feedback alias)."""
        fb_id = str(uuid.uuid4())
        try:
            from ingestion.db import get_connection

            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO feedback_registry (
                            id, case_ref_hash, outcome_label, claim_type,
                            jurisdiction_code, strategy_snapshot, fact_pattern_tags,
                            law_refs, pii_stripped, source
                        ) VALUES (
                            %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s, true, 'agent_outcome'
                        )
                        RETURNING id
                        """,
                        (
                            fb_id,
                            _case_ref_hash(case_id),
                            outcome_label,
                            claim_type,
                            jurisdiction,
                            json.dumps(strategy_snapshot),
                            fact_pattern_tags or [],
                            law_refs or [],
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
                return str(row[0]) if row else None
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("case outcome feedback skipped: %s", exc)
            return None
