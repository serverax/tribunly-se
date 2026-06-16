#!/usr/bin/env python3
"""Case OS beta ship audit - page-by-page PASS/FAIL evidence."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "client" / "public" / "pages"
REPORT = ROOT / "reports" / "case_os_beta_ship_cursor.txt"

CASE_OS_PAGES = [
    "dashboard",
    "case-intake",
    "analysis",
    "workspace",
    "timeline",
    "deadlines",
    "evidence",
    "documents",
    "escalation",
    "advisor",
    "settings",
]

FORBIDDEN_USER = [
    re.compile(r"0 corpus", re.I),
    re.compile(r"corpus excerpt", re.I),
    re.compile(r"partial coverage", re.I),
    re.compile(r">production<", re.I),
    re.compile(r">partial<", re.I),
]


def audit_page(name: str) -> tuple[str, list[str]]:
    path = PAGES / f"{name}.html"
    if not path.is_file():
        return "FAIL", [f"missing file {path}"]
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    if "legal-notice" not in text and "beta-banner" not in text:
        issues.append("missing honesty banner (legal-notice or beta-banner)")
    has_boundary = "case-os-boundary" in text or "app-shell.js" in text
    if not has_boundary:
        issues.append("missing boundary footer or app-shell injection")
    if name in ("case-intake", "analysis", "workspace"):
        if "claim_type" not in text and "CaseEngine" not in text and "case-engine" not in text:
            issues.append("no claim_type routing hook")
    for pat in FORBIDDEN_USER:
        if pat.search(text):
            issues.append(f"forbidden user-facing text: {pat.pattern}")
    return ("PASS" if not issues else "FAIL"), issues


def audit_index() -> tuple[str, list[str]]:
    path = ROOT / "client" / "public" / "index.html"
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    if "legal-notice" not in text:
        issues.append("missing legal-notice")
    if not re.search(r"controlled beta|11 employment", text, re.I):
        issues.append("missing controlled beta scope copy")
    for pat in FORBIDDEN_USER:
        if pat.search(text):
            issues.append(f"forbidden: {pat.pattern}")
    return ("PASS" if not issues else "FAIL"), issues


def grep_forbidden() -> list[str]:
    hits: list[str] = []
    base = ROOT / "client" / "public"
    for fp in base.rglob("*"):
        if fp.suffix not in {".html", ".js", ".css"}:
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        if "0 corpus" in text.lower():
            hits.append(f"{fp.relative_to(ROOT)}: 0 corpus")
        if re.search(r">production<", text, re.I):
            rel = fp.relative_to(ROOT)
            if "beta-scope.js" not in str(rel) and "case-os.css" not in str(rel):
                hits.append(f"{rel}: >production<")
    return hits


def main() -> int:
    lines: list[str] = [
        "LawApp Case OS beta ship audit",
        "Generated: 2026-06-16 (evidence run)",
        f"Branch: release/lawapp-clean-snapshot",
        "",
        "## Page-by-page",
        "",
        "| Page | Result | Notes |",
        "|------|--------|-------|",
    ]
    any_fail = False
    for name in CASE_OS_PAGES:
        status, issues = audit_page(name)
        if status == "FAIL":
            any_fail = True
        note = "; ".join(issues) if issues else "ok"
        lines.append(f"| {name} | {status} | {note} |")
    idx_status, idx_issues = audit_index()
    if idx_status == "FAIL":
        any_fail = True
    lines.append(f"| index.html | {idx_status} | {'; '.join(idx_issues) or 'ok'} |")
    lines.append("")
    grep_hits = grep_forbidden()
    lines.append("## Forbidden string grep (client/public)")
    if grep_hits:
        any_fail = True
        for h in grep_hits:
            lines.append(f"- FAIL: {h}")
    else:
        lines.append("- PASS: zero hits for 0 corpus / >production< (excluding internal mappers)")
    lines.append("")
    lines.append(f"## Verdict: {'FAIL' if any_fail else 'PASS'}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
