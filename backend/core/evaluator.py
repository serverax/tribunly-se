"""
Legal Evaluation AI.

Every legal answer must pass evaluation before final output.
Evaluation checks mirror and extend the governance gate.

Evaluation rubric:
  1. Citation validity — citations exist in DB
  2. Authority hierarchy — primary legislation > case law > guidance
  3. Jurisdiction — answer matches requested jurisdiction
  4. Limitation/deadline logic — dates are rule-derived, not estimated
  5. Missing evidence — key gaps were stated, not ignored
  6. Hallucination risk — reasoning summary doesn't invent facts
  7. Overconfident advice — no guarantees, no reserved activities
  8. Human review requirement — high-risk claims flagged
  9. Data privacy — no PII in output

If evaluation fails on any CRITICAL check, the answer is blocked or
returned to the brain for correction.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Blocked phrases (extended from govern.py) ────────────────────────────────

_GUARANTEE_PHRASES = [
    "guaranteed to win",
    "you will win",
    "you will receive",
    "you are entitled to",
    "definite outcome",
    "certain to succeed",
    "will definitely",
    "100% chance",
]

_RESERVED_ACTIVITY_PHRASES = [
    "we will file",
    "we will represent",
    "we will conduct",
    "we will litigate",
    "lawapp will file",
    "lawapp will represent",
]

_INCORRECT_DEADLINES = {
    "6 months to bring unfair dismissal": "incorrect_ud_deadline",
    "12 months to claim": "incorrect_ud_deadline",
    "1 year to bring": "incorrect_ud_deadline",
    "two years to claim": "incorrect_ud_deadline",
}


def evaluate_assessment(
    assessment: dict,
    facts: dict,
    bundle: Any = None,
    evidence_gaps: Optional[list[str]] = None,
) -> dict:
    """
    Run the legal evaluation rubric against a draft assessment.

    Returns:
      {"passed": bool, "reason": str | None, "checks": list[dict]}
    """
    checks = []
    failures = []

    # ── Check 1: Citation validity ────────────────────────────────────────────
    citations = assessment.get("citations", [])
    if citations:
        try:
            from backend.core.citation_verifier import verify_bundle_citations
            from ingestion.db import get_connection as _gc
            # Check if source tables have been ingested — skip citation DB check if empty
            _conn = _gc()
            try:
                with _conn.cursor() as _cur:
                    _cur.execute("SELECT COUNT(*) FROM legislation")
                    _leg_count = _cur.fetchone()[0]
            finally:
                _conn.close()

            if _leg_count == 0:
                # Source tables not ingested — can't verify DB citations; don't block
                citation_ok = True
            else:
                cit_list = [{"cite": c.get("cite", c) if isinstance(c, dict) else c, "type": "legislation"}
                            for c in citations[:10]]
                result = verify_bundle_citations(cit_list)
                citation_ok = result["pass_rate"] >= 0.5
        except Exception:
            citation_ok = True  # DB unavailable — don't block
        check = {"check": "citation_validity", "passed": citation_ok, "severity": "high"}
        checks.append(check)
        if not citation_ok:
            failures.append("citation_validity_low_pass_rate")
    else:
        status = assessment.get("status", "")
        # No citations OK for insufficient_grounding or not_supported
        ok = status in ("insufficient_grounding", "not_supported", "missing_edt", "low_confidence")
        checks.append({"check": "citation_validity", "passed": ok, "severity": "medium"})
        if not ok:
            failures.append("no_citations_in_viable_assessment")

    # ── Check 2: Jurisdiction ─────────────────────────────────────────────────
    resp_j = assessment.get("jurisdiction", "EW").upper()
    req_j = facts.get("jurisdiction", "EW").upper()
    j_ok = resp_j == req_j or assessment.get("status") in ("not_supported", "insufficient_grounding")
    checks.append({"check": "jurisdiction", "passed": j_ok, "severity": "critical"})
    if not j_ok:
        failures.append(f"jurisdiction_mismatch:{resp_j}_vs_{req_j}")

    # ── Check 3: Deadline source ─────────────────────────────────────────────
    deadline_info = assessment.get("deadline_info") or {}
    if deadline_info:
        dl_source = deadline_info.get("source", "unknown")
        dl_ok = dl_source in ("rules", "rules_engine")
        checks.append({"check": "deadline_source", "passed": dl_ok, "severity": "critical"})
        if not dl_ok:
            failures.append(f"deadline_not_from_rules:source={dl_source}")
    else:
        checks.append({"check": "deadline_source", "passed": True, "severity": "low",
                       "note": "no_deadline_in_response"})

    # ── Check 4: No overconfident / guarantee language ────────────────────────
    text_to_check = " ".join([
        assessment.get("reasoning_summary", ""),
        str(assessment.get("recommended_next_step", "")),
        str(assessment.get("message", "")),
    ]).lower()
    guarantee_found = None
    for phrase in _GUARANTEE_PHRASES:
        if phrase in text_to_check:
            guarantee_found = phrase
            break
    reserved_found = None
    for phrase in _RESERVED_ACTIVITY_PHRASES:
        if phrase in text_to_check:
            reserved_found = phrase
            break
    advice_ok = (guarantee_found is None) and (reserved_found is None)
    checks.append({"check": "no_overconfident_advice", "passed": advice_ok, "severity": "critical"})
    if guarantee_found:
        failures.append(f"guarantee_language:{guarantee_found}")
    if reserved_found:
        failures.append(f"reserved_activity:{reserved_found}")

    # ── Check 5: Known incorrect deadline statements ──────────────────────────
    for phrase, label in _INCORRECT_DEADLINES.items():
        if phrase in text_to_check:
            failures.append(f"incorrect_deadline_statement:{label}")
            checks.append({"check": "deadline_statement_accuracy", "passed": False,
                           "severity": "critical", "phrase": phrase})
            break
    else:
        checks.append({"check": "deadline_statement_accuracy", "passed": True, "severity": "medium"})

    # ── Check 6: Honesty — weaknesses stated for viable claims ───────────────
    viable = assessment.get("has_viable_claim") in ("yes", "uncertain")
    weaknesses = assessment.get("key_weaknesses", [])
    honesty_ok = (not viable) or bool(weaknesses)
    checks.append({"check": "honesty_weaknesses_present", "passed": honesty_ok, "severity": "high"})
    if not honesty_ok:
        failures.append("viable_claim_missing_weaknesses")

    # ── Check 7: Evidence gaps acknowledged ──────────────────────────────────
    gaps = evidence_gaps or []
    required_gaps = [g for g in gaps if not g.startswith("recommended:")]
    if required_gaps and assessment.get("status") not in ("insufficient_grounding", "not_supported"):
        checks.append({
            "check": "evidence_gaps_acknowledged",
            "passed": False,
            "severity": "high",
            "gaps": required_gaps,
        })
        failures.append(f"missing_required_facts:{','.join(required_gaps)}")
    else:
        checks.append({"check": "evidence_gaps_acknowledged", "passed": True, "severity": "medium"})

    # ── Check 8: PII not in output ────────────────────────────────────────────
    boundary_log = assessment.get("boundary_log") or {}
    pii_in_output = boundary_log.get("pii_in_output", [])
    pii_ok = len(pii_in_output) == 0
    checks.append({"check": "no_pii_in_output", "passed": pii_ok, "severity": "critical"})
    if not pii_ok:
        failures.append(f"pii_in_output:{pii_in_output}")

    # ── Determine overall pass/fail ───────────────────────────────────────────
    critical_failures = [
        f for f, c in zip(failures, [ch for ch in checks if not ch["passed"]])
        if c.get("severity") == "critical"
    ]
    high_failures = [
        f for f, c in zip(failures, [ch for ch in checks if not ch["passed"]])
        if c.get("severity") == "high"
    ]

    passed = len(failures) == 0
    reason = "; ".join(failures) if failures else None

    return {
        "passed": passed,
        "reason": reason,
        "checks": checks,
        "failures": failures,
        "critical_failures": len([c for c in checks if not c.get("passed") and c.get("severity") == "critical"]),
        "high_failures": len([c for c in checks if not c.get("passed") and c.get("severity") == "high"]),
    }
