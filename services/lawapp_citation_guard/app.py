"""lawapp-citation-guard  -  every LLM legal claim must cite a real local corpus UUID.

Wraps backend.core.agentic.corpus_citation_guard. A citation is valid ONLY if its
UUID exists in `corpus_chunks`. Fabricated UUIDs (e.g. the all-zeros UUID) return
valid=false. X-Trace-ID via the shared factory.
"""
from __future__ import annotations

from pydantic import BaseModel

from services._common import create_service

app = create_service("lawapp-citation-guard", needs_db=True)


class ValidateRequest(BaseModel):
    text: str = ""
    citations: list[str] = []


@app.post("/v1/citations/validate")
def validate(req: ValidateRequest):
    # cached_valid_corpus_uuids: Redis-cached existence on the hot path (<100ms
    # at 100k), pooled DB on miss, and FAIL-CLOSED + cache-degrades-to-DB. The
    # cache can only ever cache a fabricated UUID as negative, never valid.
    from backend.core.agentic.corpus_citation_guard import (
        cached_valid_corpus_uuids,
        extract_uuids,
    )

    claimed = list(req.citations) + extract_uuids(req.text or "")
    if not claimed:
        # No citation at all backing a response is itself invalid (fail-closed).
        return {"service": "lawapp-citation-guard", "valid": False,
                "reason": "no_citation_present", "claimed": [], "valid_uuids": []}

    good = cached_valid_corpus_uuids(claimed)
    # Compare case-insensitively: corpus ids are lowercased in `good`.
    all_real = all(c.lower() in good for c in claimed)
    return {
        "service": "lawapp-citation-guard",
        "valid": all_real,
        "claimed": claimed,
        "valid_uuids": sorted(good),
    }
