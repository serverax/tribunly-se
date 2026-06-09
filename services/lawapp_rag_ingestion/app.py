"""lawapp-rag-ingestion — governed corpus ingestion (critic → graph → embed).

Wraps backend.core.ingestion.perpetual_law_brain.PerpetualLawBrain. Every source
is whitelist-enforced (403 off-whitelist) and runs through the audited critic /
graph / embed gates — uncited or critic-rejected rows are NOT stored. No fake
ingestion rows. Fail-closed (503) on any pipeline/DB error. X-Trace-ID via the
shared factory.
"""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service

app = create_service("lawapp-rag-ingestion", needs_db=True)


class IngestRequest(BaseModel):
    source_url: str
    source_type: str            # e.g. "legislation", "acas_guidance", "case_law"
    parser_type: str = "html"
    jurisdiction: str = "EW"
    authority_ref: str          # citation/authority reference (required — no uncited rows)
    node_id: str
    node_type: str
    label: str
    links: list[dict] | None = None


@app.post("/v1/ingest/legal-source")
def ingest_legal_source(req: IngestRequest):
    from backend.core.ingestion.crawler import BlockedDomainError, assert_whitelisted
    from backend.core.ingestion.perpetual_law_brain import PerpetualLawBrain

    if not req.authority_ref.strip():
        raise HTTPException(status_code=422, detail={"error": "authority_ref_required_no_uncited_rows"})
    try:
        assert_whitelisted(req.source_url)
    except BlockedDomainError as e:
        raise HTTPException(status_code=403, detail={"error": "source_not_whitelisted", "reason": str(e)})

    brain = PerpetualLawBrain()
    try:
        result = brain.ingest_url(
            req.source_url, node_id=req.node_id, node_type=req.node_type, label=req.label,
            source_type=req.source_type, parser_type=req.parser_type,
            jurisdiction=req.jurisdiction, authority_ref=req.authority_ref,
            links=req.links)
    except BlockedDomainError as e:
        raise HTTPException(status_code=403, detail={"error": "redirect_off_whitelist", "reason": str(e)})
    except Exception as e:
        raise HTTPException(status_code=503, detail={"error": "ingestion_failed", "reason": str(e)})

    # critic rejection is a real, non-fake outcome — surface as 422, not stored.
    if result.get("status") == "rejected":
        raise HTTPException(status_code=422, detail={"error": "critic_rejected",
                                                     "reason": result.get("reason"),
                                                     "checks": result.get("checks")})
    return {"service": "lawapp-rag-ingestion", **result}
