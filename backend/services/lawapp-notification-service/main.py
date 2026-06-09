"""
LAWAPP Notification Service
============================
Notification service for in-app notifications and email queuing.
Notifications are REAL: inserted into database AND (if email) queued to Redis.

Service Contract: port 8009
Endpoints:
  - GET /health → {status: 'ok'}
  - GET /ready → {status: 'ready'} or 503
  - POST /api/notifications/create → create in-app notification (database insert)
  - POST /api/notifications/send-email → queue email to Redis + insert in database
  - GET /api/notifications → list user notifications
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

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

# ────────────────────────────────────────────────────────────────────
# DATABASE & REDIS CONNECTIONS
# ────────────────────────────────────────────────────────────────────

def get_db_connection():
    """Get a fresh database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_redis_client():
    """Get a fresh Redis client."""
    return redis.from_url(REDIS_URL, decode_responses=True)


# ────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ────────────────────────────────────────────────────────────────────

class CreateNotificationRequest(BaseModel):
    user_id: str
    notification_type: str  # deadline_warning|payment_completed|document_ready|handoff_triggered|assessment_updated
    template_key: str
    title: str
    message: str
    details: Dict[str, Any] = {}
    case_id: Optional[str] = None
    delivery_method: str = "in_app"  # in_app|email|both


class SendEmailNotificationRequest(BaseModel):
    user_id: str
    template_key: str
    subject: str
    context: Dict[str, Any] = {}
    delivery_email: Optional[str] = None
    case_id: Optional[str] = None


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    sent_at: Optional[str] = None
    read_at: Optional[str] = None
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int


# ────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LAWAPP Notification Service",
    version="1.0.0",
    description="In-app and email notification service"
)


# ────────────────────────────────────────────────────────────────────
# HEALTH & READINESS
# ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check (always 200 if service is running)."""
    return {
        "status": "healthy",
        "service": "lawapp-notification-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready")
async def ready():
    """Readiness check (503 if DB or Redis unavailable)."""
    db_ok = False
    redis_ok = False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_ok = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")

    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_ok = True
    except Exception as e:
        logger.error(f"Redis check failed: {e}")

    if not db_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "lawapp-notification-service",
                "db": db_ok,
                "redis": redis_ok
            }
        )

    return {
        "status": "ready",
        "service": "lawapp-notification-service",
        "timestamp": datetime.utcnow().isoformat()
    }


# ────────────────────────────────────────────────────────────────────
# CREATE IN-APP NOTIFICATION
# ────────────────────────────────────────────────────────────────────

@app.post("/api/notifications/create")
async def create_notification(
    request: CreateNotificationRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Create an in-app notification.
    INSERTS REAL RECORD into database.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Verify user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", [request.user_id])
        if not cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=404, detail="User not found")

        # Verify case (if provided) belongs to user
        if request.case_id:
            cursor.execute(
                "SELECT id FROM cases WHERE id = %s AND user_id = %s",
                [request.case_id, request.user_id]
            )
            if not cursor.fetchone():
                cursor.close()
                raise HTTPException(status_code=404, detail="Case not found")

        # Create notification
        notification_id = str(uuid4())
        cursor.execute("""
            INSERT INTO notifications
            (id, user_id, case_id, notification_type, template_key, title, message,
             details, delivery_method, x_trace_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            notification_id,
            request.user_id,
            request.case_id,
            request.notification_type,
            request.template_key,
            request.title,
            request.message,
            psycopg2.extras.Json(request.details),
            request.delivery_method,
            trace_id
        ])

        conn.commit()
        cursor.close()

        logger.info(f"Notification created: id={notification_id}, user={request.user_id}, "
                    f"type={request.notification_type} (trace={trace_id})")

        return {
            "id": notification_id,
            "status": "created",
            "created_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification: {e} (trace={trace_id})", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create notification")

    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────────
# SEND EMAIL NOTIFICATION (queue + database record)
# ────────────────────────────────────────────────────────────────────

@app.post("/api/notifications/send-email")
async def send_email_notification(
    request: SendEmailNotificationRequest,
    x_trace_id: Optional[str] = Header(None),
):
    """
    Queue an email notification to Redis AND insert into database.
    The SAME notification record stores both in-app AND email state.
    REAL QUEUE: Redis qlen will increase, no fakes.
    REAL DATABASE: row inserted and retrievable.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None
    redis_client = None

    try:
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Verify user exists
        cursor.execute("SELECT email FROM users WHERE id = %s", [request.user_id])
        user_row = cursor.fetchone()
        if not user_row:
            cursor.close()
            raise HTTPException(status_code=404, detail="User not found")

        user_email = request.delivery_email or user_row['email']
        if not user_email:
            cursor.close()
            raise HTTPException(status_code=400, detail="No email address available")

        # Verify case (if provided)
        if request.case_id:
            cursor.execute(
                "SELECT id FROM cases WHERE id = %s AND user_id = %s",
                [request.case_id, request.user_id]
            )
            if not cursor.fetchone():
                cursor.close()
                raise HTTPException(status_code=404, detail="Case not found")

        # Create notification in database
        notification_id = str(uuid4())
        now = datetime.utcnow()

        cursor.execute("""
            INSERT INTO notifications
            (id, user_id, case_id, notification_type, template_key, title, message,
             details, delivery_email, delivery_method, x_trace_id, email_queued_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            notification_id,
            request.user_id,
            request.case_id,
            "email",  # notification_type
            request.template_key,
            f"Email: {request.template_key}",  # title
            f"Email notification for {request.template_key}",  # message
            psycopg2.extras.Json(request.context),
            user_email,
            "email",
            trace_id,
            now
        ])

        conn.commit()
        cursor.close()

        # ════════════════════════════════════════════════════════════════
        # QUEUE EMAIL TO REDIS (the real queue)
        # ════════════════════════════════════════════════════════════════
        redis_client = get_redis_client()

        email_job = {
            "notification_id": notification_id,
            "user_id": request.user_id,
            "email": user_email,
            "template_key": request.template_key,
            "subject": request.subject,
            "context": request.context,
            "created_at": now.isoformat(),
            "trace_id": trace_id
        }

        # Push to email queue (real Redis list)
        queue_key = "lawapp:email_queue"
        redis_client.rpush(queue_key, json.dumps(email_job))
        queue_length = redis_client.llen(queue_key)

        logger.info(f"Email notification queued: id={notification_id}, user={request.user_id}, "
                    f"email={user_email}, queue_len={queue_length} (trace={trace_id})")

        return {
            "id": notification_id,
            "status": "queued",
            "email_queued_at": now.isoformat(),
            "queue_position": queue_length
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email notification: {e} (trace={trace_id})", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue email notification")

    finally:
        if conn:
            conn.close()
        if redis_client:
            redis_client.close()


# ────────────────────────────────────────────────────────────────────
# LIST USER NOTIFICATIONS
# ────────────────────────────────────────────────────────────────────

@app.get("/api/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    unread_only: bool = Query(False),
    x_trace_id: Optional[str] = Header(None),
):
    """
    List notifications for a user.
    """
    trace_id = x_trace_id or str(uuid4())
    conn = None

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        where_clause = "WHERE user_id = %s"
        params = [user_id]

        if unread_only:
            where_clause += " AND read_at IS NULL"

        cursor.execute(f"""
            SELECT id, user_id, notification_type, title, message, sent_at, read_at, created_at
            FROM notifications
            {where_clause}
            ORDER BY created_at DESC
            LIMIT 50
        """, params)

        notifications = []
        for row in cursor.fetchall():
            notifications.append(NotificationResponse(
                id=str(row['id']),
                user_id=str(row['user_id']),
                notification_type=row['notification_type'],
                title=row['title'],
                message=row['message'],
                sent_at=row['sent_at'].isoformat() if row['sent_at'] else None,
                read_at=row['read_at'].isoformat() if row['read_at'] else None,
                created_at=row['created_at'].isoformat()
            ))

        cursor.close()

        logger.info(f"Notifications listed: user={user_id}, count={len(notifications)} (trace={trace_id})")

        return NotificationListResponse(
            notifications=notifications,
            total=len(notifications)
        )

    except Exception as e:
        logger.error(f"Error listing notifications: {e} (trace={trace_id})")
        raise HTTPException(status_code=500, detail="Failed to list notifications")

    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────────
# MARK NOTIFICATION AS READ
# ────────────────────────────────────────────────────────────────────

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_trace_id: Optional[str] = Header(None),
):
    """Mark a notification as read."""
    trace_id = x_trace_id or str(uuid4())
    conn = None

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID header")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check ownership
        cursor.execute(
            "SELECT id FROM notifications WHERE id = %s AND user_id = %s",
            [notification_id, user_id]
        )
        if not cursor.fetchone():
            cursor.close()
            raise HTTPException(status_code=404, detail="Notification not found")

        # Mark as read
        cursor.execute(
            "UPDATE notifications SET read_at = %s WHERE id = %s",
            [datetime.utcnow(), notification_id]
        )
        conn.commit()
        cursor.close()

        logger.info(f"Notification marked read: {notification_id}, user={user_id} (trace={trace_id})")

        return {"status": "read", "notification_id": notification_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification read: {e} (trace={trace_id})")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")

    finally:
        if conn:
            conn.close()


# ────────────────────────────────────────────────────────────────────
# DEBUG: CHECK EMAIL QUEUE
# ────────────────────────────────────────────────────────────────────

@app.get("/api/notifications/debug/queue-status")
async def check_queue_status():
    """Check email queue status (DEBUG ONLY)."""
    try:
        redis_client = get_redis_client()
        queue_key = "lawapp:email_queue"
        queue_length = redis_client.llen(queue_key)
        redis_client.close()

        return {
            "queue_key": queue_key,
            "queue_length": queue_length,
            "status": "ok" if queue_length >= 0 else "error"
        }

    except Exception as e:
        logger.error(f"Error checking queue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check queue status")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)
