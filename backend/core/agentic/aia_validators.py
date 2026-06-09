"""
The 4 AIA governance validators that gate every provider (OpenRouter) output in
Workflow C. The provider sits BETWEEN the core algorithm and these validators;
if ANY validator fails, the result is rejected and the system fails closed.

  AIA 1 — Citation/Retrieval: every cited authority must already be in the RAG bundle.
  AIA 2 — Rules/Deterministic: deadlines/caps/thresholds must equal the rules table.
  AIA 3 — PII Boundary: no PII may appear in the outbound payload (or be reintroduced).
  AIA 4 — Legal Boundary/Honesty: no reserved/guarantee wording; weaknesses required.
"""

from __future__ import annotations

import re
from typing import Any

_RESERVED = [
    "guaranteed win", "guarantee you will win", "you will win", "we will file",
    "we will represent you", "we represent you", "we act for you",
    "rights of audience", "conduct litigation for you", "as your solicitor",
    "we are a law firm", "this is legal advice",
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def validate_citations(cited: list[str], rag_bundle_citations: list[str]) -> tuple[bool, list[str]]:
    """AIA 1: every cited authority must resolve to something in the retrieved bundle."""
    allowed = [_norm(c) for c in rag_bundle_citations]
    failures = []
    for c in cited or []:
        nc = _norm(c)
        if not any(nc in a or a in nc for a in allowed if a):
            failures.append(c)
    return (len(failures) == 0, failures)


def validate_rules(claimed: dict, rules_values: dict) -> tuple[bool, list[str]]:
    """AIA 2: any deterministic value the model asserts must equal the rules table.
    ``claimed`` and ``rules_values`` map e.g. {'time_limit_months': 3, ...}."""
    failures = []
    for key, val in (claimed or {}).items():
        if key in (rules_values or {}):
            if str(rules_values[key]) != str(val):
                failures.append(f"{key}: model={val} != rules={rules_values[key]}")
    return (len(failures) == 0, failures)


def validate_pii_boundary(payload: Any) -> tuple[bool, list[str]]:
    """AIA 3: no residual PII may be present in the (outbound or returned) payload."""
    from backend.core.agentic.pii import residual_pii
    leak = residual_pii(payload)
    return (leak is None, [] if leak is None else [f"residual_pii:{leak}"])


def validate_legal_boundary(text: str, *, non_trivial: bool = True,
                            has_weaknesses: bool = True) -> tuple[bool, list[str]]:
    """AIA 4: block reserved-activity / guarantee wording; require weaknesses for a
    non-trivial case."""
    failures = []
    low = (text or "").lower()
    for phrase in _RESERVED:
        if phrase in low:
            failures.append(f"reserved_wording:{phrase}")
    if non_trivial and not has_weaknesses:
        failures.append("missing_weaknesses_for_non_trivial_case")
    return (len(failures) == 0, failures)


def run_all_validators(
    *,
    cited: list[str],
    rag_bundle_citations: list[str],
    claimed_rule_values: dict,
    rules_values: dict,
    outbound_payload: Any,
    answer_text: str,
    non_trivial: bool = True,
    has_weaknesses: bool = True,
) -> tuple[bool, dict]:
    """Run all 4 AIA validators. Returns (all_passed, {validator: failures})."""
    c_ok, c_f = validate_citations(cited, rag_bundle_citations)
    r_ok, r_f = validate_rules(claimed_rule_values, rules_values)
    p_ok, p_f = validate_pii_boundary(outbound_payload)
    b_ok, b_f = validate_legal_boundary(answer_text, non_trivial=non_trivial,
                                        has_weaknesses=has_weaknesses)
    report = {
        "citation": c_f, "rules": r_f, "pii": p_f, "legal_boundary": b_f,
    }
    return (c_ok and r_ok and p_ok and b_ok, report)
