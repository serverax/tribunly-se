"""lawapp-rag-retrieval — local-corpus hybrid retrieval (NO LLM, NO web).

Wraps backend.core.retrieve.retrieve: deterministic rules + pgvector/BM25
authorities from the local corpus only. source is always "local_corpus" and the
LLM is never called here. X-Trace-ID via the shared factory.
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service

app = create_service("lawapp-rag-retrieval", needs_db=True)


class RetrievalRequest(BaseModel):
    query: str
    claim_type: str = "unfair_dismissal"
    jurisdiction: str = "EW"
    effective_date: str | None = None


@app.post("/v1/retrieve")
def retrieve_endpoint(req: RetrievalRequest):
    from backend.core.retrieve import retrieve
    edt = date.fromisoformat(req.effective_date) if req.effective_date else date.today()
    try:
        bundle = retrieve(req.query, req.claim_type, req.jurisdiction, edt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"retrieval_db_unavailable: {e}")
    return {
        "service": "lawapp-rag-retrieval",
        "source": "local_corpus",
        "llm_called": False,
        "exact_rules": bundle.exact_rules,
        "authorities": bundle.authorities,
        "insufficient_grounding": bundle.insufficient_grounding,
    }
