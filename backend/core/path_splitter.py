"""Path-Splitter — deterministic vs generative routing (ADR: Deterministic vs.
Generative Routing).

Splits an incoming query into two lanes:
  - FACTUAL  -> FAST_DETERMINISTIC: served from the rules table / deterministic
    engine only. NO LLM is invoked. Target latency < 400ms.
  - REASONING -> STREAMING_GENERATIVE: requires synthesis/assessment; routed to the
    LocalInferenceReasoningModel and streamed (SSE). The 400ms gate does not apply.

SAFETY DEFAULT: when intent is ambiguous, default to REASONING. We never answer a
question that needs reasoning with a terse deterministic lookup, and the reasoning
lane keeps the grounding + Critic gates. The fast lane is only taken when the query
is unambiguously a factual rule/DB lookup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

FACTUAL = "FACTUAL"
REASONING = "REASONING"

FAST_DETERMINISTIC = "FAST_DETERMINISTIC"
STREAMING_GENERATIVE = "STREAMING_GENERATIVE"

# Unambiguous factual-lookup phrasings (answerable from the rules table).
_FACTUAL_PATTERNS = [
    re.compile(r"\bwhat is the (time limit|deadline|cap|maximum|qualifying period)", re.I),
    re.compile(r"\bhow (long|much) (is|do i have|can i claim)", re.I),
    re.compile(r"\b(time limit|limitation period|compensatory cap|basic award|qualifying period)\b", re.I),
    re.compile(r"\bcurrent (cap|limit|maximum) (for|on)\b", re.I),
]

# Phrasings that require synthesis/assessment — always REASONING.
_REASONING_PATTERNS = [
    re.compile(r"\b(do i have|have i got) (a|any) (claim|case)\b", re.I),
    re.compile(r"\b(was|were) (i|we) (unfairly|wrongfully|constructively) dismissed\b", re.I),
    re.compile(r"\b(should i|can i|is it worth|advise|advice|assess|evaluate|review my)\b", re.I),
    re.compile(r"\b(my (situation|case|employer)|what are my (options|chances))\b", re.I),
]


@dataclass
class PathDecision:
    intent: str          # FACTUAL | REASONING
    lane: str            # FAST_DETERMINISTIC | STREAMING_GENERATIVE
    reason: str
    invokes_llm: bool    # explicit: does this lane call the generative model?


def _has_narrative(facts: Optional[dict]) -> bool:
    """A fact pattern (dates, parties, events) implies an assessment, not a lookup."""
    if not facts:
        return False
    narrative_keys = {"edt", "dismissal_date", "service_start_date", "reason_for_dismissal",
                      "was_procedure_followed", "events", "narrative"}
    return any(k in facts for k in narrative_keys)


def classify_intent(query: str, facts: Optional[dict] = None) -> str:
    """Return FACTUAL or REASONING. Ambiguous => REASONING (safe default)."""
    q = query or ""
    # Reasoning markers and narrative fact patterns dominate.
    if _has_narrative(facts):
        return REASONING
    if any(p.search(q) for p in _REASONING_PATTERNS):
        return REASONING
    # Only an unambiguous factual lookup with no reasoning markers takes the fast lane.
    if any(p.search(q) for p in _FACTUAL_PATTERNS):
        return FACTUAL
    return REASONING


def route(query: str, facts: Optional[dict] = None) -> PathDecision:
    """The path-splitter entry point used by the orchestrator/endpoint."""
    intent = classify_intent(query, facts)
    if intent == FACTUAL:
        return PathDecision(
            intent=FACTUAL, lane=FAST_DETERMINISTIC,
            reason="factual rule/DB lookup — deterministic engine, <400ms target, no LLM",
            invokes_llm=False,
        )
    return PathDecision(
        intent=REASONING, lane=STREAMING_GENERATIVE,
        reason="requires synthesis/assessment — generative lane, SSE stream, 400ms gate N/A",
        invokes_llm=True,
    )


def sse_frames(token_iter):
    """Wrap an iterator of text deltas as Server-Sent Events (text/event-stream).
    Mount on a FastAPI route with:
        StreamingResponse(sse_frames(model.stream_chat(messages)),
                          media_type='text/event-stream')
    """
    for tok in token_iter:
        # Escape newlines so a single SSE 'data:' line carries the delta intact.
        safe = str(tok).replace("\n", "\\n")
        yield f"data: {safe}\n\n"
    yield "data: [DONE]\n\n"
