"""
LAWAPP Redaction Service
========================
Removes PII before sending to third-party models.
Never logs original PII. Detects and redacts: names, addresses, phones, emails, dates, companies, salaries.

Service Contract: port 8019
Endpoints:
  - GET /health → {status: 'ok'}
  - GET /ready → {status: 'ready'} or 503
  - POST /api/redact → {text: "..."} → {redacted_text: "...", redaction_map: {...}}
  - POST /api/validate_redaction → {original: "...", redacted: "..."} → {valid: bool}
"""

import os
import logging
import re
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Any
from uuid import uuid4
import json

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
import psycopg2.extras

# ────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lawapp:lawapp@db:5432/lawapp")


def get_db_connection():
    """Get a fresh database connection."""
    return psycopg2.connect(DATABASE_URL)


# ────────────────────────────────────────────────────────────────────
# PII DETECTION PATTERNS
# ────────────────────────────────────────────────────────────────────

# Simple regex patterns for common PII types
# Production systems would use libraries like microsoft-presidio or spacy

PII_PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "PHONE": re.compile(r'\b(?:\+44|0)(?:\d\s?){9,10}\b'),
    "UK_POSTCODE": re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', re.IGNORECASE),
    "SALARY": re.compile(r'\£[\d,]+(?:\.\d{2})?'),
    "DATE": re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
    "NAME": re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),  # Simple pattern for person names
}

COMPANY_KEYWORDS = [
    "ltd", "limited", "plc", "inc", "corp", "corporation", "company",
    "group", "holdings", "partners", "llp", "llc"
]


# ────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ────────────────────────────────────────────────────────────────────


class RedactionRequest(BaseModel):
    text: str
    trace_id: Optional[str] = None


class RedactionEntity(BaseModel):
    type: str
    original_value: str
    redacted_value: str
    position: int


class RedactionResponse(BaseModel):
    redacted_text: str
    entities_found: int
    entities: List[RedactionEntity]
    redaction_rule_hash: str


class ValidationRequest(BaseModel):
    original: str
    redacted: str


class ValidationResponse(BaseModel):
    valid: bool
    reason: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str
    database_connected: bool
    timestamp: str


# ────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LAWAPP Redaction Service",
    version="1.0.0",
    description="PII detection and redaction service"
)


# ────────────────────────────────────────────────────────────────────
# HEALTH & READINESS ENDPOINTS
# ────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready", response_model=ReadinessResponse)
async def readiness():
    """Readiness check (503 if DB unavailable)."""
    db_ok = False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_ok = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "database_connected": False,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    return {
        "status": "ready",
        "database_connected": True,
        "timestamp": datetime.utcnow().isoformat()
    }


# ────────────────────────────────────────────────────────────────────
# REDACTION LOGIC
# ────────────────────────────────────────────────────────────────────


def detect_pii(text: str) -> List[Dict[str, Any]]:
    """
    Detect PII entities in text.
    Returns list of {type, value, position}.
    """
    entities = []

    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            entities.append({
                "type": pii_type,
                "value": match.group(),
                "position": match.start(),
                "end_position": match.end()
            })

    # Detect company names (words followed by company keywords)
    for keyword in COMPANY_KEYWORDS:
        pattern = re.compile(rf'\b[A-Za-z\s]+\s{keyword}\b', re.IGNORECASE)
        for match in pattern.finditer(text):
            entities.append({
                "type": "COMPANY",
                "value": match.group(),
                "position": match.start(),
                "end_position": match.end()
            })

    # Sort by position for proper replacement
    entities.sort(key=lambda x: x["position"])
    return entities


def redact_text(text: str, entities: List[Dict[str, Any]]) -> tuple:
    """
    Redact detected PII entities.
    Returns (redacted_text, redaction_map).
    """
    redaction_map = {}
    redacted = text

    # Process entities in reverse order to maintain positions
    for entity in reversed(entities):
        start = entity["position"]
        end = entity["end_position"]
        pii_type = entity["type"]
        original_value = entity["value"]

        redacted_placeholder = f"[{pii_type}]"
        redacted = redacted[:start] + redacted_placeholder + redacted[end:]

        # Store mapping for audit (never expose actual PII in logs)
        redaction_map[redacted_placeholder] = {
            "type": pii_type,
            "hash": hashlib.sha256(original_value.encode()).hexdigest(),
            "length": len(original_value)
        }

    return redacted, redaction_map


# ────────────────────────────────────────────────────────────────────
# REDACTION ENDPOINTS
# ────────────────────────────────────────────────────────────────────


@app.post("/api/redact", response_model=RedactionResponse)
async def redact(
    request: RedactionRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Redact PII from text.
    Returns redacted_text and metadata about redactions (but not original PII).
    """
    trace_id = x_trace_id or request.trace_id or str(uuid4())

    try:
        # Detect PII
        entities = detect_pii(request.text)

        # Redact
        redacted_text, redaction_map = redact_text(request.text, entities)

        # Create hash of redaction rules applied
        rule_hash = hashlib.sha256(
            json.dumps(redaction_map, sort_keys=True).encode()
        ).hexdigest()

        # Log to audit table (never store original text)
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            original_hash = hashlib.sha256(request.text.encode()).hexdigest()
            redacted_hash = hashlib.sha256(redacted_text.encode()).hexdigest()

            query = """
                INSERT INTO redaction_audit (
                    trace_id, original_hash, redacted_hash, redaction_rules_applied, created_at
                ) VALUES (%s, %s, %s, %s, NOW())
            """

            cursor.execute(query, [
                trace_id,
                original_hash,
                redacted_hash,
                json.dumps(redaction_map)
            ])
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.warning(f"Failed to log redaction audit: {e}")
            if conn:
                conn.rollback()
                conn.close()

        # Build response with safe entity list (no original PII)
        safe_entities = [
            RedactionEntity(
                type=e["type"],
                original_value="[REDACTED]",
                redacted_value=f"[{e['type']}]",
                position=e["position"]
            )
            for e in entities
        ]

        logger.info(
            f"Redacted {len(entities)} PII entities (trace={trace_id})"
        )

        return RedactionResponse(
            redacted_text=redacted_text,
            entities_found=len(entities),
            entities=safe_entities,
            redaction_rule_hash=rule_hash
        )

    except Exception as e:
        logger.error(f"Error redacting text: {e} (trace={trace_id})")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/validate_redaction", response_model=ValidationResponse)
async def validate_redaction(
    request: ValidationRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Validate that a redaction is correct.
    Ensures original PII has been properly replaced.
    """
    trace_id = x_trace_id or str(uuid4())

    try:
        # Detect PII in original
        entities = detect_pii(request.original)

        if not entities:
            return ValidationResponse(
                valid=True,
                reason="No PII detected in original text"
            )

        # Check that redacted text does not contain original PII values
        for entity in entities:
            original_value = entity["value"]
            if original_value.lower() in request.redacted.lower():
                logger.warning(
                    f"Validation failed: original PII still in redacted text (trace={trace_id})"
                )
                return ValidationResponse(
                    valid=False,
                    reason="Original PII value found in redacted text"
                )

        logger.info(
            f"Redaction validation passed: {len(entities)} entities properly redacted (trace={trace_id})"
        )

        return ValidationResponse(
            valid=True,
            reason=f"All {len(entities)} PII entities properly redacted"
        )

    except Exception as e:
        logger.error(f"Error validating redaction: {e} (trace={trace_id})")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8019"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())
