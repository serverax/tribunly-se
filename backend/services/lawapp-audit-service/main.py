"""
LAWAPP Audit Service
====================
Records all actions for compliance, debugging, and governance.
Write-only service (no deletes). All writes include trace_id, user_id, tenant_id.

Service Contract: port 8020
Endpoints:
  - GET /health → {status: 'ok'}
  - GET /ready → {status: 'ready'} or 503
  - POST /api/audit/log → {trace_id, action, result, timestamp} → 201
  - GET /api/audit/trace/{trace_id} → returns all steps for this trace
  - GET /api/audit/user/{user_id}?limit=100 → returns recent actions for user
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
import json

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import redis

# ────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lawapp:lawapp@db:5432/lawapp")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


def get_db_connection():
    """Get a fresh database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_redis_client():
    """Get a fresh Redis client."""
    return redis.from_url(REDIS_URL, decode_responses=True)


# ────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ────────────────────────────────────────────────────────────────────


class AuditLogRequest(BaseModel):
    trace_id: str
    user_id: str
    tenant_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    result: str
    error_message: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: str
    trace_id: str
    user_id: str
    tenant_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    result: str
    error_message: Optional[str]
    created_at: str


class AuditTraceResponse(BaseModel):
    trace_id: str
    steps: List[AuditLogResponse]
    total_steps: int


class UserAuditResponse(BaseModel):
    user_id: str
    recent_actions: List[AuditLogResponse]
    total_count: int


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
    title="LAWAPP Audit Service",
    version="1.0.0",
    description="Immutable audit logging service for compliance and governance"
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
# AUDIT LOGGING ENDPOINTS
# ────────────────────────────────────────────────────────────────────


@app.post("/api/audit/log", status_code=201, response_model=AuditLogResponse)
async def log_audit(
    request: AuditLogRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Create an immutable audit log entry.
    All writes include trace_id, user_id, tenant_id for traceability.
    """
    log_id = str(uuid4())
    trace_id = x_trace_id or request.trace_id

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO audit_events (
                id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
                result, error_message, metadata, created_at
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            RETURNING id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
                      result, error_message, created_at
        """

        params = [
            log_id,
            trace_id,
            request.user_id,
            request.tenant_id,
            request.action,
            request.resource_type,
            request.resource_id,
            request.result,
            request.error_message,
            json.dumps({"old_value": request.old_value, "new_value": request.new_value}),
        ]

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.commit()
        cursor.close()

        logger.info(
            f"Logged audit entry: {request.action} on {request.resource_type} "
            f"(trace={trace_id}, user={request.user_id})"
        )

        return AuditLogResponse(
            id=row[0],
            trace_id=row[1],
            user_id=row[2],
            tenant_id=row[3],
            action=row[4],
            resource_type=row[5],
            resource_id=row[6],
            result=row[7],
            error_message=row[8],
            created_at=row[9].isoformat()
        )

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error logging audit entry: {e} (trace={trace_id})")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@app.get("/api/audit/trace/{trace_id}", response_model=AuditTraceResponse)
async def get_audit_trace(
    trace_id: str,
):
    """
    Retrieve all audit log entries for a specific trace.
    Useful for replaying the entire decision history of a request.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
                   result, error_message, created_at
            FROM audit_events
            WHERE trace_id = %s
            ORDER BY created_at ASC
        """

        cursor.execute(query, [trace_id])
        rows = cursor.fetchall()
        cursor.close()

        steps = []
        for row in rows:
            steps.append(AuditLogResponse(
                id=row["id"],
                trace_id=row["trace_id"],
                user_id=row["user_id"],
                tenant_id=row["tenant_id"],
                action=row["action"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                result=row["result"],
                error_message=row["error_message"],
                created_at=row["created_at"].isoformat()
            ))

        logger.info(f"Retrieved audit trace {trace_id}: {len(steps)} steps")
        return AuditTraceResponse(
            trace_id=trace_id,
            steps=steps,
            total_steps=len(steps)
        )

    except Exception as e:
        logger.error(f"Error retrieving audit trace: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@app.get("/api/audit/user/{user_id}", response_model=UserAuditResponse)
async def get_user_audit(
    user_id: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Retrieve recent audit log entries for a specific user.
    User isolation: service must verify user is authorized to view these logs
    (handled by upstream gateway-api JWT validation).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT id, trace_id, user_id, tenant_id, action, resource_type, resource_id,
                   result, error_message, created_at
            FROM audit_events
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """

        cursor.execute(query, [user_id, limit])
        rows = cursor.fetchall()
        cursor.close()

        actions = []
        for row in rows:
            actions.append(AuditLogResponse(
                id=row["id"],
                trace_id=row["trace_id"],
                user_id=row["user_id"],
                tenant_id=row["tenant_id"],
                action=row["action"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                result=row["result"],
                error_message=row["error_message"],
                created_at=row["created_at"].isoformat()
            ))

        # Get total count for pagination
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_events WHERE user_id = %s", [user_id])
        total = cursor.fetchone()[0]
        cursor.close()

        logger.info(f"Retrieved audit for user {user_id}: {len(actions)} recent actions (total={total})")
        return UserAuditResponse(
            user_id=user_id,
            recent_actions=actions,
            total_count=total
        )

    except Exception as e:
        logger.error(f"Error retrieving user audit: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8020"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())
