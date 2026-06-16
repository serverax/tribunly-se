"""
DSPy Optimizer  -  Evolving Intelligence Stack, Component B (DETACHED CI ONLY).

NEVER runs in the request path (would add latency + unpredictability). It is invoked
by the CI job `dsp_optimize_prompts`. The flywheel:

  agent_validation_failures + feedback_registry  (training signals)
        -> propose a candidate prompt version
        -> evaluate (success rate on the signals/agent tests)
        -> PROMOTION GATE: candidate must beat the current production prompt's metric
           AND introduce ZERO safety/AIA regression
        -> write to prompt_versions (is_production=true only if promoted)

Prompts are versioned DATA in `prompt_versions`  -  agents load the production prompt
from the DB at startup; production prompts are never hand-edited.

OWNER-BLOCKED: real DSPy *compilation* calls an LLM. Without a model/OpenRouter key,
`dspy_available()` is False and the optimizer runs the deterministic, rule-based
candidate path (a real candidate derived from the recorded critiques)  -  it does NOT
fabricate a "compiled" prompt or a fake metric.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def dspy_available() -> bool:
    """True only if DSPy is installed AND a real LLM provider key is configured.
    Otherwise live compilation is OWNER-BLOCKED."""
    # LOCAL OLLAMA ONLY (hard mandate): DSPy live compilation drives an external LLM
    # (OpenRouter/Anthropic) and is forbidden. Always False -> the optimizer falls back
    # to the deterministic rule-based path. No external key may enable it.
    return False


@dataclass
class Candidate:
    agent_name: str
    prompt_key: str
    prompt_text: str
    source: str               # "dspy_compiled" | "rule_based_from_failures"


class Optimizer:
    """Detached prompt optimizer. Build with a DB connection factory."""

    def __init__(self, get_conn: Optional[Callable] = None):
        if get_conn is None:
            from ingestion.db import get_connection as _gc
            get_conn = _gc
        self._get_conn = get_conn

    # ── training signals ────────────────────────────────────────────────────
    def pull_failures(self, agent_name: str, limit: int = 200) -> list[dict]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT failure_reason, raw_output_excerpt FROM agent_validation_failures "
                    "WHERE agent_name = %s ORDER BY created_at DESC LIMIT %s",
                    (agent_name, limit),
                )
                return [{"failure_reason": r[0], "excerpt": r[1]} for r in cur.fetchall()]
        finally:
            conn.close()

    def pull_outcomes(self, claim_type: Optional[str] = None, limit: int = 500) -> list[dict]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if claim_type:
                    cur.execute(
                        "SELECT outcome_label, law_refs, grounding_score FROM feedback_registry "
                        "WHERE claim_type = %s ORDER BY created_at DESC LIMIT %s",
                        (claim_type, limit),
                    )
                else:
                    cur.execute(
                        "SELECT outcome_label, law_refs, grounding_score FROM feedback_registry "
                        "ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                return [{"outcome": r[0], "law_refs": r[1], "grounding": r[2]} for r in cur.fetchall()]
        finally:
            conn.close()

    # ── prompt versions ─────────────────────────────────────────────────────
    def production_prompt(self, agent_name: str, prompt_key: str) -> Optional[dict]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT version, prompt_text, metric_score FROM prompt_versions "
                    "WHERE agent_name=%s AND prompt_key=%s AND is_production=true "
                    "ORDER BY version DESC LIMIT 1",
                    (agent_name, prompt_key),
                )
                r = cur.fetchone()
                return {"version": r[0], "prompt_text": r[1], "metric_score": float(r[2]) if r[2] is not None else 0.0} if r else None
        finally:
            conn.close()

    def _next_version(self, agent_name: str, prompt_key: str) -> int:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(version),0)+1 FROM prompt_versions WHERE agent_name=%s AND prompt_key=%s",
                    (agent_name, prompt_key),
                )
                return int(cur.fetchone()[0])
        finally:
            conn.close()

    # ── candidate generation ────────────────────────────────────────────────
    def propose(self, agent_name: str, prompt_key: str, base_prompt: str) -> Candidate:
        """Propose a candidate. With DSPy+LLM => compiled (owner path). Otherwise a real
        rule-based candidate that bakes the most common recorded critiques into the
        prompt as explicit guardrails (no fabricated 'compilation')."""
        failures = self.pull_failures(agent_name)
        critiques = [f["failure_reason"] for f in failures if f.get("failure_reason")]
        if dspy_available():
            text = self._dspy_compile(base_prompt, critiques)
            return Candidate(agent_name, prompt_key, text, "dspy_compiled")
        distinct = sorted(set(critiques))[:8]
        guard = "\n".join(f"- MUST NOT: {c}" for c in distinct)
        text = base_prompt + (
            "\n\n# Learned guardrails (from recorded Critic rejections):\n" + guard if guard else ""
        )
        return Candidate(agent_name, prompt_key, text, "rule_based_from_failures")

    def _dspy_compile(self, base_prompt: str, critiques: list[str]) -> str:  # pragma: no cover (owner key)
        import dspy  # noqa: F401
        raise NotImplementedError("DSPy live compilation requires a configured LLM provider key")

    # ── promotion gate ──────────────────────────────────────────────────────
    def optimize(self, agent_name: str, prompt_key: str, base_prompt: str,
                 evaluate: Callable[[str], dict]) -> dict:
        """Run one optimization cycle. `evaluate(prompt_text)` must return
        {'success_rate': float, 'safety_regression': bool}. Promote ONLY if the
        candidate beats production AND has no safety regression."""
        prod = self.production_prompt(agent_name, prompt_key)
        prod_score = prod["metric_score"] if prod else 0.0
        cand = self.propose(agent_name, prompt_key, base_prompt)
        ev = evaluate(cand.prompt_text)
        cand_score = float(ev.get("success_rate", 0.0))
        safety_regression = bool(ev.get("safety_regression", True))
        promote = (cand_score > prod_score) and (not safety_regression)

        version = self._next_version(agent_name, prompt_key)
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                if promote:
                    cur.execute(
                        "UPDATE prompt_versions SET is_production=false WHERE agent_name=%s AND prompt_key=%s",
                        (agent_name, prompt_key),
                    )
                cur.execute(
                    """
                    INSERT INTO prompt_versions
                        (agent_name, prompt_key, version, prompt_text, metric_name, metric_score,
                         is_production, safety_regression, created_by)
                    VALUES (%s,%s,%s,%s,'success_rate',%s,%s,%s,%s)
                    """,
                    (agent_name, prompt_key, version, cand.prompt_text, cand_score,
                     promote, safety_regression, "dspy_optimizer"),
                )
            conn.commit()
        finally:
            conn.close()

        return {
            "agent_name": agent_name, "prompt_key": prompt_key, "version": version,
            "candidate_source": cand.source,
            "prod_score": prod_score, "candidate_score": cand_score,
            "safety_regression": safety_regression, "promoted": promote,
            "dspy_live": dspy_available(),
        }


if __name__ == "__main__":  # pragma: no cover  -  detached CI entrypoint
    import json
    opt = Optimizer()
    print(json.dumps({"dspy_available": dspy_available()}))
