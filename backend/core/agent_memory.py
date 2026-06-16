"""
Agent memory store — PII-masked, consent-gated.

Scaffold for adaptive feedback loop. Does NOT fine-tune models.
Writes go to agent_memory table with masked_value derived from memory_value.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Patterns stripped before persistence in masked_value
_PII_PATTERNS = [
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[email]"),
    (re.compile(r"\b0\d{10,11}\b"), "[phone]"),
    (re.compile(r"\b\d{2}/\d{2}/\d{4}\b"), "[date]"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[date]"),
    (re.compile(r"\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b", re.I), "[postcode]"),
    (re.compile(r"\bNI\s?\d{2}\s?[A-Z]{2}\s?\d[A-Z]{2}\b", re.I), "[ni_number]"),
]


def mask_pii(value: Any) -> Any:
    """Recursively mask obvious PII in strings / dicts / lists."""
    if isinstance(value, str):
        out = value
        for pattern, repl in _PII_PATTERNS:
            out = pattern.sub(repl, out)
        return out
    if isinstance(value, dict):
        return {k: mask_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_pii(v) for v in value]
    return value


def save_agent_memory(
    user_id: str,
    memory_key: str,
    memory_value: Any,
    *,
    case_id: Optional[str] = None,
    memory_type: str = "preference",
    consent_given: bool = False,
) -> dict:
    """
    Persist masked agent memory. Requires consent_given=True for retention.
    """
    if not user_id or not memory_key:
        raise ValueError("user_id and memory_key are required")
    if not consent_given:
        raise ValueError("consent_given is required to save agent memory")

    masked = mask_pii(memory_value)
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_memory (
                    user_id, case_id, memory_key, memory_value, masked_value,
                    memory_type, consent_given
                ) VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING id::text
                """,
                (
                    user_id,
                    case_id,
                    memory_key,
                    json.dumps(memory_value),
                    json.dumps(masked),
                    memory_type,
                    consent_given,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "saved": row is not None,
            "memory_key": memory_key,
            "memory_type": memory_type,
            "pii_masked": True,
        }
    finally:
        conn.close()


def record_feedback(
    user_id: str,
    corrected_value: str,
    *,
    case_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    correction_type: str = "factual",
    original_excerpt: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict:
    """Insert user correction into agent_feedback (PII stripped on text fields)."""
    if not user_id or not corrected_value:
        raise ValueError("user_id and corrected_value are required")

    from ingestion.db import get_connection

    masked_corrected = mask_pii(corrected_value)
    masked_original = mask_pii(original_excerpt) if original_excerpt else None
    masked_comment = mask_pii(comment) if comment else None
    pii_stripped = (
        masked_corrected != corrected_value
        or (original_excerpt and masked_original != original_excerpt)
        or (comment and masked_comment != comment)
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_feedback (
                    user_id, case_id, trace_id, correction_type,
                    original_excerpt, corrected_value, comment,
                    status, pii_stripped
                ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 'pending', %s)
                RETURNING id::text
                """,
                (
                    user_id,
                    case_id,
                    trace_id,
                    correction_type,
                    masked_original,
                    masked_corrected,
                    masked_comment,
                    pii_stripped,
                ),
            )
            fid = cur.fetchone()[0]
        conn.commit()
        return {"feedback_id": fid, "status": "pending", "pii_stripped": pii_stripped}
    finally:
        conn.close()
