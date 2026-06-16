"""
LAWAPP GraphRAG Service (Port 8018)  -  Legal Path Finding API

Endpoints:
  POST /api/graphrag/traverse → traverse legal path for claim type
  GET /api/graphrag/requirements/{claim_type} → all prerequisites
  GET /api/graphrag/remedies/{claim_type} → all remedies
  GET /api/graphrag/deadlines/{claim_type} → all time limits

Health checks:
  GET /health → {"status": "ok"}
  GET /ready → {"status": "ready", "database_connected": bool}

HARD RULE: All endpoints enforce real database queries from legal_nodes/legal_edges.
No invented graph structures. Graph seeded with real UK employment law.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import uvicorn

from backend.core.rag.graphrag_traversal import (
    build_legal_path,
    build_legal_path_cached,
    find_deadlines_for_claim,
    find_remedies_for_claim,
    graph_engine_mode,
    search_legal_graph_cached,
    traverse_requirements,
)
from ingestion.db import get_connection

# ── Setup ──────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="LAWAPP GraphRAG Service",
    description="Legal knowledge graph traversal for claim analysis",
    version="1.0.0",
)

PORT = int(os.getenv("PORT", 8018))

# ── Request/Response Models ────────────────────────────────────────────

class GraphRAGTraverseRequest(BaseModel):
    claim_type: str = Field(..., description="Claim type: unfair_dismissal | constructive_dismissal | employment_status")
    module: str = Field(..., description="Module for graph context")
    jurisdiction: str = Field(default="EW", description="EW (England/Wales) | S (Scotland)")
    facts: dict = Field(default_factory=dict, description="Optional claim facts for path validation")


class LegalNode(BaseModel):
    node_id: str
    node_type: str  # legislation_section | claim_type | legal_test | remedy | defence | deadline | procedure
    label: str
    description: Optional[str] = None
    authority_level: int
    source_ref: Optional[str] = None
    source_url: Optional[str] = None
    required: bool
    depth: int


class LegalEdge(BaseModel):
    from_node_id: str
    to_node_id: str
    relationship: str  # requires | applies_to | leads_to | interprets | extends | reduces | excludes
    weight: float
    notes: Optional[str] = None


class GraphRAGTraverseResponse(BaseModel):
    claim_type: str
    path: list[LegalNode]
    edges: list[LegalEdge]
    confidence: float
    missing_prerequisites: list[str]
    jurisdiction: str
    trace_id: Optional[str] = None


class RequirementsResponse(BaseModel):
    claim_type: str
    requirements: list[LegalNode]
    procedures: list[LegalNode]
    total_requirements: int
    jurisdiction: str
    trace_id: Optional[str] = None


class RemediesResponse(BaseModel):
    claim_type: str
    remedies: list[LegalNode]
    total_remedies: int
    jurisdiction: str
    trace_id: Optional[str] = None


class DeadlinesResponse(BaseModel):
    claim_type: str
    deadlines: list[LegalNode]
    total_deadlines: int
    jurisdiction: str
    trace_id: Optional[str] = None


class GraphSearchRequest(BaseModel):
    query: str = Field(..., description="Natural language graph search query")
    jurisdiction: str = Field(default="EW", description="EW | S")
    limit: int = Field(default=10, ge=1, le=50)


class GraphSearchResponse(BaseModel):
    query: str
    claim_type: str
    path: list[LegalNode]
    edges: list[LegalEdge]
    matches: list[LegalNode]
    confidence: float
    jurisdiction: str
    engine: str
    cache_hit: bool = False
    trace_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    engine: Optional[str] = None
    mode: Optional[str] = None


class ReadinessResponse(BaseModel):
    status: str
    database_connected: bool
    engine: str = "postgres"
    neo4j_enabled: bool = False


# ── Middleware ────────────────────────────────────────────────────────

@app.middleware("http")
async def add_trace_id(request, call_next):
    """Extract or generate trace ID from request headers."""
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
    response = await call_next(request)
    if trace_id:
        response.headers["X-Trace-ID"] = trace_id
    return response


# ── Health & Readiness ────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe."""
    from datetime import datetime
    from backend.core.rag.graphrag_traversal import health as graph_health

    gh = graph_health()
    return {
        "status": gh.get("status", "ok"),
        "timestamp": datetime.utcnow().isoformat(),
        "engine": gh.get("engine"),
        "mode": gh.get("mode"),
    }


@app.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Readiness probe. Postgres always required; Neo4j optional when enabled."""
    from backend.core.rag.neo4j_traversal import neo4j_enabled

    db_ok = False
    engine = graph_engine_mode()

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM legal_nodes LIMIT 1")
        conn.close()
        db_ok = True
    except Exception as e:
        logger.warning(f"Database connectivity check failed: {e}")

    if not db_ok:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "ready",
        "database_connected": db_ok,
        "engine": engine,
        "neo4j_enabled": neo4j_enabled(),
    }


# ── GraphRAG Traversal Endpoint ────────────────────────────────────────

@app.post("/api/graphrag/traverse", response_model=GraphRAGTraverseResponse)
async def graphrag_traverse(
    request: GraphRAGTraverseRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Traverse legal graph from claim type through all prerequisites to remedies.

    Returns path nodes with confidence score and missing prerequisites.
    """
    try:
        path_result = build_legal_path_cached(
            claim_type=request.claim_type,
            module=request.module,
            jurisdiction=request.jurisdiction,
            query=request.claim_type,
        )

        # Convert path nodes to Pydantic models
        path_nodes = [
            LegalNode(
                node_id=n["node_id"],
                node_type=n["node_type"],
                label=n["label"],
                description=n["description"],
                authority_level=n["authority_level"],
                source_ref=n["source_ref"],
                source_url=n["source_url"],
                required=n["required"],
                depth=n["depth"],
            )
            for n in path_result.get("path", [])
        ]

        # Convert edges to Pydantic models
        edges = [
            LegalEdge(
                from_node_id=e["from"],
                to_node_id=e["to"],
                relationship=e["relationship"],
                weight=e["weight"],
                notes=e["notes"],
            )
            for e in path_result.get("edges", [])
        ]

        # Write audit (non-fatal)
        _write_graphrag_audit(request.claim_type, len(path_nodes), x_trace_id)

        return GraphRAGTraverseResponse(
            claim_type=request.claim_type,
            path=path_nodes,
            edges=edges,
            confidence=path_result.get("confidence", 0.0),
            missing_prerequisites=path_result.get("missing_prerequisites", []),
            jurisdiction=request.jurisdiction,
            trace_id=x_trace_id,
        )

    except Exception as e:
        logger.error(f"GraphRAG traversal failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"GraphRAG traversal failed: {str(e)}")


@app.post("/api/graph/search", response_model=GraphSearchResponse)
async def graph_search(
    request: GraphSearchRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """Natural-language graph search (hybrid Neo4j or Postgres)."""
    try:
        result = search_legal_graph_cached(
            query=request.query,
            jurisdiction=request.jurisdiction,
            limit=request.limit,
        )
        path_nodes = [
            LegalNode(
                node_id=n["node_id"],
                node_type=n["node_type"],
                label=n["label"],
                description=n.get("description"),
                authority_level=n.get("authority_level", 2),
                source_ref=n.get("source_ref"),
                source_url=n.get("source_url"),
                required=n.get("required", False),
                depth=n.get("depth", 0),
            )
            for n in result.get("path", [])
        ]
        match_nodes = [
            LegalNode(
                node_id=n["node_id"],
                node_type=n["node_type"],
                label=n["label"],
                description=n.get("description"),
                authority_level=n.get("authority_level", 2),
                source_ref=n.get("source_ref"),
                source_url=n.get("source_url"),
                required=n.get("required", False),
                depth=n.get("depth", 0),
            )
            for n in result.get("matches", [])
        ]
        edges = [
            LegalEdge(
                from_node_id=e["from"],
                to_node_id=e["to"],
                relationship=e["relationship"],
                weight=e.get("weight", 1.0),
                notes=e.get("notes"),
            )
            for e in result.get("edges", [])
        ]
        return GraphSearchResponse(
            query=request.query,
            claim_type=result.get("claim_type", ""),
            path=path_nodes,
            edges=edges,
            matches=match_nodes,
            confidence=result.get("confidence", 0.0),
            jurisdiction=request.jurisdiction,
            engine=result.get("engine", graph_engine_mode()),
            cache_hit=bool(result.get("cache_hit")),
            trace_id=x_trace_id,
        )
    except Exception as e:
        logger.error(f"Graph search failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Graph search failed: {str(e)}")


# ── Requirements Endpoint ──────────────────────────────────────────────

@app.get("/api/graphrag/requirements/{claim_type}", response_model=RequirementsResponse)
async def get_requirements(
    claim_type: str,
    jurisdiction: str = "EW",
    x_trace_id: Optional[str] = Header(None),
):
    """
    List all legal requirements (tests and procedures) for a claim type.
    """
    try:
        result = traverse_requirements(claim_type, jurisdiction)

        # Convert to Pydantic models
        requirements = [
            LegalNode(
                node_id=r["node_id"],
                node_type=r["node_type"],
                label=r["label"],
                description=r["description"],
                authority_level=r["authority_level"],
                source_ref=r["source_ref"],
                source_url=r["source_url"],
                required=True,
                depth=0,
            )
            for r in result.get("requirements", [])
        ]

        procedures = [
            LegalNode(
                node_id=p["node_id"],
                node_type=p["node_type"],
                label=p["label"],
                description=p["description"],
                authority_level=p["authority_level"],
                source_ref=p["source_ref"],
                source_url=p["source_url"],
                required=True,
                depth=0,
            )
            for p in result.get("procedures", [])
        ]

        return RequirementsResponse(
            claim_type=claim_type,
            requirements=requirements,
            procedures=procedures,
            total_requirements=result.get("total_requirements", 0),
            jurisdiction=jurisdiction,
            trace_id=x_trace_id,
        )

    except Exception as e:
        logger.error(f"Requirements retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Requirements retrieval failed: {str(e)}")


# ── Remedies Endpoint ──────────────────────────────────────────────────

@app.get("/api/graphrag/remedies/{claim_type}", response_model=RemediesResponse)
async def get_remedies(
    claim_type: str,
    jurisdiction: str = "EW",
    x_trace_id: Optional[str] = Header(None),
):
    """
    List all remedies applicable to a claim type.
    """
    try:
        result = find_remedies_for_claim(claim_type, jurisdiction)

        # Convert to Pydantic models
        remedies = [
            LegalNode(
                node_id=r["node_id"],
                node_type=r["node_type"],
                label=r["label"],
                description=r["description"],
                authority_level=r["authority_level"],
                source_ref=r["source_ref"],
                source_url=r["source_url"],
                required=False,
                depth=0,
            )
            for r in result.get("remedies", [])
        ]

        return RemediesResponse(
            claim_type=claim_type,
            remedies=remedies,
            total_remedies=result.get("total_remedies", 0),
            jurisdiction=jurisdiction,
            trace_id=x_trace_id,
        )

    except Exception as e:
        logger.error(f"Remedies retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Remedies retrieval failed: {str(e)}")


# ── Deadlines Endpoint ────────────────────────────────────────────────

@app.get("/api/graphrag/deadlines/{claim_type}", response_model=DeadlinesResponse)
async def get_deadlines(
    claim_type: str,
    jurisdiction: str = "EW",
    x_trace_id: Optional[str] = Header(None),
):
    """
    List all time limits and deadlines for a claim type.
    """
    try:
        result = find_deadlines_for_claim(claim_type, jurisdiction)

        # Convert to Pydantic models
        deadlines = [
            LegalNode(
                node_id=d["node_id"],
                node_type=d["node_type"],
                label=d["label"],
                description=d["description"],
                authority_level=d["authority_level"],
                source_ref=d["source_ref"],
                source_url=d["source_url"],
                required=True,
                depth=0,
            )
            for d in result.get("deadlines", [])
        ]

        return DeadlinesResponse(
            claim_type=claim_type,
            deadlines=deadlines,
            total_deadlines=result.get("total_deadlines", 0),
            jurisdiction=jurisdiction,
            trace_id=x_trace_id,
        )

    except Exception as e:
        logger.error(f"Deadlines retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deadlines retrieval failed: {str(e)}")


# ── Audit Logging (non-fatal) ──────────────────────────────────────────

def _write_graphrag_audit(
    claim_type: str,
    nodes_count: int,
    trace_id: Optional[str],
) -> None:
    """Write GraphRAG audit row. Fails silently."""
    try:
        from ingestion.db import get_connection as _gc
        conn = _gc()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO routing_decisions
                        (user_id, claim_type, selected_path, risk_level, reason)
                    VALUES (%s, %s, 'graphrag_traversal', %s, %s)
                    """,
                    (None, claim_type, "low", f"GraphRAG: {nodes_count} nodes in path"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"GraphRAG audit write skipped: {e}")


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting LAWAPP GraphRAG Service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level=os.getenv("LOG_LEVEL", "INFO").lower())
