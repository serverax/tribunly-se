"""
Post-fusion reranking for legal authorities.

Phase 1: deterministic score-based rerank combining:
  - RRF score (hybrid retrieval rank)
  - trust_score (source-type prior)
  - exact_citation_match boost

No cross-encoder model in Phase 1  -  avoids new runtime deps. Env flag
RERANK_MODEL_ENABLED reserved for Phase 2 local cross-encoder.
"""

from __future__ import annotations

import os
from typing import Sequence


def _base_score(auth: dict) -> float:
    rrf = float(auth.get("rrf_score") or 0.0)
    trust = float(auth.get("trust_score") or 0.0) / 100.0
    exact = 1.0 if auth.get("exact_citation_match") else 0.0
    # Weighted combination  -  RRF primary, trust secondary, exact citation tie-break
    return (rrf * 0.55) + (trust * 0.35) + (exact * 0.10)


def rerank_authorities(authorities: Sequence[dict], *, limit: int | None = None) -> list[dict]:
    """
    Rerank authority dicts in-place annotation with rerank_score; return sorted copy.

    Args:
        authorities: list from retrieve() after trust_scorer
        limit: optional cap on returned items
    """
    if not authorities:
        return []

    if os.getenv("RERANK_MODEL_ENABLED", "").lower() in ("1", "true", "yes"):
        # Phase 2 hook  -  fall through to score-based until model wired
        pass

    ranked: list[dict] = []
    for auth in authorities:
        item = dict(auth)
        item["rerank_score"] = round(_base_score(item), 6)
        ranked.append(item)

    ranked.sort(
        key=lambda a: (
            a.get("rerank_score", 0.0),
            a.get("trust_score", 0),
            a.get("rrf_score", 0.0),
        ),
        reverse=True,
    )
    if limit is not None:
        ranked = ranked[:limit]
    return ranked
