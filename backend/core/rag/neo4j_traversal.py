"""
Neo4j graph traversal for Graph RAG Layer v1.

Active only when NEO4J_ENABLED=true and the driver can connect.
Falls back to Postgres via graphrag_traversal when Neo4j is empty or down.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lawapp_dev_only")

_CLAIM_ROOTS = {
    "unfair_dismissal": "ud_claim",
    "constructive_dismissal": "cd_claim",
    "employment_status": "es_claim",
}


def neo4j_enabled() -> bool:
    return os.getenv("NEO4J_ENABLED", "false").lower() in ("1", "true", "yes")


def _driver():
    if not neo4j_enabled():
        return None
    try:
        from neo4j import GraphDatabase

        return GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))
    except Exception as exc:
        logger.warning("Neo4j driver unavailable: %s", exc)
        return None


def health() -> dict[str, str]:
    if not neo4j_enabled():
        return {"status": "disabled", "mode": "postgres", "engine": "legal_nodes/legal_edges"}
    driver = _driver()
    if driver is None:
        return {"status": "degraded", "mode": "postgres_fallback", "engine": "neo4j_unreachable"}
    try:
        with driver.session() as session:
            session.run("RETURN 1").consume()
        return {"status": "ok", "mode": "neo4j", "engine": "neo4j"}
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return {"status": "degraded", "mode": "postgres_fallback", "engine": "neo4j_unreachable"}
    finally:
        driver.close()


def _normalise_relationship(rel: str) -> str:
    return (rel or "requires").lower()


def _row_to_node(record: dict, depth: int = 0) -> dict:
    labels = record.get("labels") or []
    node_type = "legal_test"
    if "Section" in labels or "Statute" in labels:
        node_type = "legislation_section"
    elif "Case" in labels:
        node_type = "case_law"
    elif "Outcome" in labels:
        node_type = "remedy"
    elif "Concept" in labels:
        node_type = "procedure"
    elif "Rule" in labels:
        node_type = "rule"
    return {
        "node_id": record.get("id") or "",
        "node_type": node_type,
        "label": record.get("label") or "",
        "description": record.get("description"),
        "authority_level": int(record.get("authority_level") or 2),
        "source_ref": record.get("source_ref"),
        "source_url": record.get("source_url"),
        "required": node_type == "legal_test",
        "depth": depth,
    }


def build_legal_chain(
    claim_type: str,
    module: str = "",
    jurisdiction: str = "EW",
    max_depth: int = 10,
) -> dict[str, Any]:
    """Traverse Neo4j from claim root through REQUIRES / LEADS_TO edges."""
    from backend.core.rag.graphrag_traversal import build_legal_path as pg_build

    if not neo4j_enabled():
        return pg_build(claim_type, module or claim_type, jurisdiction, max_depth)

    root_id = _CLAIM_ROOTS.get(claim_type)
    if not root_id:
        return pg_build(claim_type, module or claim_type, jurisdiction, max_depth)

    driver = _driver()
    if driver is None:
        return pg_build(claim_type, module or claim_type, jurisdiction, max_depth)

    cypher = """
    MATCH (root {id: $root_id})
    OPTIONAL MATCH path = (root)-[:REQUIRES|LEADS_TO|APPLIES_TO*0..%d]->(n)
    WHERE n IS NULL OR coalesce(n.jurisdiction, $jurisdiction) = $jurisdiction
    WITH collect(DISTINCT root) + collect(DISTINCT n) AS nodes
    UNWIND nodes AS node
    WITH DISTINCT node
    RETURN labels(node) AS labels, node.id AS id, node.label AS label,
           node.description AS description, node.authority_level AS authority_level,
           node.source_ref AS source_ref, node.source_url AS source_url
  """ % max_depth

    try:
        with driver.session() as session:
            rows = session.run(
                cypher,
                root_id=root_id,
                jurisdiction=jurisdiction,
            ).data()
            if not rows:
                return pg_build(claim_type, module or claim_type, jurisdiction, max_depth)

            path_nodes = [_row_to_node(r, 0) for r in rows if r.get("id")]

            edge_rows = session.run(
                """
                MATCH (a)-[r:REQUIRES|LEADS_TO|APPLIES_TO|INTERPRETS]->(b)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel, coalesce(r.weight, 1.0) AS weight
                """,
                ids=[n["node_id"] for n in path_nodes],
            ).data()

        edges = [
            {
                "from_node_id": e["from_id"],
                "to_node_id": e["to_id"],
                "from": e["from_id"],
                "to": e["to_id"],
                "relationship": _normalise_relationship(e["rel"]),
                "weight": float(e.get("weight") or 1.0),
                "notes": None,
            }
            for e in edge_rows
        ]

        legal_test_count = sum(1 for n in path_nodes if n["node_type"] == "legal_test")
        remedy_count = sum(1 for n in path_nodes if n["node_type"] == "remedy")
        confidence = min(1.0, 0.5 + min(0.3, legal_test_count * 0.1) + (0.1 if remedy_count else 0))

        return {
            "claim_type": claim_type,
            "path": path_nodes,
            "edges": edges,
            "confidence": confidence,
            "missing_prerequisites": [],
            "jurisdiction": jurisdiction,
            "engine": "neo4j",
        }
    except Exception as exc:
        logger.warning("Neo4j build_legal_chain failed, Postgres fallback: %s", exc)
        result = pg_build(claim_type, module or claim_type, jurisdiction, max_depth)
        result["engine"] = "postgres_fallback"
        return result
    finally:
        driver.close()


def search_legal_graph(query: str, jurisdiction: str = "EW", limit: int = 10) -> dict[str, Any]:
    """Full-text or keyword graph search; returns matched nodes and a short chain."""
    from backend.core.rag.graphrag_traversal import build_legal_path as pg_build

    claim_type = _infer_claim_type(query)
    cache_query = query

    if not neo4j_enabled():
        chain = pg_build(claim_type, claim_type, jurisdiction) if claim_type else _empty_search(query)
        chain["engine"] = "postgres"
        chain["query"] = query
        chain["matches"] = _filter_path_by_query(chain.get("path", []), query)
        return chain

    driver = _driver()
    if driver is None:
        chain = pg_build(claim_type, claim_type, jurisdiction) if claim_type else _empty_search(query)
        chain["engine"] = "postgres_fallback"
        chain["query"] = query
        chain["matches"] = _filter_path_by_query(chain.get("path", []), query)
        return chain

    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    try:
        with driver.session() as session:
            try:
                ft_rows = session.run(
                    """
                    CALL db.index.fulltext.queryNodes('legal_graph_search', $q)
                    YIELD node, score
                    RETURN labels(node) AS labels, node.id AS id, node.label AS label,
                           node.description AS description, node.source_ref AS source_ref,
                           node.source_url AS source_url, score
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    q=query,
                    limit=limit,
                ).data()
            except Exception:
                ft_rows = []

            if not ft_rows and tokens:
                ft_rows = session.run(
                    """
                    MATCH (n)
                    WHERE any(l IN labels(n) WHERE l IN ['LegalTest','Concept','Section','Case'])
                      AND (
                        toLower(coalesce(n.label,'')) CONTAINS $needle
                        OR toLower(coalesce(n.description,'')) CONTAINS $needle
                      )
                    RETURN labels(n) AS labels, n.id AS id, n.label AS label,
                           n.description AS description, n.source_ref AS source_ref,
                           n.source_url AS source_url, 1.0 AS score
                    LIMIT $limit
                    """,
                    needle=tokens[0],
                    limit=limit,
                ).data()

        matches = [_row_to_node(r) for r in ft_rows]
        chain = build_legal_chain(claim_type, claim_type, jurisdiction) if claim_type else _empty_search(query)
        chain["query"] = cache_query
        chain["matches"] = matches or _filter_path_by_query(chain.get("path", []), query)
        chain["engine"] = "neo4j"
        return chain
    except Exception as exc:
        logger.warning("Neo4j search failed, Postgres fallback: %s", exc)
        chain = pg_build(claim_type, claim_type, jurisdiction) if claim_type else _empty_search(query)
        chain["engine"] = "postgres_fallback"
        chain["query"] = query
        chain["matches"] = _filter_path_by_query(chain.get("path", []), query)
        return chain
    finally:
        driver.close()


def _infer_claim_type(query: str) -> str:
    q = query.lower()
    if "constructive" in q:
        return "constructive_dismissal"
    if "employment status" in q or "worker" in q:
        return "employment_status"
    if "unfair" in q or "dismissal" in q or "reasonable" in q:
        return "unfair_dismissal"
    return "unfair_dismissal"


def _filter_path_by_query(path: list[dict], query: str) -> list[dict]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 3]
    if not tokens:
        return path[:5]
    out = []
    for node in path:
        blob = f"{node.get('label','')} {node.get('description','')}".lower()
        if any(t in blob for t in tokens):
            out.append(node)
    return out or path[:5]


def _empty_search(query: str) -> dict[str, Any]:
    return {
        "claim_type": "",
        "path": [],
        "edges": [],
        "confidence": 0.0,
        "missing_prerequisites": ["no_claim_type_inferred"],
        "jurisdiction": "EW",
        "query": query,
        "matches": [],
    }
