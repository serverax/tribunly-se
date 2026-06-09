from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date
from typing import Any


RULES_URL = os.getenv("RULES_SERVICE_URL", "http://lawapp-rules-service:8016").rstrip("/")
RAG_URL = os.getenv("RAG_SERVICE_URL", "http://lawapp-rag-service:8017").rstrip("/")
GRAPH_RAG_URL = os.getenv("GRAPH_RAG_SERVICE_URL", "http://lawapp-graph-rag-service:8018").rstrip("/")


def _get_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def build_authority_bundle(message: str, claim_type: str | None, facts: dict) -> dict[str, Any]:
    rules = _get_json(f"{RULES_URL}/api/rules/list?domain=uk_employment")
    rag = _post_json(f"{RAG_URL}/api/rag/search", {"query": message, "limit": 5})
    graph: dict[str, Any] = {}
    if claim_type:
        graph = _post_json(
            f"{GRAPH_RAG_URL}/api/graphrag/traverse",
            {"claim_type": claim_type, "module": claim_type, "jurisdiction": "EW", "facts": facts},
        )

    exact_rules: list[dict[str, Any]] = []
    authorities: list[dict[str, Any]] = []

    # Local DB-backed fallback/merge. This avoids marking chatbot PARTIAL just
    # because a sidecar service is unavailable or returns an older response shape.
    if claim_type:
        try:
            from backend.core.retrieve import retrieve

            bundle = retrieve(message, claim_type, "EW", date.today())
            exact_rules.extend(bundle.exact_rules)
            authorities.extend(bundle.authorities)
        except Exception:
            pass
        try:
            from backend.core.rag.graphrag_traversal import build_legal_path

            if not graph.get("path"):
                graph = build_legal_path(claim_type, claim_type, "EW")
        except Exception:
            pass

    citations: list[dict[str, Any]] = []
    for rule in exact_rules:
        authority_ref = rule.get("authority_ref")
        if authority_ref:
            citations.append(
                {
                    "cite": authority_ref,
                    "url": rule.get("authority_url"),
                    "support": "rules_table",
                    "rule_key": rule.get("rule_key"),
                }
            )
    for result in rag.get("results", []) or []:
        authority = result.get("authority_ref") or result.get("source")
        if authority:
            citations.append(
                {
                    "cite": authority,
                    "source": result.get("source"),
                    "chunk_id": result.get("chunk_id"),
                    "support": "retrieved_rag_chunk",
                }
            )
    for authority in authorities:
        authority_ref = authority.get("authority_ref") or authority.get("cite")
        if authority_ref:
            citations.append(
                {
                    "cite": authority_ref,
                    "url": authority.get("url"),
                    "support": "rag_authority",
                    "source_id": authority.get("source_id"),
                }
            )
    for node in graph.get("path", []) or []:
        source_ref = node.get("source_ref")
        if source_ref:
            citations.append(
                {
                    "cite": source_ref,
                    "url": node.get("source_url"),
                    "support": "graph_rag_node",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (str(citation.get("cite") or ""), str(citation.get("url") or ""))
        if key not in seen:
            seen.add(key)
            deduped.append(citation)

    rules_ready = bool(exact_rules) or bool((rules.get("rules") or {}).get(claim_type or ""))
    rag_ready = bool(authorities) or bool(rag.get("results"))
    graph_ready = bool(graph.get("path"))
    grounding_score = 0.0
    if deduped:
        grounding_score = min(1.0, 0.35 + (0.2 if rules_ready else 0.0) + (0.2 if rag_ready else 0.0) + (0.2 if graph_ready else 0.0))

    return {
        "exact_rules": exact_rules,
        "authorities": authorities,
        "rules": rules,
        "rag": rag,
        "graph": graph,
        "citations": deduped,
        "grounding_score": grounding_score,
        "confidence_score": grounding_score,
        "insufficient_grounding": not (rules_ready and deduped),
        "rules_ready": rules_ready,
        "rag_ready": rag_ready,
        "graph_rag_ready": graph_ready,
    }
