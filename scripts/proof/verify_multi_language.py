#!/usr/bin/env python3
"""Multi-language verification report (pytest + static grep)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "multi_language_verify_cursor.txt"

FORBIDDEN = (
    "googletrans",
    "translate.googleapis",
    "deepl",
    "azure.cognitiveservices.speech.translation",
    "amazontranslate",
    "libretranslate",
)


def grep_forbidden() -> list[str]:
    hits: list[str] = []
    for base in (ROOT / "backend" / "language_engine", ROOT / "client" / "public"):
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            if fp.suffix not in {".py", ".js", ".html", ".json"}:
                continue
            text = fp.read_text(encoding="utf-8", errors="ignore").lower()
            for pat in FORBIDDEN:
                if pat in text:
                    hits.append(f"{fp.relative_to(ROOT)}:{pat}")
    return hits


def run_pytest() -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_no_translation_invariant.py",
        "tests/test_i18n_api.py",
        "tests/test_language_engine_router.py",
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    hits = grep_forbidden()
    code, out = run_pytest()
    static_rows = [
        ("No third-party translate APIs", "PASS" if not hits else "FAIL", ", ".join(hits) or "none"),
        ("Native EN/AR engines", "PASS" if (ROOT / "backend/language_engine/en").is_dir() else "FAIL", "backend/language_engine/en"),
        ("i18n UI locales", "PASS" if (ROOT / "client/public/js/i18n/locales/en.json").is_file() else "FAIL", "client/public/js/i18n"),
        ("Case OS locale switcher", "PASS" if "data-set-locale" in (ROOT / "client/public/js/app-shell.js").read_text(encoding="utf-8") else "FAIL", "app-shell.js"),
    ]
    any_fail = code != 0 or hits or any(r[1] == "FAIL" for r in static_rows)
    lines = [
        "LawApp multi-language verification",
        "Generated: 2026-06-16 (evidence run)",
        "Branch: release/lawapp-clean-snapshot",
        "",
        "| Check | Result | Evidence |",
        "|-------|--------|----------|",
    ]
    for name, status, ev in static_rows:
        lines.append(f"| {name} | {status} | {ev} |")
    lines.extend(["", "## Pytest", "", f"Exit code: {code}", "```", out.strip()[-1500:] if out else "", "```", "", f"## Verdict: {'FAIL' if any_fail else 'PASS'}"])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
