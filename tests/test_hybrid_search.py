"""End-to-end hybrid retrieval tests (backend/core/retrieve.py).

Proves the high-accuracy retrieval path against the LIVE local corpus:

  - lexical (PostgreSQL full-text / ts_rank) + semantic (pgvector cosine)
    fused with Reciprocal Rank Fusion (k=60),
  - exact-citation priority (a query naming "s.111" surfaces ERA 1996 s.111),
  - every returned authority is a LOCAL-DB row carrying citation + source_url
    + jurisdiction + effective window (architecture correction  -  no LLM memory,
    no inferred/approximate sources),
  - retrieval is domain-scoped and FAILS CLOSED on an unknown/disabled domain.

DB-backed: skips cleanly when the local Docker DB is unreachable. Run:
  docker compose run --rm -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp \
      ingestion pytest tests/test_hybrid_search.py -q
"""
from __future__ import annotations

from datetime import date

import pytest


def _db_up() -> bool:
    try:
        from ingestion.db import get_connection
        c = get_connection()
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN  -  local DB not accessible")

_QUERY = "unfair dismissal time limit section 111"
_CLAIM = "unfair_dismissal"


@pytest.fixture(scope="module")
def bundle():
    from backend.core.retrieve import retrieve
    return retrieve(_QUERY, _CLAIM, "EW", date.today())


def test_hybrid_returns_grounded_authorities(bundle):
    """Hybrid retrieval returns real authorities and is not insufficient for a
    well-grounded GB claim."""
    assert bundle.insufficient_grounding is False
    assert len(bundle.authorities) > 0, "no authorities retrieved for a grounded query"


def test_every_authority_is_local_db_with_source_url(bundle):
    """Architecture correction: every result is a local-DB row with a citation
    AND a source_url. No authority may be returned without provenance."""
    assert bundle.authorities, "expected authorities"
    for a in bundle.authorities:
        assert a.get("type") in {"legislation", "case_law", "acas"}, a.get("type")
        assert (a.get("authority_ref") or a.get("cite")), f"authority missing citation: {a}"
        assert a.get("url"), f"authority missing source_url: {a}"
        # source_url must be a real external authority URL, never an LLM artefact.
        assert str(a["url"]).startswith("http"), f"non-URL source: {a['url']}"


def test_every_authority_carries_jurisdiction_and_effective_fields(bundle):
    """Each authority surfaces jurisdiction + effective_from/effective_to keys so
    the answer layer can prove (and date-check) provenance. Values may be None
    when the underlying row is undated  -  the KEYS must always be present, and a
    present jurisdiction must be a known GB-family code for an EW query."""
    for a in bundle.authorities:
        assert "jurisdiction" in a and "effective_from" in a and "effective_to" in a, a
        if a.get("jurisdiction") is not None:
            assert a["jurisdiction"] in {"GB", "EW", "S", "UK", "NI"}, a["jurisdiction"]


def test_rrf_provenance_present(bundle):
    """RRF fusion provenance is preserved: each authority records its fused score
    and which path(s) found it, so the ranking is auditable."""
    for a in bundle.authorities:
        assert a.get("rrf_score") is not None, f"missing rrf_score: {a}"
        assert a.get("retrieval") in {"lexical", "vector", "hybrid"}, a.get("retrieval")


def test_exact_citation_query_surfaces_named_section(bundle):
    """A query naming 's.111' must surface ERA 1996 s.111 at the very top with
    exact_citation_match=True  -  an exact authority outranks a merely-similar one."""
    top = bundle.authorities[0]
    assert top.get("exact_citation_match") is True, f"top result not an exact match: {top}"
    ref = (top.get("authority_ref") or top.get("cite") or "").lower()
    assert "111" in ref, f"expected s.111 at rank 1, got: {ref}"


def test_retrieval_is_domain_scoped_fail_closed():
    """Retrieval validates the domain FAIL-CLOSED: an unknown domain raises rather
    than silently serving an unsupported/placeholder corpus."""
    from backend.core.retrieve import retrieve
    from backend.domains.registry import UnsupportedDomainError

    with pytest.raises(UnsupportedDomainError):
        retrieve(_QUERY, _CLAIM, "EW", date.today(), domain="__nonexistent_domain__")
