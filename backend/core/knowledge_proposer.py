"""
Knowledge proposer  -  queue-only ingestion proposals.

GUARDRAIL: NEVER writes rules, legislation, or corpus rows directly.
All proposals land in knowledge.ingestion_proposals for human/ops review.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Optional

from backend.core.legal_truth_validator import validate_proposal_payload

logger = logging.getLogger(__name__)


def _proposal_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def propose_ingestion(
    *,
    source_type: str,
    authority_ref: str,
    rationale: str,
    payload: Optional[dict] = None,
    gap_type: str = "retrieval_miss",
    trace_id: Optional[str] = None,
) -> dict:
    """
    Insert an ingestion proposal into the proposal queue (migration 082).

    Returns {"status": "queued"|"rejected", "proposal_id": ..., "reason": ...}.
    """
    body = {
        "source_type": source_type,
        "authority_ref": authority_ref,
        "rationale": rationale,
        "gap_type": gap_type,
        "payload": payload or {},
        "proposed_action": "ingestion_review",
        "trace_id": trace_id,
    }
    verdict = validate_proposal_payload(body)
    if not verdict.passed:
        return {"status": "rejected", "reason": verdict.failures, "checks": verdict.checks}

    proposal_id = str(uuid.uuid4())
    content_hash = _proposal_hash(body)

    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge.ingestion_proposals (
                        id, source_type, authority_ref, gap_type, rationale,
                        payload, content_hash, status, trace_id
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s,
                        %s::jsonb, %s, 'pending', %s
                    )
                    ON CONFLICT (content_hash) DO NOTHING
                    RETURNING id
                    """,
                    (
                        proposal_id,
                        source_type,
                        authority_ref,
                        gap_type,
                        rationale,
                        json.dumps(body["payload"]),
                        content_hash,
                        trace_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            if row:
                return {"status": "queued", "proposal_id": str(row[0]), "content_hash": content_hash}
            return {"status": "duplicate", "content_hash": content_hash}
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Proposal queue unavailable: %s", exc)
        return {"status": "rejected", "reason": [str(exc)], "offline_safe": True}
