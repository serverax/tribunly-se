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

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT node_id, label, description FROM legal_nodes "
                "WHERE node_type = 'claim_type' AND label ILIKE %s AND jurisdiction = %s",
                (f"%{claim_type.replace('_', ' ')}%", jurisdiction),
            )
            root_node = cur.fetchone()

        if not root_node:
            logger.warning(
                "No root node found for claim type %s in jurisdiction %s",
                claim_type,
                jurisdiction,
            )
            return {
                "claim_type": claim_type,
                "path": [],
                "edges": [],
                "confidence": 0.0,
                "missing_prerequisites": ["No root node found in legal graph"],
                "jurisdiction": jurisdiction,
            }

        visited: set[str] = set()
        path_nodes: list[dict] = []
        path_edges: list[dict] = []
        queue: list[tuple[str, int]] = [(root_node["node_id"], 0)]

        while queue and len(visited) < 100:
            current_node_id, depth = queue.pop(0)
            if depth > max_depth or current_node_id in visited:
                continue
            visited.add(current_node_id)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM legal_nodes WHERE node_id = %s",
                    (current_node_id,),
                )
                node = cur.fetchone()

            if node:
                path_nodes.append({
                    "node_id": node["node_id"],
                    "node_type": node["node_type"],
                    "label": node["label"],
                    "description": node["description"],
                    "authority_level": node["authority_level"],
                    "source_ref": node["source_ref"],
                    "source_url": node["source_url"],
                    "required": node["node_type"] in ("legal_test", "procedure"),
                    "depth": depth,
                })

                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT le.*, ln.node_type, ln.label AS to_label
                        FROM legal_edges le
                        JOIN legal_nodes ln ON le.to_node_id = ln.node_id
                        WHERE le.from_node_id = %s AND ln.is_active = true
                        """,
                        (current_node_id,),
                    )
                    edges = cur.fetchall()

                for edge in edges:
                    path_edges.append({
                        "from_node_id": edge["from_node_id"],
                        "to_node_id": edge["to_node_id"],
                        "from": edge["from_node_id"],
                        "to": edge["to_node_id"],
                        "relationship": edge["relationship_type"],
                        "weight": edge["weight"],
                        "notes": edge["notes"],
                    })

                    if edge["to_node_id"] not in visited:
                        queue.append((edge["to_node_id"], depth + 1))

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

    finally:
        conn.close()

    return {
        "claim_type": claim_type,
        "path": path_nodes,
        "edges": path_edges,
        "confidence": confidence,
        "missing_prerequisites": missing_prerequisites,
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
