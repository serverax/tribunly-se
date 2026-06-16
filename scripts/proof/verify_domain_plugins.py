#!/usr/bin/env python3
"""Write reports/domain_plugin_verify_cursor.txt from domain pytest suite."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "domain_plugin_verify_cursor.txt"

TESTS = [
    "tests/test_domain_modularity.py",
    "tests/test_domain_plugin_system.py",
    "tests/test_domain_pack_loader.py",
]


def main() -> int:
    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"Generated: {ts}")
    lines.append("Task: F - domain plugin verification (employment_uk only enabled)")
    lines.append("")

    cmd = [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    lines.append(" ".join(cmd))
    lines.append(proc.stdout.strip() or "(no stdout)")
    if proc.stderr.strip():
        lines.append(proc.stderr.strip())
    lines.append("")
    lines.append("Invariant checks:")
    lines.append("- Unknown/disabled domains fail closed")
    lines.append("- Domain switching routes through brain/control plane, not bypass")
    lines.append("- Only employment pack enabled for beta")
    lines.append("")
    lines.append(f"exit_code: {proc.returncode}")
    lines.append("PASS" if proc.returncode == 0 else "FAIL")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
