"""
Postgres legal graph traversal wrapper.

Uses legal_nodes / legal_edges (migration 018). NOT Neo4j.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.domains.constants import DEFAULT_JURISDICTION


class GraphController:
    """Read-only Postgres graph access for the control plane."""

    def get_subgraph(
        self,
        claim_type: str,
        jurisdiction: str = DEFAULT_JURISDICTION,
        max_depth: int = 2,
    ) -> dict:
        from backend.core.legal_graph import get_claim_subgraph

        return get_claim_subgraph(claim_type, jurisdiction, max_depth)

    def traverse_from_nodes(
        self,
        node_ids: list[str],
        jurisdiction: str = DEFAULT_JURISDICTION,
    ) -> dict:
        from backend.core.legal_graph import get_concept_context

        return get_concept_context(node_ids, jurisdiction)

    def enrich_bundle_context(
        self,
        claim_type: str,
        jurisdiction: str = DEFAULT_JURISDICTION,
    ) -> Optional[dict]:
        g = self.get_subgraph(claim_type, jurisdiction)
        if g.get("nodes"):
            return g
        return None
