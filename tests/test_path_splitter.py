"""Path-Splitter proof (ADR: Deterministic vs Generative Routing).

Core guarantees:
  - an unambiguous factual lookup takes the FAST_DETERMINISTIC lane and NEVER
    invokes the LLM,
  - an assessment/reasoning query takes the STREAMING_GENERATIVE lane,
  - a narrative fact pattern forces REASONING,
  - ambiguous input defaults to REASONING (safe default).
"""
from __future__ import annotations

from backend.core.path_splitter import (
    FACTUAL, REASONING, FAST_DETERMINISTIC, STREAMING_GENERATIVE,
    classify_intent, route,
)


def test_factual_lookup_takes_fast_lane_no_llm():
    d = route("What is the time limit for unfair dismissal?")
    assert d.intent == FACTUAL
    assert d.lane == FAST_DETERMINISTIC
    assert d.invokes_llm is False


def test_compensatory_cap_question_is_factual():
    assert classify_intent("What is the current compensatory cap for unfair dismissal?") == FACTUAL


def test_assessment_question_takes_generative_lane():
    d = route("Do I have a claim for unfair dismissal?")
    assert d.intent == REASONING
    assert d.lane == STREAMING_GENERATIVE
    assert d.invokes_llm is True


def test_narrative_fact_pattern_forces_reasoning():
    # Even a short query becomes REASONING when a fact pattern is attached.
    d = route("time limit", facts={"edt": "2024-05-01", "reason_for_dismissal": "conduct"})
    assert d.intent == REASONING
    assert d.invokes_llm is True


def test_ambiguous_defaults_to_reasoning():
    assert classify_intent("my employer and the dismissal") == REASONING
    assert classify_intent("") == REASONING


def test_fast_lane_never_marks_llm():
    # Property: any FAST_DETERMINISTIC decision must have invokes_llm == False.
    for q in ["what is the qualifying period",
              "how long do i have to claim",
              "the limitation period"]:
        d = route(q)
        if d.lane == FAST_DETERMINISTIC:
            assert d.invokes_llm is False
