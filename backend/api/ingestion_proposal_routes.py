"""
Admin-gated ingestion proposal routes (controlled write-back queue).

GUARDRAIL: Approve enqueues ingestion job via outbox only. No direct rules INSERT.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.core.knowledge_proposer import approve_proposal, list_proposals

router = APIRouter(prefix="/admin", tags=["admin-ingestion-proposals"])


def _require_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> str:
    import os

    configured = os.getenv("ADMIN_API_KEY", "")
    if not configured:
        return "dev-open"
    if x_admin_key != configured:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-Admin-Key header.",
        )
    return x_admin_key


@router.get("/ingestion-proposals")
def get_ingestion_proposals(
    approval_status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _key: str = Depends(_require_admin_key),
) -> dict:
    if approval_status and approval_status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=422, detail="Invalid approval_status")
    items = list_proposals(approval_status=approval_status, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/ingestion-proposals/{proposal_id}/approve")
def post_approve_ingestion_proposal(
    proposal_id: str,
    _key: str = Depends(_require_admin_key),
) -> dict:
    result = approve_proposal(proposal_id, reviewed_by="admin_api")
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "approve_failed"))
    return result
