"""
lawapp MCP Connector Layer — deny-by-default tool registry.

Provides controlled access to external tools and services.
Every connector call is logged to mcp_tool_calls.

GUARDRAIL: deny-by-default — unknown tools are blocked.
GUARDRAIL: No connector may file claims, represent users, or send emails.
GUARDRAIL: All calls are audited with trace_id and user_id.
GUARDRAIL: Raw personal data never leaves the lawapp boundary via MCP.

Implemented connectors (Phase 1):
  - legislation_lookup: retrieve ERA 1996 / statute section from DB
  - rules_lookup:       retrieve effective-dated rules from DB
  - document_generate:  generate self-help draft documents

Future connectors (Phase 2+):
  - case_law_lookup
  - acas_guidance_fetch
  - source_freshness_check
  - deadline_reminder (requires consent)
  - referral_package  (requires consent + human review)
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Tool allowlist (deny-by-default) ─────────────────────────────────────────

_ALLOWED_TOOLS: set[str] = {
    "legislation_lookup",
    "rules_lookup",
    "document_generate",
    "acas_guidance_lookup",
    "source_freshness_check",
    "retrieve_case_law",
}

_PROHIBITED_TOOLS: set[str] = {
    "file_et1",
    "submit_claim_to_tribunal",
    "contact_employer",
    "send_email_on_behalf",
    "represent_user_at_hearing",
    "sign_document_for_user",
    "contact_tribunal",
    "access_other_user_data",
}


def call_tool(
    tool_name: str,
    action: str,
    params: dict,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> dict:
    """
    Execute a tool call through the MCP connector layer.

    GUARDRAIL: Unknown or prohibited tools are blocked and logged.
    GUARDRAIL: Every call is written to mcp_tool_calls audit table.

    Returns:
        {"status": "ok"|"blocked"|"error", "result": ..., "tool": tool_name}
    """
    # ── Deny-by-default gate ────────────────────────────────────────────────
    if tool_name in _PROHIBITED_TOOLS:
        _audit(tool_name, action, allowed=False, consent=False,
               result={"reason": "prohibited_tool"},
               trace_id=trace_id, user_id=user_id, case_id=case_id)
        logger.warning("MCP: prohibited tool blocked: %s", tool_name)
        return {
            "status": "blocked",
            "reason": f"Tool '{tool_name}' is not permitted in lawapp.",
            "tool": tool_name,
        }

    if tool_name not in _ALLOWED_TOOLS:
        _audit(tool_name, action, allowed=False, consent=False,
               result={"reason": "unknown_tool"},
               trace_id=trace_id, user_id=user_id, case_id=case_id)
        logger.warning("MCP: unknown tool blocked: %s", tool_name)
        return {
            "status": "blocked",
            "reason": f"Tool '{tool_name}' is not registered.",
            "tool": tool_name,
        }

    # ── Execute allowed tool ────────────────────────────────────────────────
    try:
        result = _dispatch(tool_name, action, params)
        _audit(tool_name, action, allowed=True, consent=True,
               result={"keys": list(result.keys()) if isinstance(result, dict) else "ok"},
               trace_id=trace_id, user_id=user_id, case_id=case_id)
        return {"status": "ok", "result": result, "tool": tool_name}
    except Exception as exc:
        logger.error("MCP tool error %s/%s: %s", tool_name, action, exc)
        _audit(tool_name, action, allowed=True, consent=True,
               result={"error": str(exc)[:200]},
               trace_id=trace_id, user_id=user_id, case_id=case_id)
        return {"status": "error", "error": str(exc), "tool": tool_name}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _dispatch(tool_name: str, action: str, params: dict) -> Any:
    if tool_name == "legislation_lookup":
        return _legislation_lookup(params)
    if tool_name == "rules_lookup":
        return _rules_lookup(params)
    if tool_name == "document_generate":
        return _document_generate(params)
    if tool_name == "acas_guidance_lookup":
        return _acas_lookup(params)
    if tool_name == "source_freshness_check":
        return _freshness_check(params)
    raise ValueError(f"No dispatcher for tool: {tool_name}")


def _legislation_lookup(params: dict) -> dict:
    """Retrieve a legislation section from the DB by ERA/section reference."""
    section_ref = params.get("section_ref", "")
    jurisdiction = params.get("jurisdiction", "EW")
    claim_type = params.get("claim_type", "")

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT act_title, section_ref, body_text, source_url,
                       effective_from, last_verified_at
                FROM legislation
                WHERE (section_ref ILIKE %s OR body_text ILIKE %s)
                  AND jurisdiction = %s
                ORDER BY last_verified_at DESC NULLS LAST
                LIMIT 3;
                """,
                (f"%{section_ref}%", f"%{section_ref}%", jurisdiction),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            results = [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()

    return {
        "source": "legislation_db",
        "section_ref": section_ref,
        "results": results,
        "count": len(results),
    }


def _rules_lookup(params: dict) -> dict:
    """Retrieve effective-dated rules for a claim type."""
    claim_type = params.get("claim_type", "unfair_dismissal")
    jurisdiction = params.get("jurisdiction", "EW")
    ref_date = params.get("ref_date")

    from backend.core.retrieve import retrieve_rules
    import datetime as _dt

    date_obj = _dt.date.today()  # default to today for current rules
    if ref_date:
        try:
            date_obj = _dt.date.fromisoformat(str(ref_date))
        except (ValueError, TypeError):
            pass

    rules = retrieve_rules(claim_type, jurisdiction, date_obj)
    return {
        "source": "rules_db",
        "claim_type": claim_type,
        "jurisdiction": jurisdiction,
        "rules": rules,
        "count": len(rules),
    }


def _document_generate(params: dict) -> dict:
    """Generate a self-help draft document from structured facts."""
    doc_type = params.get("doc_type", "particulars_of_claim")
    facts = params.get("facts", {})
    assessment = params.get("assessment", {})
    jurisdiction = params.get("jurisdiction", "EW")

    if doc_type == "particulars_of_claim":
        from backend.core.documents import generate_particulars_of_claim
        return generate_particulars_of_claim(facts, assessment, jurisdiction=jurisdiction)
    elif doc_type == "schedule_of_loss":
        from backend.core.documents import generate_schedule_of_loss
        return generate_schedule_of_loss(facts, assessment, jurisdiction=jurisdiction)
    elif doc_type == "letter_before_action":
        from backend.core.documents import generate_letter_before_action
        return generate_letter_before_action(facts, assessment, jurisdiction=jurisdiction)
    else:
        raise ValueError(f"Unknown doc_type: {doc_type}")


def _acas_lookup(params: dict) -> dict:
    """Retrieve ACAS guidance chunks from the DB."""
    query = params.get("query", "")
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, body_text, source_url, last_verified_at
                FROM acas_guidance
                WHERE body_text ILIKE %s
                ORDER BY last_verified_at DESC NULLS LAST
                LIMIT 3;
                """,
                (f"%{query}%",),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            results = [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()
    return {"source": "acas_guidance_db", "query": query, "results": results}


def _freshness_check(params: dict) -> dict:
    """Check when legal sources were last verified."""
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 'legislation' as source, COUNT(*) as total,
                       MAX(last_verified_at) as last_verified
                FROM legislation
                UNION ALL
                SELECT 'case_law_chunks', COUNT(*), MAX(updated_at)
                FROM case_law_chunks
                UNION ALL
                SELECT 'acas_guidance', COUNT(*), MAX(last_verified_at)
                FROM acas_guidance
                UNION ALL
                SELECT 'rules', COUNT(*), MAX(updated_at)
                FROM rules;
                """
            )
            rows = cur.fetchall()
            results = [
                {"source": r[0], "total": r[1], "last_verified": str(r[2]) if r[2] else None}
                for r in rows
            ]
    finally:
        conn.close()
    return {"freshness": results}


# ── Audit writer ──────────────────────────────────────────────────────────────

def _audit(
    tool_name: str,
    action: str,
    allowed: bool,
    consent: bool,
    result: Any,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> None:
    """Write MCP tool call to audit log. Fails silently."""
    try:
        import json
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mcp_tool_calls
                        (trace_id, user_id, case_id, tool_name, action,
                         allowed, consent, result)
                    VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        trace_id,
                        user_id,
                        case_id,
                        tool_name,
                        action,
                        allowed,
                        consent,
                        json.dumps(result),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("MCP audit write failed (non-fatal): %s", exc)


# ── Convenience: list allowed tools ──────────────────────────────────────────

def list_allowed_tools() -> list[str]:
    return sorted(_ALLOWED_TOOLS)


def list_prohibited_tools() -> list[str]:
    return sorted(_PROHIBITED_TOOLS)
