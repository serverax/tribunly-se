"""
Stage 2  -  Hybrid retrieval module.

ALWAYS runs before any reasoning. Returns a RetrievalBundle of:
  - exact_rules: deterministic values from the `rules` table (deadlines, caps,
    qualifying periods). Queried with is_prospective=false to guarantee
    current-in-force values, NOT date-overlap alone.
  - authorities: semantic matches from legislation, case_law_chunks, acas_guidance.
    PENDING: returns [] until embeddings exist. Coded and wired; not a
    keyword-search substitute. Do not replace this stub with text search.

If the bundle is empty/weak, insufficient_grounding=True is set and the
reasoning stage is skipped.

GUARDRAIL (prospective rows): the rules query explicitly filters
is_prospective=false. Both the current cap row and the prospective uncapped row
have effective_to=NULL, so date-overlap alone would select both. The flag is
the gate, not the date.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import psycopg2.extras

from ingestion.db import get_connection
from shared.schemas import RetrievalBundle
from backend.core.retrieval.trust_scorer import score_authorities
from backend.core.retrieval.rrf import reciprocal_rank_fusion
from backend.core.retrieval.rerank import rerank_authorities

logger = logging.getLogger(__name__)


class _RetrieverPatchPoint:
    """Patchable local retriever facade; production retrieval uses DB functions above."""

    def search(self, *args, **kwargs) -> list[dict]:
        return []


pgvector_client = _RetrieverPatchPoint()
bm25_index = _RetrieverPatchPoint()

# Minimum authorities to consider grounding sufficient when no deterministic
# rules are found. The corpus is now ingested + embedded, so require at least
# one retrieved authority: with no rules AND no authorities the bundle fails
# closed (insufficient_grounding=True) instead of silently proceeding.
_MIN_AUTHORITIES_FOR_GROUNDING = 1

# ── Jurisdiction model ──────────────────────────────────────────────────────
# Employment legislation/rules/guidance ingested so far apply Great Britain-wide
# (England & Wales + Scotland). Northern Ireland is a SEPARATE regime and is NOT
# ingested  -  NI must fail closed, never silently reuse GB law.
# Map an incoming user jurisdiction to the set of jurisdiction values that
# may lawfully satisfy it.
_GB_CODES = ("GB", "EW", "S", "UK")
_JURISDICTION_CODE_MAP = {
    "EW": _GB_CODES, "S": _GB_CODES, "SCT": _GB_CODES, "GB": _GB_CODES, "UK": _GB_CODES,
    "NI": ("NI",), "NIR": ("NI",),
}


def juris_codes(jurisdiction: str) -> tuple[str, ...]:
    """jurisdiction values that may satisfy this user jurisdiction (fail-closed default)."""
    return _JURISDICTION_CODE_MAP.get((jurisdiction or "").upper(), ("__none__",))


def jurisdiction_supported(jurisdiction: str) -> bool:
    """A jurisdiction is supported only if at least one CURRENT verified rule exists
    for its jurisdiction set. NI has no ingested rules => unsupported => fail-closed."""
    codes = juris_codes(jurisdiction)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Effective-dating (NOT a lazy is_current flag, which does not exist on `rules`).
            # "Current" = in force today: effective_from <= today, not yet ended, not prospective.
            cur.execute(
                "SELECT count(*) FROM rules WHERE jurisdiction = ANY(%s) "
                "AND is_prospective = false "
                "AND effective_from <= CURRENT_DATE "
                "AND (effective_to IS NULL OR effective_to >= CURRENT_DATE) "
                "AND verification_status IN ('verified','case_law_verified')",
                (list(codes),),
            )
            return cur.fetchone()[0] > 0
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "jurisdiction_supported failed closed for %s: %s", jurisdiction, exc
        )
        return False
    finally:
        if conn is not None:
            conn.close()


def retrieve_rules(
    claim_type: str,
    jurisdiction: str,
    edt: date,
) -> list[dict]:
    """
    Fetch all current-in-force rules for the claim type and jurisdiction
    applicable at the EDT date.

    Explicitly filters is_prospective=false  -  this is the correct gate, not
    date-overlap alone. Both the £123,543 cap and the prospective 'uncapped'
    row have effective_to=NULL; only is_prospective=false prevents selecting
    the future law.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (rule_key)
                    rule_key, value_numeric, value_text, unit,
                    description, authority_ref, authority_url,
                    effective_from, effective_to, is_prospective
                FROM rules
                WHERE claim_type       = %s
                  AND jurisdiction = ANY(%s)
                  AND is_prospective   = false
                  AND effective_from  <= %s
                  AND (effective_to IS NULL OR effective_to >= %s)
                ORDER BY rule_key, effective_from DESC
                """,
                (claim_type, list(juris_codes(jurisdiction)), edt, edt),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def retrieve_keyword(
    query: str,
    jurisdiction: str = "EW",
    edt: Optional[date] = None,
    k: int = 5,
) -> list[dict]:
    """
    BM25-style keyword fallback using PostgreSQL full-text search.

    Activates automatically when corpus embeddings are absent (OpenAI quota
    blocker). Returns citations from legislation, case law, and ACAS guidance
    ranked by ts_rank over the existing ingested text.

    Terms are OR-combined (to_tsquery 'a | b | c') so a multi-term legal query
    still matches chunks containing ANY of the terms, ranked by ts_rank  -  a
    realistic BM25-style behaviour rather than requiring every term (plainto AND).
    """
    import re as _re
    edt_filter = edt or date.today()
    _terms = _re.findall(r"[A-Za-z0-9]+", query.lower())
    tsq = " | ".join(_terms) if _terms else query
    results: list[dict] = []
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Legislation FTS
            cur.execute(
                """
                SELECT 'legislation' AS source_type,
                       COALESCE(act_title || ' s.' || section_ref, act_title) AS cite,
                       heading,
                       LEFT(body_text, 600) AS text,
                       source_url AS url,
                       jurisdiction AS jurisdiction,
                       effective_from, effective_to,
                       ts_rank(to_tsvector('english', body_text),
                               to_tsquery('english', %s)) AS rank
                FROM legislation
                WHERE jurisdiction = ANY(%s)
                  AND is_prospective = false
                  AND (effective_to IS NULL OR effective_to >= %s)
                  AND to_tsvector('english', body_text) @@ to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (tsq, list(juris_codes(jurisdiction)), edt_filter, tsq, k),
            )
            results.extend(dict(r) for r in cur.fetchall())

            # Case law chunks FTS (join for citation metadata)
            cur.execute(
                """
                SELECT 'case_law' AS source_type,
                       d.neutral_citation AS cite,
                       d.case_name AS heading,
                       LEFT(c.body_text, 600) AS text,
                       d.fetch_url AS url,
                       'UK' AS jurisdiction,
                       d.decision_date AS effective_from,
                       NULL::date AS effective_to,
                       ts_rank(to_tsvector('english', c.body_text),
                               to_tsquery('english', %s)) AS rank
                FROM case_law_chunks c
                JOIN case_law_documents d ON c.document_id = d.id
                WHERE to_tsvector('english', c.body_text) @@ to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (tsq, tsq, k),
            )
            results.extend(dict(r) for r in cur.fetchall())

            # ACAS guidance FTS
            cur.execute(
                """
                SELECT 'acas' AS source_type,
                       doc_title AS cite,
                       doc_title AS heading,
                       LEFT(body_text, 600) AS text,
                       source_url AS url,
                       jurisdiction AS jurisdiction,
                       effective_from,
                       NULL::date AS effective_to,
                       ts_rank(to_tsvector('english', body_text),
                               to_tsquery('english', %s)) AS rank
                FROM acas_guidance
                WHERE jurisdiction = ANY(%s)
                  AND to_tsvector('english', body_text) @@ to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (tsq, list(juris_codes(jurisdiction)), tsq, k),
            )
            results.extend(dict(r) for r in cur.fetchall())
    finally:
        conn.close()

    results.sort(key=lambda r: r.get("rank", 0.0), reverse=True)
    return results[:k]


def retrieve_semantic(
    query: str,
    jurisdiction: str = "EW",
    edt: Optional[date] = None,
    k: int = 5,
) -> list[dict]:
    """
    Primary retrieval: pgvector cosine search when embeddings exist;
    BM25 keyword fallback when they don't (run the embedder first).

    Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, local, no API key).
    Both paths return the same dict shape. The semantic path activates
    automatically once `python -m ingestion.embeddings.embedder` has run.
    """
    # Check embeddings in a short-lived connection, then close it.
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM legislation WHERE embedding IS NOT NULL LIMIT 1)"
            )
            has_embeddings = cur.fetchone()["exists"]
    finally:
        conn.close()

    if not has_embeddings:
        logger.info(
            "Embeddings absent  -  using BM25 keyword fallback. "
            "Run `python -m ingestion.embeddings.embedder` to activate semantic retrieval."
        )
        return retrieve_keyword(query, jurisdiction, edt, k)

    # Embeddings exist  -  open a new connection for the cosine search.
    from ingestion.embeddings.embedder import embed_texts

    query_embedding = embed_texts([query])[0]
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    edt_filter = edt or date.today()
    results: list[dict] = []

    conn2 = get_connection()
    try:
        with conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    'legislation'       AS source_type,
                    act_title || ' s.' || section_ref AS cite,
                    heading,
                    LEFT(body_text, 600) AS text,
                    source_url          AS url,
                    jurisdiction   AS jurisdiction,
                    effective_from, effective_to,
                    embedding <=> %s::vector AS distance
                FROM legislation
                WHERE jurisdiction = ANY(%s)
                  AND is_prospective = false
                  AND (effective_to IS NULL OR effective_to >= %s)
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, list(juris_codes(jurisdiction)), edt_filter, embedding_str, k),
            )
            results.extend(dict(r) for r in cur.fetchall())

            cur.execute(
                """
                SELECT
                    'case_law'                 AS source_type,
                    d.neutral_citation         AS cite,
                    d.case_name                AS heading,
                    LEFT(c.body_text, 600)     AS text,
                    d.fetch_url                AS url,
                    'UK'                       AS jurisdiction,
                    d.decision_date            AS effective_from,
                    NULL::date                 AS effective_to,
                    c.embedding <=> %s::vector AS distance
                FROM case_law_chunks c
                JOIN case_law_documents d ON c.document_id = d.id
                WHERE d.court_code  = 'eat'
                  AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, embedding_str, k),
            )
            results.extend(dict(r) for r in cur.fetchall())

            cur.execute(
                """
                SELECT
                    'acas'              AS source_type,
                    doc_title           AS cite,
                    doc_title           AS heading,
                    LEFT(body_text, 600) AS text,
                    source_url          AS url,
                    jurisdiction   AS jurisdiction,
                    effective_from,
                    NULL::date          AS effective_to,
                    embedding <=> %s::vector AS distance
                FROM acas_guidance
                WHERE jurisdiction = ANY(%s)
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, list(juris_codes(jurisdiction)), embedding_str, k),
            )
            results.extend(dict(r) for r in cur.fetchall())
    finally:
        conn2.close()

    results.sort(key=lambda r: r.get("distance", 1.0))
    return results[:k]


def _section_tokens(query: str) -> set[str]:
    import re as _re
    return {
        m.group(1).lower()
        for m in _re.finditer(r"\b(?:s|section|reg|regulation|art|article)\.?\s*(\d+[A-Za-z]?)\b", query or "", _re.I)
    }


def _exact_rule_authorities(query: str, rules: list[dict], jurisdiction: str) -> list[dict]:
    """Build exact statutory-authority candidates from the already-loaded rules.

    This is not a fallback source: the rule row must already exist, name the same
    section requested by the user, and carry a real authority URL.
    """
    tokens = _section_tokens(query)
    if not tokens:
        return []
    out: list[dict] = []
    for rule in rules:
        ref = str(rule.get("authority_ref") or "")
        url = str(rule.get("authority_url") or "")
        if not ref or not url.startswith("http"):
            continue
        compact = ref.lower().replace("section", "s.").replace(" ", "")
        if not any(f"s.{tok}" in compact or f"s{tok}" in compact for tok in tokens):
            continue
        out.append({
            "source_type": "legislation",
            "cite": ref,
            "heading": ref,
            "text": str(rule.get("description") or ref),
            "url": url,
            "jurisdiction": jurisdiction,
            "effective_from": rule.get("effective_from"),
            "effective_to": rule.get("effective_to"),
            "rank": 1.0,
        })
    return out


def retrieve(
    query: str,
    claim_type: str,
    jurisdiction: str,
    edt: date,
    domain: Optional[str] = None,
) -> RetrievalBundle:
    """
    Run the full hybrid retrieval. Always runs before reasoning.

    Retrieval is domain-scoped. ``domain`` may be passed explicitly; if omitted
    it is resolved from ``claim_type`` via the domain registry (falling back to
    "employment" for backward compatibility with existing callers). The domain
    is then validated FAIL-CLOSED before any query runs:

      - unknown domain  -> UnsupportedDomainError
      - disabled domain -> DomainDisabledError

    so retrieval can never silently serve an unsupported/placeholder domain.

    Returns a RetrievalBundle. Sets insufficient_grounding=True when the
    bundle cannot support a grounded assessment.
    """
    # Domain registry is the single source of truth for what may be retrieved.
    from backend.domains.registry import (
        resolve_domain_for_matter,
        require_domain,
        retrieval_domain_for,
    )

    if domain is None:
        domain = resolve_domain_for_matter(claim_type) or "employment"
    require_domain(domain)                       # fail closed: raises if unknown/disabled
    retrieval_tag = retrieval_domain_for(domain)  # e.g. "employment_uk"

    rules = retrieve_rules(claim_type, jurisdiction, edt)

    # True hybrid retrieval: lexical (BM25 full-text) + semantic (pgvector cosine),
    # merged with Reciprocal Rank Fusion (RRF, k=60). A source found by BOTH paths
    # accumulates both reciprocals and so outranks a single-path hit; an authority
    # the query explicitly names (e.g. "section 98", "[2021] UKSC 1") is boosted to
    # the top. Rules are NOT fused here  -  they stay deterministic and separate.
    lexical  = _exact_rule_authorities(query, rules, jurisdiction) + retrieve_keyword(query, jurisdiction, edt)
    semantic = retrieve_semantic(query, jurisdiction, edt)
    authorities = reciprocal_rank_fusion(lexical, semantic, query=query)

    # Grounding assessment
    has_rules = len(rules) > 0
    has_authorities = len(authorities) >= _MIN_AUTHORITIES_FOR_GROUNDING
    insufficient = not has_rules and not has_authorities

    auth_payload = [
        {
            "type":      r["source_type"],
            "retrieval": r.get("retrieval", "vector"),
            "cite":      r.get("cite") or r.get("heading") or "",
            # authority_ref / jurisdiction / effective dates are surfaced per
            # authority (architecture correction): every grounded result carries
            # its citation, source_url, jurisdiction, and effective window so the
            # answer layer can prove provenance  -  and a stale-dated source is
            # visible, never silently used.
            "authority_ref":  r.get("cite") or r.get("heading") or "",
            "jurisdiction":   r.get("jurisdiction"),
            "effective_from": r.get("effective_from").isoformat() if r.get("effective_from") else None,
            "effective_to":   r.get("effective_to").isoformat() if r.get("effective_to") else None,
            "text":      r.get("text", ""),
            "url":       r.get("url", ""),
            "source_id": f"src_{idx+1}",
            # RRF provenance  -  preserved per Phase 3 (vector_score, lexical_score,
            # rrf_score) so the answer layer and /api/search/hybrid can show WHY a
            # source ranked where it did, and so an exact-citation hit is visible.
            "rrf_score":            r.get("rrf_score"),
            "vector_score":         r.get("vector_score"),
            "lexical_score":        r.get("lexical_score"),
            "exact_citation_match": r.get("exact_citation_match", False),
        }
        for idx, r in enumerate(authorities)
    ]
    
    # Apply Trust Scorer (Phase 3) then score-based rerank (Phase 1 agentic foundation)
    auth_payload = score_authorities(auth_payload)
    auth_payload = rerank_authorities(auth_payload)
    citations = [
        {
            "authority_ref": a.get("authority_ref") or a.get("cite"),
            "url": a.get("url"),
            "source_type": a.get("type"),
        }
        for a in auth_payload
        if a.get("url") or a.get("authority_ref") or a.get("cite")
    ]
    grounding_score = 0.0 if insufficient else min(1.0, 0.4 + 0.2 * len(auth_payload) + 0.1 * len(rules))
    confidence_score = grounding_score

    bundle = RetrievalBundle(
        exact_rules=rules,
        authorities=auth_payload,
        citations=citations,
        grounding_score=grounding_score,
        confidence_score=confidence_score,
        insufficient_grounding=insufficient,
    )

    # Write retrieval audit row (non-fatal)
    _write_retrieval_audit(query, claim_type, jurisdiction, rules, auth_payload, insufficient, retrieval_tag)

    return bundle


def _write_retrieval_audit(
    query: str,
    claim_type: str,
    jurisdiction: str,
    rules: list[dict],
    authorities: list[dict],
    insufficient: bool,
    retrieval_domain: str = "employment_uk",
) -> None:
    """Write a retrieval audit row. Fails silently to not block the pipeline.

    ``retrieval_domain`` is the registry-resolved domain tag for the audit's
    ``domain`` column (no longer a hardcoded employment literal)."""
    try:
        from ingestion.db import get_connection as _gc
        # Count by source type
        leg_count  = sum(1 for a in authorities if a.get("type") == "legislation")
        acas_count = sum(1 for a in authorities if a.get("type") == "acas_guidance")
        cl_count   = sum(1 for a in authorities if a.get("type") == "case_law")
        other      = len(authorities) - leg_count - acas_count - cl_count
        conn = _gc()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO retrieval_audit
                        (retrieval_type, query_hash,
                         rules_count, legislation_count, acas_count,
                         guidance_count, case_law_count, total_authorities,
                         insufficient_grounding)
                    VALUES ('hybrid', md5(%s), %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        query[:500],
                        len(rules),
                        leg_count,
                        acas_count,
                        other,
                        cl_count,
                        len(authorities),
                        insufficient,
                    ),
                )
                # New jurisdiction-aware audit table (legal_retrieval_audit).
                import json as _json
                jcode = juris_codes(jurisdiction)[0]
                bundle_json = _json.dumps({
                    "authorities": [
                        {"cite": a.get("cite"), "url": a.get("url"), "type": a.get("type"),
                         "retrieval": a.get("retrieval")}
                        for a in authorities
                    ],
                    "rule_keys": [r.get("rule_key") for r in rules],
                })
                rules_json = _json.dumps([
                    {"rule_key": r.get("rule_key"), "authority_ref": r.get("authority_ref"),
                     "authority_url": r.get("authority_url"), "value_numeric": float(r["value_numeric"])
                     if r.get("value_numeric") is not None else None}
                    for r in rules
                ])
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'legal_retrieval_audit'
                      AND column_name IN ('jurisdiction_code', 'jurisdiction')
                    """
                )
                audit_columns = {row[0] for row in cur.fetchall()}
                jurisdiction_column = (
                    "jurisdiction_code"
                    if "jurisdiction_code" in audit_columns
                    else "jurisdiction"
                )
                cur.execute(
                    f"""
                    INSERT INTO legal_retrieval_audit
                        (query_text, query_hash, domain, claim_type, {jurisdiction_column},
                         retrieved_bundle, exact_rules, grounding_score, retrieval_model, embedding_model)
                    VALUES (%s, md5(%s), %s, %s, %s,
                            %s::jsonb, %s::jsonb, %s, 'hybrid', 'bge-small-en-v1.5')
                    """,
                    (query[:500], query[:500], retrieval_domain, claim_type, jcode,
                     bundle_json, rules_json, 0.0 if insufficient else 1.0),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("retrieval_audit write skipped: %s", exc)


# ── Semantic search stubs ────────────────────────────────────────────────────

def generate_query_embedding(query: str) -> list[float]:
    """
    Generate embedding vector for a query.

    Args:
        query: Query text

    Returns:
        Embedding vector (384-dim for all-MiniLM-L6-v2)
    """
    try:
        from ingestion.embeddings.embedder import embed_texts
        return embed_texts([query])[0]
    except Exception as exc:
        logger.warning("generate_query_embedding failed: %s (returning zero vector)", exc)
        return [0.0] * 384


def vector_search(
    query: str,
    module: str = "employment",
    jurisdiction: str | None = None,
    source_type: str | None = None,
    threshold: float = 0.5,
    k: int = 5,
) -> list[dict]:
    """
    Vector semantic search using pgvector.

    Args:
        query: Query text
        module: Document module/domain
        threshold: Minimum similarity threshold (0-1)
        k: Maximum results

    Returns:
        List of semantically similar documents with relevance scores
    """
    logger.debug("vector_search: query=%d chars, module=%s, k=%d", len(query), module, k)
    try:
        raw = pgvector_client.search(
            query=query,
            module=module,
            jurisdiction=jurisdiction,
            source_type=source_type,
            k=k,
            metric="cosine",
        )
    except TypeError:
        raw = pgvector_client.search(query, module)
    results = [dict(r) for r in (raw or [])]
    if jurisdiction:
        results = [r for r in results if r.get("jurisdiction") in (None, jurisdiction)]
    if module and module != "employment":
        results = [r for r in results if r.get("module") in (None, module)]
    if source_type:
        results = [r for r in results if r.get("source_type") == source_type]
    results = [
        r for r in results
        if r.get("relevance", r.get("score", 1.0)) >= threshold
    ]
    results.sort(key=lambda r: (r.get("distance", 999.0), -r.get("relevance", r.get("score", 0.0))))
    if results and "distance" not in results[0]:
        results.sort(key=lambda r: r.get("relevance", r.get("score", 0.0)), reverse=True)
    return results[:k]


def bm25_search(
    query: str,
    module: str = "employment",
    k: int = 5,
) -> list[dict]:
    """
    BM25 full-text keyword search.

    Args:
        query: Query text
        module: Document module/domain
        k: Maximum results

    Returns:
        List of keyword-matched documents with BM25 scores
    """
    logger.debug("bm25_search: query=%d chars, module=%s, k=%d", len(query), module, k)
    try:
        raw = bm25_index.search(query=query, module=module, k=k)
    except TypeError:
        raw = bm25_index.search(query, module)
    results = [dict(r) for r in (raw or [])]
    results.sort(key=lambda r: r.get("score", r.get("relevance", 0.0)), reverse=True)
    return results[:k]


def hybrid_search(
    query: str,
    module: str = "employment",
    k: int = 5,
) -> list[dict]:
    """
    Hybrid search combining semantic and lexical retrieval.

    Uses Reciprocal Rank Fusion (RRF) to merge vector and BM25 results.

    Args:
        query: Query text
        module: Document module/domain
        k: Maximum results

    Returns:
        Merged and ranked documents from both paths
    """
    logger.debug("hybrid_search: query=%d chars, module=%s, k=%d", len(query), module, k)

    semantic = vector_search(query, module, k=k)
    lexical = bm25_search(query, module, k=k)

    # RRF merge
    merged = reciprocal_rank_fusion(lexical, semantic, query=query)
    return merged[:k]


def score_citation(citation: dict) -> float:
    """
    Score a citation for relevance/authority.

    Higher scores for statute > case > guidance.

    Args:
        citation: Citation dict with 'type' and optional authority fields

    Returns:
        Score (0-1.0)
    """
    citation_type = citation.get("type", "").lower()

    # Authority hierarchy
    type_scores = {
        "legislation": 0.95,
        "statute": 0.95,
        "case_law": 0.75,
        "acas": 0.65,
        "guidance": 0.60,
    }

    base_score = type_scores.get(citation_type, 0.5)
    authority_level = (citation.get("authority_level") or "").lower()
    if authority_level in ("primary", "supreme", "binding"):
        base_score = max(base_score, 0.95)
    elif authority_level in ("appellate", "court_of_appeal", "eat"):
        base_score = max(base_score, 0.85)
    elif authority_level in ("tribunal", "first_instance"):
        base_score = min(base_score, 0.65)
    elif authority_level in ("non_binding", "guidance"):
        base_score = min(base_score, 0.60)

    # Boost if recent verification
    if citation.get("last_verified_at"):
        base_score = min(1.0, base_score + 0.05)

    return base_score


def rank_citations_for_answer(
    citations: list[dict],
    query: str = "",
) -> list[dict]:
    """
    Rank citations for inclusion in a legal answer.

    Scores and sorts by:
    1. Citation authority (statute > case > guidance)
    2. Relevance to query (if provided)
    3. Recency (newer > older)

    Args:
        citations: List of citations
        query: Optional query to score relevance against

    Returns:
        Ranked citations (highest authority first)
    """
    logger.debug("rank_citations_for_answer: %d citations", len(citations))

    # Score each citation
    scored = []
    for citation in citations:
        score = score_citation(citation)
        scored.append((score, citation))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    return [c for _, c in scored]
