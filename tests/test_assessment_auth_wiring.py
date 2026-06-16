"""P0-005 — assessment.html mutating routes use fetchWithAuth."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSESSMENT = ROOT / "client" / "public" / "pages" / "assessment.html"


def test_assessment_mutations_use_fetch_with_auth():
    text = ASSESSMENT.read_text(encoding="utf-8")
    # Protected POST paths must not use raw fetch( — only fetchWithAuth
    protected = [
        r"fetch\([^)]*['\"`](/cases|/api/payments/create-session|/api/documents/generate|/handoff/leads)",
        r"fetch\([^)]*['\"`]\\$\{API_BASE\}/(cases|api/payments/create-session|api/documents/generate|handoff/leads)",
    ]
    for pattern in protected:
        assert not re.search(pattern, text), (
            f"assessment.html still uses raw fetch for protected route: {pattern}"
        )
    assert text.count("fetchWithAuth") >= 5, "expected multiple fetchWithAuth call sites"


def test_assessment_save_case_wired():
    text = ASSESSMENT.read_text(encoding="utf-8")
    assert "fetchWithAuth(`${API_BASE}/cases`" in text.replace("\n", " ").replace("  ", " ")
