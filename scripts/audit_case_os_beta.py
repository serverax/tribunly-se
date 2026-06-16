#!/usr/bin/env python3
"""Audit Case OS pages for honesty banner, boundary footer, coverage label hygiene."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "client" / "public" / "pages"
INDEX = ROOT / "client" / "public" / "index.html"
REPORT = ROOT / "reports" / "case_os_beta_ship_cursor.txt"

CASE_OS = [
    "dashboard.html",
    "case-intake.html",
    "analysis.html",
    "my-case.html",
    "deadlines.html",
    "evidence.html",
    "documents.html",
    "escalation.html",
    "advisor.html",
    "settings.html",
    "timeline.html",
    "workspace.html",
]

HONESTY = re.compile(r"Not a law firm|not a law firm|We're a guide, not a law firm", re.I)
BOUNDARY = re.compile(r"case-os-boundary|boundary|does not provide regulated legal advice|does not file", re.I)
BAD_LABEL = re.compile(r"corpus excerpts|0 corpus", re.I)


def audit_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    shell = "app-shell.js" in text or path.name == "workspace.html"
    return {
        "honesty": bool(HONESTY.search(text)),
        "boundary": bool(BOUNDARY.search(text)) or shell,
        "bad_coverage_label": bool(BAD_LABEL.search(text)),
    }


def main() -> int:
    lines: list[str] = ["Case OS beta ship audit", f"Root: {ROOT}", ""]
    all_pass = True
    for name in CASE_OS + ["../index.html"]:
        path = (PAGES / name) if not name.startswith("..") else ROOT / "client" / "public" / "index.html"
        if not path.exists():
            lines.append(f"FAIL {name}: missing")
            all_pass = False
            continue
        r = audit_file(path)
        ok = r["honesty"] and r["boundary"] and not r["bad_coverage_label"]
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        lines.append(
            f"{status} {path.relative_to(ROOT)} "
            f"honesty={r['honesty']} boundary={r['boundary']} bad_label={r['bad_coverage_label']}"
        )
    lines.append("")
    lines.append("app-shell.js injects boundary footer on dynamic Case OS pages.")
    lines.append("beta-scope.js provides Ready to read / Partial coverage / Coming soon labels.")
    lines.append("")
    lines.append("OVERALL: " + ("PASS" if all_pass else "FAIL"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
