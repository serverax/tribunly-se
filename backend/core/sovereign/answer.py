"""DB-First cited-answer builder + WASM-equivalent citation guard (Test Cases B/C).

Retrieval runs FIRST (corpus_chunks lexical match, jurisdiction-filtered). The
answer cites the REAL corpus_chunks UUID(s) it is built from. The citation guard
(corpus_citation_guard) is the circuit breaker: an answer making a legal claim
without a valid corpus UUID is BLOCKED (fail-closed), never returned to the user.
"""
from __future__ import annotations

from typing import Callable, Optional


def _get_conn():
    from ingestion.db import get_connection
    return get_connection()


def retrieve_cited_chunks(query: str, jurisdiction: str = "EW",
                          limit: int = 3, get_conn: Optional[Callable] = None) -> list[dict]:
    """DB-first retrieval: jurisdiction-filtered lexical match over corpus_chunks.
    Returns real rows with their UUIDs so the answer can cite them verifiably."""
    from backend.core.retrieve import juris_codes
    codes = list(juris_codes(jurisdiction))
    conn = (get_conn or _get_conn)()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, authority_ref, title, body_text
                FROM corpus_chunks
                WHERE jurisdiction_code = ANY(%s) AND is_current = true
                  AND to_tsvector('english', body_text) @@ plainto_tsquery('english', %s)
                ORDER BY ts_rank(to_tsvector('english', body_text),
                                 plainto_tsquery('english', %s)) DESC
                LIMIT %s
                """,
                (codes, query, query, limit),
            )
            rows = cur.fetchall()
        return [{"uuid": r[0], "authority_ref": r[1], "title": r[2],
                 "snippet": (r[3] or "")[:240]} for r in rows]
    finally:
        conn.close()


def build_answer(query: str, chunks: list[dict]) -> tuple[str, list[str]]:
    """Build a cited answer from retrieved chunks. With no grounding, returns the
    safe 'cannot advise' answer (no legal claim, no citation needed)."""
    if not chunks:
        return ("I cannot advise on this — no verified legal source was found in "
                "the local database for your question.", [])
    lines = ["Based strictly on the verified local legal database:"]
    cited: list[str] = []
    for c in chunks:
        lines.append(f"- {c['authority_ref'] or c['title']}: {c['snippet']} "
                     f"(Citation: {c['uuid']})")
        cited.append(c["uuid"])
    return ("\n".join(lines), cited)


def passes_wasm_guard(answer_text: str, get_conn: Optional[Callable] = None) -> bool:
    """Circuit breaker: an answer that makes a legal claim must cite a valid
    corpus_chunks UUID. Safe non-claim answers (e.g. 'I cannot advise') pass."""
    from backend.core.agentic.corpus_citation_guard import response_has_valid_corpus_citation
    low = answer_text.lower()
    makes_legal_claim = any(p in low for p in
                            ("entitled to", "you can claim", "dismissal", "notice period",
                             "unfair", "compensation", "your right", "the law requires"))
    if not makes_legal_claim:
        return True
    return response_has_valid_corpus_citation(answer_text, get_conn)
