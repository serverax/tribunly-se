"""Real DB queries for admin workspace APIs (cases, AI logs, users, health, compliance)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from ingestion.db import get_connection


def _row_dict(cursor, row) -> dict[str, Any]:
    if row is None:
        return {}
    cols = [d[0] for d in cursor.description]
    out: dict[str, Any] = {}
    for col, val in zip(cols, row):
        if hasattr(val, "isoformat"):
            out[col] = val.isoformat()
        elif val is not None and col in ("id", "case_id", "user_id", "trace_id"):
            out[col] = str(val)
        else:
            out[col] = val
    return out


def list_admin_cases(limit: int = 100) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.id AS case_id,
                    c.user_id,
                    u.email AS user_email,
                    c.claim_type,
                    c.status,
                    c.jurisdiction,
                    c.assessment,
                    c.key_dates,
                    c.created_at,
                    c.updated_at
                FROM cases c
                LEFT JOIN users u ON u.id = c.user_id
                WHERE c.deleted_at IS NULL
                ORDER BY c.updated_at DESC NULLS LAST, c.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            cases = []
            for row in rows:
                d = _row_dict(cur, row)
                assessment = d.get("assessment") or {}
                if isinstance(assessment, str):
                    import json
                    try:
                        assessment = json.loads(assessment)
                    except Exception:
                        assessment = {}
                key_dates = d.get("key_dates") or {}
                cases.append({
                    "case_id": d.get("case_id"),
                    "user_id": d.get("user_id"),
                    "user_email": d.get("user_email"),
                    "claim_type": d.get("claim_type"),
                    "status": d.get("status"),
                    "jurisdiction": d.get("jurisdiction"),
                    "strength": (assessment or {}).get("strength"),
                    "deadline": (key_dates or {}).get("limitation_date")
                        or (assessment or {}).get("deadline"),
                    "urgency": (assessment or {}).get("urgency"),
                    "created_at": d.get("created_at"),
                    "updated_at": d.get("updated_at"),
                })
            cur.execute(
                "SELECT COUNT(*) FROM cases WHERE deleted_at IS NULL"
            )
            total = cur.fetchone()[0]
        return {"cases": cases, "count": len(cases), "total": int(total or 0)}
    finally:
        conn.close()


def list_admin_ai_logs(limit: int = 100) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    trace_id, user_id, case_id, claim_type,
                    input_summary, retrieved_sources, reasoning_trace,
                    confidence, model_version,
                    rag_sources, reasoning_chain_summary,
                    citations_verified, citations_failed,
                    compliance_verdict, final_status, evaluation_passed,
                    created_at
                FROM brain_traces
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            logs = [_row_dict(cur, row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM brain_traces")
            total = cur.fetchone()[0]
        return {"logs": logs, "count": len(logs), "total": int(total or 0)}
    finally:
        conn.close()


def list_admin_users(limit: int = 200) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id AS user_id,
                    u.email,
                    u.is_admin,
                    u.subscription_status,
                    u.created_at,
                    u.last_login_at,
                    COUNT(c.id) FILTER (WHERE c.deleted_at IS NULL) AS case_count
                FROM users u
                LEFT JOIN cases c ON c.user_id = u.id
                GROUP BY u.id, u.email, u.is_admin, u.subscription_status,
                         u.created_at, u.last_login_at
                ORDER BY u.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            users = [_row_dict(cur, row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]
        return {"users": users, "count": len(users), "total": int(total or 0)}
    finally:
        conn.close()


def get_admin_system_health() -> dict[str, Any]:
    """Aggregate DB reachability and configured service URLs (latency stub)."""
    services = {
        "backend": {"url": "http://backend:8000/health", "status": "unknown", "latency_ms": None},
        "admin_service": {"url": "http://lawapp-admin-service:8007/health", "status": "unknown", "latency_ms": None},
        "rules_service": {"url": os.getenv("RULES_SERVICE_URL", ""), "status": "configured" if os.getenv("RULES_SERVICE_URL") else "unset"},
        "rag_service": {"url": os.getenv("RAG_SERVICE_URL", ""), "status": "configured" if os.getenv("RAG_SERVICE_URL") else "unset"},
        "audit_service": {"url": os.getenv("AUDIT_SERVICE_URL", ""), "status": "configured" if os.getenv("AUDIT_SERVICE_URL") else "unset"},
    }
    db_status = "disconnected"
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {"status": db_status},
        "services": services,
        "docker_note": "Full container health requires docker compose ps from operator host",
    }


def get_admin_compliance(limit: int = 100) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    trace_id, case_id, user_id, claim_type,
                    compliance_verdict, citations_verified, citations_failed,
                    final_status, confidence, rag_sources, created_at
                FROM brain_traces
                WHERE compliance_verdict IS NOT NULL
                       OR citations_failed > 0
                       OR final_status IN ('blocked', 'citation_failed', 'fail_closed')
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            flags = []
            for row in cur.fetchall():
                d = _row_dict(cur, row)
                weak = (
                    (d.get("citations_failed") or 0) > 0
                    or d.get("compliance_verdict") in ("fail", "blocked", "weak_grounding")
                    or d.get("final_status") in ("blocked", "citation_failed", "fail_closed")
                )
                d["weak_grounding"] = weak
                flags.append(d)
            cur.execute(
                """
                SELECT COUNT(*) FROM brain_traces
                WHERE citations_failed > 0
                   OR compliance_verdict IN ('fail', 'blocked', 'weak_grounding')
                """
            )
            weak_count = cur.fetchone()[0]
        return {
            "flags": flags,
            "count": len(flags),
            "weak_grounding_total": int(weak_count or 0),
        }
    finally:
        conn.close()
