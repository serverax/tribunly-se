"""Build language-neutral assessment core from pipeline / mother output."""

from __future__ import annotations

from typing import Any


_NEUTRAL_KEYS = (
    "status",
    "claim_type",
    "jurisdiction",
    "has_viable_claim",
    "strength",
    "recommended_next_step",
    "insufficient_grounding",
    "trace_id",
    "lane",
    "intent",
    "result_type",
)


def build_assessment_core(result: dict[str, Any]) -> dict[str, Any]:
    """
    Extract language-neutral assessment core from a governed pipeline result.

    Prose fields are kept as canonical English machine output; locale engines
    render native phrasing from these codes and structured fields.
    """
    core: dict[str, Any] = {
        "schema_version": "multi_native_v1",
        "language_neutral": True,
    }

    for key in _NEUTRAL_KEYS:
        if key in result and result[key] is not None:
            core[key] = result[key]

    for key in (
        "reasoning_summary",
        "key_weaknesses",
        "employer_arguments",
        "citations",
        "deadline",
        "deadline_info",
        "value_range",
        "qualifying_check",
        "governance_result",
        "message",
    ):
        if key in result:
            core[key] = result[key]

    if "assessment" in result and isinstance(result["assessment"], dict):
        nested = result["assessment"]
        for k, v in nested.items():
            if k not in core or core.get(k) in (None, "", []):
                core[k] = v

    return core
