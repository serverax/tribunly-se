"""
GraphRagService (Python) - legal chain builder for Mother Algorithm.

NestJS control-plane is not present in this repo; this module provides the
equivalent of buildLegalChain(), format(), and optional path scoring.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.core.rag.graph_engine import build_graph_chain, search_graph_by_query
from backend.domains.constants import DEFAULT_JURISDICTION


def build_legal_chain(
    claim_type: str,
    jurisdiction: str = DEFAULT_JURISDICTION,
    max_depth: int = 10,
    query: Optional[str] = None,
) -> dict[str, Any]:
    """Build authority chain from claim type through tests to remedies."""
    return build_graph_chain(
        claim_type=claim_type,
        jurisdiction=jurisdiction,
        max_depth=max_depth,
        query=query,
    )


def format_chain(chain: dict[str, Any]) -> str:
    """Format chain for LLM context injection."""
    text = chain.get("context_text") or ""
    if not text and chain.get("path"):
        from backend.core.rag.graph_engine import _format_path_text

        text = _format_path_text(chain.get("path", []), chain.get("edges", []))
    engine = chain.get("engine", "unknown")
    confidence = chain.get("confidence", 0.0)
    header = f"[Graph engine={engine} confidence={confidence:.2f}]"
    return f"{header}\n{text}".strip()


def score_path(chain: dict[str, Any]) -> float:
    """
    Optional path scoring: base confidence plus bonuses for tests and sources.
    """
    base = float(chain.get("confidence", 0.0))
    path = chain.get("path") or []
    test_bonus = min(0.2, 0.05 * sum(1 for n in path if n.get("node_type") in ("legaltest", "legal_test")))
    source_bonus = 0.05 * sum(1 for n in path if n.get("source_url"))
    return min(1.0, base + test_bonus + source_bonus)


def search_legal_chain(query: str, jurisdiction: str = DEFAULT_JURISDICTION, limit: int = 10) -> dict[str, Any]:
    """Query-driven graph search used by port 8018 /api/graph/search."""
    result = search_graph_by_query(query, jurisdiction=jurisdiction, limit=limit)
    result["path_score"] = score_path(result)
    result["formatted"] = format_chain(result)
    return result
