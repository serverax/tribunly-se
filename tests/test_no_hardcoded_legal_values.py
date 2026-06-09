"""No legal numeric value (caps/awards) is hardcoded in app code (order §6, §22.22).

Reads the distinctive cap amounts from the rules table at runtime, then scans the
application source (backend + client/WASM) for those exact integer literals. They
must come from the DB, never be baked into code. Generic values (qualifying period,
3-month limit) are excluded to avoid false positives; the distinctive 4+ digit cap
amounts are the meaningful test.
"""
from __future__ import annotations

import os
import re

import pytest


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_up():
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="UNPROVEN — DB not accessible")

# App dirs that must NOT hardcode legal values. Excludes ingestion/ (the
# authoritative seed loader), tests/, migrations/, and fixtures.
_SCAN_DIRS = ["backend/core", "backend/api", "backend/domains", "client"]
_SKIP = ("/tests/", "/test_", "fixture", "/migrations/", "/ingestion/")


def _distinctive_cap_values() -> list[str]:
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT value_numeric FROM rules
                           WHERE rule_key IN (
                             'unfair_dismissal.compensatory_cap_amount',
                             'unfair_dismissal.weeks_pay_cap_amount')
                             AND value_numeric IS NOT NULL AND is_current = true""")
            out = []
            for (v,) in cur.fetchall():
                iv = int(round(float(v)))
                if iv >= 1000:            # only distinctive amounts (avoids false positives)
                    out.append(str(iv))
            return out
    finally:
        conn.close()


def test_distinctive_cap_values_not_hardcoded_in_app_code():
    values = _distinctive_cap_values()
    if not values:
        pytest.skip("no distinctive current cap amounts in rules to check")

    root = "/app"  # repo root inside the ingestion container
    patterns = {v: re.compile(rf"(?<!\d){re.escape(v)}(?!\d)") for v in values}
    offenders = []
    for sub in _SCAN_DIRS:
        base = os.path.join(root, sub)
        for dirpath, _dirs, files in os.walk(base):
            if any(s in (dirpath + "/").replace("\\", "/") for s in _SKIP):
                continue
            for fn in files:
                if not fn.endswith((".py", ".js", ".ts", ".rs", ".html", ".txt", ".md")):
                    continue
                path = os.path.join(dirpath, fn)
                if any(s in path.replace("\\", "/") for s in _SKIP):
                    continue
                try:
                    text = open(path, "r", encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                for v, pat in patterns.items():
                    if pat.search(text):
                        offenders.append(f"{path}: hardcoded legal value {v}")
    assert not offenders, "hardcoded legal values found:\n" + "\n".join(offenders)
