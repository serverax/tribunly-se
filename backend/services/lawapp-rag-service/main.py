"""
lawapp-rag-service
Port 8017

Hybrid RAG retrieval: BM25 keyword search + vector semantic search.
Retrieves legal corpus chunks for grounding AI responses.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import redis

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
        logger.warning(f"DB connection failed: {e}")
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
        logger.warning(f"Redis connection failed: {e}")
        return None

class SearchRequest(BaseModel):
    query: str
    corpus_filter: Optional[str] = None
    limit: Optional[int] = 10

class SearchResult(BaseModel):
    chunk_id: str
    source: str
    authority_ref: str
    text: str
    relevance_score: float
    match_type: str  # "bm25" or "vector"

app = FastAPI(title=SERVICE_NAME)
db = None
cache = None

@app.on_event("startup")
def startup():
    global db, cache
    db = get_db_connection()
    cache = get_redis_connection()
    if db:
        logger.info("✓ Database connected")
    if cache:
        logger.info("✓ Cache connected")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/ready")
def ready():
    db_ok = db is not None
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "database_connected": db_ok,
        "redis_connected": cache is not None,
    }

@app.post("/api/rag/search")
def hybrid_search(request: SearchRequest):
    """
    Hybrid search: BM25 (keyword) + vector (semantic).
    Returns top results ranked by relevance.
    """

    if not request.query or len(request.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    # Check cache
    cache_key = f"search:{request.query}:{request.corpus_filter}"
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return json.loads(cached)

    # BM25 search (keyword matching)
    bm25_results = _bm25_search(request.query, request.corpus_filter, request.limit)

    # Vector search (semantic matching) - returns empty for now (would need embeddings)
    vector_results = _vector_search(request.query, request.corpus_filter, request.limit)

    # Merge and rank results
    all_results = bm25_results + vector_results
    ranked = sorted(all_results, key=lambda x: x["relevance_score"], reverse=True)[:request.limit]

    response = {
        "query": request.query,
        "results": ranked,
        "total_found": len(ranked),
    }

    # Cache results for 1 hour
    if cache:
        cache.setex(cache_key, 3600, json.dumps(response))

    return response

def _bm25_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """BM25 keyword search against corpus."""

    results = []

    if not db:
        # Fallback: return mock results
        logger.warning("BM25 search without DB - returning empty results")
        return results

    try:
        keywords = query.lower().split()

        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Simple keyword match (production would use PostgreSQL FTS)
            where_clause = " OR ".join([f"corpus_text ILIKE %s" for _ in keywords])
            if corpus_filter:
                where_clause += f" AND corpus_source = %s"

            sql = f"""
                SELECT id, corpus_source, authority_ref, corpus_text, 1.0 as relevance
                FROM legal_corpus
                WHERE {where_clause}
                LIMIT %s
            """

            params = [f"%{kw}%" for kw in keywords]
            if corpus_filter:
                params.append(corpus_filter)
            params.append(limit)

            cur.execute(sql, params)
            rows = cur.fetchall()

            for row in rows:
                results.append({
                    "chunk_id": str(row["id"]),
                    "source": row["corpus_source"],
                    "authority_ref": row["authority_ref"],
                    "text": row["corpus_text"][:500],  # Truncate for response
                    "relevance_score": 0.8,
                    "match_type": "bm25",
                })

    except Exception as e:
        logger.warning(f"BM25 search error: {e}")

    return results

def _vector_search(query: str, corpus_filter: Optional[str], limit: int) -> List[Dict]:
    """Vector semantic search against corpus."""

    # TODO: Implement vector embeddings + pgvector search
    # For now, returns empty (would require embedding model)
    return []

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
