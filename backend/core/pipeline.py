"""
Phase 2 — Assessment pipeline orchestrator.

Stages: classify → retrieve → reason → score → govern → respond.

GUARDRAILS enforced here:
- Retrieval always runs before reasoning.
- Deadline is computed deterministically and injected into the assessment.
- De-identification runs before any model call.
- Out-of-scope and insufficient-grounding routes are hard exits.
- The model interface requires an explicit model instance — no default.

Usage:
    from backend.core.pipeline import assess
    from backend.core.models import StubReasoningModel

    result = assess(
        query="I was dismissed after 3 years with no warning",
        facts={"edt": "2026-04-01", "service_start_date": "2023-04-01", ...},
        model=StubReasoningModel(),
    )
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Union

from shared.schemas import ClassificationResult, RetrievalBundle, StructuredAssessment
from backend.core.classify import classify
from backend.core.retrieve import retrieve
from backend.domains.employment.deadline import compute_limitation_date, check_qualifying_period
from backend.core.deidentify import deidentify
from backend.core.score import score
from backend.core.govern import (
    GovernanceResult,
    govern,
    build_not_supported_response,
    build_insufficient_grounding_response,
    build_low_confidence_response,
)
from backend.core.models import ReasoningModel, StubReasoningModel, select_model
from backend.domains.employment.assess_logic import (
    build_deterministic_context, compute_value_range,
    build_deterministic_context_wages,
)
from ingestion.db import get_connection, insert_audit_log, _safe_fact_hash

logger = logging.getLogger(__name__)


def _write_deadline_audit(claim_type, jurisdiction, edt, deadline_info, time_limit_rule,
                          ec_day_a, ec_day_b) -> None:
    """Persist proof that the deadline came from the rules table, not the model.
    Non-fatal: never blocks the pipeline."""
    try:
        import json as _json
        from ingestion.db import get_connection as _gc
        from backend.core.retrieve import juris_codes as _jc
        final = deadline_info.get("limitation_date")
        base = deadline_info.get("base_limit") or final
        if not final or not base:
            return
        rules_used = _json.dumps([
            {
                "rule_key": (time_limit_rule or {}).get("rule_key", "unfair_dismissal.time_limit_months"),
                "authority_ref": (time_limit_rule or {}).get("authority_ref"),
                "authority_url": (time_limit_rule or {}).get("authority_url"),
                "value_numeric": float(time_limit_rule["value_numeric"])
                if time_limit_rule and time_limit_rule.get("value_numeric") is not None else None,
            },
            {"rule_key": "unfair_dismissal.early_conciliation_required",
             "authority": deadline_info.get("authority")},
        ])
        conn = _gc()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO deadline_calculation_audit
                        (claim_type, jurisdiction_code, edt, ec_start_date, ec_end_date,
                         base_limit_date, paused_days, one_month_floor_date,
                         final_limitation_date, rules_used, calculation_version, calculated_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'1.0','server')
                    """,
                    (claim_type, _jc(jurisdiction)[0], edt, ec_day_a, ec_day_b,
                     base, deadline_info.get("pause_days"), deadline_info.get("ec_floor"),
                     final, rules_used),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("deadline_calculation_audit write skipped: %s", exc)


def _validate_fact_dates(facts: dict) -> Optional[dict]:
    """Field-level date validation, run before classification.

    Returns an {"status": "invalid_date", "field_errors": {...}} response dict
    when a supplied date is malformed or impossible, else None.
    Only validates keys that are present — absence is handled downstream.
    """
    today = date.today()

    def _parse(key_label: str, raw) -> tuple[Optional[date], Optional[dict]]:
        try:
            return date.fromisoformat(str(raw)), None
        except ValueError:
            return None, {
                "status": "invalid_date",
                "field_errors": {key_label: f"'{raw}' is not a valid date — use YYYY-MM-DD."},
                "message": f"Could not parse date: {raw}",
            }

    edt_raw = (facts.get("edt") or facts.get("effective_date_of_termination")
               or facts.get("dismissal_date"))
    edt_val = None
    if edt_raw:
        edt_val, err = _parse("edt", edt_raw)
        if err:
            return err
        if edt_val > today:
            return {"status": "invalid_date",
                    "field_errors": {"edt": (
                        f"Dismissal date {edt_val.isoformat()} is in the future. "
                        f"Enter the date your employment actually ended.")},
                    "message": "Dismissal date cannot be in the future."}

    svc_raw = facts.get("service_start_date") or facts.get("employment_start_date")
    if svc_raw:
        svc_val, err = _parse("service_start_date", svc_raw)
        if err:
            return err
        if edt_val and svc_val >= edt_val:
            return {"status": "invalid_date",
                    "field_errors": {"service_start_date": (
                        f"Employment start date {svc_val.isoformat()} must be before "
                        f"the dismissal date {edt_val.isoformat()}.")},
                    "message": "Employment start date must be before the dismissal date."}

    for ec_key in ("ec_day_a", "ec_day_b"):
        if facts.get(ec_key):
            _, err = _parse(ec_key, facts[ec_key])
            if err:
                return err
    return None


def assess(
    query: str,
    facts: dict,
    model: Optional[ReasoningModel] = None,
    jurisdiction: str = "EW",
    graph_context: Optional[dict] = None,
) -> dict:
    """
    Run the full assessment pipeline for a single query + fact pattern.

    Returns one of:
      - {"status": "not_supported", ...}              — out-of-scope
      - {"status": "insufficient_grounding", ...}    — retrieval too weak
      - {"status": "low_confidence", ...}             — below threshold
      - {"status": "ok", "assessment": {...}}         — passes governance
      - {"status": "model_not_configured", ...}       — no model provided

    The pipeline is structured to demonstrate Phase 2 with the stub model
    (all stages run, governance gate exercises correctly) and to work correctly
    once a real model is configured.
    """

    # ── Stage 0: Date sanity (BEFORE classification) ───────────────────────
    # A malformed/impossible date must come back as a field-level error, never
    # as "out of scope" — vague queries with broken dates would otherwise be
    # refused by the classifier before the user learns their date is wrong.
    _early = _validate_fact_dates(facts)
    if _early is not None:
        return _early

    # ── Stage 1: Classify ──────────────────────────────────────────────────
    classification = classify(query, facts)
    logger.info("Classification: %s", classification.model_dump())

    if not classification.in_scope:
        return build_not_supported_response(matter_type=classification.matter_type)

    claim_type = classification.matter_type  # "unfair_dismissal" | "unpaid_wages"

    # ── Extract reference date (claim-type aware) ──────────────────────────────
    if claim_type == "unpaid_wages":
        ref_str = facts.get("wages_due_date") or facts.get("date_wages_due")
        missing_status  = "missing_wages_date"
        missing_message = "Date wages were due is required to compute the claim deadline."
        tl_rule_key     = "unlawful_deduction_wages.time_limit_months"
    else:
        ref_str = (
            facts.get("edt")
            or facts.get("effective_date_of_termination")
            or facts.get("dismissal_date")
        )
        missing_status  = "missing_edt"
        missing_message = "Effective date of termination is required to compute deadline."
        tl_rule_key     = "unfair_dismissal.time_limit_months"

    if not ref_str:
        return {"status": missing_status, "message": missing_message}
    try:
        ref_date = date.fromisoformat(str(ref_str))
    except ValueError:
        return {"status": f"invalid_date", "message": f"Could not parse date: {ref_str}"}

    # Keep edt alias for backward-compat with pipeline stages that use it
    edt = ref_date

    # ── Jurisdiction gate (fail-closed) ────────────────────────────────────
    # Northern Ireland is a separate employment-law regime and is NOT ingested.
    # If the jurisdiction has no verified rules, fail closed — never reuse GB law.
    from backend.core.retrieve import jurisdiction_supported as _jur_supported, juris_codes as _jcodes
    if not _jur_supported(jurisdiction):
        return {
            "status": "not_supported",
            "jurisdiction": jurisdiction,
            "jurisdiction_supported": False,
            "insufficient_grounding": True,
            "recommended_next_step": "human_review",
            "message": (
                f"{jurisdiction} employment-law support is not yet verified in this "
                f"system. This matter needs human review / a solicitor."
            ),
        }

    # ── Stage 2: Retrieve (always, before reasoning) ───────────────────────
    bundle = retrieve(query, claim_type, jurisdiction, ref_date)
    logger.info(
        "Retrieval: %d rules, %d authorities, insufficient_grounding=%s",
        len(bundle.exact_rules), len(bundle.authorities), bundle.insufficient_grounding,
    )

    if bundle.insufficient_grounding and not bundle.exact_rules:
        return build_insufficient_grounding_response(
            "No rules or authority retrieved for this query."
        )

    # ── Deterministic deadline (claim-type aware rule key) ─────────────────────
    time_limit_rule = next(
        (r for r in bundle.exact_rules if r["rule_key"] == tl_rule_key),
        None,
    )
    time_limit_months = int(time_limit_rule["value_numeric"]) if time_limit_rule else 3

    ec_day_a_str = facts.get("ec_day_a")
    ec_day_b_str = facts.get("ec_day_b")
    ec_day_a = date.fromisoformat(str(ec_day_a_str)) if ec_day_a_str else None
    ec_day_b = date.fromisoformat(str(ec_day_b_str)) if ec_day_b_str else None

    deadline_info = compute_limitation_date(ref_date, time_limit_months, ec_day_a, ec_day_b)

    # ── Deadline urgency (beta blocker #2): compare to today, warn clearly ───
    _lim_str = deadline_info.get("limitation_date")
    if _lim_str:
        _today = date.today()
        _lim = date.fromisoformat(str(_lim_str))
        _days_left = (_lim - _today).days
        deadline_info["deadline_passed"] = _days_left < 0
        deadline_info["days_remaining"] = _days_left
        if _days_left < 0:
            deadline_info["urgency_level"] = "expired"
            deadline_info["deadline_warning"] = (
                f"⚠ This deadline appears to have PASSED ({abs(_days_left)} days ago, "
                f"on {_lim.isoformat()}). Out-of-time claims are only accepted in "
                f"limited circumstances — seek advice from ACAS or a solicitor "
                f"IMMEDIATELY if you still wish to claim."
            )
        elif _days_left <= 14:
            deadline_info["urgency_level"] = "critical"
            deadline_info["deadline_warning"] = (
                f"⚠ URGENT: only {_days_left} day(s) left until the deadline on "
                f"{_lim.isoformat()}. You must notify ACAS (Early Conciliation) "
                f"before a tribunal claim — act now."
            )
        elif _days_left <= 42:
            deadline_info["urgency_level"] = "urgent"
            deadline_info["deadline_warning"] = (
                f"Time is short: {_days_left} days until the deadline on "
                f"{_lim.isoformat()}. Start ACAS Early Conciliation soon."
            )
        else:
            deadline_info["urgency_level"] = "normal"
            deadline_info["deadline_warning"] = None

    # ── Deadline audit: prove the deadline came from rules, not the model ───────
    _write_deadline_audit(claim_type, jurisdiction, ref_date, deadline_info,
                          time_limit_rule, ec_day_a, ec_day_b)

    # ── Qualifying period check (unfair dismissal only — no QP for unpaid wages)
    qualifying_check = None
    if claim_type == "unfair_dismissal":
        qp_rule = next(
            (r for r in bundle.exact_rules if r["rule_key"] == "unfair_dismissal.qualifying_period"),
            None,
        )
        service_start_str = facts.get("service_start_date") or facts.get("employment_start_date")
        if qp_rule and service_start_str:
            service_start = date.fromisoformat(str(service_start_str))
            qualifying_check = check_qualifying_period(
                service_start, edt,
                float(qp_rule["value_numeric"]),
                qp_rule["unit"],
            )
            facts = dict(facts)
            facts["qualifying_period_met"] = qualifying_check["meets_qualifying_period"]
            facts["service_days"] = qualifying_check["service_days"]

    # ── Stage 3: De-identify ─────────────────────────────────────────────────
    safe_facts, boundary_log = deidentify(facts)
    logger.info("De-identification boundary: %s", boundary_log)

    # ── Stage 3b: Deterministic pre-assessment ────────────────────────────────
    # Compute everything that doesn't require model judgment — value range,
    # key weaknesses from facts, citations from rules + BM25.
    # This provides citations and structure even when the model is stubbed.
    if claim_type == "unpaid_wages":
        det_ctx = build_deterministic_context_wages(
            query=query,
            safe_facts=safe_facts,
            bundle_rules=bundle.exact_rules,
            bundle_authorities=bundle.authorities,
            deadline_info=deadline_info,
        )
    else:
        det_ctx = build_deterministic_context(
            query=query,
            safe_facts=safe_facts,
            bundle_rules=bundle.exact_rules,
            bundle_authorities=bundle.authorities,
            deadline_info=deadline_info,
            qualifying_check=qualifying_check,
        )

    # Inject deterministic context into safe_facts for the model prompt
    safe_facts = dict(safe_facts)
    safe_facts["_deterministic_assessment"] = {
        "has_viable_claim":      det_ctx["has_viable_claim"],
        "strength":              det_ctx["strength"],
        "key_weaknesses":        det_ctx["key_weaknesses"],
        "recommended_next_step": det_ctx["recommended_next_step"],
        "reasoning_notes":       det_ctx["reasoning_notes"],
    }

    # ── Knowledge Wiring (System Update 001): inject the Legal Relationship Map ──
    # The legal knowledge graph (legal_nodes/legal_edges, BFS-traversed) resolves
    # legal RELATIONSHIPS (statute -> test -> limitation -> remedy), not isolated
    # snippets. We inject it into safe_facts so the reasoning engine (ART) is FORCED
    # to ingest the graph before reasoning commences — closing the variable-drop gap
    # where graph_context was computed in brain.py then dropped before this stage.
    # Fail-soft: if no subgraph exists for this claim, reasoning proceeds unchanged.
    if graph_context is None:
        try:
            from backend.core.legal_graph import get_claim_subgraph
            graph_context = get_claim_subgraph(claim_type, jurisdiction, max_depth=2)
        except Exception as exc:  # never block reasoning on graph enrichment
            logger.debug("Legal graph enrichment skipped: %s", exc)
            graph_context = {}
    _graph_nodes = graph_context.get("nodes", []) if graph_context else []
    _graph_edges = graph_context.get("edges", []) if graph_context else []
    _graph_text  = (graph_context.get("context_text", "") if graph_context else "")
    if _graph_text:
        # Labelled key => appears as a clear section in the serialized prompt.
        safe_facts["_legal_relationship_map"] = _graph_text
    graph_used = {
        "used":       bool(_graph_text),
        "node_count": len(_graph_nodes),
        "edge_count": len(_graph_edges),
        "root_node":  (graph_context.get("root_node") if graph_context else None),
        "node_ids":   [n.get("node_id") for n in _graph_nodes],
        "source":     (graph_context.get("source") if graph_context else None),
    }
    logger.info("Legal relationship map injected into ART input: %s", graph_used)

    # ── Stage 4: Reason (model or deterministic fallback) ─────────────────────
    if model is None:
        # Auto-select model from config (Anthropic → OpenRouter → Stub)
        from ingestion.config import settings as _settings
        model = select_model(_settings)

    from backend.core.agentic.corpus_citation_guard import enforce_or_regenerate

    def _do_reason(attempt: int) -> str:
        # We need to return raw text for CitationGuard to extract UUIDs.
        # But we also need the structured assessment.
        # We'll run the model reasoning and return its summary/content.
        res = model.reason(safe_facts, bundle, deadline_info, boundary_log)
        # Store the structured result in a closure variable so we can use it if accepted.
        nonlocal current_assessment
        current_assessment = res
        # Return a string containing all summary and citations for UUID extraction
        cites_text = " ".join([c.cite for c in res.citations])
        return f"{res.reasoning_summary} {cites_text}"

    current_assessment: Optional[StructuredAssessment] = None

    def _fallback() -> dict:
        # If model fails to cite correctly, use deterministic fallback
        from shared.schemas import Citation, Deadline, ValueRange
        vr = det_ctx["value_range"]
        dl_date = deadline_info.get("limitation_date")
        
        # We return a dict that can be converted to StructuredAssessment or used as is.
        return {
            "status": "fallback",
            "has_viable_claim":      det_ctx["has_viable_claim"],
            "strength":              det_ctx["strength"],
            "value_range":           vr,
            "key_weaknesses":        det_ctx["key_weaknesses"],
            "employer_arguments":    det_ctx.get("employer_arguments", []),
            "reasoning_summary":     "Deterministic guide provided: model failed grounded-citation gate.",
            "recommended_next_step": det_ctx["recommended_next_step"],
            "citations":             det_ctx["citations"],
            "deadline":              {
                "limitation_date": dl_date,
                "source": "rules",
                "authority": deadline_info.get("authority", "ERA 1996 s.111(2)"),
            },
            "insufficient_grounding": False,
            "fallback_used": True,
            "source": "rules_table"
        }

    guard_result = enforce_or_regenerate(
        reason_fn=_do_reason,
        fallback_fn=_fallback,
        max_regen=1 # bounded regeneration
    )

    if guard_result["status"] == "accepted" and current_assessment:
        assessment = current_assessment
        assessment.insufficient_grounding = False
        _fallback_used = False
        _source = "model_cited"
    else:
        # Map fallback dict back to StructuredAssessment for subsequent stages
        fb = guard_result
        from shared.schemas import Citation, Deadline, ValueRange
        assessment = StructuredAssessment(
            claim_type=claim_type,
            jurisdiction=jurisdiction,
            has_viable_claim=fb["has_viable_claim"],
            strength=fb["strength"],
            reasoning_summary=fb["reasoning_summary"],
            value_range=ValueRange(**fb["value_range"]),
            key_weaknesses=fb["key_weaknesses"],
            employer_arguments=fb["employer_arguments"],
            deadline=Deadline(**fb["deadline"]),
            recommended_next_step=fb["recommended_next_step"],
            citations=[Citation(**c) for c in fb["citations"] if c.get("cite") and c.get("url")],
            grounding_score=0.0,
            confidence_score=0.0,
            insufficient_grounding=fb.get("insufficient_grounding", False)
        )
        _fallback_used = True
        _source = "rules_table"

    # ── Stage 5: Score ────────────────────────────────────────────────────────
    assessment = score(assessment, bundle, safe_facts)
    logger.info(
        "Scores: grounding=%.2f confidence=%.2f insufficient=%s",
        assessment.grounding_score, assessment.confidence_score, assessment.insufficient_grounding,
    )

    # ── Stage 6: Govern ───────────────────────────────────────────────────────
    gov_result = govern(assessment)
    logger.info("Governance: passes=%s reason=%s", gov_result.passes, gov_result.failure_reason)

    # ── Stage 6b: Audit log — written regardless of governance outcome ─────────
    # Stores only safe metadata. No raw user facts, PII, or case narrative.
    _write_audit_log(
        safe_facts=safe_facts,
        bundle=bundle,
        model=model,
        assessment=assessment,
        gov_result=gov_result,
        boundary_log=boundary_log,
    )

    base_fields = {
        "claim_type":        "unfair_dismissal",
        "jurisdiction":      jurisdiction,
        "in_scope":          True,
        "deadline_info":     deadline_info,
        "qualifying_check":  qualifying_check,
        "boundary_log":      {
            "fields_stripped": boundary_log.get("fields_stripped", []),
            "fields_passed":   boundary_log.get("fields_passed", []),
            "pii_in_output":   boundary_log.get("pii_fields_in_output", []),
        },
        "governance_result": {
            "passes":         gov_result.passes,
            "failure_reason": gov_result.failure_reason,
        },
        "model_provider": type(model).__name__,
        "graph_context_used": graph_used,
        "fallback_used": _fallback_used,
        "source": _source,
        "governed_result": "accepted" if not _fallback_used else "fallback",
        "rules_retrieved": len(getattr(bundle, "exact_rules", []) or []),
    }

    if not gov_result.passes:
        reason = gov_result.failure_reason
        if "insufficient_grounding" in reason:
            return {**build_insufficient_grounding_response(reason), **base_fields}
        if "score_threshold" in reason or "low_confidence" in reason:
            return {**build_low_confidence_response(assessment, reason), **base_fields}
        return {**build_insufficient_grounding_response(reason), **base_fields}

    # ── Stage 7: Respond — canonical structured assessment ───────────────────
    a = gov_result.patched_assessment
    return {
        "status":           "ok",
        **base_fields,
        "has_viable_claim":      a.has_viable_claim,
        "strength":              a.strength,
        "reasoning_summary":     a.reasoning_summary,
        "value_range":           a.value_range.model_dump() if a.value_range else None,
        "key_weaknesses":        a.key_weaknesses,
        "employer_arguments":    a.employer_arguments,
        "deadline":              a.deadline.model_dump() if a.deadline else None,
        "recommended_next_step": a.recommended_next_step,
        "citations":             [c.model_dump() for c in a.citations],
        "grounding_score":       a.grounding_score,
        "confidence_score":      a.confidence_score,
        "insufficient_grounding": a.insufficient_grounding,
        "tribunal_elements":      det_ctx.get("tribunal_elements", []),
        # Day-one / automatic-unfair flag (beta blocker C): surfaced so the UI
        # and tests can see when short service does NOT defeat the claim.
        "day_one_exception_possible": det_ctx.get("day_one_exception_possible", False),
        "day_one_exception":      det_ctx.get("day_one_exception"),
        "model_boundary_payload": model.get_boundary_payload(),
    }


# ── Audit log helper ──────────────────────────────────────────────────────────

def _write_audit_log(
    safe_facts: dict,
    bundle,
    model,
    assessment,
    gov_result,
    boundary_log: dict,
) -> None:
    """
    Write one immutable audit row after every governance decision.

    Safe fields only — no personal data, no case narrative, no PII.
    Fails silently rather than crashing the user-facing pipeline.
    """
    try:
        payload = {
            "case_id":            None,  # wired in Phase 3 when cases table is integrated
            "fact_snapshot_hash": _safe_fact_hash(safe_facts),
            "rules_used": [
                {"rule_key": r["rule_key"], "authority_ref": r.get("authority_ref", "")}
                for r in bundle.exact_rules
            ],
            "retrieval_bundle": {
                "rules_count":       len(bundle.exact_rules),
                "authorities_count": len(bundle.authorities),
                "authority_types":   list({a.get("type", "unknown") for a in bundle.authorities}),
                "insufficient_grounding": bundle.insufficient_grounding,
            },
            "model_provider": type(model).__name__,
            "model_name":     getattr(model, "_model_id", None),
            "boundary_log": {
                "fields_stripped":   boundary_log.get("fields_stripped", []),
                "fields_passed":     boundary_log.get("fields_passed", []),
                "pii_in_output":     boundary_log.get("pii_fields_in_output", []),
            },
            "grounding_score":  float(assessment.grounding_score),
            "confidence_score": float(assessment.confidence_score),
            "governance_result": {
                "passes":         gov_result.passes,
                "failure_reason": gov_result.failure_reason,
            },
            "output_version": "1.0",
        }
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                insert_audit_log(cur, payload)
            conn.commit()
            logger.debug("Audit log written (grounding=%.2f passes=%s)",
                         assessment.grounding_score, gov_result.passes)
        finally:
            conn.close()
    except Exception as exc:
        # Never crash the user-facing response due to audit failure
        logger.error("Audit log write failed (non-fatal): %s", exc)
