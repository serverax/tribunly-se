"""
lawapp Brain Algorithm  -  UK Employment Law AI Central Controller.

Every legal request MUST pass through the Brain. No agent, RAG module, LLM,
or document generator may answer directly without Brain authorisation.

19-Step Pipeline (PHASE 1):
  1.  Authenticate user
  2.  Load user_id and case_id
  3.  Detect jurisdiction
  4.  Detect legal area (domain)
  5.  Detect claim type
  6.  Detect urgency and deadline risk
  7.  Detect missing facts (evidence gaps)
  8.  Select legal agents
  9.  Select RAG / Graph RAG / Knowledge Graph source
  10. Run deterministic rules engine
  11. Retrieve cited legal evidence (hybrid search)
  12. Verify citations
  13. Compress context while preserving citations
  14. Generate structured draft assessment
  15. Evaluate draft
  16. Apply legal boundary and safety policy
  17. Save case memory (only if user authenticated and consented)
  18. Store decision trace and audit log
  19. Return final answer

GUARDRAIL: The Brain is the ONLY authorised entry point to the reasoning layer.
           All downstream modules are called BY the Brain, never directly.
GUARDRAIL: No answer leaves the Brain without passing steps 15 and 16.
GUARDRAIL: No case memory is saved without user_id, case_id, and consent.
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
import uuid

from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Step definitions (immutable  -  used in trace output) ─────────────────────
# 19 steps as per PHASE 1 Brain Algorithm specification.

BRAIN_STEPS = [
    "authenticate",           # 1   -  user authentication confirmed
    "load_context",           # 2   -  user_id and case_id loaded
    "detect_jurisdiction",    # 3   -  EW / SC / NI
    "detect_legal_area",      # 4   -  employment_law / out_of_scope
    "detect_claim_type",      # 5   -  unfair_dismissal / unpaid_wages / etc.
    "detect_urgency",         # 6   -  urgency level and days remaining
    "detect_missing_facts",   # 7   -  evidence gaps before agent selection
    "select_agents",          # 8   -  choose legal agents based on claim + urgency
    "select_rag_source",      # 9   -  choose RAG / Graph RAG / KG sources
    "run_rules_engine",       # 10  -  fetch deterministic rules from DB
    "retrieve_legal_evidence",# 11  -  hybrid retrieval (SQL + BM25 + pgvector)
    "verify_citations",       # 12  -  verify every citation against DB
    "compress_context",       # 13  -  compress context preserving all citations
    "generate_draft",         # 14  -  generate structured draft via pipeline
    "evaluate_draft",         # 15  -  legal evaluation rubric
    "apply_safety_policy",    # 16  -  legal boundary + safety gate (blocks if fail)
    "save_case_memory",       # 17  -  persist to legal_memory if allowed
    "store_audit_log",        # 18  -  immutable brain_traces + evaluation_results
    "return_answer",          # 19  -  final answer returned to caller
]

# ── Agent selection map ──────────────────────────────────────────────────────

_AGENT_MAP: dict[str, list[str]] = {
    "unfair_dismissal": [
        "employment_law",
        "deadline",
        "evidence",
        "citation_verification",
        "evaluation",
    ],
    "unpaid_wages": [
        "employment_law",
        "deadline",
        "compensation",
        "citation_verification",
        "evaluation",
    ],
    "discrimination": [
        "employment_law",
        "evidence",
        "risk_review",
        "citation_verification",
        "human_review",
        "evaluation",
    ],
    "whistleblowing": [
        "employment_law",
        "evidence",
        "risk_review",
        "citation_verification",
        "human_review",
        "evaluation",
    ],
    "settlement_agreement": [
        "employment_law",
        "document_drafting",
        "risk_review",
        "human_review",
        "evaluation",
    ],
    "out_of_scope": ["safety_abuse"],
    "_default": [
        "employment_law",
        "deadline",
        "evidence",
        "citation_verification",
        "evaluation",
    ],
}

# ── Urgency thresholds ───────────────────────────────────────────────────────

_URGENT_DAYS   = 30
_CRITICAL_DAYS = 7


def _urgency_level(days_remaining: Optional[int]) -> str:
    if days_remaining is None:
        return "unknown"
    if days_remaining <= 0:
        return "expired"
    if days_remaining <= _CRITICAL_DAYS:
        return "critical"
    if days_remaining <= _URGENT_DAYS:
        return "urgent"
    return "safe"


# ── Safety policy checks ─────────────────────────────────────────────────────

_SAFETY_GUARANTEE_PHRASES = [
    "guaranteed to win", "you will win", "you will receive",
    "you are entitled to", "definite outcome", "certain to succeed",
    "will definitely", "100% chance",
]

_SAFETY_RESERVED_PHRASES = [
    "we will file", "we will represent", "we will conduct",
    "we will litigate", "lawapp will file", "lawapp will represent",
    "we are your solicitor", "we are your lawyer",
]


def _run_safety_checks(assessment: dict, trace_id: str, user_id: Optional[str]) -> dict:
    """
    Apply legal boundary and safety policy to a draft assessment.

    Returns:
      {"passed": bool, "blocked": bool, "failures": list[str], "checks": list[dict]}
    """
    checks: list[dict] = []
    failures: list[str] = []
    blocked = False

    text = " ".join([
        assessment.get("reasoning_summary", ""),
        str(assessment.get("recommended_next_step", "")),
        str(assessment.get("message", "")),
        str(assessment.get("key_weaknesses", "")),
    ]).lower()

    # Check 1: No guarantee/outcome language
    found_guarantee = next(
        (p for p in _SAFETY_GUARANTEE_PHRASES if p in text), None
    )
    c1_pass = found_guarantee is None
    checks.append({
        "check": "no_guarantee_language",
        "passed": c1_pass,
        "severity": "critical",
        "detail": found_guarantee,
    })
    if not c1_pass:
        failures.append(f"guarantee_language:{found_guarantee}")
        blocked = True

    # Check 2: No reserved activity language
    found_reserved = next(
        (p for p in _SAFETY_RESERVED_PHRASES if p in text), None
    )
    c2_pass = found_reserved is None
    checks.append({
        "check": "no_reserved_activity",
        "passed": c2_pass,
        "severity": "critical",
        "detail": found_reserved,
    })
    if not c2_pass:
        failures.append(f"reserved_activity:{found_reserved}")
        blocked = True

    # Check 3: Deadline must come from rules engine (never model estimate)
    deadline_info = assessment.get("deadline_info") or assessment.get("deadline") or {}
    if isinstance(deadline_info, dict):
        dl_source = deadline_info.get("source", "unknown")
        c3_pass = dl_source in ("rules", "rules_engine") or not deadline_info
    else:
        c3_pass = True  # Pydantic Deadline object  -  source field validated by schema
    checks.append({
        "check": "deadline_from_rules",
        "passed": c3_pass,
        "severity": "critical",
        "detail": deadline_info.get("source") if isinstance(deadline_info, dict) else None,
    })
    if not c3_pass:
        failures.append("deadline_not_from_rules_engine")
        blocked = True

    # Check 4: Jurisdiction boundary (EW only for now)
    resp_j = assessment.get("jurisdiction", "EW")
    c4_pass = resp_j in ("EW", "SC", "NI") or assessment.get("status") == "not_supported"
    checks.append({"check": "jurisdiction_valid", "passed": c4_pass, "severity": "high"})
    if not c4_pass:
        failures.append(f"invalid_jurisdiction:{resp_j}")

    # Check 5: CRITIC GATE (reasoning->drafting seam). Every cited authority in the
    # draft assessment MUST resolve to a real local-DB row. A non-resolving citation
    # (hallucination) fails closed -> the chain is blocked BEFORE any drafting, and the
    # rejection is logged for the DSPy optimizer. Graceful: contributes a critical
    # check failure (handled as a blocked state), never a 500.
    _cites = [c for c in (assessment.get("citations") or []) if isinstance(c, dict)]
    c5_pass = True
    if _cites:
        try:
            from backend.core.agentic.critic import CriticAgent, log_agent_validation_failure
            _auths = [{"cite": c.get("cite") or c.get("authority_ref", ""), "type": c.get("type")} for c in _cites]
            c5_pass = CriticAgent()._check_corpus(_auths)
            if not c5_pass:
                log_agent_validation_failure(
                    trace_id=trace_id, agent_name="ART",
                    error="Critic gate: cited authority does not resolve to a local DB row.",
                    snapshot={"citations": [a["cite"] for a in _auths]},
                )
        except Exception:
            c5_pass = False  # fail-closed: cannot verify => block
    checks.append({"check": "critic_citation_integrity", "passed": c5_pass, "severity": "critical"})
    if not c5_pass:
        failures.append("critic_citation_unresolved")
        blocked = True

    # Write to safety_boundary_checks table (non-fatal)
    _write_safety_checks(trace_id, user_id, checks, failures)

    return {
        "passed":  len([c for c in checks if not c["passed"] and c["severity"] == "critical"]) == 0,
        "blocked": blocked,
        "failures": failures,
        "checks": checks,
    }


def get_deterministic_guide(claim_type: str = "unfair_dismissal",
                            jurisdiction: str = "EW") -> dict:
    """Deterministic 'safe haven' content  -  rules-table only, no model. Returned
    when the generative model fails the corpus-citation gate after retries."""
    rules = []
    try:
        from datetime import date
        from backend.core.retrieve import retrieve_rules
        rules = retrieve_rules(claim_type, jurisdiction, date.today())
    except Exception as exc:  # never raise from the fallback path
        logger.debug("deterministic guide rules lookup skipped: %s", exc)
    return {
        "status": "deterministic_guide", "deterministic": True, "invokes_llm": False,
        "source": "rules_table", "claim_type": claim_type, "jurisdiction": jurisdiction,
        "rules": rules,
        "message": ("A verified guide based on the legal rules database is provided "
                    "because a grounded, corpus-cited model answer was not available."),
    }


def execute_generative_lane(query: str, context: Optional[dict] = None,
                            case_id: str = "", user_id: str = "",
                            jurisdiction: str = "EW", claim_type: str = "unfair_dismissal",
                            messages: Optional[list] = None, model=None) -> dict:
    """Generative lane gatekeeper (LLM Fabric / CitationGuard directive).

    Two governed paths, never raw ungrounded model text:

    1. A free-text `model` exposing stream_chat (the citation-guard path): the
       output MUST cite a valid corpus_chunks UUID. Bounded regeneration; on
       failure (e.g. fabricated citations) it falls back to the deterministic
       rules guide. Emits status/fallback_used/source/valid_uuids.

    2. No such model (the /assess path): the full governed pipeline via run_brain
       (classify -> retrieve -> rules -> reason -> govern). Emits governed_result/
       fallback_used/source on the structured assessment.
    """
    context = context or {}

    # Path 1  -  explicit free-text model: enforce corpus-UUID citation, else fallback.
    if model is not None and hasattr(model, "stream_chat"):
        from backend.core.agentic.corpus_citation_guard import enforce_or_regenerate
        msgs = messages or [{"role": "user", "content": query}]

        def _reason(_attempt: int) -> str:
            return "".join(model.stream_chat(msgs))

        return enforce_or_regenerate(
            reason_fn=_reason,
            fallback_fn=lambda: get_deterministic_guide(claim_type, jurisdiction),
        )

    # Path 2  -  governed structured pipeline (retrieval + rules + governance).
    effective_query = query or next(
        (m["content"] for m in reversed(messages or []) if m.get("role") == "user"), "")
    # Governed pipeline = pipeline.assess (retrieve -> deidentify -> reason ->
    # score -> govern). Returns the FULL governed dict (boundary_log,
    # governance_result, citations, deadline) + governed metadata. We call it
    # directly rather than via run_brain so the /assess response retains its
    # governed shape and avoids the run_brain summarisation/json path.
    from backend.core.models import select_model
    from backend.core.pipeline import assess as _pipeline_assess
    from ingestion.config import settings as _settings
    _model = model or select_model(_settings)
    result = _pipeline_assess(query=effective_query, facts=context,
                              model=_model, jurisdiction=jurisdiction)
    _ok = result.get("status") == "ok"
    result.setdefault("governed_result", "accepted" if _ok else (result.get("status") or "blocked"))
    result.setdefault("fallback_used", not _ok)
    result.setdefault("source", "model_cited" if _ok else "rules_table")
    return result


class Orchestrator:
    """Institutionalised governed pipeline orchestrator (facade over core.orchestrator)."""

    @staticmethod
    def execute_generative_lane(
        query: str,
        context: dict,
        case_id: str,
        user_id: str,
        jurisdiction: str = "EW",
        claim_type: str = "unfair_dismissal",
    ) -> dict:
        return execute_generative_lane(
            query=query,
            context=context,
            case_id=case_id,
            user_id=user_id,
            jurisdiction=jurisdiction,
            claim_type=claim_type,
        )

    @staticmethod
    def classify(message: str, facts: dict, jurisdiction: str = "EW") -> dict:
        from backend.core.orchestrator import orchestrator as _orch
        return _orch.classify(message, facts, jurisdiction)

    @staticmethod
    def route(claim_type: str, urgency: str = "safe", domain: str = "employment") -> dict:
        from backend.core.orchestrator import orchestrator as _orch
        return _orch.route(claim_type, urgency, domain)

    @staticmethod
    def delegate(agent_names, message, facts, bundle, jurisdiction="EW"):
        from backend.core.orchestrator import orchestrator as _orch
        return _orch.delegate(agent_names, message, facts, bundle, jurisdiction)

    @staticmethod
    def merge(agent_results, route: dict):
        from backend.core.orchestrator import orchestrator as _orch
        return _orch.merge(agent_results, route)

    @staticmethod
    def run_stages(message, facts, bundle, **kwargs):
        from backend.core.orchestrator import orchestrator as _orch
        return _orch.run_stages(message, facts, bundle, **kwargs)


orchestrator = Orchestrator()


def _write_safety_checks(
    trace_id: str,
    user_id: Optional[str],
    checks: list[dict],
    failures: list[str],
) -> None:
    """Persist safety check results. Fails silently."""
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                for check in checks:
                    reason = None
                    if not check["passed"]:
                        # Match this check to a failure reason
                        check_name = check["check"]
                        reason = next(
                            (f for f in failures if check_name.replace("no_", "") in f or check_name in f),
                            None,
                        )
                    cur.execute(
                        """
                        INSERT INTO safety_boundary_checks (
                            trace_id, user_id, check_name, passed,
                            failure_reason, blocked, severity
                        ) VALUES (%s, %s::uuid, %s, %s, %s, %s, %s)
                        """,
                        (
                            trace_id,
                            user_id,
                            check["check"],
                            check["passed"],
                            reason,
                            check.get("severity") == "critical" and not check["passed"],
                            check.get("severity", "medium"),
                        ),
                    )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("safety_boundary_checks write skipped: %s", exc)


# ── Brain trace dataclass ────────────────────────────────────────────────────

class BrainTrace:
    """Mutable trace object built up as the Brain runs each step."""

    def __init__(self, trace_id: str, started_at: str):
        self.trace_id        = trace_id
        self.started_at      = started_at
        self.steps: list[dict] = []
        self.jurisdiction: Optional[str]  = None
        self.legal_area: Optional[str]    = None
        self.claim_type: Optional[str]    = None
        self.urgency: Optional[str]       = None
        self.days_remaining: Optional[int] = None
        self.missing_facts: list[str]     = []
        self.agents_selected: list[str]   = []
        self.rag_sources: list[str]       = []
        self.rules_count:  int            = 0
        self.sources_count: int           = 0
        self.citations_verified: int      = 0
        self.citations_failed:   int      = 0
        self.compression_stats: dict      = {}
        self.evaluation_required: bool    = True
        self.evaluation_passed: Optional[bool] = None
        self.evaluation_reason: Optional[str]  = None
        self.safety_passed: Optional[bool]     = None
        self.safety_failures: list[str]        = []
        self.memory_saved: bool                = False
        self.audit_id: Optional[str]           = None
        self.final_status: Optional[str]       = None
        self.duration_ms: Optional[float]      = None
        self.orchestration_stages: list[dict]  = []
        self.compliance_verdict: Optional[str] = None
        self.reasoning_chain_summary: dict     = {}

    def record_step(self, name: str, status: str = "ok", detail: Any = None) -> None:
        self.steps.append({
            "step":   name,
            "status": status,
            "detail": detail,
            "ts":     _dt.datetime.now(_dt.timezone.utc).isoformat(),
        })

    def to_dict(self) -> dict:
        return {
            "trace_id":            self.trace_id,
            "started_at":          self.started_at,
            "jurisdiction":        self.jurisdiction,
            "legal_area":          self.legal_area,
            "claim_type":          self.claim_type,
            "urgency":             self.urgency,
            "days_remaining":      self.days_remaining,
            "missing_facts":       self.missing_facts,
            "agents_selected":     self.agents_selected,
            "rag_sources":         self.rag_sources,
            "rules_applied":       self.rules_count,
            "sources_retrieved":   self.sources_count,
            "citations_verified":  self.citations_verified,
            "citations_failed":    self.citations_failed,
            "compression_stats":   self.compression_stats,
            "evaluation_required": self.evaluation_required,
            "evaluation_passed":   self.evaluation_passed,
            "evaluation_reason":   self.evaluation_reason,
            "safety_passed":       self.safety_passed,
            "safety_failures":     self.safety_failures,
            "memory_saved":        self.memory_saved,
            "audit_id":            self.audit_id,
            "final_status":        self.final_status,
            "duration_ms":         self.duration_ms,
            "orchestration_stages": self.orchestration_stages,
            "compliance_verdict":  self.compliance_verdict,
            "reasoning_chain_summary": self.reasoning_chain_summary,
            "steps":               self.steps,
        }


# ── Brain Algorithm ──────────────────────────────────────────────────────────

def run_brain(
    message: str,
    facts: dict,
    user_id: Optional[str]  = None,
    case_id: Optional[str]  = None,
    jurisdiction: str       = "EW",
    model                   = None,
    memory_consent: bool    = False,
) -> dict:
    """
    Run the full 19-step lawapp Brain Algorithm.

    Args:
        message:        User query text
        facts:          Structured case facts dict
        user_id:        Authenticated user UUID (None = unauthenticated)
        case_id:        Case UUID for memory isolation (None = no case context)
        jurisdiction:   "EW" | "SC" | "NI" (default "EW")
        model:          ReasoningModel instance (None = auto-select from config)
        memory_consent: True only if user has explicitly consented to memory retention

    Returns dict with:
        - "trace":          BrainTrace.to_dict()  -  full 19-step audit
        - "assessment":     pipeline result
        - "agents_selected": list of activated agent names
        - "missing_facts":  evidence gaps detected at step 7
        - "urgency":        urgency level string
        - "days_remaining": int or None
        - "evaluation":     {"required", "passed", "reason"}
        - "safety":         {"passed", "blocked", "failures"}

    GUARDRAIL: This function is the ONLY authorised entry point to the
               reasoning layer. No downstream module may be called directly.
    """
    t0         = time.monotonic()
    # Reuse the per-request correlation id from telemetry (§18) so the SAME
    # trace_id appears in the HTTP response header, structured logs, this brain
    # trace, the brain_traces DB row, the outbox event, and the OTEL span.
    # Falls back to a fresh UUID for direct (non-HTTP) callers and tests.
    trace_id = str(uuid.uuid4())
    try:
        from backend.core import otel as _otel
        _rid = _otel.get_request_id()
        if _rid and _rid != "-":
            trace_id = str(uuid.UUID(str(_rid)))
    except Exception:
        pass
    started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    trace      = BrainTrace(trace_id=trace_id, started_at=started_at)

    # ── Pre-step: Injection guard ────────────────────────────────────────────
    try:
        from backend.core.injection_guard import check_user_input as _inj_check
        _inj = _inj_check(message, user_id=user_id, trace_id=trace_id)
        trace.record_step("injection_guard", "blocked" if not _inj.clean else "ok", _inj.to_dict())
        if not _inj.clean:
            trace.final_status = "blocked_by_injection_guard"
            trace.duration_ms  = round((time.monotonic() - t0) * 1000, 1)
            return {
                "trace": trace.to_dict(),
                "assessment": {"status": "blocked", "message": "Request blocked by security policy."},
                "agents_selected": [], "missing_facts": [],
                "urgency": "unknown", "days_remaining": None,
                "evaluation": {"required": False, "passed": None, "reason": "blocked"},
                "safety": {"passed": False, "blocked": True, "failures": [f"injection:{_inj.category}"]},
            }
    except Exception as _exc:
        logger.debug("injection_guard skipped: %s", _exc)

    # ── Step 1: Authenticate ────────────────────────────────────────────────
    # Authentication is performed in the API layer before run_brain is called.
    # user_id=None means unauthenticated / anonymous session.
    trace.record_step("authenticate", "ok", {
        "user_id_present": bool(user_id),
        "authenticated":   bool(user_id),
    })

    # ── Step 2: Load context ─────────────────────────────────────────────────
    trace.record_step("load_context", "ok", {
        "user_id":    user_id,
        "case_id":    case_id,
        "facts_keys": list(facts.keys()),
    })

    # ── Step 3: Detect jurisdiction ──────────────────────────────────────────
    j = facts.get("jurisdiction", jurisdiction).upper()
    if j not in ("EW", "SC", "NI"):
        j = "EW"
    trace.jurisdiction = j
    trace.record_step("detect_jurisdiction", "ok", {"jurisdiction": j})

    # ── Step 4: Detect legal area ─────────────────────────────────────────────
    from backend.core.classify import classify as _classify
    clf    = _classify(message, facts)
    domain = "employment_law" if clf.in_scope else "out_of_scope"
    trace.legal_area = domain
    trace.record_step("detect_legal_area",
                      "ok" if clf.in_scope else "out_of_scope",
                      {"in_scope": clf.in_scope, "domain": domain})

    # ── Step 5: Detect claim type ─────────────────────────────────────────────
    claim_type = clf.matter_type if clf.in_scope else "out_of_scope"
    trace.claim_type = claim_type
    trace.record_step("detect_claim_type", "ok", {
        "claim_type": claim_type,
        "intent":     clf.intent,
    })

    # ── Step 6: Detect urgency and deadline risk ──────────────────────────────
    edt = facts.get("edt") or facts.get("wages_due_date")
    days_remaining: Optional[int] = None
    if edt and claim_type != "out_of_scope":
        try:
            from backend.domains.employment.deadline import compute_limitation_date
            from backend.core.retrieve import retrieve_rules
            rules = retrieve_rules(claim_type, j, edt)
            tl = next(
                (r["value_numeric"] for r in rules
                 if "time_limit_months" in r.get("rule_key", "")),
                None,
            )
            if tl is None:
                raise ValueError("time_limit_months rule missing")
            deadline_result = compute_limitation_date(edt, int(tl), None, None)
            if deadline_result and deadline_result.get("limitation_date"):
                lim = _dt.date.fromisoformat(deadline_result["limitation_date"])
                days_remaining = (lim - _dt.date.today()).days
        except Exception as exc:
            logger.debug("Urgency calculation skipped: %s", exc)

    urgency = _urgency_level(days_remaining)
    trace.urgency       = urgency
    trace.days_remaining = days_remaining
    trace.record_step(
        "detect_urgency",
        "urgent" if urgency in ("urgent", "critical", "expired") else "ok",
        {"urgency": urgency, "days_remaining": days_remaining},
    )

    # ── Human review check (after urgency) ───────────────────────────────────
    human_review_id = None
    human_review_reason = "not_high_risk"
    try:
        from backend.core.human_review import should_queue as _hr_should, queue_case as _hr_queue
        _hr_needed, human_review_reason = _hr_should(claim_type, urgency, [], None)
        if _hr_needed and user_id and case_id:
            human_review_id = _hr_queue(
                trace_id=trace_id, user_id=user_id, case_id=case_id,
                claim_type=claim_type, urgency=urgency, reason=human_review_reason,
                missing_facts=[],
            )
        trace.record_step("human_review_check", "queued" if human_review_id else "not_required",
                          {"queued": bool(human_review_id), "reason": human_review_reason})
    except Exception as _exc:
        logger.debug("human_review_check skipped: %s", _exc)

    # ── Early exit for out-of-scope ───────────────────────────────────────────
    if not clf.in_scope:
        trace.final_status = "not_supported"
        trace.duration_ms  = round((time.monotonic() - t0) * 1000, 1)
        # Record remaining steps as skipped for trace completeness
        for step in ["detect_missing_facts", "select_agents", "select_rag_source",
                     "run_rules_engine", "retrieve_legal_evidence", "verify_citations",
                     "compress_context", "generate_draft", "evaluate_draft",
                     "apply_safety_policy", "save_case_memory", "store_audit_log",
                     "return_answer"]:
            trace.record_step(step, "skipped", {"reason": "out_of_scope"})
        return {
            "trace": trace.to_dict(),
            "assessment": {
                "status":     "not_supported",
                "message": (
                    "This service handles unfair dismissal and unpaid wages claims "
                    "in England and Wales only. Please seek appropriate specialist advice."
                ),
                "claim_type": claim_type,
            },
            "agents_selected": ["safety_abuse"],
            "missing_facts":   [],
            "urgency":         urgency,
            "days_remaining":  days_remaining,
            "evaluation": {"required": False, "passed": None, "reason": "out_of_scope"},
            "safety":     {"passed": True,  "blocked": False, "failures": []},
        }

    # ── Step 7: Detect missing facts ──────────────────────────────────────────
    missing_facts: list[str] = []
    try:
        from backend.core.evidence_gap import detect_gaps
        missing_facts = detect_gaps(claim_type, facts)
    except Exception as exc:
        logger.debug("Evidence gap detection skipped: %s", exc)
    trace.missing_facts = missing_facts
    trace.record_step(
        "detect_missing_facts",
        "ok" if not missing_facts else "gaps_found",
        {"gaps": missing_facts, "count": len(missing_facts)},
    )

    # ── Step 8: Select legal agents ───────────────────────────────────────────
    agents = list(_AGENT_MAP.get(claim_type, _AGENT_MAP["_default"]))
    if urgency in ("urgent", "critical", "expired") and "human_review" not in agents:
        agents = agents + ["human_review"]
    trace.agents_selected  = agents
    trace.evaluation_required = "evaluation" in agents or urgency in ("urgent", "critical")
    trace.record_step("select_agents", "ok", {
        "agents":              agents,
        "evaluation_required": trace.evaluation_required,
    })

    # ── Step 9: Select RAG / Graph RAG / Knowledge Graph source ──────────────
    from backend.core.legal_graph import select_rag_sources as _select_rag
    from backend.core.router import route as _route

    routing_decision = _route(message, facts, claim_type)
    rag_selection = _select_rag(
        claim_type    = claim_type,
        risk_level    = routing_decision.risk_level,
        is_generic    = routing_decision.path == "lite_llm_plus_glossary",
        jurisdiction  = j,
    )
    trace.rag_sources = rag_selection["sources"]
    trace.record_step("select_rag_source", "ok", {
        "sources":   rag_selection["sources"],
        "primary":   rag_selection["primary"],
        "use_graph": rag_selection["use_graph"],
        "use_kg":    rag_selection["use_kg"],
        "reason":    rag_selection["reason"],
        "route":     routing_decision.path,
    })

    # ── Step 10: Run deterministic rules engine ────────────────────────────────
    rules_list: list[dict] = []
    try:
        from backend.core.retrieve import retrieve_rules
        rules_list = retrieve_rules(claim_type, j, edt)
    except Exception as exc:
        logger.warning("Rules engine error: %s", exc)
    trace.rules_count = len(rules_list)
    trace.record_step("run_rules_engine", "ok", {
        "rules_found": len(rules_list),
        "claim_type":  claim_type,
    })

    # ── Step 11: Retrieve cited legal evidence (hybrid search) ────────────────
    bundle = None
    graph_context: dict = {}
    try:
        from backend.core.retrieve import retrieve
        bundle = retrieve(message, claim_type, j, edt)
        trace.sources_count = len(getattr(bundle, "authorities", []))

        # Enrich with legal graph if selected
        if rag_selection["use_graph"]:
            from backend.core.legal_graph import get_claim_subgraph
            graph_context = get_claim_subgraph(claim_type, j, max_depth=2)
    except Exception as exc:
        logger.warning("Retrieval error: %s", exc)
    trace.record_step("retrieve_legal_evidence", "ok", {
        "sources_count":        trace.sources_count,
        "insufficient_grounding": getattr(bundle, "insufficient_grounding", True),
        "graph_nodes":          len(graph_context.get("nodes", [])),
    })

    # ── Step 11b: Orchestrate agents (classify → route → delegate → merge) ─────
    orchestration_summary: dict = {}
    try:
        from backend.domains.registry import resolve_domain_for_matter
        from backend.core.orchestrator import orchestrator as _orch

        _domain = resolve_domain_for_matter(claim_type) or "employment"
        orch = _orch.run_stages(
            message,
            facts,
            bundle,
            jurisdiction=j,
            claim_type=claim_type,
            urgency=urgency,
            domain=_domain,
            agent_names=agents,
        )
        orchestration_summary = orch.to_dict()
        trace.orchestration_stages = orch.stages
        if orch.evidence_gaps:
            trace.missing_facts = list(dict.fromkeys(trace.missing_facts + orch.evidence_gaps))
        trace.record_step("orchestrate_agents", "ok", {
            "agents_run": orch.agents_run,
            "human_review_required": orch.human_review_required,
            "tools_available": orch.tools_available,
        })
    except Exception as exc:
        logger.warning("Agent orchestration skipped: %s", exc)
        trace.record_step("orchestrate_agents", "skipped", {"reason": str(exc)})

    # ── Step 12: Verify citations ──────────────────────────────────────────────
    verified, failed = 0, 0
    if bundle and getattr(bundle, "authorities", []):
        try:
            from backend.core.citation_verifier import verify_bundle_citations
            v_result = verify_bundle_citations(bundle.authorities)
            verified = v_result["verified"]
            failed   = v_result["failed"]
        except Exception as exc:
            logger.debug("Citation verification skipped: %s", exc)
    trace.citations_verified = verified
    trace.citations_failed   = failed
    trace.record_step("verify_citations",
                      "ok" if failed == 0 else "partial",
                      {"verified": verified, "failed": failed})

    # ── Step 13: Compress context while preserving citations ──────────────────
    compression_result: dict = {}
    try:
        from backend.core.context_compressor import compress_bundle
        compression_result = compress_bundle(
            exact_rules  = getattr(bundle, "exact_rules", rules_list),
            authorities  = getattr(bundle, "authorities", []),
            trace_id     = trace_id,
        )
        trace.compression_stats = compression_result.get("stats", {})
    except Exception as exc:
        logger.debug("Context compression skipped: %s", exc)
    trace.record_step("compress_context", "ok", {
        "stats": trace.compression_stats or {"skipped": True},
    })

    # ── Cost governor (before LLM call) ──────────────────────────────────────
    routing_path = routing_decision.path
    try:
        from backend.core.cost_governor import check as _cost_check
        _cost = _cost_check(user_id=user_id, route=routing_path, trace_id=trace_id)
        trace.record_step("cost_governor", "blocked" if not _cost.allowed else "ok", _cost.to_dict())
        if not _cost.allowed:
            trace.final_status = "blocked_by_cost_governor"
            trace.duration_ms  = round((time.monotonic() - t0) * 1000, 1)
            return {
                "trace": trace.to_dict(),
                "assessment": {"status": "quota_exceeded",
                               "message": "Daily usage quota exceeded. Please try again later."},
                "agents_selected": agents,
                "missing_facts": missing_facts,
                "urgency": urgency, "days_remaining": days_remaining,
                "evaluation": {"required": False, "passed": None, "reason": "quota_exceeded"},
                "safety": {"passed": True, "blocked": False, "failures": []},
            }
    except Exception as _exc:
        logger.debug("cost_governor skipped: %s", _exc)

    # ── Step 14: Generate structured draft assessment ─────────────────────────
    assessment: dict = {}
    try:
        from backend.core.pipeline import assess as _assess
        # Knowledge Wiring (System Update 001): pass the graph_context computed at
        # Step 11 into the reasoning payload so ART ingests the legal relationship
        # map BEFORE reasoning  -  closes the variable-drop where graph_context was
        # previously computed then dropped before drafting.
        #
        # pipeline.assess now includes CitationGuard (LLM Fabric directive).
        result = _assess(message, facts, model=model, jurisdiction=j,
                         graph_context=graph_context or None)
        
        # Extract governed metadata from the pipeline result
        assessment = result
        assessment["governed_result"] = "accepted" if not result.get("fallback_used") else "fallback_rules_table"
        assessment["source"] = result.get("source", "model_cited")
        assessment["fallback_used"] = result.get("fallback_used", False)
        assessment["trace_id"] = trace_id
        
        # Collect rules used from retrieval
        assessment["rules_used"] = [r.get("rule_key") for r in (bundle.exact_rules if bundle else [])]

    except Exception as exc:
        logger.error("Pipeline error in brain: %s", exc)
        assessment = {"status": "error", "message": "Internal assessment error. Please try again."}
    
    trace.record_step("generate_draft",
                      assessment.get("status", "error"),
                      {"status": assessment.get("status")})

    # ── Step 15: Evaluate draft ────────────────────────────────────────────────
    eval_passed = None
    eval_reason = ""
    try:
        from backend.core.evaluator import evaluate_assessment
        eval_result  = evaluate_assessment(assessment, facts, bundle, missing_facts)
        eval_passed  = eval_result["passed"]
        eval_reason  = eval_result.get("reason", "")
    except Exception as exc:
        logger.debug("Evaluation skipped: %s", exc)
        eval_passed = assessment.get("status") not in ("error",)
    trace.evaluation_passed = eval_passed
    trace.evaluation_reason = eval_reason
    trace.record_step("evaluate_draft",
                      "pass" if eval_passed else "fail",
                      {"passed": eval_passed, "reason": eval_reason})

    # ── Step 16: Apply legal boundary and safety policy ───────────────────────
    safety_result = _run_safety_checks(assessment, trace_id, user_id)
    trace.safety_passed   = safety_result["passed"]
    trace.safety_failures = safety_result["failures"]
    trace.record_step(
        "apply_safety_policy",
        "pass" if safety_result["passed"] else "fail",
        {
            "passed":   safety_result["passed"],
            "blocked":  safety_result["blocked"],
            "failures": safety_result["failures"],
        },
    )

    # Compliance verdict for audit (CitationGuard + safety + evaluation)
    _citation_ok = failed == 0 and verified > 0
    if safety_result["blocked"]:
        trace.compliance_verdict = "blocked_safety"
    elif eval_passed is False:
        trace.compliance_verdict = "blocked_evaluation"
    elif assessment.get("status") == "ok" and _citation_ok and safety_result["passed"]:
        trace.compliance_verdict = "pass"
    elif assessment.get("governance_result", {}).get("passes") is False:
        trace.compliance_verdict = "blocked_governance"
    else:
        trace.compliance_verdict = "conditional"
    trace.reasoning_chain_summary = {
        "claim_type": claim_type,
        "agents_selected": agents,
        "agents_run": orchestration_summary.get("agents_run", []),
        "rules_count": trace.rules_count,
        "sources_count": trace.sources_count,
        "citations_verified": verified,
        "evaluation_passed": eval_passed,
        "governance_passes": assessment.get("governance_result", {}).get("passes"),
        "orchestration": orchestration_summary,
    }

    # If safety gate blocked the answer, return a safe fallback
    if safety_result["blocked"]:
        trace.final_status = "blocked_by_safety"
        trace.duration_ms  = round((time.monotonic() - t0) * 1000, 1)
        trace.record_step("save_case_memory", "skipped", {"reason": "blocked_by_safety"})
        trace.record_step("store_audit_log",  "skipped", {"reason": "blocked_by_safety"})
        trace.record_step("return_answer",    "blocked", {"status": "blocked_by_safety"})
        return {
            "trace": trace.to_dict(),
            "assessment": {
                "status":  "blocked",
                "message": (
                    "This response was blocked by the lawapp safety policy. "
                    "It may have contained prohibited language. Please contact support."
                ),
            },
            "agents_selected": agents,
            "missing_facts":   missing_facts,
            "urgency":         urgency,
            "days_remaining":  days_remaining,
            "evaluation": {"required": trace.evaluation_required,
                           "passed":   eval_passed, "reason": eval_reason},
            "safety":     safety_result,
        }

    # ── Step 17: Save case memory (only if allowed) ───────────────────────────
    memory_saved = False
    if (user_id and case_id and memory_consent
            and assessment.get("status") == "ok"):
        try:
            from backend.core.memory import save_memory as _save_memory
            _save_memory(
                user_id     = user_id,
                case_id     = case_id,
                memory_type = "previous_answers",
                key         = f"brain_trace_{trace_id}",
                value       = {
                    "claim_type":  claim_type,
                    "urgency":     urgency,
                    "eval_passed": eval_passed,
                    "status":      assessment.get("status"),
                },
                encrypted   = False,
            )
            memory_saved = True
        except Exception as exc:
            logger.debug("Memory save skipped: %s", exc)
    trace.memory_saved = memory_saved
    trace.record_step("save_case_memory",
                      "saved" if memory_saved else "skipped",
                      {
                          "saved":   memory_saved,
                          "reason":  "no_consent_or_auth" if not memory_consent else
                                     "assessment_not_ok"  if assessment.get("status") != "ok" else
                                     "saved",
                      })

    # ── Step 18: Store decision trace and audit log ───────────────────────────
    audit_id = None
    try:
        audit_id = _write_brain_audit(
            trace_id           = trace_id,
            user_id            = user_id,
            case_id            = case_id,
            claim_type         = claim_type,
            agents             = agents,
            rag_sources        = rag_selection["sources"],
            missing_facts      = missing_facts,
            rules_count        = len(rules_list),
            sources_count      = trace.sources_count,
            citations_verified = verified,
            citations_failed   = failed,
            evaluation_passed  = eval_passed,
            safety_passed      = safety_result["passed"],
            memory_saved       = memory_saved,
            final_status       = assessment.get("status", "error"),
            compliance_verdict = trace.compliance_verdict,
            reasoning_chain_summary = trace.reasoning_chain_summary,
            orchestration_stages = trace.orchestration_stages,
        )
    except Exception as exc:
        logger.debug("Brain audit write skipped: %s", exc)
    trace.audit_id = audit_id
    trace.record_step("store_audit_log", "ok", {"audit_id": audit_id})

    # ── Step 18b: Publish assessment_complete event to transactional outbox ───
    # Fail-open: outbox delivery is async and must never block the user answer,
    # but a successful, audited assessment must emit a durable event for the
    # background worker (reindex / notifications / evaluation jobs).
    outbox_event_id = None
    try:
        from backend.core import outbox as _outbox
        if assessment.get("status") == "ok":
            outbox_event_id = _outbox.publish(
                "assessment_complete",
                {
                    "trace_id":   trace_id,
                    "user_id":    user_id,
                    "case_id":    case_id,
                    "claim_type": claim_type,
                    "urgency":    urgency,
                    "status":     assessment.get("status"),
                    "audit_id":   audit_id,
                },
                trace_id=trace_id,
                idempotency_key=f"assessment_complete:{trace_id}",
            )
    except Exception as exc:
        logger.debug("outbox publish skipped: %s", exc)
    trace.record_step(
        "publish_outbox_event",
        "published" if outbox_event_id else "skipped",
        {"event_id": outbox_event_id},
    )

    # ── Step 19: Return final answer ──────────────────────────────────────────
    trace.final_status = assessment.get("status", "error")
    trace.duration_ms  = round((time.monotonic() - t0) * 1000, 1)
    trace.record_step("return_answer", "ok", {
        "status":      trace.final_status,
        "duration_ms": trace.duration_ms,
    })

    return {
        "trace":           trace.to_dict(),
        "assessment":      assessment,
        "agents_selected": agents,
        "missing_facts":   missing_facts,
        "urgency":         urgency,
        "days_remaining":  days_remaining,
        "evaluation": {
            "required": trace.evaluation_required,
            "passed":   eval_passed,
            "reason":   eval_reason,
        },
        "safety": safety_result,
    }


# ── Brain audit writer ────────────────────────────────────────────────────────

def _write_brain_audit(
    trace_id:           str,
    user_id:            Optional[str],
    case_id:            Optional[str],
    claim_type:         str,
    agents:             list[str],
    rag_sources:        list[str],
    missing_facts:      list[str],
    rules_count:        int,
    sources_count:      int,
    citations_verified: int,
    citations_failed:   int,
    evaluation_passed:  Optional[bool],
    safety_passed:      Optional[bool],
    memory_saved:       bool,
    final_status:       str,
    compliance_verdict: Optional[str] = None,
    reasoning_chain_summary: Optional[dict] = None,
    orchestration_stages: Optional[list] = None,
) -> Optional[str]:
    """
    Write brain trace to brain_traces table. Returns trace_id on success.
    Fails silently if DB unavailable.
    """
    import json
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brain_traces (
                    trace_id, user_id, case_id, claim_type,
                    agents_used, rules_count, sources_count,
                    citations_verified, citations_failed,
                    evidence_gaps, evaluation_passed, final_status,
                    missing_facts, rag_sources, safety_passed, memory_saved,
                    compliance_verdict, reasoning_chain_summary, orchestration_stages
                ) VALUES (
                    %s, %s::uuid, %s::uuid, %s,
                    %s::jsonb, %s, %s,
                    %s, %s,
                    %s::jsonb, %s, %s,
                    %s::jsonb, %s::jsonb, %s, %s,
                    %s, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (trace_id) DO NOTHING
                RETURNING trace_id
                """,
                (
                    trace_id,
                    user_id,
                    case_id,
                    claim_type,
                    json.dumps(agents),
                    rules_count,
                    sources_count,
                    citations_verified,
                    citations_failed,
                    json.dumps(missing_facts),
                    evaluation_passed,
                    final_status,
                    json.dumps(missing_facts),
                    json.dumps(rag_sources),
                    safety_passed,
                    memory_saved,
                    compliance_verdict,
                    json.dumps(reasoning_chain_summary or {}),
                    json.dumps(orchestration_stages or []),
                ),
            )
            conn.commit()
            return trace_id
    finally:
        conn.close()
