"""
Critic Agent — Evolving Intelligence Stack, Component A.

Sits between Agent ART (reasoning/strategy) and Agent SEA (drafting). It cross-
references ART's cited legal authorities against the LOCAL DB corpus (legislation /
case_law / acas_guidance / rules) using the real citation verifier — NOT model memory.

If ART makes a legal assertion with no citation, or cites an authority that does NOT
resolve to a real DB row (hallucination / weak link), the Critic returns a Critique
that forces ART to re-generate. Bounded retries; then it HALTS the chain (fail-closed)
rather than letting an ungrounded strategy reach SEA/drafting.

FAIL-CLOSED: if the Critic cannot verify against the DB (e.g. DB error), it HALTS.
No mock, no bypass, no fabricated citations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import BaseModel

from backend.core.citation_verifier import verify_bundle_citations

logger = logging.getLogger(__name__)

MAX_CRITIC_RETRIES = 2  # bounded ART<->Critic loop, then escalate to human_review

# Critic verdict actions.
ACCEPT = "accept"
REGENERATE = "regenerate"
HALT = "halt"


@dataclass
class Critique:
    passed: bool
    action: str                          # accept | regenerate | halt
    issues: list[dict] = field(default_factory=list)
    verified: int = 0
    total: int = 0
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "passed": self.passed, "action": self.action, "issues": self.issues,
            "verified": self.verified, "total": self.total, "reason": self.reason,
        }


def _extract_authorities(reasoning: dict) -> list[dict]:
    """Pull cited authorities from an ART reasoning payload (several shapes tolerated)."""
    auths = reasoning.get("authorities") or reasoning.get("citations") or []
    out: list[dict] = []
    for a in auths:
        if isinstance(a, dict):
            out.append({"cite": a.get("cite") or a.get("authority_ref") or "",
                        "type": a.get("type") or a.get("source_type"),
                        "url": a.get("url") or a.get("authority_url", "")})
    return out


def _makes_legal_assertion(reasoning: dict) -> bool:
    """A definite legal conclusion (yes/no viable claim, or an asserted strength)."""
    hv = reasoning.get("has_viable_claim")
    return hv in ("yes", "no") or bool(reasoning.get("legal_assertions"))


def critique(reasoning: dict, attempt: int = 0) -> Critique:
    """Critique one ART reasoning output against the local DB. Fail-closed on error."""
    try:
        authorities = _extract_authorities(reasoning)
        asserts = _makes_legal_assertion(reasoning)

        # 1) A definite legal assertion with NO citation is a weak/ungrounded link.
        if asserts and not authorities:
            return Critique(False, REGENERATE if attempt < MAX_CRITIC_RETRIES else HALT,
                            issues=[{"type": "uncited_assertion",
                                     "detail": "Legal conclusion asserted with no cited authority."}],
                            reason="uncited legal assertion")

        if not authorities:
            # No assertion and no authorities — nothing to verify; let grounding gate handle it.
            return Critique(True, ACCEPT, reason="no authorities to verify (deferred to grounding gate)")

        # 2) Every cited authority MUST resolve to a real DB row.
        result = verify_bundle_citations(authorities)
        verified = int(result.get("verified", 0))
        total = int(result.get("total", len(authorities)))
        unresolved = [a for a in result.get("details", [])
                      if isinstance(a, dict) and not a.get("verified", False)]

        if unresolved:
            action = REGENERATE if attempt < MAX_CRITIC_RETRIES else HALT
            return Critique(
                False, action,
                issues=[{"type": "unresolved_citation", "cite": u.get("cite", ""),
                         "detail": "Cited authority does not resolve to a DB row (possible hallucination)."}
                        for u in unresolved],
                verified=verified, total=total,
                reason=f"{len(unresolved)}/{total} citations do not resolve to the local DB",
            )

        return Critique(True, ACCEPT, verified=verified, total=total,
                        reason="all cited authorities resolve to the local DB")
    except Exception as exc:
        # FAIL-CLOSED: cannot verify against the DB => halt the chain.
        logger.error("Critic failed-closed (cannot verify against DB): %s", exc)
        return Critique(False, HALT, issues=[{"type": "verification_error", "detail": str(exc)}],
                        reason="critic could not verify against the local DB — fail-closed halt")


def run_critic_loop(reason_fn: Callable[[Optional[dict]], dict]) -> dict:
    """Drive ART <-> Critic with bounded retries.

    reason_fn(critique_or_none) -> ART reasoning payload. On a REGENERATE verdict the
    critique is fed back so ART can re-generate. Returns:
      {"status": "accepted"|"halted", "reasoning": {...}, "critique": {...}, "attempts": n}
    A HALT means the chain must NOT proceed to SEA/drafting — escalate to human_review.
    """
    last_critique: Optional[Critique] = None
    reasoning: dict = {}
    for attempt in range(MAX_CRITIC_RETRIES + 1):
        reasoning = reason_fn(last_critique.as_dict() if last_critique else None)
        verdict = critique(reasoning, attempt=attempt)
        if verdict.action == ACCEPT:
            return {"status": "accepted", "reasoning": reasoning,
                    "critique": verdict.as_dict(), "attempts": attempt + 1}
        if verdict.action == HALT:
            return {"status": "halted", "reasoning": reasoning,
                    "critique": verdict.as_dict(), "attempts": attempt + 1,
                    "recommended_next_step": "human_review"}
        last_critique = verdict  # REGENERATE: feed critique back to ART
    # Exhausted retries without acceptance => halt, fail-closed.
    return {"status": "halted", "reasoning": reasoning,
            "critique": (last_critique.as_dict() if last_critique else {}),
            "attempts": MAX_CRITIC_RETRIES + 1, "recommended_next_step": "human_review"}


# ── System Update 001 interface (hard gatekeeper between ART and SEA) ────────

class CritiqueResult(BaseModel):
    passed: bool
    reasoning: str
    critique: Optional[str] = None
    suggested_correction: Optional[str] = None


# Alias to match the System Update 001 spec name.
CriticResult = CritiqueResult


class CriticRejectionError(Exception):
    """Raised by the orchestrator when the Critic does not sign off ART's strategy.
    The drafting agent (SEA) must NEVER run after this is raised."""

    def __init__(self, critique: str, suggested_correction: Optional[str] = None):
        self.critique = critique
        self.suggested_correction = suggested_correction
        super().__init__(critique)


def log_agent_validation_failure(trace_id: Optional[str], error: str,
                                 snapshot: Optional[dict] = None,
                                 case_id: Optional[str] = None,
                                 agent_name: str = "ART") -> None:
    """Persist a Critic rejection to agent_validation_failures (DSPy training signal).
    Fails soft: never blocks the request path on a logging error."""
    try:
        import json
        from ingestion.db import get_connection
        excerpt = (json.dumps(snapshot)[:2000] if snapshot else None)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_validation_failures
                        (trace_id, case_id, agent_name, raw_output_excerpt, failure_reason)
                    VALUES (%s::uuid, %s, %s, %s, %s)
                    """,
                    (str(trace_id) if trace_id else None, case_id, agent_name, excerpt, error[:1000]),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("agent_validation_failures log skipped: %s", exc)


class CriticAgent:
    """Hard gatekeeper between Agent ART (reasoning) and Agent SEA (drafting).
    Validates legal logic against the local DB corpus. Fail-closed: if the legal
    link cannot be verified, review() returns passed=False and SEA must not run."""

    def __init__(self, db_interface=None, graph_rag=None):
        self.db = db_interface
        self.graph = graph_rag

    def review(self, proposed_strategy: dict, evidence_context: Optional[dict] = None) -> CritiqueResult:
        """Cross-reference the proposed strategy against verified DB authorities.
        Hallucination / uncited assertion / weak link => passed=False (fail-closed)."""
        verdict = critique(proposed_strategy or {})
        if verdict.passed:
            return CritiqueResult(passed=True, reasoning=verdict.reason)
        issue = (verdict.issues[0] if verdict.issues else {})
        return CritiqueResult(
            passed=False,
            reasoning="The proposed argument lacks a verified link to the cited legislation.",
            critique=verdict.reason or issue.get("detail", "unverified legal link"),
            suggested_correction=(
                "Re-evaluate the cited authorities — each must resolve to a real row in "
                "the local legal DB (legislation/case_law/acas/rules)."
            ),
        )

    def _verify_legal_chain(self, strategy: dict) -> bool:
        """A definite legal conclusion must carry at least one cited authority."""
        return not (_makes_legal_assertion(strategy) and not _extract_authorities(strategy))

    def _check_corpus(self, citations: list) -> bool:
        """Every cited authority must resolve to a real DB row (local GraphRAG corpus)."""
        if not citations:
            return True
        auths = [{"cite": c} if isinstance(c, str) else c for c in citations]
        res = verify_bundle_citations(auths)
        return int(res.get("failed", 1)) == 0
