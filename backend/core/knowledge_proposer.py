"""
Knowledge proposer  -  queue-only ingestion proposals.

GUARDRAIL: NEVER writes rules, legislation, or corpus rows directly.
All proposals land in knowledge.ingestion_proposals (082) for human/ops review.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Optional

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
    Insert an ingestion proposal into knowledge.ingestion_proposals (082).

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
    merged_payload = {
        **body["payload"],
        "source_type": source_type,
        "authority_ref": authority_ref,
        "rationale": rationale,
        "gap_type": gap_type,
        "content_hash": content_hash,
    }

    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge.ingestion_proposals (
                        id, proposed_by, proposal_type, payload,
                        source_verification_status, approval_status, trace_id
                    ) VALUES (
                        %s::uuid, 'llm', %s, %s::jsonb,
                        'pending_review', 'pending', %s
                    )
                    RETURNING id
                    """,
                    (
                        proposal_id,
                        gap_type,
                        json.dumps(merged_payload),
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


def propose_knowledge_gap(
    gap_type: str,
    payload: dict,
    *,
    proposed_by: str = "llm",
    trace_id: Optional[str] = None,
) -> dict:
    """
    Queue a knowledge-gap proposal for human/ops review.

    Compatibility entry point used by the brain path. It writes only to the
    proposal queue and never applies rules, legislation, or corpus rows.
    """
    if proposed_by not in {"llm", "human"}:
        raise ValueError("proposed_by must be 'llm' or 'human'")

    proposal_id = str(uuid.uuid4())
    body = {
        "gap_type": gap_type,
        "payload": payload or {},
        "trace_id": trace_id,
    }
    content_hash = _proposal_hash(body)
    merged_payload = {
        **body["payload"],
        "gap_type": gap_type,
        "content_hash": content_hash,
    }

    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge.ingestion_proposals (
                    id, proposed_by, proposal_type, payload,
                    source_verification_status, approval_status, trace_id
                ) VALUES (
                    %s::uuid, %s, %s, %s::jsonb,
                    'pending_review', 'pending', %s
                )
                RETURNING id, proposed_by, proposal_type, payload,
                          source_verification_status, approval_status, trace_id, created_at
                """,
                (
                    proposal_id,
                    proposed_by,
                    gap_type,
                    json.dumps(merged_payload),
                    trace_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return {}
        return {
            "id": str(row[0]),
            "proposed_by": row[1],
            "proposal_type": row[2],
            "payload": row[3],
            "source_verification_status": row[4],
            "approval_status": row[5],
            "trace_id": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "content_hash": content_hash,
        }
    finally:
        conn.close()


def list_proposals(*, approval_status: str | None = None, limit: int = 50) -> list[dict]:
    """List queued ingestion proposals for admin review."""
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if approval_status:
                cur.execute(
                    """
                    SELECT id, proposed_by, proposal_type, payload, approval_status,
                           source_verification_status, trace_id, created_at
                    FROM knowledge.ingestion_proposals
                    WHERE approval_status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (approval_status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, proposed_by, proposal_type, payload, approval_status,
                           source_verification_status, trace_id, created_at
                    FROM knowledge.ingestion_proposals
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "proposed_by": r[1],
                "proposal_type": r[2],
                "payload": r[3],
                "approval_status": r[4],
                "source_verification_status": r[5],
                "trace_id": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    finally:
        conn.close()


def approve_proposal(proposal_id: str, *, reviewed_by: str = "admin") -> dict:
    """Mark proposal approved and enqueue ingestion job metadata (no direct rules write)."""
    from ingestion.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE knowledge.ingestion_proposals
                   SET approval_status = 'approved',
                       reviewed_by = %s,
                       reviewed_at = now(),
                       updated_at = now()
                 WHERE id = %s::uuid AND approval_status = 'pending'
                 RETURNING id, proposal_type, payload
                """,
                (reviewed_by, proposal_id),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "proposal_not_found_or_not_pending"}
            job_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO ingestion_jobs (
                    id, worker_type, queue_name, document_id, postgres_status, metadata
                ) VALUES (
                    %s::uuid, 'legislation', 'ingestion-legislation', %s, 'pending', %s::jsonb
                )
                """,
                (
                    job_id,
                    proposal_id,
                    json.dumps({"proposal_id": proposal_id, "proposal_type": row[1]}),
                ),
            )
        conn.commit()
        return {"ok": True, "proposal_id": proposal_id, "ingestion_job_id": job_id}
    except Exception as exc:
        conn.rollback()
        logger.warning("approve_proposal failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()
