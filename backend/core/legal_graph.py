"""
Legal Knowledge Graph  -  lawapp Brain Step 9 (RAG source selection).

Queries the legal_nodes and legal_edges tables populated by migration 018
to provide structured graph context for the Brain.

Used when Brain selects "legal_graph" or "knowledge_graph" as RAG source.

GUARDRAIL: Only reads from DB. Never writes during a user request.
GUARDRAIL: All results filtered by jurisdiction.
GUARDRAIL: Authority level respected (1=primary legislation has priority).
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.domains.constants import DEFAULT_JURISDICTION

logger = logging.getLogger(__name__)

# Claim type → root node mapping
_CLAIM_ROOT_NODES: dict[str, str] = {
    "unfair_dismissal": "ud_claim",
    "unpaid_wages":     "upw_claim",
    "wrongful_dismissal": "ud_claim",
}

_RELATIONSHIP_PRIORITY = [
    "requires",
    "applies_to",
    "leads_to",
    "extends",
    "interprets",
    "reduces",
    "excludes",
]


# ── Public API ────────────────────────────────────────────────────────────────

def get_claim_subgraph(
    claim_type: str,
    jurisdiction: str = DEFAULT_JURISDICTION,
    max_depth: int = 2,
) -> dict:
    """
    Retrieve the relevant legal knowledge subgraph for a claim type.

    Returns:
        {
          "nodes": list[dict],    -  relevant legal nodes
          "edges": list[dict],    -  edges between nodes
          "context_text": str,    -  formatted text for model context
          "root_node": str,       -  root claim node_id
          "depth": int,
          "source": "legal_graph"
        }

    Returns empty graph dict if DB unavailable  -  never raises.
    """
    root_node_id = _CLAIM_ROOT_NODES.get(claim_type)
    if not root_node_id:
        return _empty_graph("unknown_claim_type")

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            return _traverse_graph(conn, root_node_id, jurisdiction, max_depth)
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Legal graph query skipped: %s", exc)
        return _empty_graph(str(exc))


def get_concept_context(node_ids: list[str], jurisdiction: str = DEFAULT_JURISDICTION) -> dict:
    """
    Fetch specific node context by node_id list.

    Used by Brain when specific legal tests are needed (e.g. Burchell test,
    ACAS Code, qualifying period) that were identified during claim classification.
    """
    if not node_ids:
        return _empty_graph("no_node_ids")

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(node_ids))
                cur.execute(
                    f"""
                    SELECT node_id, node_type, label, description,
                           jurisdiction, authority_level, source_ref, source_url
                    FROM legal_nodes
                    WHERE node_id IN ({placeholders})
                      AND jurisdiction = %s
                      AND is_active = true
                    ORDER BY authority_level ASC
                    """,
                    node_ids + [jurisdiction],
                )
                rows = cur.fetchall()
                if not rows:
                    return _empty_graph("no_nodes_found")
                columns = [d[0] for d in cur.description]
                nodes = [dict(zip(columns, row)) for row in rows]
            return {
                "nodes":        nodes,
                "edges":        [],
                "context_text": _format_nodes_text(nodes),
                "root_node":    node_ids[0] if node_ids else None,
                "depth":        0,
                "source":       "knowledge_graph",
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("get_concept_context skipped: %s", exc)
        return _empty_graph(str(exc))


# ── Graph traversal ──────────────────────────────────────────────────────────

def _traverse_graph(conn, root_node_id: str, jurisdiction: str, max_depth: int) -> dict:
    """BFS traversal of legal_nodes/legal_edges up to max_depth hops."""
    visited_nodes: set[str] = set()
    all_nodes: list[dict] = []
    all_edges: list[dict] = []

    queue = [(root_node_id, 0)]
    visited_nodes.add(root_node_id)

    while queue:
        node_id, depth = queue.pop(0)

        # Fetch node
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_id, node_type, label, description,
                       jurisdiction, authority_level, source_ref, source_url
                FROM legal_nodes
                WHERE node_id = %s AND jurisdiction = %s AND is_active = true
                """,
                (node_id, jurisdiction),
            )
            row = cur.fetchone()
            if not row:
                continue
            cols = [d[0] for d in cur.description]
            all_nodes.append(dict(zip(cols, row)))

        if depth >= max_depth:
            continue

        # Fetch outgoing edges
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT from_node_id, to_node_id, relationship_type, weight, notes
                FROM legal_edges
                WHERE from_node_id = %s AND jurisdiction = %s
                ORDER BY weight DESC
                """,
                (node_id, jurisdiction),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            for row in rows:
                edge = dict(zip(cols, row))
                all_edges.append(edge)
                target = edge["to_node_id"]
                if target not in visited_nodes:
                    visited_nodes.add(target)
                    queue.append((target, depth + 1))

    return {
        "nodes":        all_nodes,
        "edges":        all_edges,
        "context_text": _format_graph_text(all_nodes, all_edges),
        "root_node":    root_node_id,
        "depth":        max_depth,
        "source":       "legal_graph",
    }


def _format_graph_text(nodes: list[dict], edges: list[dict]) -> str:
    """Format graph as compact text context for model prompt."""
    lines = ["LEGAL KNOWLEDGE GRAPH:"]

    # Sort nodes by authority_level (primary legislation first)
    sorted_nodes = sorted(nodes, key=lambda n: n.get("authority_level", 5))
    for node in sorted_nodes:
        ref = node.get("source_ref") or ""
        desc = node.get("description") or ""
        label = node.get("label", node["node_id"])
        line = f"  [{node['node_type']}] {label}"
        if ref:
            line += f" ({ref})"
        if desc:
            line += f"  -  {desc[:150]}"
        lines.append(line)

    if edges:
        lines.append("RELATIONSHIPS:")
        for edge in edges:
            lines.append(
                f"  {edge['from_node_id']} --[{edge['relationship_type']}]--> {edge['to_node_id']}"
            )

    return "\n".join(lines)


def _format_nodes_text(nodes: list[dict]) -> str:
    return _format_graph_text(nodes, [])


def _empty_graph(reason: str) -> dict:
    return {
        "nodes":        [],
        "edges":        [],
        "context_text": "",
        "root_node":    None,
        "depth":        0,
        "source":       "legal_graph",
        "unavailable_reason": reason,
    }


# ── RAG source selector ───────────────────────────────────────────────────────

def select_rag_sources(
    claim_type: str,
    risk_level: str,
    is_generic: bool,
    jurisdiction: str = DEFAULT_JURISDICTION,
) -> dict:
    """
    Determine which RAG sources to activate for this query.

    Called by Brain at step 9 (select_rag_source).

    Returns:
        {
          "sources":       list[str]   -  ["hybrid", "legal_graph", "knowledge_graph"]
          "primary":       str         -  the primary source for retrieval
          "use_graph":     bool
          "use_kg":        bool
          "reason":        str
        }
    """
    sources = ["hybrid"]     # hybrid (SQL rules + BM25 + pgvector) is always active
    use_graph = False
    use_kg    = False
    reason    = "hybrid_always_active"

    # Legal graph activated for known claim types with non-generic queries
    if claim_type not in ("out_of_scope",) and not is_generic:
        sources.append("legal_graph")
        use_graph = True
        reason = "known_claim_type_graph_activated"

    # Knowledge graph activated for high-risk or when deep legal analysis needed
    if risk_level == "high" or claim_type in ("discrimination", "whistleblowing"):
        sources.append("knowledge_graph")
        use_kg = True
        reason = "high_risk_knowledge_graph_activated"

    return {
        "sources":   sources,
        "primary":   "hybrid",
        "use_graph": use_graph,
        "use_kg":    use_kg,
        "reason":    reason,
    }
