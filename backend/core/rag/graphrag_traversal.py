"""
GraphRAG Traversal - Legal Path Finding for 3 Core Modules

Loads legal_nodes and legal_edges from PostgreSQL. Traverses graph to find
legal paths from user facts -> claim -> legal tests -> statute -> remedies -> deadlines.

Returns legal path with authority chain and confidence scoring.

HARD RULE: Nodes/edges must match actual legal structure (not AI invention).
Node types: legislation_section, claim_type, legal_test, remedy, defence, deadline, procedure
Relationship types: requires, applies_to, leads_to, interprets, extends, reduces, excludes
"""

from __future__ import annotations

import logging

import psycopg2.extras

from ingestion.db import get_connection

logger = logging.getLogger(__name__)

# Supported claim types for Phase 1
_SUPPORTED_CLAIM_TYPES = {
    "unfair_dismissal",
    "constructive_dismissal",
    "employment_status",
}

# Module mapping for claim types
_CLAIM_TYPE_TO_MODULE = {
    "unfair_dismissal": "unfair_dismissal",
    "constructive_dismissal": "constructive_dismissal",
    "employment_status": "employment_status",
}


def build_legal_path(
    claim_type: str,
    module: str,
    jurisdiction: str = "EW",
    max_depth: int = 10,
) -> dict:
    """
    Build the legal path from claim_type through all prerequisites to remedies/deadlines.

    Returns:
      {
        "claim_type": str,
        "path": [list of nodes in order],
        "edges": [relationship metadata],
        "confidence": float,
        "missing_prerequisites": [optional list],
        "jurisdiction": str
      }

    Graph traversal order:
    1. Start at claim_type node (e.g., "ud_claim")
    2. Find all 'requires' edges -> collect legal_test nodes
    3. From each legal_test, find 'leads_to' edges -> next tests
    4. Continue until no more prerequisite edges
    5. Collect 'remedy' and 'deadline' nodes reachable from start

    FAIL-CLOSED: If claim_type unsupported or graph empty, return empty path.
    """
    if claim_type not in _SUPPORTED_CLAIM_TYPES:
        logger.warning("Claim type %s not supported for Phase 1 GraphRAG.", claim_type)
        return {
            "claim_type": claim_type,
            "path": [],
            "edges": [],
            "confidence": 0.0,
            "missing_prerequisites": [f"Claim type {claim_type} not supported"],
            "jurisdiction": jurisdiction,
        }

    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT node_id, label, description
                  FROM legal_nodes
                 WHERE node_type = 'claim_type'
                   AND label ILIKE %s
                   AND jurisdiction = %s
                   AND is_active = true
                 LIMIT 1
                """,
                (f"%{claim_type.replace('_', ' ')}%", jurisdiction),
            )
            root_node = cur.fetchone()

        if not root_node:
            logger.warning(
                "No root node found for claim type %s in jurisdiction %s",
                claim_type,
                jurisdiction,
            )
            return _empty_path(claim_type, jurisdiction, ["No root node found in legal graph"])

        root_id = root_node["node_id"]
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                WITH RECURSIVE graph_walk AS (
                    SELECT
                        ln.node_id,
                        ln.node_type,
                        ln.label,
                        ln.description,
                        ln.authority_level,
                        ln.source_ref,
                        ln.source_url,
                        0 AS depth,
                        ARRAY[ln.node_id]::text[] AS path_ids
                    FROM legal_nodes ln
                    WHERE ln.node_id = %s
                      AND ln.is_active = true
                    UNION ALL
                    SELECT
                        ln.node_id,
                        ln.node_type,
                        ln.label,
                        ln.description,
                        ln.authority_level,
                        ln.source_ref,
                        ln.source_url,
                        gw.depth + 1,
                        gw.path_ids || ln.node_id
                    FROM graph_walk gw
                    JOIN legal_edges le ON le.from_node_id = gw.node_id
                    JOIN legal_nodes ln ON ln.node_id = le.to_node_id
                    WHERE ln.is_active = true
                      AND gw.depth < %s
                      AND NOT (ln.node_id = ANY (gw.path_ids))
                )
                SELECT DISTINCT ON (node_id)
                    node_id, node_type, label, description,
                    authority_level, source_ref, source_url, depth
                FROM graph_walk
                ORDER BY node_id, depth
                """,
                (root_id, max_depth),
            )
            path_nodes_raw = cur.fetchall()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            node_ids = [n["node_id"] for n in path_nodes_raw]
            if node_ids:
                cur.execute(
                    """
                    SELECT le.from_node_id, le.to_node_id, le.relationship_type,
                           le.weight, le.notes
                      FROM legal_edges le
                     WHERE le.from_node_id = ANY(%s)
                       AND le.to_node_id = ANY(%s)
                    """,
                    (node_ids, node_ids),
                )
                edges_raw = cur.fetchall()
            else:
                edges_raw = []

        path_nodes = [
            {
                "node_id": n["node_id"],
                "node_type": n["node_type"],
                "label": n["label"],
                "description": n["description"],
                "authority_level": n["authority_level"],
                "source_ref": n["source_ref"],
                "source_url": n["source_url"],
                "required": n["node_type"] in ("legal_test", "procedure"),
                "depth": n["depth"],
            }
            for n in path_nodes_raw
        ]
        path_edges = [
            {
                "from_node_id": e["from_node_id"],
                "to_node_id": e["to_node_id"],
                "from": e["from_node_id"],
                "to": e["to_node_id"],
                "relationship": e["relationship_type"],
                "weight": e["weight"],
                "notes": e["notes"],
            }
            for e in edges_raw
        ]

        if path_nodes:
            legal_test_count = sum(1 for n in path_nodes if n["node_type"] == "legal_test")
            remedy_count = sum(1 for n in path_nodes if n["node_type"] == "remedy")
            deadline_count = sum(1 for n in path_nodes if n["node_type"] == "deadline")

            base_confidence = 0.5
            test_bonus = min(0.3, legal_test_count * 0.1)
            remedy_bonus = 0.1 if remedy_count > 0 else 0.0
            deadline_bonus = 0.1 if deadline_count > 0 else 0.0
            confidence = min(1.0, base_confidence + test_bonus + remedy_bonus + deadline_bonus)
        else:
            confidence = 0.0

        missing_prerequisites = _identify_missing_prerequisites(claim_type, path_nodes)

    except Exception as exc:
        logger.error("Graph traversal failed closed: %s", exc)
        return _empty_path(claim_type, jurisdiction, [f"Graph traversal unavailable: {type(exc).__name__}"])
    finally:
        if conn is not None:
            conn.close()

    return {
        "claim_type": claim_type,
        "path": path_nodes,
        "edges": path_edges,
        "confidence": confidence,
        "missing_prerequisites": missing_prerequisites,
        "jurisdiction": jurisdiction,
    }


def _empty_path(claim_type: str, jurisdiction: str, missing: list[str]) -> dict:
    return {
        "claim_type": claim_type,
        "path": [],
        "edges": [],
        "confidence": 0.0,
        "missing_prerequisites": missing,
        "jurisdiction": jurisdiction,
    }


def traverse_requirements(
    claim_type: str,
    jurisdiction: str = "EW",
) -> dict:
    """
    List all legal requirements (tests, procedures, evidence) for a claim type.

    Returns:
      {
        "claim_type": str,
        "requirements": [list of legal_test nodes],
        "procedures": [list of procedure nodes],
        "total_requirements": int,
        "jurisdiction": str
      }
    """
    if claim_type not in _SUPPORTED_CLAIM_TYPES:
        return {
            "claim_type": claim_type,
            "requirements": [],
            "procedures": [],
            "total_requirements": 0,
            "jurisdiction": jurisdiction,
        }

    path = build_legal_path(
        claim_type,
        _CLAIM_TYPE_TO_MODULE.get(claim_type, claim_type),
        jurisdiction,
    )
    path_nodes = path.get("path", [])

    requirements = [n for n in path_nodes if n["node_type"] == "legal_test"]
    procedures = [n for n in path_nodes if n["node_type"] == "procedure"]

    return {
        "claim_type": claim_type,
        "requirements": requirements,
        "procedures": procedures,
        "total_requirements": len(requirements),
        "jurisdiction": jurisdiction,
    }


def find_remedies_for_claim(
    claim_type: str,
    jurisdiction: str = "EW",
) -> dict:
    """
    List all remedies (awards, remedies) applicable to a claim type.

    Returns:
      {
        "claim_type": str,
        "remedies": [list of remedy nodes],
        "total_remedies": int,
        "jurisdiction": str
      }
    """
    if claim_type not in _SUPPORTED_CLAIM_TYPES:
        return {
            "claim_type": claim_type,
            "remedies": [],
            "total_remedies": 0,
            "jurisdiction": jurisdiction,
        }

    path = build_legal_path(
        claim_type,
        _CLAIM_TYPE_TO_MODULE.get(claim_type, claim_type),
        jurisdiction,
    )
    path_nodes = path.get("path", [])

    remedies = [n for n in path_nodes if n["node_type"] == "remedy"]

    return {
        "claim_type": claim_type,
        "remedies": remedies,
        "total_remedies": len(remedies),
        "jurisdiction": jurisdiction,
    }


def find_deadlines_for_claim(
    claim_type: str,
    jurisdiction: str = "EW",
) -> dict:
    """
    List all time limits and deadlines applicable to a claim type.

    Returns:
      {
        "claim_type": str,
        "deadlines": [list of deadline nodes],
        "total_deadlines": int,
        "jurisdiction": str
      }
    """
    if claim_type not in _SUPPORTED_CLAIM_TYPES:
        return {
            "claim_type": claim_type,
            "deadlines": [],
            "total_deadlines": 0,
            "jurisdiction": jurisdiction,
        }

    path = build_legal_path(
        claim_type,
        _CLAIM_TYPE_TO_MODULE.get(claim_type, claim_type),
        jurisdiction,
    )
    path_nodes = path.get("path", [])

    deadlines = [n for n in path_nodes if n["node_type"] == "deadline"]

    return {
        "claim_type": claim_type,
        "deadlines": deadlines,
        "total_deadlines": len(deadlines),
        "jurisdiction": jurisdiction,
    }


def _identify_missing_prerequisites(claim_type: str, path_nodes: list[dict]) -> list[str]:
    """
    Check if all known prerequisites for a claim type are in the path.

    Returns list of missing prerequisite node_ids (empty if complete).
    """
    expected_prerequisites = {
        "unfair_dismissal": [
            "employee_status",
            "qualifying_service",
            "dismissal",
            "fair_reason",
            "reasonableness_test",
        ],
        "constructive_dismissal": [
            "employee_status",
            "qualifying_service",
            "breach_of_contract",
            "affreightment",
        ],
        "employment_status": [
            "employment_contract",
            "control_test",
        ],
    }

    expected = expected_prerequisites.get(claim_type, [])
    found_ids = {n["node_id"] for n in path_nodes}

    return [p for p in expected if p not in found_ids]


class GraphRAGTraversal:
    """Postgres-backed graph traversal for lawapp-graph-rag-service (port 8018)."""

    def __init__(self, *args, **kwargs) -> None:
        self._db_ok = self._check_database()

    def _check_database(self) -> bool:
        try:
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM legal_nodes LIMIT 1")
                return True
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("GraphRAG database check failed: %s", exc)
            return False

    def traverse(self, claim_type: str, module: str = "", jurisdiction: str = "EW", **kwargs) -> list[dict]:
        if not self._db_ok:
            return []
        result = build_legal_path(claim_type, module or claim_type, jurisdiction=jurisdiction)
        return result.get("path", [])

    def related_provisions(self, provision_id: str, **kwargs) -> list[dict]:
        if not self._db_ok:
            return []
        try:
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT ln.node_id, ln.label, ln.source_ref, le.relationship_type
                          FROM legal_edges le
                          JOIN legal_nodes ln ON ln.node_id = le.to_node_id
                         WHERE le.from_node_id = %s AND ln.is_active = true
                        """,
                        (provision_id,),
                    )
                    return [dict(row) for row in cur.fetchall()]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("related_provisions failed closed: %s", exc)
            return []

    def neighbours(self, node_id: str, **kwargs) -> list[dict]:
        if not self._db_ok:
            return []
        try:
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT ln.node_id, ln.node_type, ln.label, le.relationship_type
                          FROM legal_edges le
                          JOIN legal_nodes ln ON ln.node_id = le.to_node_id
                         WHERE le.from_node_id = %s AND ln.is_active = true
                        """,
                        (node_id,),
                    )
                    return [dict(row) for row in cur.fetchall()]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("neighbours failed closed: %s", exc)
            return []

    def health(self) -> dict[str, str]:
        if self._db_ok:
            return {"status": "ok", "mode": "postgres", "engine": "legal_nodes/legal_edges"}
        return {"status": "degraded", "mode": "fail_closed", "engine": "postgres_unavailable"}


def graphrag_traversal(claim_type: str, module: str = "", jurisdiction: str = "EW", **kwargs) -> list[dict]:
    return GraphRAGTraversal().traverse(claim_type, module, jurisdiction, **kwargs)


def traverse(claim_type: str, module: str = "", jurisdiction: str = "EW", **kwargs) -> list[dict]:
    return graphrag_traversal(claim_type, module, jurisdiction, **kwargs)


def health() -> dict[str, str]:
    return GraphRAGTraversal().health()
