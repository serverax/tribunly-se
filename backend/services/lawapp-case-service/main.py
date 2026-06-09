"""
LAWAPP Case Service
===================
Case details and timeline endpoints.
All timeline events are queried from the case_events table in REAL TIME.

Service Contract: port 8008
Endpoints:
  - GET /health → {status: 'ok'}
  - GET /ready → {status: 'ready'} or 503
  - GET /api/cases/{case_id}/timeline → ordered timeline of case events with deadlines
  - GET /api/cases/{case_id} → case details with ownership check
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Depends
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

# ────────────────────────────────────────────────────────────────────
# DATABASE CONNECTION
# ────────────────────────────────────────────────────────────────────

def get_db_connection():
    """Get a fresh database connection."""
    return psycopg2.connect(DATABASE_URL)


# ────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ────────────────────────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    id: str
    event_type: str
    timestamp: str
    details: Dict[str, Any]
    triggered_by_user_id: Optional[str] = None


class CaseDeadline(BaseModel):
    deadline_type: str  # tribunal_claim | appeal | etc
    date: str
    days_remaining: int


class CaseTimelineResponse(BaseModel):
    case_id: str
    created_at: str
    status: str
    claim_type: str
    jurisdiction: str
    events: List[TimelineEvent]
    deadline: Optional[CaseDeadline] = None


class CaseDetailResponse(BaseModel):
    id: str
    user_id: str
    status: str
    claim_type: str
    jurisdiction: str
    created_at: str
    updated_at: str
    payment_tier: Optional[str] = None
    payment_status: Optional[str] = None


# ────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LAWAPP Case Service",
    version="1.0.0",
    description="Case details and timeline"
)


# ────────────────────────────────────────────────────────────────────
# HEALTH & READINESS
# ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check (always 200 if service is running)."""
    return {
        "status": "healthy",
        "service": "lawapp-case-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready")
async def ready():
    """Readiness check (503 if DB unavailable)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "lawapp-case-service",
                "db": "disconnected"
            }
        )

    return {
        "status": "ready",
        "service": "lawapp-case-service",
        "timestamp": datetime.utcnow().isoformat()
    }


# ────────────────────────────────────────────────────────────────────
# CASE TIMELINE ENDPOINT
# ────────────────────────────────────────────────────────────────────

@app.get("/api/cases/{case_id}/timeline", response_model=CaseTimelineResponse)
async def get_case_timeline(
    case_id: str,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_trace_id: Optional[str] = Header(None),
):
    """
    Get case timeline with real events from case_events table.
    ENFORCES USER OWNERSHIP: only the case owner can view the timeline.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # ════════════════════════════════════════════════════════════════
        # 1. OWNERSHIP CHECK: verify user owns this case
        # ════════════════════════════════════════════════════════════════
        cursor.execute("""
            SELECT id, user_id, status, claim_type, jurisdiction, created_at, updated_at,
                   payment_tier, payment_status
            FROM cases
            WHERE id = %s AND user_id = %s
        """, [case_id, user_id])

        case_row = cursor.fetchone()
        if not case_row:
            logger.warning(f"Case not found or ownership check failed: {case_id}, user={user_id} (trace={trace_id})")
            raise HTTPException(status_code=404, detail="Case not found")

        # ════════════════════════════════════════════════════════════════
        # 2. FETCH TIMELINE EVENTS (ordered by creation time)
        # ════════════════════════════════════════════════════════════════
        cursor.execute("""
            SELECT id, event_type, details, triggered_by_user_id, created_at
            FROM case_events
            WHERE case_id = %s
            ORDER BY created_at ASC
        """, [case_id])

        events = []
        for row in cursor.fetchall():
            events.append(TimelineEvent(
                id=str(row['id']),
                event_type=row['event_type'],
                timestamp=row['created_at'].isoformat(),
                details=row['details'] or {},
                triggered_by_user_id=str(row['triggered_by_user_id']) if row['triggered_by_user_id'] else None
            ))

        # ════════════════════════════════════════════════════════════════
        # 3. CALCULATE DEADLINE (from key_dates or rules)
        # ════════════════════════════════════════════════════════════════
        deadline = None

        # Check if case has key_dates with tribunal claim deadline
        cursor.execute("""
            SELECT key_dates FROM cases WHERE id = %s
        """, [case_id])
        key_dates_row = cursor.fetchone()

        if key_dates_row and key_dates_row['key_dates']:
            key_dates = key_dates_row['key_dates']
            if 'tribunal_claim_deadline' in key_dates:
                deadline_str = key_dates['tribunal_claim_deadline']
                deadline_date = datetime.fromisoformat(deadline_str).date()
                days_remaining = (deadline_date - datetime.utcnow().date()).days

                deadline = CaseDeadline(
                    deadline_type="tribunal_claim",
                    date=deadline_str,
                    days_remaining=max(0, days_remaining)
                )

        cursor.close()

        # ════════════════════════════════════════════════════════════════
        # BUILD RESPONSE
        # ════════════════════════════════════════════════════════════════

        response = CaseTimelineResponse(
            case_id=str(case_row['id']),
            created_at=case_row['created_at'].isoformat(),
            status=case_row['status'],
            claim_type=case_row['claim_type'],
            jurisdiction=case_row['jurisdiction'],
            events=events,
            deadline=deadline
        )

        logger.info(f"Case timeline retrieved: case={case_id}, events={len(events)}, user={user_id} (trace={trace_id})")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving case timeline: {e} (trace={trace_id})", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve case timeline")

    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────────
# CASE DETAIL ENDPOINT
# ────────────────────────────────────────────────────────────────────

@app.get("/api/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: str,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_trace_id: Optional[str] = Header(None),
):
    """
    Get case details with ownership enforcement.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT id, user_id, status, claim_type, jurisdiction, created_at, updated_at,
                   payment_tier, payment_status
            FROM cases
            WHERE id = %s AND user_id = %s
        """, [case_id, user_id])

        case_row = cursor.fetchone()
        cursor.close()

        if not case_row:
            logger.warning(f"Case not found or ownership failed: {case_id}, user={user_id} (trace={trace_id})")
            raise HTTPException(status_code=404, detail="Case not found")

        response = CaseDetailResponse(
            id=str(case_row['id']),
            user_id=str(case_row['user_id']),
            status=case_row['status'],
            claim_type=case_row['claim_type'],
            jurisdiction=case_row['jurisdiction'],
            created_at=case_row['created_at'].isoformat(),
            updated_at=case_row['updated_at'].isoformat(),
            payment_tier=case_row['payment_tier'],
            payment_status=case_row['payment_status']
        )

        logger.info(f"Case detail retrieved: case={case_id}, user={user_id} (trace={trace_id})")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving case detail: {e} (trace={trace_id})")
        raise HTTPException(status_code=500, detail="Failed to retrieve case detail")

    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────────
# CREATE CASE EVENT (for testing/workflow)
# ────────────────────────────────────────────────────────────────────

from pydantic import BaseModel

class CreateCaseEventRequest(BaseModel):
    event_type: str
    details: Dict[str, Any] = {}
    triggered_by_user_id: Optional[str] = None


@app.post("/api/cases/{case_id}/events")
async def create_case_event(
    case_id: str,
    request: CreateCaseEventRequest,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_trace_id: Optional[str] = Header(None),
):
    """
    Create a case event (for workflow testing and event creation).
    ENFORCES USER OWNERSHIP.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Check ownership
        cursor.execute("SELECT id FROM cases WHERE id = %s AND user_id = %s", [case_id, user_id])
        if not cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=404, detail="Case not found")

        # Create event
        event_id = str(uuid4())
        cursor.execute("""
            INSERT INTO case_events (id, case_id, event_type, details, triggered_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, [
            event_id,
            case_id,
            request.event_type,
            psycopg2.extras.Json(request.details),
            request.triggered_by_user_id or user_id
        ])

        conn.commit()
        cursor.close()

        logger.info(f"Case event created: case={case_id}, event_type={request.event_type}, user={user_id} (trace={trace_id})")

        return {
            "id": event_id,
            "event_type": request.event_type,
            "created_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating case event: {e} (trace={trace_id})", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create case event")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
