"""
Dual-mode graph engine: Neo4j (primary when NEO4J_ENABLED=true) or Postgres fallback.

Redis caches traversal results under graph:chain:{hash}.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_GRAPH_CACHE_PREFIX = "graph:chain:"
_DEFAULT_TTL = int(os.getenv("GRAPH_CHAIN_CACHE_TTL_S", "300"))


def _neo4j_enabled() -> bool:
    return os.getenv("NEO4J_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return _GRAPH_CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


def _get_redis():
    redis_url = os.getenv("REDIS_URL", "").strip()
    redis_host = os.getenv("REDIS_HOST", "").strip()
    if not redis_url and not redis_host:
        return None
    try:
        import redis

        if redis_url:
            return redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        return redis.Redis(
            host=redis_host,
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception as exc:
        logger.debug("Redis unavailable for graph cache: %s", exc)
        return None


def _cache_get(key: str) -> Optional[dict]:
    client = _get_redis()
    if not client:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: dict, ttl: int = _DEFAULT_TTL) -> None:
    client = _get_redis()
    if not client:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def _get_neo4j_driver():
    if not _neo4j_enabled():
        return None
    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "lawapp_dev_only")
        return GraphDatabase.driver(uri, auth=(user, password))
    except Exception as exc:
        logger.warning("Neo4j driver unavailable: %s", exc)
        return None


def _postgres_chain(claim_type: str, jurisdiction: str, max_depth: int) -> dict:
    from backend.core.rag.graphrag_traversal import build_legal_path

    result = build_legal_path(claim_type, claim_type, jurisdiction=jurisdiction, max_depth=max_depth)
    return {
        "engine": "postgres",
        "claim_type": claim_type,
        "jurisdiction": jurisdiction,
        "path": result.get("path", []),
        "edges": result.get("edges", []),
        "confidence": result.get("confidence", 0.0),
        "missing_prerequisites": result.get("missing_prerequisites", []),
        "context_text": _format_path_text(result.get("path", []), result.get("edges", [])),
    }


def _neo4j_chain(claim_type: str, jurisdiction: str, max_depth: int) -> Optional[dict]:
    driver = _get_neo4j_driver()
    if driver is None:
        return None

    cypher = """
    MATCH (root)
    WHERE (root:Concept OR root:LegalTest OR root:Section)
      AND (
        toLower(root.label) CONTAINS $claim_hint
        OR root.id = $claim_id
      )
      AND (root.jurisdiction IS NULL OR root.jurisdiction IN [$jurisdiction, 'GB', 'EW', 'UK'])
    WITH root LIMIT 1
    CALL apoc.path.subgraphAll(root, {
      relationshipFilter: 'REQUIRES>|LEADS_TO>|APPLIES_TO>|INTERPRETS>|ESTABLISHES>|IMPLIES>|CONTAINS>',
      maxLevel: $max_depth
    })
    YIELD nodes, relationships
    RETURN nodes, relationships
    """

    # Fallback query without APOC (Neo4j 5 community)
    cypher_simple = """
    MATCH (root)
    WHERE (root:Concept OR root:LegalTest OR root:Section)
      AND (
        toLower(coalesce(root.label, '')) CONTAINS $claim_hint
        OR root.id = $claim_id
      )
    WITH root LIMIT 1
    OPTIONAL MATCH path = (root)-[r:REQUIRES|LEADS_TO|APPLIES_TO|INTERPRETS|ESTABLISHES|IMPLIES|CONTAINS*1..3]->(n)
    WITH root, collect(DISTINCT n) AS reached, [rel IN relationships(path) | rel] AS rels
    RETURN root AS nodes0, reached AS nodes, rels AS relationships
    """

    claim_hint = claim_type.replace("_", " ").lower()
    claim_id_map = {
        "unfair_dismissal": "unfair_dismissal",
        "constructive_dismissal": "constructive_dismissal",
        "employment_status": "employment_status",
    }
    params = {
        "claim_hint": claim_hint,
        "claim_id": claim_id_map.get(claim_type, claim_type),
        "jurisdiction": jurisdiction,
        "max_depth": max_depth,
    }

    try:
        with driver.session() as session:
            try:
                record = session.run(cypher, **params).single()
            except Exception:
                record = session.run(
                    cypher_simple,
                    claim_hint=claim_hint,
                    claim_id=params["claim_id"],
                ).single()

            if not record:
                return None

            nodes_raw = []
            if record.get("nodes0"):
                nodes_raw.append(record["nodes0"])
            for n in record.get("nodes") or []:
                if n is not None:
                    nodes_raw.append(n)

            path_nodes = []
            for node in nodes_raw:
                if node is None:
                    continue
                labels = list(node.labels) if hasattr(node, "labels") else []
                path_nodes.append({
                    "node_id": node.get("id", str(node.element_id) if hasattr(node, "element_id") else ""),
                    "node_type": labels[0].lower() if labels else "concept",
                    "label": node.get("label", ""),
                    "description": node.get("description"),
                    "authority_level": int(node.get("authority_level", 2)),
                    "source_ref": node.get("source_ref"),
                    "source_url": node.get("source_url"),
                    "required": "LegalTest" in labels or "legaltest" in [x.lower() for x in labels],
                    "depth": 0,
                })

            edges = []
            for rel in record.get("relationships") or []:
                if rel is None:
                    continue
                if hasattr(rel, "type"):
                    edges.append({
                        "from_node_id": rel.start_node.get("id", ""),
                        "to_node_id": rel.end_node.get("id", ""),
                        "relationship": rel.type.lower(),
                        "weight": 1.0,
                        "notes": None,
                    })

            confidence = min(1.0, 0.5 + 0.1 * len(path_nodes)) if path_nodes else 0.0
            return {
                "engine": "neo4j",
                "claim_type": claim_type,
                "jurisdiction": jurisdiction,
                "path": path_nodes,
                "edges": edges,
                "confidence": confidence,
                "missing_prerequisites": [],
                "context_text": _format_path_text(path_nodes, edges),
            }
    except Exception as exc:
        logger.warning("Neo4j traversal failed, will fall back to Postgres: %s", exc)
        return None
    finally:
        try:
            driver.close()
        except Exception:
            pass


def _format_path_text(path: list[dict], edges: list[dict]) -> str:
    lines = ["LEGAL GRAPH CHAIN:"]
    for node in sorted(path, key=lambda n: n.get("authority_level", 5)):
        label = node.get("label") or node.get("node_id", "")
        ref = node.get("source_ref") or ""
        line = f"  [{node.get('node_type', 'node')}] {label}"
        if ref:
            line += f" ({ref})"
        lines.append(line)
    if edges:
        lines.append("RELATIONSHIPS:")
        for edge in edges[:50]:
            lines.append(
                f"  {edge.get('from_node_id')} --[{edge.get('relationship')}]--> {edge.get('to_node_id')}"
            )
    return "\n".join(lines)


def build_graph_chain(
    claim_type: str,
    jurisdiction: str = "EW",
    max_depth: int = 10,
    query: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    """
    Build legal graph chain with Neo4j primary (when enabled) and Postgres fallback.
  """
    cache_payload = {
        "claim_type": claim_type,
        "jurisdiction": jurisdiction,
        "max_depth": max_depth,
        "query": query or "",
        "neo4j": _neo4j_enabled(),
    }
    key = _cache_key(cache_payload)
    if use_cache:
        cached = _cache_get(key)
        if cached:
            cached["cache_hit"] = True
            return cached

    result: Optional[dict] = None
    if _neo4j_enabled():
        result = _neo4j_chain(claim_type, jurisdiction, max_depth)

    if result is None:
        result = _postgres_chain(claim_type, jurisdiction, max_depth)

    result["cache_hit"] = False
    _cache_set(key, result)
    return result


def search_graph_by_query(query: str, jurisdiction: str = "EW", limit: int = 10) -> dict:
    """Map natural-language query to claim type and return graph chain."""
    q = (query or "").lower()
    claim_type = "unfair_dismissal"
    if "constructive" in q:
        claim_type = "constructive_dismissal"
    elif "employment status" in q or "worker" in q and "dismissal" not in q:
        claim_type = "employment_status"
    elif "unfair dismissal" in q or "reasonable responses" in q or "band of reasonable" in q:
        claim_type = "unfair_dismissal"

    chain = build_graph_chain(claim_type, jurisdiction=jurisdiction, query=query)
    chain["query"] = query
    chain["matched_claim_type"] = claim_type
    chain["hits"] = chain.get("path", [])[:limit]
    return chain


def engine_health() -> dict[str, Any]:
    mode = "postgres"
    neo4j_ok = False
    if _neo4j_enabled():
        mode = "neo4j"
        driver = _get_neo4j_driver()
        if driver:
            try:
                with driver.session() as session:
                    session.run("RETURN 1").single()
                neo4j_ok = True
            except Exception as exc:
                logger.warning("Neo4j health check failed: %s", exc)
            finally:
                driver.close()
        if not neo4j_ok:
            mode = "neo4j_degraded_postgres_fallback"

    from backend.core.rag.graphrag_traversal import GraphRAGTraversal

    pg = GraphRAGTraversal().health()
    return {
        "neo4j_enabled": _neo4j_enabled(),
        "neo4j_ok": neo4j_ok,
        "mode": mode,
        "postgres": pg,
        "redis": _get_redis() is not None,
    }
