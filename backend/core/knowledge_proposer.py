"""
Controlled write-back: LLM proposes knowledge gaps only.

GUARDRAIL: Creates rows in knowledge.ingestion_proposals only.
           Never INSERT/UPDATE rules, legislation, case_law, or knowledge.provision.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from backend.core.legal_truth_validator import validate_proposal_payload

logger = logging.getLogger(__name__)

_ALLOWED_PROPOSERS = frozenset({"llm", "human"})
_ALLOWED_TYPES = frozenset({
    "missing_rule",
    "missing_provision",
    "missing_case_law",
    "stale_source",
    "other",
})


def propose_knowledge_gap(
    proposal_type: str,
    payload: dict[str, Any],
    *,
    proposed_by: str = "llm",
    trace_id: Optional[str] = None,
    source_verification_status: str = "unverified",
) -> Optional[dict]:
    """Queue a knowledge ingestion proposal for human/admin review."""
    if proposed_by not in _ALLOWED_PROPOSERS:
        raise ValueError(f"proposed_by must be one of {sorted(_ALLOWED_PROPOSERS)}")
    if proposal_type not in _ALLOWED_TYPES:
        proposal_type = "other"
    if source_verification_status not in (
        "unverified", "pending_review", "verified", "rejected"
    ):
        source_verification_status = "unverified"

    verdict = validate_proposal_payload(payload)
    if not verdict.passed:
        logger.info("Proposal rejected by payload validator: %s", verdict.failures)
        return None

    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge.ingestion_proposals (
                        proposed_by, proposal_type, payload,
                        source_verification_status, approval_status, trace_id
                    ) VALUES (%s, %s, %s::jsonb, %s, 'pending', %s)
                    RETURNING id, proposed_by, proposal_type, payload,
                              source_verification_status, approval_status,
                              trace_id, created_at
                    """,
                    (
                        proposed_by,
                        proposal_type,
                        json.dumps(payload),
                        source_verification_status,
                        trace_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "proposed_by": row[1],
                "proposal_type": row[2],
                "payload": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                "source_verification_status": row[4],
                "approval_status": row[5],
                "trace_id": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("knowledge proposal insert failed: %s", exc)
        return None


def propose_ingestion(
    *,
    source_type: str,
    authority_ref: str,
    rationale: str,
    payload: Optional[dict] = None,
    gap_type: str = "retrieval_miss",
    trace_id: Optional[str] = None,
) -> dict:
    """Compatibility wrapper mapping legacy call shape to proposal queue."""
    body = {
        "source_type": source_type,
        "authority_ref": authority_ref,
        "rationale": rationale,
        "gaps": [gap_type],
        **(payload or {}),
    }
    ptype = "missing_rule" if "rule" in gap_type else "missing_provision"
    row = propose_knowledge_gap(ptype, body, trace_id=trace_id)
    if row:
        return {"status": "queued", "proposal_id": row["id"]}
    return {"status": "rejected", "reason": ["queue_insert_failed"]}


def list_proposals(
    approval_status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List ingestion proposals for admin review."""
    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if approval_status:
                    cur.execute(
                        """
                        SELECT id, proposed_by, proposal_type, payload,
                               source_verification_status, approval_status,
                               trace_id, ingestion_job_id, created_at, updated_at
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
                        SELECT id, proposed_by, proposal_type, payload,
                               source_verification_status, approval_status,
                               trace_id, ingestion_job_id, created_at, updated_at
                          FROM knowledge.ingestion_proposals
                         ORDER BY created_at DESC
                         LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()
        finally:
            conn.close()
        out: list[dict] = []
        for row in rows:
            payload = row[3]
            if isinstance(payload, str):
                payload = json.loads(payload)
            out.append({
                "id": str(row[0]),
                "proposed_by": row[1],
                "proposal_type": row[2],
                "payload": payload,
                "source_verification_status": row[4],
                "approval_status": row[5],
                "trace_id": row[6],
                "ingestion_job_id": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
                "updated_at": row[9].isoformat() if row[9] else None,
            })
        return out
    except Exception as exc:
        logger.warning("list_proposals failed: %s", exc)
        return []


def approve_proposal(
    proposal_id: str,
    reviewed_by: str = "admin",
) -> dict:
    """Approve proposal and enqueue ingestion job via outbox only."""
    try:
        from ingestion.db import get_connection
        from backend.core import outbox as _outbox

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
                     WHERE id = %s::uuid
                       AND approval_status = 'pending'
                    RETURNING id, proposal_type, payload, trace_id
                    """,
                    (reviewed_by, proposal_id),
                )
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "error": "not_found_or_not_pending"}

                job_id = f"ingestion-proposal:{row[0]}"
                cur.execute(
                    """
                    UPDATE knowledge.ingestion_proposals
                       SET ingestion_job_id = %s, updated_at = now()
                     WHERE id = %s::uuid
                    """,
                    (job_id, proposal_id),
                )
            conn.commit()
        finally:
            conn.close()

        payload = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
        event_id = _outbox.publish(
            "ingestion_proposal_approved",
            {
                "proposal_id": str(row[0]),
                "proposal_type": row[1],
                "payload": payload,
                "ingestion_job_id": job_id,
            },
            trace_id=row[3],
            idempotency_key=job_id,
        )
        return {
            "ok": True,
            "proposal_id": str(row[0]),
            "ingestion_job_id": job_id,
            "outbox_event_id": event_id,
        }
    except Exception as exc:
        logger.warning("approve_proposal failed: %s", exc)
        return {"ok": False, "error": str(exc)}
