"""lawapp-document-service  -  generate legal documents from CONFIRMED facts only.

Wraps backend.core.documents real generators (particulars of claim, schedule of
loss, letter before action, ET1 wages notes). Fail-closed: tenancy required,
citations required, unknown document_type rejected. No fabricated values  -  the
generators surface unconfirmed facts as explicit placeholders. X-Trace-ID via the
shared factory.
"""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service

app = create_service("lawapp-document-service", needs_db=False)

# document_type -> real generator in backend.core.documents
_GENERATORS = {
    "particulars_of_claim": "generate_particulars_of_claim",
    "schedule_of_loss": "generate_schedule_of_loss",
    "letter_before_action": "generate_letter_before_action",
    "et1_support_notes_wages": "generate_et1_support_notes_wages",
}


class DocumentRequest(BaseModel):
    user_id: str
    workspace_id: str
    case_id: str
    document_type: str
    assessment: dict | None = None
    facts: dict | None = None
    citations: list[str] = []


@app.post("/v1/documents/generate")
def generate(req: DocumentRequest):
    if not (req.user_id and req.workspace_id and req.case_id):
        raise HTTPException(status_code=400, detail="user_id, workspace_id and case_id required")
    if not req.citations:
        raise HTTPException(status_code=422, detail={"error": "citations_required"})
    fn_name = _GENERATORS.get(req.document_type)
    if not fn_name:
        raise HTTPException(status_code=422, detail={"error": "unknown_document_type",
                                                     "supported": sorted(_GENERATORS)})
    import backend.core.documents as docs
    generator = getattr(docs, fn_name)
    try:
        content = generator(req.assessment or {}, req.facts or {})
    except Exception as e:
        raise HTTPException(status_code=503, detail={"error": "document_generation_failed", "reason": str(e)})

    safety = docs.safety_check(content)
    return {
        "service": "lawapp-document-service",
        "document_type": req.document_type,
        "content": content,
        "content_length": len(content),
        "safety": safety,
    }


@app.get("/v1/documents/{document_id}")
def get_document(document_id: str):
    # Honest: this service generates documents on demand; persistent retrieval is
    # NOT implemented here (no documents store wired). Controlled 501, never a fake
    # echo of an unknown id.
    raise HTTPException(status_code=501, detail={"error": "document_retrieval_not_implemented",
                                                 "document_id": document_id})
