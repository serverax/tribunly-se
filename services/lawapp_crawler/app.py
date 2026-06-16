"""lawapp-crawler  -  fetch official legal sources, whitelist-enforced.

Wraps backend.core.ingestion.crawler (DOMAIN_WHITELIST / assert_whitelisted /
WhitelistCrawler). Refuses any non-whitelisted domain BEFORE touching the network
(403). No duplicated whitelist; the real backend whitelist is the single source of
truth. X-Trace-ID via the shared factory.
"""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service

app = create_service("lawapp-crawler", needs_db=False)


class CrawlRequest(BaseModel):
    source_url: str
    fetch: bool = False   # when False, only validate the whitelist (no network)


@app.post("/v1/crawl/approved-source")
def crawl(req: CrawlRequest):
    from backend.core.ingestion.crawler import (
        BlockedDomainError, WhitelistCrawler, is_whitelisted, assert_whitelisted)

    # Fail closed on non-whitelisted domains (and redirects)  -  real backend logic.
    try:
        assert_whitelisted(req.source_url)
    except BlockedDomainError as e:
        raise HTTPException(status_code=403, detail={"error": "domain_not_whitelisted", "reason": str(e)})

    if not req.fetch:
        return {"service": "lawapp-crawler", "whitelisted": is_whitelisted(req.source_url),
                "fetched": False, "source_url": req.source_url}

    try:
        result = WhitelistCrawler().fetch(req.source_url)
    except BlockedDomainError as e:
        raise HTTPException(status_code=403, detail={"error": "redirect_off_whitelist", "reason": str(e)})
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "fetch_failed", "reason": str(e)})

    return {
        "service": "lawapp-crawler",
        "fetched": True,
        "final_url": result.final_url,
        "status_code": result.status_code,
        "content_hash": result.content_hash,
        "content_length": len(result.content),
        "domain": result.domain,
    }
