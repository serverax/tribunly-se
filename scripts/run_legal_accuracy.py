#!/usr/bin/env python3
"""
Legal accuracy regression gate.

Runs deterministic legal-accuracy checks directly against the backend
pipeline, without relying on pytest or test files in the runtime image.

Default (CI / beta gate): StubReasoningModel — fast, deterministic, does NOT
prove live Ollama or CitationGuard on generative output.

With --live: LocalInferenceReasoningModel against LAWAPP_OLLAMA_BASE_URL.
Fails closed if Ollama is unreachable (writes OLLAMA_NOT_REACHABLE artifact).

Expected to exit non-zero if:
  - a grounded unfair-dismissal case does not return a full assessment
  - citations are missing
  - deadline computation is not sourced from the rules table
  - an out-of-scope query is not refused
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fail(msg: str) -> int:
    print(f"FAIL: LEGAL ACCURACY GATE FAILED — {msg}")
    return 1


def _ollama_reachable() -> bool:
    import httpx

    base = os.environ.get("LAWAPP_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        r = httpx.get(f"{base}/api/tags", timeout=5.0)
        r.raise_for_status()
        return True
    except Exception:
        return False


def _write_ollama_unreachable_artifact() -> None:
    reports = Path(__file__).resolve().parent.parent / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "legal_accuracy_live.txt"
    path.write_text(
        "OLLAMA_NOT_REACHABLE\n"
        f"LAWAPP_OLLAMA_BASE_URL={os.environ.get('LAWAPP_OLLAMA_BASE_URL', '')}\n"
        "Live legal-accuracy profile cannot run without local Ollama.\n"
        "Stub suite (default) remains valid for CI speed — not generative proof.\n",
        encoding="utf-8",
    )
    print(f"Wrote {path}")


def _run_checks(model, *, live: bool) -> int:
    from backend.core.pipeline import assess

    print("=" * 70)
    print("LAWAPP — LEGAL ACCURACY REGRESSION SUITE")
    print("=" * 70)
    mode = "live Ollama" if live else "StubReasoningModel (deterministic)"
    print(f"Model profile: {mode}")
    print()

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
    deadline_info = grounded.get("deadline_info") or {}
    print("Grounded case:")
    print(f"  status:              {grounded.get('status')}")
    print(f"  claim_type:          {grounded.get('claim_type')}")
    print(f"  citations:           {len(grounded.get('citations') or [])}")
    print(f"  grounding_score:     {grounded.get('grounding_score')}")
    print(f"  confidence_score:    {grounded.get('confidence_score')}")
    print(f"  deadline_info:       {json.dumps(deadline_info, ensure_ascii=True)}")
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

    label = "LIVE LEGAL ACCURACY GATE PASSED" if live else "LEGAL ACCURACY GATE PASSED"
    print(f"PASS: {label}")
    print("=" * 70)
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="LawApp legal accuracy gate")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use local Ollama (LocalInferenceReasoningModel); fail-closed if unreachable",
    )
    args = parser.parse_args()

    if args.live:
        if not _ollama_reachable():
            _write_ollama_unreachable_artifact()
            return _fail("OLLAMA_NOT_REACHABLE — live profile requires local Ollama")
        from backend.core.models import LocalInferenceReasoningModel

        model = LocalInferenceReasoningModel()
        rc = _run_checks(model, live=True)
        if rc == 0:
            out = Path(__file__).resolve().parent.parent / "reports" / "legal_accuracy_live.txt"
            out.write_text("PASS: live legal accuracy gate (LocalInferenceReasoningModel)\n", encoding="utf-8")
        return rc

    from backend.core.models import StubReasoningModel

    print("Running deterministic fact-pattern checks (StubReasoningModel)...")
    print("NOTE: stub PASS does not prove live Ollama/CitationGuard — use --live for that.")
    print()
    return _run_checks(StubReasoningModel(), live=False)


if __name__ == "__main__":
    raise SystemExit(main())
