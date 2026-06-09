#!/usr/bin/env python3
"""
Legal accuracy regression gate.

Runs deterministic legal-accuracy checks directly against the backend
pipeline, without relying on pytest or test files in the runtime image.

Expected to exit non-zero if:
  - a grounded unfair-dismissal case does not return a full assessment
  - citations are missing
  - deadline computation is not sourced from the rules table
  - an out-of-scope query is not refused
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fail(msg: str) -> int:
    print(f"FAIL: LEGAL ACCURACY GATE FAILED — {msg}")
    return 1


def main() -> int:
    from backend.core.pipeline import assess
    from backend.core.models import StubReasoningModel

    print("=" * 70)
    print("LAWAPP — LEGAL ACCURACY REGRESSION SUITE")
    print("=" * 70)
    print("Running deterministic fact-pattern checks (StubReasoningModel)...")
    print()

    model = StubReasoningModel()

    grounded = assess(
        "I was dismissed after 14 months with no procedure",
        {
            "edt": "2026-03-15",
            "service_start_date": "2025-01-01",
            "reason_for_dismissal": "conduct",
            "was_procedure_followed": False,
            "weekly_pay": 450,
            "jurisdiction": "EW",
        },
        model=model,
    )
    print("Grounded case:")
    print(f"  status:              {grounded.get('status')}")
    print(f"  claim_type:          {grounded.get('claim_type')}")
    print(f"  citations:           {len(grounded.get('citations') or [])}")
    print(f"  grounding_score:     {grounded.get('grounding_score')}")
    print(f"  confidence_score:    {grounded.get('confidence_score')}")
    print(f"  deadline_info:       {grounded.get('deadline_info')}")
    print(f"  recommended_next:    {grounded.get('recommended_next_step')}")
    print()

    if grounded.get("status") != "ok":
        return _fail(f"expected grounded assessment to be ok, got {grounded.get('status')}")
    if grounded.get("claim_type") != "unfair_dismissal":
        return _fail(f"expected claim_type unfair_dismissal, got {grounded.get('claim_type')}")
    if not grounded.get("citations"):
        return _fail("grounded assessment returned no citations")
    if float(grounded.get("grounding_score") or 0) <= 0:
        return _fail("grounding_score was not positive")

    deadline_info = grounded.get("deadline_info") or {}
    if deadline_info.get("source") != "rules":
        return _fail(f"deadline source was not rules: {deadline_info}")
    if not deadline_info.get("authority"):
        return _fail("deadline authority missing")

    refusal = assess(
        "I want to sue my landlord for deposit",
        {},
        model=model,
    )
    print("Refusal case:")
    print(f"  status:              {refusal.get('status')}")
    print(f"  matter_type:         {refusal.get('matter_type')}")
    print(f"  message:             {refusal.get('message')}")
    print()

    if refusal.get("status") != "not_supported":
        return _fail(f"expected not_supported refusal, got {refusal.get('status')}")

    print("PASS: LEGAL ACCURACY GATE PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
