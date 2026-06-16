"""
Legal Truth Validator  -  DB-first cross-check after CitationGuard.

Input: LLM structured output + retrieval bundle + rules query results.
Cross-checks citations against corpus_chunks, rules, legislation, knowledge.provision.

GUARDRAIL: Mismatch -> reject or flag insufficient_grounding. Never rewrite DB.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


@dataclass
class LegalTruthVerdict:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "failures": self.failures, "checks": self.checks}


@dataclass
class LegalTruthValidationResult:
    passed: bool
    status: str  # ok | insufficient_grounding | rejected
    mismatches: list[dict] = field(default_factory=list)
    verified_count: int = 0
    failed_count: int = 0
    gaps_detected: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "status": self.status,
            "mismatches": self.mismatches,
            "verified_count": self.verified_count,
            "failed_count": self.failed_count,
            "gaps_detected": self.gaps_detected,
            "detail": self.detail,
        }


def _bundle_rules(bundle: Any) -> list[dict]:
    if bundle is None:
        return []
    if isinstance(bundle, dict):
        return list(bundle.get("exact_rules") or [])
    return list(getattr(bundle, "exact_rules", None) or [])


def _rule_keys_in_bundle(rules: list[dict], bundle: Any) -> set[str]:
    keys: set[str] = set()
    for row in rules:
        if row.get("rule_key"):
            keys.add(str(row["rule_key"]))
    for row in _bundle_rules(bundle):
        if row.get("rule_key"):
            keys.add(str(row["rule_key"]))
    return keys


def _verify_corpus_chunk_id(chunk_id: str) -> bool:
    try:
        uuid.UUID(str(chunk_id))
    except (ValueError, TypeError):
        return False
    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM corpus_chunks WHERE id = %s::uuid LIMIT 1",
                    (str(chunk_id),),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("corpus_chunks lookup failed: %s", exc)
        return False


def _verify_provision_authority(authority_ref: str) -> bool:
    try:
        from ingestion.db import get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM knowledge.provision
                     WHERE authority_ref ILIKE %s
                     LIMIT 1
                    """,
                    (authority_ref.strip(),),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("knowledge.provision lookup skipped: %s", exc)
        return False


def validate_legal_truth(
    assessment: dict,
    bundle: Any = None,
    rules: Optional[list[dict]] = None,
    *,
    trace_id: Optional[str] = None,
) -> LegalTruthValidationResult:
    """Cross-check LLM output against DB-grounded retrieval and rules."""
    rules = list(rules or [])
    mismatches: list[dict] = []
    verified = 0
    failed = 0
    gaps: list[str] = []

    if assessment.get("status") in ("not_supported", "blocked", "error"):
        return LegalTruthValidationResult(
            passed=False,
            status="rejected",
            detail={"reason": f"assessment_status:{assessment.get('status')}"},
        )

    if assessment.get("insufficient_grounding"):
        return LegalTruthValidationResult(
            passed=False,
            status="insufficient_grounding",
            gaps_detected=["insufficient_grounding_flag"],
            detail={"reason": "pipeline_flagged_insufficient_grounding"},
        )

    from backend.core.citation_verifier import verify_citation

    allowed_rule_keys = _rule_keys_in_bundle(rules, bundle)
    citations = [
        c for c in (assessment.get("citations") or []) if isinstance(c, dict)
    ]

    if not citations and assessment.get("status") == "ok":
        mismatches.append({"kind": "missing_citations", "detail": "ok with zero citations"})
        failed += 1
        gaps.append("missing_citations")

    for cite_row in citations:
        cite = (cite_row.get("cite") or cite_row.get("authority_ref") or "").strip()
        if not cite:
            mismatches.append({"kind": "empty_citation", "detail": cite_row})
            failed += 1
            continue

        source_type = cite_row.get("type") or cite_row.get("source_type")
        result = verify_citation(cite, source_type=source_type)
        if result.get("verified"):
            verified += 1
            continue

        chunk_id = cite_row.get("chunk_id") or cite_row.get("corpus_chunk_id")
        if chunk_id and _verify_corpus_chunk_id(str(chunk_id)):
            verified += 1
            continue
        if _verify_provision_authority(cite):
            verified += 1
            continue

        failed += 1
        mismatches.append({
            "kind": "citation_db_mismatch",
            "cite": cite,
            "reason": result.get("reason"),
            "method": result.get("method"),
        })

    for chunk_id in _UUID_RE.findall(str(assessment.get("reasoning_summary", ""))):
        if not _verify_corpus_chunk_id(chunk_id):
            failed += 1
            mismatches.append({"kind": "corpus_uuid_mismatch", "chunk_id": chunk_id})

    for rule_key in assessment.get("rules_used") or []:
        rk = str(rule_key)
        if rk not in allowed_rule_keys:
            failed += 1
            mismatches.append({"kind": "rule_not_in_retrieval", "rule_key": rk})
            gaps.append(f"missing_rule:{rk}")

    bundle_grounded = True
    if bundle is not None:
        if isinstance(bundle, dict):
            bundle_grounded = not bundle.get("insufficient_grounding", True)
        else:
            bundle_grounded = not getattr(bundle, "insufficient_grounding", True)

    if failed > 0:
        status = "rejected" if failed == len(citations) and citations else "insufficient_grounding"
        if not citations:
            gaps.append("missing_rule")
        return LegalTruthValidationResult(
            passed=False,
            status=status,
            mismatches=mismatches,
            verified_count=verified,
            failed_count=failed,
            gaps_detected=list(dict.fromkeys(gaps)),
            detail={"trace_id": trace_id, "bundle_grounded": bundle_grounded},
        )

    if not bundle_grounded and assessment.get("status") == "ok":
        return LegalTruthValidationResult(
            passed=False,
            status="insufficient_grounding",
            gaps_detected=["retrieval_insufficient_grounding"],
            detail={"trace_id": trace_id, "bundle_grounded": False},
        )

    return LegalTruthValidationResult(
        passed=True,
        status="ok",
        verified_count=verified,
        detail={"trace_id": trace_id, "bundle_grounded": bundle_grounded},
    )


def apply_validation_to_assessment(
    assessment: dict,
    result: LegalTruthValidationResult,
) -> dict:
    """Fail-closed assessment mutation when legal truth validation fails."""
    if result.passed:
        assessment["legal_truth_status"] = "ok"
        return assessment

    assessment["legal_truth_status"] = result.status
    assessment["legal_truth_mismatches"] = result.mismatches
    if result.status == "rejected":
        assessment["status"] = "blocked"
        assessment["message"] = (
            "This response was blocked because cited legal sources could not be "
            "verified against the law database."
        )
    else:
        assessment["status"] = "insufficient_grounding"
        assessment["insufficient_grounding"] = True
        assessment.setdefault(
            "message",
            "Not enough verified legal sources in the database to support this answer.",
        )
    return assessment


def validate_assessment_truth(assessment: dict, *, trace_id: Optional[str] = None) -> LegalTruthVerdict:
    """Legacy wrapper: governance + safety + citation bundle checks."""
    failures: list[str] = []
    checks: list[dict] = []

    gov = assessment.get("governance_result") or {}
    gov_pass = gov.get("passes") is True
    checks.append({"check": "governance_passes", "passed": gov_pass})
    if not gov_pass:
        failures.append(gov.get("failure_reason") or "governance_failed")

    cites = assessment.get("citations") or []
    if cites and isinstance(cites[0], dict):
        try:
            from backend.core.citation_verifier import verify_bundle_citations

            v = verify_bundle_citations(cites)
            cite_ok = v.get("failed", 1) == 0
            checks.append({
                "check": "citation_db_integrity",
                "passed": cite_ok,
                "verified": v.get("verified"),
                "total": v.get("total"),
            })
            if not cite_ok:
                failures.append("citation_verification_failed")
        except Exception as exc:
            checks.append({"check": "citation_db_integrity", "passed": False, "error": str(exc)})
            failures.append("citation_verification_unavailable")

    lt = validate_legal_truth(assessment, trace_id=trace_id)
    checks.append({"check": "legal_truth_validator", "passed": lt.passed, "status": lt.status})
    if not lt.passed:
        failures.extend(lt.gaps_detected or [lt.status])

    return LegalTruthVerdict(passed=len(failures) == 0, failures=failures, checks=checks)


def validate_proposal_payload(payload: dict) -> LegalTruthVerdict:
    """Validate an ingestion proposal before queue insert."""
    failures: list[str] = []
    checks: list[dict] = []

    if payload.get("proposed_action") in ("direct_rule_write", "direct_legislation_write"):
        checks.append({"check": "no_direct_law_write", "passed": False})
        failures.append("direct_law_write_forbidden")
        return LegalTruthVerdict(passed=False, failures=failures, checks=checks)

    has_gap = bool(payload.get("gaps") or payload.get("rule_key") or payload.get("authority_ref"))
    checks.append({"check": "proposal_has_gap_metadata", "passed": has_gap})
    if not has_gap:
        failures.append("missing_gap_metadata")

    return LegalTruthVerdict(passed=len(failures) == 0, failures=failures, checks=checks)
