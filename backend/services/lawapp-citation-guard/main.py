"""
lawapp-citation-guard
Port 8018

Citation validator: ensures all legal answers are grounded in corpus.
Rejects any answer without proper citations.
Fail-closed: no answer is better than a fabricated answer.
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

SERVICE_NAME = "lawapp-citation-guard"
SERVICE_PORT = 8018

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
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

class ValidateRequest(BaseModel):
    answer: str
    corpus_chunk_ids: List[str]
    claim_text: str

class ValidationResponse(BaseModel):
    is_valid: bool
    confidence: float
    citations: List[Dict]
    message: str

app = FastAPI(title=SERVICE_NAME)
db = None

@app.on_event("startup")
def startup():
    global db
    db = get_db_connection()
    if db:
        logger.info("✓ Database connected")

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
    }

@app.post("/api/citation/validate")
def validate_answer(request: ValidateRequest) -> Dict:
    """
    Validate that an answer is properly cited in corpus.

    Fail-closed: returns invalid if ANY citation is missing or broken.
    """

    if not request.corpus_chunk_ids:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "citations": [],
            "message": "No corpus citations provided - answer is unsupported",
        }

    # Verify all chunk IDs exist and are valid
    citations = _verify_citations(request.corpus_chunk_ids)

    if len(citations) != len(request.corpus_chunk_ids):
        # Some citations are missing or invalid
        return {
            "is_valid": False,
            "confidence": 0.0,
            "citations": citations,
            "message": "One or more citations could not be verified",
        }

    # All citations valid - check if answer text matches corpus
    grounded = _check_grounding(request.answer, citations)

    return {
        "is_valid": grounded["is_valid"],
        "confidence": grounded["confidence"],
        "citations": citations,
        "message": grounded["message"],
    }

def _verify_citations(chunk_ids: List[str]) -> List[Dict]:
    """Verify that all chunk IDs exist in corpus."""

    verified = []

    if not db:
        logger.warning("Cannot verify citations without DB")
        return []

    try:
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            placeholders = ",".join(["%s"] * len(chunk_ids))
            sql = f"""
                SELECT id, source_type, source_table, authority_ref, body_text
                FROM corpus_chunks
                WHERE id IN ({placeholders})
            """

            cur.execute(sql, chunk_ids)
            rows = cur.fetchall()

            for row in rows:
                verified.append({
                    "chunk_id": str(row["id"]),
                    "source": row.get("source_type") or row.get("source_table") or "corpus",
                    "authority_ref": row["authority_ref"],
                    "text_preview": (row.get("body_text") or "")[:200],
                })

    except Exception as e:
        logger.error(f"Citation verification error: {e}")
        return []

    return verified

def _check_grounding(answer: str, citations: List[Dict]) -> Dict:
    """
    Check if answer is grounded in citations.
    Fail-closed: requires high confidence match.
    """

    if not citations:
        return {
            "is_valid": False,
            "confidence": 0.0,
            "message": "No valid citations found",
        }

    # Simple keyword overlap check (production would use better NLP)
    answer_words = set(answer.lower().split())
    citation_words = set()

    for citation in citations:
        text = citation.get("text_preview", "").lower()
        citation_words.update(text.split())

    overlap = len(answer_words & citation_words)
    possible = len(answer_words)

    # Require 40% word overlap for grounding
    if possible > 0:
        overlap_ratio = overlap / possible
    else:
        overlap_ratio = 0.0

    is_valid = overlap_ratio >= 0.4

    return {
        "is_valid": is_valid,
        "confidence": min(1.0, overlap_ratio),
        "message": f"Answer grounded with {overlap_ratio:.0%} word overlap" if is_valid else "Answer not sufficiently grounded in citations",
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
