"""
lawapp-rag-service
Port 8017

Hybrid RAG retrieval: PostgreSQL FTS (keyword) + pgvector semantic search
against the real `corpus_chunks` table (not the legacy `legal_corpus` stub).

Query embeddings: Ollama bge-large-en-v1.5 (1024-dim), matching corpus_chunks.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ollama_embed import EMBEDDING_DIM, embed_query

SERVICE_NAME = "lawapp-rag-service"
SERVICE_PORT = 8017

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    try:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            return psycopg2.connect(database_url)
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "lawapp"),
            user=os.getenv("POSTGRES_USER", "lawapp"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
    except Exception as e:
        logger.warning("DB connection failed: %s", e)
        return None


def _ensure_db():
    """Lazy (re)connect  -  startup may race DB readiness."""
    global db
    try:
        if db is None or db.closed:
            db = get_db_connection()
    except Exception as exc:
        logger.warning("DB reconnect failed: %s", exc)
        db = None
    return db


def get_redis_connection():
    try:
        return redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
    except Exception as e:
        logger.warning("Redis connection failed: %s", e)
        return None


class SearchRequest(BaseModel):
    query: str
    corpus_filter: Optional[str] = None
    limit: Optional[int] = 10


app = FastAPI(title=SERVICE_NAME)
db = None
cache = None


@app.on_event("startup")
def startup():
    global db, cache
    db = get_db_connection()
    cache = get_redis_connection()
    if db:
        logger.info("Database connected")
    else:
        logger.warning("Database not connected at startup  -  will retry per request")
    if cache:
        logger.info("Cache connected")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    conn = _ensure_db()
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "database_connected": conn is not None,
        "redis_connected": cache is not None,
    }


@app.post("/api/rag/search")
def hybrid_search(request: SearchRequest):
    """Hybrid search over corpus_chunks: FTS keyword + pgvector semantic."""

    if not request.query or len(request.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    if _ensure_db() is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    limit = max(1, min(int(request.limit or 10), 50))
    cache_key = f"search:{request.query}:{request.corpus_filter}:{limit}"
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    bm25_results = _fts_search(request.query, request.corpus_filter, limit)
    vector_results = _vector_search(request.query, request.corpus_filter, limit)

    merged: dict[str, dict] = {}
    for row in bm25_results:
        merged[row["chunk_id"]] = row
    for row in vector_results:
        chunk_id = row["chunk_id"]
        existing = merged.get(chunk_id)
        if existing is None:
            merged[chunk_id] = row
        else:
            existing["relevance_score"] = max(existing["relevance_score"], row["relevance_score"])
            existing["match_type"] = "hybrid"

    ranked = sorted(merged.values(), key=lambda x: x["relevance_score"], reverse=True)[:limit]
    response = {
        "query": request.query,
        "results": ranked,
        "total_found": len(ranked),
    }

    if cache:
        cache.setex(cache_key, 3600, json.dumps(response))

    return response


def _row_to_result(row: psycopg2.extras.DictRow, match_type: str, score: float) -> Dict[str, Any]:
    source = row.get("source_type") or row.get("source_table") or "corpus"
    authority = row.get("authority_ref") or ""
    text = (row.get("body_text") or "")[:500]
    eff_from = row.get("effective_from")
    eff_to = row.get("effective_to")
    return {
        "chunk_id": str(row["id"]),
        "source": source,
        "source_type": source,
        "authority_ref": authority,
        "source_url": row.get("source_url") or "",
        "section": authority,
        "jurisdiction": row.get("jurisdiction_code"),
        "effective_from": eff_from.isoformat() if eff_from else None,
        "effective_to": eff_to.isoformat() if eff_to else None,
        "text": text,
        "relevance_score": round(float(score), 4),
        "match_type": match_type,
    }


def _fts_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """Full-text search against corpus_chunks (indexed via corpus_chunks_fts_idx)."""
    conn = _ensure_db()
    if not conn:
        logger.warning("FTS search skipped  -  no DB connection")
        return []

    results: List[Dict] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            filter_sql = ""
            sql_params: list[Any] = [query, query]
            if corpus_filter:
                filter_sql = " AND (source_type = %s OR source_table = %s)"
                sql_params.extend([corpus_filter, corpus_filter])
            sql_params.append(limit)
            cur.execute(
                f"""
                SELECT id, source_type, source_table, authority_ref, source_url,
                       jurisdiction_code, effective_from, effective_to, body_text,
                       ts_rank(
                           to_tsvector('english', body_text),
                           plainto_tsquery('english', %s)
                       ) AS rank
                FROM corpus_chunks
                WHERE is_current IS DISTINCT FROM false
                  AND to_tsvector('english', body_text) @@ plainto_tsquery('english', %s)
                  {filter_sql}
                ORDER BY rank DESC
                LIMIT %s
                """,
                sql_params,
            )
            for row in cur.fetchall():
                rank = float(row.get("rank") or 0.0)
                results.append(_row_to_result(row, "bm25", max(0.1, rank)))
    except Exception as e:
        logger.warning("FTS search error: %s", e)

    return results


def _corpus_embedding_dim(conn) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT vector_dims(embedding) FROM corpus_chunks "
            "WHERE embedding IS NOT NULL LIMIT 1"
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None


def _vector_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """Semantic search via pgvector on corpus_chunks (1024-dim Ollama query embed)."""
    conn = _ensure_db()
    if not conn:
        return []

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1)"
            )
            if not cur.fetchone()["exists"]:
                return []
    except Exception as e:
        logger.warning("Embedding probe failed: %s", e)
        return []

    corpus_dim = _corpus_embedding_dim(conn)
    if corpus_dim is None:
        return []

    try:
        query_vec = embed_query(query)
    except RuntimeError as e:
        logger.warning("Query embedding failed: %s", e)
        return []

    if len(query_vec) != corpus_dim:
        logger.error(
            "Query embedding dim %s != corpus dim %s  -  vector search rejected",
            len(query_vec),
            corpus_dim,
        )
        return []

    if corpus_dim != EMBEDDING_DIM:
        logger.error(
            "Corpus dim %s != configured EMBEDDING_DIM %s  -  vector search rejected",
            corpus_dim,
            EMBEDDING_DIM,
        )
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_vec) + "]"
    results: List[Dict] = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            params: list[Any] = [embedding_str, embedding_str]
            filter_sql = ""
            if corpus_filter:
                filter_sql = " AND (source_type = %s OR source_table = %s)"
                params.extend([corpus_filter, corpus_filter])
            params.append(limit)
            cur.execute(
                f"""
                SELECT id, source_type, source_table, authority_ref, source_url,
                       jurisdiction_code, effective_from, effective_to, body_text,
                       (1.0 - (embedding <=> %s::vector)) AS similarity
                FROM corpus_chunks
                WHERE embedding IS NOT NULL
                  AND is_current IS DISTINCT FROM false
                  {filter_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            for row in cur.fetchall():
                sim = float(row.get("similarity") or 0.0)
                results.append(_row_to_result(row, "vector", sim))
    except Exception as e:
        logger.warning("Vector search error: %s", e)

    return results


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
