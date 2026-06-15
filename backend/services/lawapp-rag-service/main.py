"""
lawapp-rag-service
Port 8017

Hybrid RAG retrieval: PostgreSQL FTS (keyword) + pgvector semantic search
against the real `corpus_chunks` table (not the legacy `legal_corpus` stub).
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
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "database_connected": db is not None,
        "redis_connected": cache is not None,
    }


@app.post("/api/rag/search")
def hybrid_search(request: SearchRequest):
    """Hybrid search over corpus_chunks: FTS keyword + pgvector semantic."""

    if not request.query or len(request.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    limit = max(1, min(int(request.limit or 10), 50))
    cache_key = f"search:{request.query}:{request.corpus_filter}:{limit}"
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    bm25_results = _fts_search(request.query, request.corpus_filter, limit)
    vector_results = _vector_search(request.query, request.corpus_filter, limit)

    merged: dict[str, dict] = {}
    # Prefer FTS (keyword) hits — vector ranking is noisy on a sparse corpus.
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
    return {
        "chunk_id": str(row["id"]),
        "source": source,
        "authority_ref": authority,
        "text": text,
        "relevance_score": round(float(score), 4),
        "match_type": match_type,
    }


def _fts_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """Full-text search against corpus_chunks (indexed via corpus_chunks_fts_idx)."""
    if not db:
        logger.warning("FTS search skipped — no DB connection")
        return []

    results: List[Dict] = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            filter_sql = ""
            sql_params: list[Any] = [query, query]
            if corpus_filter:
                filter_sql = " AND (source_type = %s OR source_table = %s)"
                sql_params.extend([corpus_filter, corpus_filter])
            sql_params.append(limit)
            cur.execute(
                f"""
                SELECT id, source_type, source_table, authority_ref, body_text,
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


def _vector_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """Semantic search via pgvector on corpus_chunks when embeddings exist."""
    if not db:
        return []

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1)"
            )
            if not cur.fetchone()["exists"]:
                return []
    except Exception as e:
        logger.warning("Embedding probe failed: %s", e)
        return []

    try:
        from fastembed import TextEmbedding
    except ImportError:
        logger.info("fastembed not installed — vector search disabled")
        return []

    try:
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        query_vec = list(model.embed([query]))[0].tolist()
        embedding_str = "[" + ",".join(str(x) for x in query_vec) + "]"
    except Exception as e:
        logger.warning("Query embedding failed: %s", e)
        return []

    results: List[Dict] = []
    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            params: list[Any] = [embedding_str, embedding_str]
            filter_sql = ""
            if corpus_filter:
                filter_sql = " AND (source_type = %s OR source_table = %s)"
                params.extend([corpus_filter, corpus_filter])
            params.append(limit)
            cur.execute(
                f"""
                SELECT id, source_type, source_table, authority_ref, body_text,
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
