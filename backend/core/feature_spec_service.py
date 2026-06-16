"""
Feature Spec service layer (tasks/FEATURE_SPEC_lawapp.md).

Bridges spec-facing operations to existing deterministic tools, RAG retrieval,
and the governed brain path. Fails closed on missing statutory data.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

from ingestion.db import get_connection

from backend.core import tools
from backend.core.agentic.pii import redact_text

logger = logging.getLogger(__name__)

_PREVIEW_DISCLAIMER = (
    "Information only, not legal advice. Sign in to save results to your case."
)


def _tables_ready(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'matter'
            LIMIT 1
            """
        )
        return cur.fetchone() is not None


def list_knowledge_modules() -> dict:
    """F1: browse employment_modules with honest corpus counts."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.module_key, m.label, m.status,
                       count(c.id) AS chunk_count
                FROM employment_modules m
                LEFT JOIN corpus_chunks c
                  ON c.claim_type = m.module_key
                GROUP BY m.module_key, m.label, m.status
                ORDER BY m.module_key
                """
            )
            rows = cur.fetchall()
        modules = [
            {
                "module_key": r[0],
                "label": r[1],
                "status": r[2],
                "chunk_count": int(r[3] or 0),
                "browse_url": f"/pages/knowledge.html?module={r[0]}",
            }
            for r in rows
        ]
        production = sum(1 for m in modules if m["status"] == "production")
        return {
            "modules": modules,
            "module_count": len(modules),
            "production_count": production,
            "beta_scope_note": (
                f"Controlled beta covers {production} production topics. "
                "Additional modules are partial or planned."
            ),
            "verification_badge": "corpus_backed",
        }
    finally:
        conn.close()


def knowledge_module_detail(module_key: str, as_at: Optional[str] = None) -> dict:
    """F1: sample provisions from corpus_chunks for a module."""
    ref_date = date.fromisoformat(as_at[:10]) if as_at else date.today()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT label, status FROM employment_modules
                WHERE module_key = %s
                """,
                (module_key,),
            )
            mod = cur.fetchone()
            if not mod:
                return {"error": "module_not_found", "module_key": module_key}

            cur.execute(
                """
                SELECT cc.id, cc.title, cc.authority_ref, cc.source_url,
                       cc.effective_from, cc.effective_to, cc.is_prospective,
                       left(cc.body_text, 400) AS excerpt
                FROM corpus_chunks cc
                WHERE cc.claim_type = %s
                  AND (cc.effective_from IS NULL OR cc.effective_from <= %s)
                  AND (cc.effective_to IS NULL OR cc.effective_to > %s)
                ORDER BY cc.quality_score DESC NULLS LAST, cc.title
                LIMIT 20
                """,
                (module_key, ref_date, ref_date),
            )
            provisions = [
                {
                    "chunk_id": str(r[0]),
                    "title": r[1],
                    "citation": r[2],
                    "source_url": r[3],
                    "effective_from": r[4].isoformat() if r[4] else None,
                    "effective_to": r[5].isoformat() if r[5] else None,
                    "is_prospective": bool(r[6]),
                    "excerpt": r[7],
                    "verification_badge": "verified" if r[2] else "unverified",
                }
                for r in cur.fetchall()
            ]
        return {
            "module_key": module_key,
            "label": mod[0],
            "status": mod[1],
            "as_at_date": ref_date.isoformat(),
            "provisions": provisions,
            "provision_count": len(provisions),
            "disclaimer": _PREVIEW_DISCLAIMER,
        }
    finally:
        conn.close()


def decode_document(text: str, doc_type: str = "letter") -> dict:
    """
    F3: Plain-English decoder. Anonymous: redact, retrieve, return in memory only.
    No DB persistence of upload content.
    """
    if not (text or "").strip():
        return {"error": "empty_document", "detail": "Provide document text to decode."}

    redacted = redact_text(text.strip())
    query = f"Explain this {doc_type} in plain English for a UK employee: {redacted[:500]}"

    citations: list[dict] = []
    verification_badge = "unverified"
    try:
        from backend.core.retrieve import hybrid_search

        hits = hybrid_search(query, module="employment", k=5)
        for h in hits[:5]:
            citations.append(
                {
                    "citation": h.get("citation") or h.get("authority_ref") or h.get("title"),
                    "source_url": h.get("source_url"),
                    "excerpt": (h.get("content") or h.get("body_text") or "")[:280],
                    "verification_badge": "verified" if (h.get("citation") or h.get("authority_ref")) else "unverified",
                }
            )
        if citations and all(c.get("citation") for c in citations):
            verification_badge = "verified"
    except Exception as exc:
        logger.warning("document decode retrieval miss: %s", exc)

    # Plain-English breakdown (deterministic scaffold; full draft uses brain on registration)
    sections = []
    lowered = redacted.lower()
    if any(w in lowered for w in ("terminat", "dismiss", "redundan")):
        sections.append(
            {
                "heading": "Employment ending",
                "plain_english": (
                    "This document appears to concern the end of your employment. "
                    "Check the effective date and whether it mentions notice, reason, or appeal rights."
                ),
            }
        )
    if any(w in lowered for w in ("settlement", "compromise", "without prejudice")):
        sections.append(
            {
                "heading": "Settlement wording",
                "plain_english": (
                    "Settlement or compromise wording may limit claims you can bring later. "
                    "Do not sign without understanding the waiver and tax treatment."
                ),
            }
        )
    if any(w in lowered for w in ("disciplinary", "misconduct", "warning")):
        sections.append(
            {
                "heading": "Disciplinary process",
                "plain_english": (
                    "Disciplinary language may affect fairness arguments. "
                    "Note whether you were given a hearing and the right to be accompanied."
                ),
            }
        )
    if not sections:
        sections.append(
            {
                "heading": "General review",
                "plain_english": (
                    "We could not auto-classify clauses. Compare dates, parties, and any "
                    "deadlines mentioned against your contract and handbook."
                ),
            }
        )

    return {
        "doc_type": doc_type,
        "sections": sections,
        "citations": citations,
        "verification_badge": verification_badge,
        "persisted": False,
        "pii_redacted": redacted != text.strip(),
        "disclaimer": (
            "Anonymous decode is not saved. Special category data is not stored. "
            + _PREVIEW_DISCLAIMER
        ),
    }


def run_claim_assessment(
    facts: str | dict,
    *,
    matter_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """F4: Claim identifier with optional persistence to claim_assessment."""
    screen = tools.check_claim(facts)
    strength = 0.5 if screen.get("has_claim") else 0.2
    if screen.get("confidence"):
        strength = float(screen["confidence"])

    result = {
        **screen,
        "strength_score": round(strength, 3),
        "verification_badge": "preview",
        "matched_module_keys": screen.get("signals") or [],
        "disclaimer": _PREVIEW_DISCLAIMER,
    }

    if matter_id and user_id:
        conn = get_connection()
        try:
            if not _tables_ready(conn):
                result["persist_warning"] = "operational_tables_not_migrated"
                return result
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM matter WHERE id = %s::uuid AND user_id = %s::uuid
                    """,
                    (matter_id, user_id),
                )
                if not cur.fetchone():
                    result["persist_error"] = "matter_not_found_or_forbidden"
                    return result
                cur.execute(
                    """
                    INSERT INTO claim_assessment (
                        matter_id, matched_tests, strength_score, rationale,
                        verification_badge
                    ) VALUES (%s::uuid, %s::jsonb, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (
                        matter_id,
                        json.dumps({"signals": screen.get("signals"), "explanation": screen.get("explanation")}),
                        strength,
                        screen.get("explanation"),
                        "unverified",
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            result["claim_assessment_id"] = str(row[0])
            result["saved_at"] = row[1].isoformat()
            result["verification_badge"] = "unverified"
        except Exception as exc:
            conn.rollback()
            logger.error("claim_assessment persist failed: %s", exc)
            result["persist_error"] = "save_failed"
        finally:
            conn.close()

    return result


def create_matter(
    user_id: str,
    *,
    title: Optional[str] = None,
    case_id: Optional[str] = None,
    claim_types: Optional[list[int]] = None,
) -> dict:
    """F5: Create matter row (registration-gated)."""
    conn = get_connection()
    try:
        if not _tables_ready(conn):
            raise RuntimeError("matter table not migrated")
        with conn.cursor() as cur:
            if case_id:
                cur.execute(
                    """
                    SELECT id FROM cases WHERE id = %s::uuid AND user_id = %s::uuid
                    """,
                    (case_id, user_id),
                )
                if not cur.fetchone():
                    raise PermissionError("case_not_owned")

            cur.execute(
                """
                INSERT INTO matter (user_id, case_id, title, claim_types, status)
                VALUES (%s::uuid, %s::uuid, %s, %s, 'active')
                RETURNING id, created_at
                """,
                (
                    user_id,
                    case_id,
                    title or "My employment matter",
                    claim_types,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return {"matter_id": str(row[0]), "created_at": row[1].isoformat()}
    finally:
        conn.close()


def matter_hub(matter_id: str, user_id: str) -> dict:
    """F5: Case Hub aggregate."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.title, m.status, m.strength_score, m.case_id, m.claim_types
                FROM matter m
                WHERE m.id = %s::uuid AND m.user_id = %s::uuid
                """,
                (matter_id, user_id),
            )
            m = cur.fetchone()
            if not m:
                return {"error": "not_found"}

            cur.execute(
                """
                SELECT id, deadline_type, due_date, status, rule_ref
                FROM deadline WHERE matter_id = %s::uuid ORDER BY due_date
                """,
                (matter_id,),
            )
            deadlines = [
                {
                    "id": str(r[0]),
                    "deadline_type": r[1],
                    "due_date": r[2].isoformat(),
                    "status": r[3],
                    "rule_ref": r[4],
                    "days_remaining": (r[2] - date.today()).days,
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT id, strength_score, rationale, verification_badge, created_at
                FROM claim_assessment
                WHERE matter_id = %s::uuid
                ORDER BY created_at DESC LIMIT 1
                """,
                (matter_id,),
            )
            assessment_row = cur.fetchone()
            assessment = None
            if assessment_row:
                assessment = {
                    "id": str(assessment_row[0]),
                    "strength_score": float(assessment_row[1]) if assessment_row[1] is not None else None,
                    "rationale": assessment_row[2],
                    "verification_badge": assessment_row[3],
                    "created_at": assessment_row[4].isoformat(),
                }

            cur.execute(
                "SELECT count(*) FROM evidence_item WHERE matter_id = %s::uuid",
                (matter_id,),
            )
            evidence_count = int(cur.fetchone()[0])

        next_action = "Review your deadlines and gather evidence."
        if deadlines:
            open_dl = [d for d in deadlines if d["status"] == "open"]
            if open_dl:
                nearest = min(open_dl, key=lambda d: d["due_date"])
                next_action = f"Next: address {nearest['deadline_type']} by {nearest['due_date']}."

        return {
            "matter_id": str(m[0]),
            "title": m[1],
            "status": m[2],
            "strength_score": float(m[3]) if m[3] is not None else None,
            "case_id": str(m[4]) if m[4] else None,
            "claim_types": m[5],
            "deadlines": deadlines,
            "latest_assessment": assessment,
            "evidence_count": evidence_count,
            "next_action": next_action,
        }
    finally:
        conn.close()


def save_matter_deadlines(
    matter_id: str,
    user_id: str,
    *,
    event_type: str,
    event_date: str,
    claim_type: str = "unfair_dismissal",
    acas_start: Optional[str] = None,
    acas_end: Optional[str] = None,
) -> dict:
    """F2 save path: key_event + deadline rows."""
    calc = tools.calculate_deadline(event_date, event_type, "EW")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM matter WHERE id = %s::uuid AND user_id = %s::uuid",
                (matter_id, user_id),
            )
            if not cur.fetchone():
                raise PermissionError("matter_not_found")

            cur.execute(
                """
                INSERT INTO key_event (matter_id, event_type, event_date)
                VALUES (%s::uuid, %s, %s::date)
                RETURNING id
                """,
                (matter_id, event_type, event_date),
            )
            key_event_id = str(cur.fetchone()[0])

            due = calc.get("deadline") or calc.get("limitation_date")
            rule_ref = calc.get("authority") or "rules.time_limit_months"
            cur.execute(
                """
                INSERT INTO deadline (
                    matter_id, deadline_type, due_date, computed_from, rule_ref, status
                ) VALUES (%s::uuid, 'et1_limitation', %s::date, %s::uuid[], %s, 'open')
                RETURNING id
                """,
                (matter_id, due, [uuid.UUID(key_event_id)], rule_ref),
            )
            deadline_id = str(cur.fetchone()[0])
        conn.commit()
        return {
            "matter_id": matter_id,
            "key_event_id": key_event_id,
            "deadline_id": deadline_id,
            "calculation": calc,
        }
    finally:
        conn.close()


def save_valuation(
    matter_id: str,
    user_id: str,
    *,
    weekly_pay: float,
    months_employed: int,
    as_at: Optional[str] = None,
) -> dict:
    """F7 save path."""
    est = tools.estimate_compensation(weekly_pay, months_employed, "EW")
    ref_date = date.fromisoformat(as_at[:10]) if as_at else date.today()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM matter WHERE id = %s::uuid AND user_id = %s::uuid",
                (matter_id, user_id),
            )
            if not cur.fetchone():
                raise PermissionError("matter_not_found")
            low = est.get("estimated_amount")
            mid = est.get("estimated_amount")
            high = est.get("estimated_amount")
            cur.execute(
                """
                INSERT INTO valuation (matter_id, low, mid, high, basis, as_at)
                VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s::date)
                RETURNING id
                """,
                (matter_id, low, mid, high, json.dumps(est), ref_date),
            )
            vid = str(cur.fetchone()[0])
        conn.commit()
        return {"valuation_id": vid, "estimate": est, "as_at": ref_date.isoformat()}
    finally:
        conn.close()


def create_referral(
    matter_id: str,
    user_id: str,
    *,
    referral_type: str,
    partner_id: Optional[str] = None,
) -> dict:
    """F12 scaffold: referral row only; partner notify deferred."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM matter WHERE id = %s::uuid AND user_id = %s::uuid",
                (matter_id, user_id),
            )
            if not cur.fetchone():
                raise PermissionError("matter_not_found")
            cur.execute(
                """
                INSERT INTO referral (matter_id, partner_id, referral_type, status)
                VALUES (%s::uuid, %s::uuid, %s, 'open')
                RETURNING id, created_at
                """,
                (matter_id, partner_id, referral_type),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "referral_id": str(row[0]),
            "created_at": row[1].isoformat(),
            "partner_notified": False,
            "note": "Partner agreements and notification wiring are deferred.",
        }
    finally:
        conn.close()
