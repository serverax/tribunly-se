#!/usr/bin/env python3
"""Grounding verification report from pytest + static brain-path checks."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "grounding_verification_cursor.txt"


def run_pytest() -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_grounding_regression.py",
        "tests/test_legal_truth_validator.py",
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def static_checks() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    brain = (ROOT / "backend/core/brain.py").read_text(encoding="utf-8")
    rows.append(("Brain CitationGuard step", "PASS" if "verify_citations" in brain else "FAIL", "brain.py"))
    pipe = (ROOT / "backend/core/pipeline.py").read_text(encoding="utf-8")
    rows.append(
        (
            "Pipeline corpus_citation_guard",
            "PASS" if "corpus_citation_guard" in pipe or "enforce_or_regenerate" in pipe else "FAIL",
            "pipeline.py",
        )
    )
    main = (ROOT / "backend/api/main.py").read_text(encoding="utf-8")
    rows.append(
        (
            "No /api/v1/legal/reason",
            "PASS" if "/api/v1/legal/reason" not in main else "FAIL",
            "main.py",
        )
    )
    return rows


def main() -> int:
    code, out = run_pytest()
    static = static_checks()
    any_fail = code != 0 or any(r[1] == "FAIL" for r in static)
    lines = [
        "LawApp grounding verification (assess/brain path)",
        "Generated: 2026-06-16 (evidence run)",
        "Branch: release/lawapp-clean-snapshot",
        "",
        "## Static checks",
        "",
        "| Check | Result | Evidence |",
        "|-------|--------|----------|",
    ]
    for name, status, ev in static:
        lines.append(f"| {name} | {status} | {ev} |")
    lines.extend(
        [
            "",
            "## Pytest",
            "",
            f"Exit code: {code}",
            "```",
            out.strip()[-2000:] if out else "(no output)",
            "```",
            "",
            f"## Verdict: {'FAIL' if any_fail else 'PASS'}",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
