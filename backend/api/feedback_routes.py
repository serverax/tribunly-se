"""
POST /api/feedback  -  user corrections on assessments (auth-gated).

Scaffold for adaptive feedback loop. Persists to agent_feedback with PII masking.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.core.agent_memory import record_feedback

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackRequest(BaseModel):
    corrected_value: str = Field(..., min_length=1, max_length=8000)
    correction_type: str = Field(default="factual")
    original_excerpt: Optional[str] = Field(default=None, max_length=4000)
    comment: Optional[str] = Field(default=None, max_length=2000)
    case_id: Optional[str] = None
    trace_id: Optional[str] = None


def _require_authenticated_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    from backend.core.user_auth import get_auth_mode, get_current_user

    mode = get_auth_mode()
    user_id = get_current_user(x_user_id, authorization)
    if mode != "none" and not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user_id:
        # Dev mode: require explicit X-User-ID for feedback writes
        if x_user_id:
            return x_user_id
        raise HTTPException(
            status_code=401,
            detail="X-User-ID or Bearer token required for feedback",
        )
    return user_id


@router.post("/feedback", status_code=201)
def submit_feedback(
    body: FeedbackRequest,
    user_id: str = Depends(_require_authenticated_user),
) -> dict:
    """Record a user correction linked to optional case/trace."""
    allowed_types = {"factual", "citation", "deadline", "tone", "other"}
    if body.correction_type not in allowed_types:
        raise HTTPException(status_code=422, detail=f"correction_type must be one of {sorted(allowed_types)}")

    try:
        result = record_feedback(
            user_id=user_id,
            corrected_value=body.corrected_value,
            case_id=body.case_id,
            trace_id=body.trace_id,
            correction_type=body.correction_type,
            original_excerpt=body.original_excerpt,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Feedback storage unavailable")

    return result
