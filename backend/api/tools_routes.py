"""
/api/tools/* — free, no-login PREVIEW tools.

Thin HTTP layer over backend/core/tools.py. These endpoints are the public funnel:
anonymous visitors may run a quick screen / estimate and see a preview. The full,
saved, citation-backed result lives behind login + the governed brain pipeline.

Every statutory value used by these tools is loaded from the effective-dated
`rules` table (DB-first, fail-closed) — see backend/core/tools.py. When a required
statutory rule is missing the tool raises ToolDataUnavailable and this layer maps
it to an honest 503, never a fabricated legal answer (constitution §9).

Endpoints:
  POST /api/tools/claim-checker          {facts}
  POST /api/tools/deadline-calculator    {event_date, event_type}
  POST /api/tools/compensation-estimate  {weekly_pay, months_employed}
  POST /api/tools/acas-prep              {case_summary}
"""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core import tools

router = APIRouter(prefix="/api/tools", tags=["tools"])

# Per-IP limiter so the public (unauthenticated) preview funnel can't be abused.
# RateLimitExceeded is handled by the app-level handler registered in main.py.
_limiter = Limiter(key_func=get_remote_address)


# ── request models ────────────────────────────────────────────────────────────

class ClaimCheckerRequest(BaseModel):
    facts: Union[str, dict]


class DeadlineRequest(BaseModel):
    event_date: str
    event_type: str
    jurisdiction: str = "EW"


class CompensationRequest(BaseModel):
    weekly_pay: float
    months_employed: int
    jurisdiction: str = "EW"


class AcasPrepRequest(BaseModel):
    case_summary: Union[str, dict]


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/claim-checker")
@_limiter.limit("30/minute")
def claim_checker(request: Request, body: ClaimCheckerRequest) -> dict:
    """Preliminary claim screen. No login required (preview)."""
    return tools.check_claim(body.facts)


@router.post("/deadline-calculator")
@_limiter.limit("30/minute")
def deadline_calculator(request: Request, body: DeadlineRequest) -> dict:
    """Employment Tribunal limitation date. No login required (preview)."""
    try:
        return tools.calculate_deadline(body.event_date, body.event_type, body.jurisdiction)
    except tools.ToolDataUnavailable as exc:
        # Fail closed — statutory rule missing. Honest 503, never a fabricated date.
        raise HTTPException(status_code=503, detail=str(exc))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


@router.post("/compensation-estimate")
@_limiter.limit("30/minute")
def compensation_estimate(request: Request, body: CompensationRequest) -> dict:
    """Statutory basic-award estimate. No login required (preview)."""
    try:
        return tools.estimate_compensation(body.weekly_pay, body.months_employed, body.jurisdiction)
    except tools.ToolDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


@router.post("/acas-prep")
@_limiter.limit("30/minute")
def acas_prep(request: Request, body: AcasPrepRequest) -> dict:
    """ACAS Early Conciliation prep checklist. No login required (preview)."""
    return tools.prepare_acas(body.case_summary)
