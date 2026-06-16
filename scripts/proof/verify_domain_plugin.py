#!/usr/bin/env python3
"""Domain plugin verification report."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "domain_plugin_verify_cursor.txt"


def run_pytest() -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_domain_plugin_system.py",
        "tests/test_domain_pack_loader.py",
        "-q",
        "--tb=no",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def runtime_probe() -> tuple[str, str]:
    try:
        out = subprocess.run(
            [
                sys.executable,
                "-c",
                "from backend.domains.registry import enabled_domains, require_domain; "
                "from backend.domains.registry import DomainDisabledError, UnsupportedDomainError; "
                "print('enabled', enabled_domains()); "
                "require_domain('employment'); print('employment PASS'); "
                "try: require_domain('housing'); print('housing UNEXPECTED'); "
                "except DomainDisabledError: print('housing DomainDisabledError'); "
                "try: require_domain('employment_uk'); print('employment_uk UNEXPECTED'); "
                "except Exception as e: print('employment_uk', type(e).__name__)",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (out.stdout or "") + (out.stderr or "")
        ok = out.returncode == 0 and "DomainDisabledError" in text
        return ("PASS" if ok else "FAIL"), text.strip()
    except Exception as exc:
        return "FAIL", str(exc)


def main() -> int:
    code, pytest_out = run_pytest()
    rt_status, rt_out = runtime_probe()
    packs = list((ROOT / "domains").glob("*/domain_config.json"))
    emp = ROOT / "domains/employment/domain_config.json"
    any_fail = code != 0 or rt_status == "FAIL" or not emp.is_file()
    lines = [
        "LawApp domain plugin verification",
        "Generated: 2026-06-16 (evidence run)",
        "Branch: release/lawapp-clean-snapshot",
        "",
        "| Check | Result | Evidence |",
        "|-------|--------|----------|",
        (f"| Domain packs on disk | {'PASS' if packs else 'FAIL'} | {len(packs)} packs |"),
        (f"| employment pack | {'PASS' if emp.is_file() else 'FAIL'} | domains/employment/domain_config.json |"),
        (f"| Runtime fail-closed probe | {rt_status} | see below |"),
        (f"| Pytest domain suite | {'PASS' if code == 0 else 'FAIL'} | exit {code} |"),
        "",
        "## Runtime probe",
        "```",
        rt_out,
        "```",
        "",
        "## Pytest",
        "```",
        pytest_out.strip()[-1500:] if pytest_out else "",
        "```",
        "",
        f"## Verdict: {'FAIL' if any_fail else 'PASS'}",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
