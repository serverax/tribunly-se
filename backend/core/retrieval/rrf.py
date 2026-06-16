"""Reciprocal Rank Fusion (RRF) for hybrid legal retrieval.

Merges independently-ranked result lists  -  lexical BM25 (PostgreSQL full-text)
and semantic (pgvector cosine)  -  into one ranking using RRF:

    rrf_score(d) = Σ_l  1 / (k + rank_l(d))

where rank_l(d) is the 1-based position of document d in list l, and k is a
smoothing constant (default 60, the value from the original Cormack et al. RRF
paper). A document found by BOTH paths accumulates both reciprocals and so
ranks above a document found by only one  -  this is the property that makes
hybrid retrieval beat either path alone.

DETERMINISTIC-RULES BOUNDARY (constitution §9):
  This module fuses ONLY the *authorities* (legislation / case_law / acas).
  The `rules` table (deadlines, caps, qualifying periods, thresholds) is a
  deterministic legal-fact source and is NEVER passed through RRF. An
  approximate similarity score must never reorder or suppress an exact legal
  value. retrieve() keeps `exact_rules` entirely separate from this fusion.

EXACT-CITATION PRIORITY:
  A query that names a specific authority (e.g. "section 98 ERA 1996",
  "[2021] UKSC 1") must surface that exact authority at the top even if a
  semantically-similar-but-wrong chunk scores higher on cosine. After fusion
  we add a bounded exact-match boost so a genuine exact hit wins rank 1,
  without letting the boost manufacture an authority that retrieval did not
  actually return.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

DEFAULT_RRF_K = 60

# Boost added to rrf_score when the query explicitly names this authority.
# Chosen > 1/(k+1) (the maximum a single list contributes) so a true exact
# match outranks any purely-similarity hit, but still finite/auditable.
EXACT_CITATION_BOOST = 1.0


def _default_key(r: dict) -> tuple:
    """Identity used to recognise the same authority across both lists.

    Uses the citation plus a text prefix so two distinct chunks of the same
    Act/case are not collapsed, while the identical chunk found by both the
    lexical and semantic path IS collapsed (and gets both reciprocals).
    """
    cite = (r.get("cite") or r.get("heading") or "").strip()
    text_prefix = (r.get("text") or "")[:80]
    return (cite, text_prefix)


# Citation-like tokens we treat as an explicit authority reference in the query.
# UK-shaped: "s.98" / "section 98", neutral citations "[2021] UKSC 1",
# and Act-with-section "ERA 1996 s 98". Deliberately conservative  -  a false
# positive here only means a small boost, never a fabricated result.
_SECTION_RE = re.compile(r"\b(?:s|section|reg|regulation|art|article)\.?\s*(\d+[A-Za-z]?)\b", re.I)
_NEUTRAL_CITATION_RE = re.compile(r"\[\d{4}\]\s*[A-Z]{2,6}\s*\d+", re.I)


def _query_citation_tokens(query: str) -> list[str]:
    """Lowercased citation tokens present in the query (sections + neutral cites)."""
    tokens: list[str] = []
    for m in _SECTION_RE.finditer(query or ""):
        tokens.append(f"s{m.group(1).lower()}")
    for m in _NEUTRAL_CITATION_RE.finditer(query or ""):
        tokens.append(re.sub(r"\s+", " ", m.group(0).lower()).strip())
    return tokens


def _result_matches_citation(result: dict, tokens: Sequence[str]) -> bool:
    """True if the result's cite/heading contains one of the query citation tokens."""
    if not tokens:
        return False
    hay = ((result.get("cite") or "") + " " + (result.get("heading") or "")).lower()
    # Normalise "s." / "section" in the haystack to the same "s<n>" shape.
    hay_sections = {f"s{m.group(1).lower()}" for m in _SECTION_RE.finditer(hay)}
    hay_neutral = {re.sub(r"\s+", " ", m.group(0).lower()).strip()
                   for m in _NEUTRAL_CITATION_RE.finditer(hay)}
    for tok in tokens:
        if tok in hay_sections or tok in hay_neutral:
            return True
    return False


def reciprocal_rank_fusion(
    lexical: Sequence[dict],
    semantic: Sequence[dict],
    *,
    k: int = DEFAULT_RRF_K,
    query: str = "",
    key_fn: Optional[Callable[[dict], tuple]] = None,
    final_limit: Optional[int] = None,
) -> list[dict]:
    """Fuse two ranked authority lists into one RRF-ordered list.

    Args:
        lexical:  results in lexical-rank order (best first). Each may carry a
                  per-list score under 'rank' (ts_rank)  -  preserved as lexical_score.
        semantic: results in semantic-rank order (best first). Each may carry a
                  'distance' (cosine)  -  preserved as vector_score = 1 - distance.
        k:        RRF smoothing constant (default 60).
        query:    original user query, used only for exact-citation boosting.
        key_fn:   identity function for cross-list dedup (default _default_key).
        final_limit: optional cap on returned results.

    Returns:
        list[dict] sorted by rrf_score desc (exact-citation boost applied),
        each annotated with: rrf_score, lexical_score, vector_score,
        semantic_rank, lexical_rank, retrieval ('lexical'|'vector'|'hybrid'),
        exact_citation_match (bool).
    """
    if k < 1:
        raise ValueError("RRF k must be >= 1")
    key = key_fn or _default_key
    tokens = _query_citation_tokens(query)

    merged: dict[tuple, dict] = {}

    def _ingest(items: Sequence[dict], list_name: str) -> None:
        for position, r in enumerate(items, start=1):
            kk = key(r)
            entry = merged.get(kk)
            if entry is None:
                entry = dict(r)  # shallow copy  -  never mutate caller's dicts
                entry["rrf_score"] = 0.0
                entry["lexical_rank"] = None
                entry["semantic_rank"] = None
                entry.setdefault("lexical_score", None)
                entry.setdefault("vector_score", None)
                entry["_paths"] = set()
                merged[kk] = entry
            entry["rrf_score"] += 1.0 / (k + position)
            entry["_paths"].add(list_name)
            if list_name == "lexical":
                entry["lexical_rank"] = position
                if r.get("rank") is not None:
                    entry["lexical_score"] = float(r["rank"])
            else:
                entry["semantic_rank"] = position
                if r.get("distance") is not None:
                    # cosine distance -> similarity in [0,1]-ish for readability
                    entry["vector_score"] = round(1.0 - float(r["distance"]), 6)

    _ingest(lexical, "lexical")
    _ingest(semantic, "semantic")

    out: list[dict] = []
    for entry in merged.values():
        paths = entry.pop("_paths")
        entry["retrieval"] = (
            "hybrid" if len(paths) == 2 else ("lexical" if "lexical" in paths else "vector")
        )
        is_exact = _result_matches_citation(entry, tokens)
        entry["exact_citation_match"] = is_exact
        if is_exact:
            entry["rrf_score"] += EXACT_CITATION_BOOST
        entry["rrf_score"] = round(entry["rrf_score"], 8)
        out.append(entry)

    # Sort: exact matches first (their boost already lifts rrf_score), then by
    # fused score, with a stable secondary on having appeared in both lists.
    out.sort(key=lambda e: (e["rrf_score"], e["retrieval"] == "hybrid"), reverse=True)
    if final_limit is not None:
        out = out[:final_limit]
    return out
