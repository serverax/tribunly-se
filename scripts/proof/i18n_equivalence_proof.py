#!/usr/bin/env python3
"""Prove assessment_core is identical for en vs ar on same input."""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.core.control_plane.mother_controller import MotherController, MotherInput

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "i18n_equivalence_proof.txt"


def main() -> int:
    payload = {
        "query": "What is the time limit for unfair dismissal?",
        "facts": {"claim_type": "unfair_dismissal", "edt": "2026-01-15", "employment_length": 24},
        "jurisdiction": "EW",
        "use_model": False,
    }
    en = MotherController().process(MotherInput(**payload, locale="en", trace_id="equiv-proof-001")).to_dict()
    ar = MotherController().process(MotherInput(**payload, locale="ar", trace_id="equiv-proof-001")).to_dict()

    def _core_for_compare(body: dict) -> dict:
        core = dict(body.get("assessment_core") or {})
        for key in ("trace_id",):
            core.pop(key, None)
        return core
    def _json_default(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(type(obj))

    core_en = json.dumps(_core_for_compare(en), sort_keys=True, indent=2, default=_json_default)
    core_ar = json.dumps(_core_for_compare(ar), sort_keys=True, indent=2, default=_json_default)
    diff = list(
        difflib.unified_diff(
            core_en.splitlines(),
            core_ar.splitlines(),
            fromfile="en",
            tofile="ar",
            lineterm="",
        )
    )
    identical = core_en == core_ar
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "i18n assessment_core equivalence proof",
        f"Generated: {ts}",
        "Branch: release/lawapp-clean-snapshot",
        "",
        "Input: same query+facts, locale=en vs locale=ar, use_model=False",
        f"assessment_core identical: {identical}",
        f"locale en={en.get('locale')} ar={ar.get('locale')}",
        f"rendered differs (expected): {en.get('reasoning_summary') != ar.get('reasoning_summary')}",
        "",
    ]
    if diff:
        lines.append("DIFF (must be empty for PASS):")
        lines.extend(diff[:80])
    else:
        lines.append("DIFF: (empty)")
    lines.append("")
    lines.append("VERDICT: " + ("PASS" if identical else "FAIL"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
