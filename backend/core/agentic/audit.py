"""
Agent-run audit persistence (AC-010). Writes one ``agent_runs`` row per agent
invocation so every run is traceable by ``trace_id`` for OTEL correlation.

Phase-2 golden rule: the trace_id must flow from the adapter to the DB. Writes
are fail-open (never break the workflow) but log on failure.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def record_agent_run(
    *,
    trace_id: str,
    case_id: str,
    agent_name: str,
    model_route: str,
    status: str,
    validation_passed: bool,
    model_name: str = "",
    prompt_id: str = "",
    prompt_version: str = "",
    input_schema_version: str = "1.0",
    output_schema_version: str = "1.0",
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    grounding_score: Optional[float] = None,
    confidence_score: Optional[float] = None,
    escalated: bool = False,
    failure_reason: Optional[str] = None,
    conn=None,
) -> Optional[str]:
    """Insert an agent_runs row. Returns the new id (uuid str) or None."""
    own = conn is None
    try:
        if own:
            from ingestion.db import get_connection
            conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_runs (
                        trace_id, case_id, agent_name, model_name, model_route,
                        prompt_id, prompt_version, input_schema_version, output_schema_version,
                        started_at, completed_at, status, validation_passed,
                        grounding_score, confidence_score, escalated, failure_reason
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        COALESCE(%s::timestamptz, now()), %s::timestamptz, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        trace_id, case_id, agent_name, model_name, model_route,
                        prompt_id, prompt_version, input_schema_version, output_schema_version,
                        started_at, completed_at, status, validation_passed,
                        grounding_score, confidence_score, escalated, failure_reason,
                    ),
                )
                row = cur.fetchone()
            if own:
                conn.commit()
            return str(row[0]) if row else None
        finally:
            if own and conn is not None:
                conn.close()
    except Exception as exc:
        logger.warning("record_agent_run failed trace_id=%s: %s", trace_id, exc)
        return None
