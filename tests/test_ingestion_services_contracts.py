"""Contract + negative proof for the repaired ingestion-side services:
lawapp-crawler, lawapp-document-service, lawapp-rag-ingestion.

Proves each wraps real backend logic (not static success), uses the shared
factory (X-Trace-ID), and fails closed. Network/DB-heavy paths are monkeypatched
so the test is deterministic and offline; the fail-closed/whitelist/validation
paths run the REAL backend logic.
"""
from __future__ import annotations

import importlib
import pathlib

import pytest
from fastapi.testclient import TestClient

SERVICES = [
    ("services.lawapp_crawler.app", "lawapp-crawler"),
    ("services.lawapp_document_service.app", "lawapp-document-service"),
    ("services.lawapp_rag_ingestion.app", "lawapp-rag-ingestion"),
]

WHITELISTED = "https://www.legislation.gov.uk/ukpga/1996/18/section/94"
OFFLIST = "https://evil.example.com/fake-law"


def _mod(m):
    return importlib.import_module(m)


def _client(m):
    return TestClient(_mod(m).app)


@pytest.mark.parametrize("modname,name", SERVICES)
def test_contract_factory_and_health(modname, name):
    mod = _mod(modname)
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "from services._common import create_service" in src, f"{name}: not shared factory"
    assert "FastAPI(" not in src, f"{name}: raw FastAPI() present"
    c = TestClient(mod.app)
    h = c.get("/health")
    assert h.status_code == 200 and h.json()["service"] == name
    assert h.json()["status"] == "healthy"
    assert "X-Trace-ID" in h.headers
    assert c.get("/ready").status_code in (200, 503)
    assert len({r.path for r in mod.app.routes}) > 3


# ── lawapp-crawler ──────────────────────────────────────────────────────────

def test_crawler_rejects_offlist_domain():
    """No fake crawl result: a non-whitelisted domain is refused (403) before any
    network call — real backend assert_whitelisted."""
    r = _client("services.lawapp_crawler.app").post(
        "/v1/crawl/approved-source", json={"source_url": OFFLIST, "fetch": True})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "domain_not_whitelisted"


def test_crawler_whitelist_validate_only():
    r = _client("services.lawapp_crawler.app").post(
        "/v1/crawl/approved-source", json={"source_url": WHITELISTED, "fetch": False})
    assert r.status_code == 200 and r.json()["whitelisted"] is True and r.json()["fetched"] is False


def test_crawler_fetch_uses_real_crawler(monkeypatch):
    """Positive path calls the REAL WhitelistCrawler.fetch (monkeypatched to avoid
    network) — proves wiring, not a static response."""
    import backend.core.ingestion.crawler as cr

    def _fake_fetch(self, url):
        return cr.FetchResult(url=url, final_url=url, status_code=200,
                              content="<html>statute</html>",
                              content_hash=cr.content_hash("x"), domain="www.legislation.gov.uk")

    monkeypatch.setattr(cr.WhitelistCrawler, "fetch", _fake_fetch)
    r = _client("services.lawapp_crawler.app").post(
        "/v1/crawl/approved-source", json={"source_url": WHITELISTED, "fetch": True})
    assert r.status_code == 200
    j = r.json()
    assert j["fetched"] is True and j["status_code"] == 200 and j["content_length"] > 0


# ── lawapp-document-service ─────────────────────────────────────────────────

def test_document_missing_tenancy_is_400():
    r = _client("services.lawapp_document_service.app").post(
        "/v1/documents/generate", json={"user_id": "u", "workspace_id": "", "case_id": "",
                                        "document_type": "particulars_of_claim",
                                        "citations": ["x"]})
    assert r.status_code == 400


def test_document_no_citations_is_422():
    """No placeholder citation stored: no citations => rejected."""
    r = _client("services.lawapp_document_service.app").post(
        "/v1/documents/generate", json={"user_id": "u", "workspace_id": "w", "case_id": "c",
                                        "document_type": "particulars_of_claim", "citations": []})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "citations_required"


def test_document_unknown_type_is_422():
    """No fake document created for an unknown type."""
    r = _client("services.lawapp_document_service.app").post(
        "/v1/documents/generate", json={"user_id": "u", "workspace_id": "w", "case_id": "c",
                                        "document_type": "totally_made_up", "citations": ["x"]})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "unknown_document_type"


def test_document_generate_uses_real_generator():
    """Positive path calls backend.core.documents.generate_particulars_of_claim and
    returns a real, non-empty document."""
    body = {
        "user_id": "u", "workspace_id": "w", "case_id": "c",
        "document_type": "particulars_of_claim",
        "citations": ["Employment Rights Act 1996 s.94"],
        "assessment": {"has_viable_claim": "yes", "claim_type": "unfair_dismissal"},
        "facts": {"claimant_name": "A. Claimant", "employer_name": "Employer Ltd"},
    }
    r = _client("services.lawapp_document_service.app").post("/v1/documents/generate", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["document_type"] == "particulars_of_claim" and j["content_length"] > 100


def test_document_retrieval_is_honest_501():
    r = _client("services.lawapp_document_service.app").get("/v1/documents/some-id")
    assert r.status_code == 501


# ── lawapp-rag-ingestion ────────────────────────────────────────────────────

def test_ingestion_requires_authority_ref():
    r = _client("services.lawapp_rag_ingestion.app").post(
        "/v1/ingest/legal-source",
        json={"source_url": WHITELISTED, "source_type": "legislation", "authority_ref": "  ",
              "node_id": "n", "node_type": "legislation", "label": "ERA 1996 s94"})
    assert r.status_code == 422


def test_ingestion_rejects_offlist():
    """No fake ingestion row: off-whitelist source refused (403)."""
    r = _client("services.lawapp_rag_ingestion.app").post(
        "/v1/ingest/legal-source",
        json={"source_url": OFFLIST, "source_type": "legislation", "authority_ref": "X",
              "node_id": "n", "node_type": "legislation", "label": "x"})
    assert r.status_code == 403


def test_ingestion_dependency_failure_is_503_not_200(monkeypatch):
    """Dependency failure must not return 200."""
    import backend.core.ingestion.perpetual_law_brain as plb

    class _Boom:
        def ingest_url(self, *a, **k):
            raise RuntimeError("db/critic unavailable")

    monkeypatch.setattr(plb, "PerpetualLawBrain", _Boom)
    r = _client("services.lawapp_rag_ingestion.app").post(
        "/v1/ingest/legal-source",
        json={"source_url": WHITELISTED, "source_type": "legislation", "authority_ref": "ERA1996",
              "node_id": "n", "node_type": "legislation", "label": "ERA 1996 s94"})
    assert r.status_code == 503


def test_ingestion_critic_rejection_is_422_not_stored(monkeypatch):
    """A critic-rejected document is NOT stored as success — surfaced as 422."""
    import backend.core.ingestion.perpetual_law_brain as plb

    class _Reject:
        def ingest_url(self, *a, **k):
            return {"status": "rejected", "reason": "uncited", "checks": {}}

    monkeypatch.setattr(plb, "PerpetualLawBrain", _Reject)
    r = _client("services.lawapp_rag_ingestion.app").post(
        "/v1/ingest/legal-source",
        json={"source_url": WHITELISTED, "source_type": "legislation", "authority_ref": "ERA1996",
              "node_id": "n", "node_type": "legislation", "label": "ERA 1996 s94"})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "critic_rejected"


def test_ingestion_success_path(monkeypatch):
    """Positive path calls the REAL PerpetualLawBrain (monkeypatched) and returns
    its ingested result — proves wiring, not static success."""
    import backend.core.ingestion.perpetual_law_brain as plb

    class _Ok:
        def ingest_url(self, *a, **k):
            return {"status": "ingested", "run_id": "r1", "chunks_written": 3}

    monkeypatch.setattr(plb, "PerpetualLawBrain", _Ok)
    r = _client("services.lawapp_rag_ingestion.app").post(
        "/v1/ingest/legal-source",
        json={"source_url": WHITELISTED, "source_type": "legislation", "authority_ref": "ERA1996",
              "node_id": "n", "node_type": "legislation", "label": "ERA 1996 s94"})
    assert r.status_code == 200 and r.json()["status"] == "ingested" and r.json()["chunks_written"] == 3
