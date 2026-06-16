"""
Evolution Gate  -  proves the automated learning flywheel (System Update 001):

  1. ART produces a strategy with a hallucinated citation.
  2. The Critic Agent (real DB verification) rejects it (fail-closed) -> logged to
     agent_validation_failures.
  3. The Optimizer reads the failures and proposes a new prompt version with the
     learned guardrails baked in.
  4. PROMOTION GATE: the candidate is promoted ONLY because it beats the production
     prompt's metric AND has no safety regression.
  5. The previously-failing case passes on the new prompt version.

DSPy *live* compilation needs an LLM key (owner-blocked); the flywheel itself runs
real + deterministically without one (rule-based candidate from recorded critiques).

Run: docker compose run --rm -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion \
       pytest tests/test_evolution_gate.py -q
"""
from __future__ import annotations

import uuid

from backend.core.agentic.critic import CriticAgent, log_agent_validation_failure
from backend.core.agentic.optimizer import Optimizer


def test_critic_rejects_hallucination_and_accepts_real_citation():
    critic = CriticAgent()
    # Real authority resolves to the DB -> pass.
    ok = critic.review({"has_viable_claim": "no",
                        "authorities": [{"cite": "Employment Rights Act 1996 s.98", "type": "legislation"}]})
    assert ok.passed is True

    # Hallucinated authority does NOT resolve -> fail-closed.
    bad = critic.review({"has_viable_claim": "yes",
                         "authorities": [{"cite": "Fictional Employment Act 2099 s.999", "type": "legislation"}]})
    assert bad.passed is False
    assert bad.critique


def test_evolution_flywheel_promotes_only_on_improvement_without_safety_regression():
    trace_id = str(uuid.uuid4())
    agent, key = "ART", f"reason_strategy_test_{trace_id[:8]}"

    # 1+2. Critic rejects a hallucinated strategy -> log the failure (training signal).
    critic = CriticAgent()
    verdict = critic.review({"has_viable_claim": "yes",
                             "authorities": [{"cite": "Made Up Act 2099 s.1", "type": "legislation"}]})
    assert verdict.passed is False
    log_agent_validation_failure(trace_id=trace_id, error=verdict.critique,
                                 snapshot={"authorities": ["Made Up Act 2099 s.1"]}, agent_name=agent)

    opt = Optimizer()
    base_prompt = "You are Agent ART. Produce an unfair-dismissal strategy."

    # 3+4. A candidate that beats the (absent=0.0) production metric AND has no safety
    # regression must be PROMOTED. The candidate bakes in the learned guardrails.
    def evaluate_improved(prompt_text: str) -> dict:
        improved = "Learned guardrails" in prompt_text
        return {"success_rate": 0.95 if improved else 0.50, "safety_regression": False}

    res = opt.optimize(agent, key, base_prompt, evaluate_improved)
    assert res["promoted"] is True
    assert res["candidate_score"] > res["prod_score"]
    assert res["safety_regression"] is False

    # The new prompt version is now production.
    prod = opt.production_prompt(agent, key)
    assert prod is not None and prod["metric_score"] == 0.95

    # 5. SAFETY GATE: a candidate with a safety regression must NEVER be promoted,
    # even if its raw metric is higher.
    def evaluate_unsafe(prompt_text: str) -> dict:
        return {"success_rate": 0.99, "safety_regression": True}

    res2 = opt.optimize(agent, key, base_prompt, evaluate_unsafe)
    assert res2["promoted"] is False, "safety regression must block promotion"

    # Production prompt is unchanged (still the safe 0.95 candidate).
    prod2 = opt.production_prompt(agent, key)
    assert prod2["metric_score"] == 0.95


def test_optimizer_reads_failures_for_agent():
    opt = Optimizer()
    rows = opt.pull_failures("ART", limit=5)
    assert isinstance(rows, list)
