"""
/api/features/*  -  Feature Spec layer (tasks/FEATURE_SPEC_lawapp.md).

Wires spec-facing endpoints to backend.core.feature_spec_service.
Free tools also remain at /api/tools/* for the legacy funnel.
"""

from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core import feature_spec_service as fs
from backend.core import tools

router = APIRouter(prefix="/api/features", tags=["features"])
_limiter = Limiter(key_func=get_remote_address)


def _require_user(x_user_id: Optional[str], authorization: Optional[str]) -> str:
    from backend.core.user_auth import get_current_user, get_auth_mode

    uid = get_current_user(x_user_id, authorization)
    if not uid and get_auth_mode() != "none":
        raise HTTPException(status_code=401, detail="Authentication required")
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(uid)


class DocumentDecodeRequest(BaseModel):
    text: str
    doc_type: str = "letter"


class ClaimAssessmentRequest(BaseModel):
    facts: Union[str, dict]
    matter_id: Optional[str] = None


class CreateMatterRequest(BaseModel):
    title: Optional[str] = None
    case_id: Optional[str] = None
    claim_types: Optional[list[int]] = None


class SaveDeadlineRequest(BaseModel):
    event_type: str
    event_date: str
    claim_type: str = "unfair_dismissal"
    acas_start: Optional[str] = None
    acas_end: Optional[str] = None


class ValuationRequest(BaseModel):
    weekly_pay: float
    months_employed: int
    as_at: Optional[str] = None


class ReferralRequest(BaseModel):
    referral_type: str
    partner_id: Optional[str] = None


@router.get("/knowledge/modules")
@_limiter.limit("60/minute")
def knowledge_modules(request: Request) -> dict:
    """F1: browse modules."""
    return fs.list_knowledge_modules()


@router.get("/knowledge/modules/{module_key}")
@_limiter.limit("60/minute")
def knowledge_module_detail(
    request: Request,
    module_key: str,
    as_at: Optional[str] = None,
) -> dict:
    """F1: module detail with date-scoped corpus excerpts."""
    out = fs.knowledge_module_detail(module_key, as_at=as_at)
    if out.get("error") == "module_not_found":
        raise HTTPException(status_code=404, detail="Module not found")
    return out


@router.post("/document-decode")
@_limiter.limit("20/minute")
def document_decode(request: Request, body: DocumentDecodeRequest) -> dict:
    """F3: anonymous in-memory decoder."""
    if body.text and len(body.text) > 50000:
        raise HTTPException(status_code=413, detail="Document too large for anonymous decode")
    return fs.decode_document(body.text, body.doc_type)


@router.post("/claim-assessment")
@_limiter.limit("30/minute")
def claim_assessment(
    request: Request,
    body: ClaimAssessmentRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F4: claim identifier; optional persist when matter_id + auth."""
    user_id = None
    if body.matter_id:
        user_id = _require_user(x_user_id, authorization)
    return fs.run_claim_assessment(body.facts, matter_id=body.matter_id, user_id=user_id)


@router.post("/matter", status_code=201)
@_limiter.limit("30/minute")
def create_matter(
    request: Request,
    body: CreateMatterRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F5: registration-gated matter creation."""
    uid = _require_user(x_user_id, authorization)
    try:
        return fs.create_matter(
            uid,
            title=body.title,
            case_id=body.case_id,
            claim_types=body.claim_types,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Case not found or not owned")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/matter/{matter_id}/hub")
@_limiter.limit("60/minute")
def matter_hub(
    request: Request,
    matter_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F5: Case Hub aggregate."""
    uid = _require_user(x_user_id, authorization)
    out = fs.matter_hub(matter_id, uid)
    if out.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Matter not found")
    return out


@router.post("/matter/{matter_id}/deadlines", status_code=201)
@_limiter.limit("30/minute")
def save_deadlines(
    request: Request,
    matter_id: str,
    body: SaveDeadlineRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F2 registration save: key_event + deadline."""
    uid = _require_user(x_user_id, authorization)
    try:
        return fs.save_matter_deadlines(
            matter_id,
            uid,
            event_type=body.event_type,
            event_date=body.event_date,
            claim_type=body.claim_type,
            acas_start=body.acas_start,
            acas_end=body.acas_end,
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Matter not found")
    except tools.ToolDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/matter/{matter_id}/valuation", status_code=201)
@_limiter.limit("30/minute")
def save_valuation(
    request: Request,
    matter_id: str,
    body: ValuationRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F7 registration save."""
    uid = _require_user(x_user_id, authorization)
    try:
        return fs.save_valuation(
            matter_id,
            uid,
            weekly_pay=body.weekly_pay,
            months_employed=body.months_employed,
            as_at=body.as_at,
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Matter not found")
    except tools.ToolDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/matter/{matter_id}/referral", status_code=201)
@_limiter.limit("15/minute")
def create_referral(
    request: Request,
    matter_id: str,
    body: ReferralRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """F12 scaffold."""
    if body.referral_type not in ("settlement_signoff", "representation"):
        raise HTTPException(status_code=422, detail="Invalid referral_type")
    uid = _require_user(x_user_id, authorization)
    try:
        return fs.create_referral(
            matter_id,
            uid,
            referral_type=body.referral_type,
            partner_id=body.partner_id,
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Matter not found")


@router.post("/strength")
@_limiter.limit("30/minute")
def strength_preview(request: Request, body: ClaimAssessmentRequest) -> dict:
    """F6: basic strength preview (full rationale registration-gated)."""
    out = fs.run_claim_assessment(body.facts)
    out["full_rationale_gated"] = True
    out["note"] = (
        "ET outcome dataset and case-by-case breakdown require registration. "
        "Preview uses rules and triage signals only."
    )
    return out
