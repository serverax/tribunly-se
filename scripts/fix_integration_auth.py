"""One-off helper: add mock auth headers to integration case saves."""
from __future__ import annotations

from pathlib import Path

FILES = [
    "test_phase4b_bundle.py",
    "test_phase4c_timeline.py",
    "test_phase5b_unpaid_wages.py",
    "test_phase6a_deployment.py",
    "test_phase6b_beta_readiness.py",
]

IMPORT = "from tests.integration.auth_helpers import TEST_USER_ID, mock_auth_headers\n"
AUTH_DEF = "_LEGACY_AUTH = mock_auth_headers(TEST_USER_ID)\n"
OLD_AUTH = '_LEGACY_AUTH = {"X-User-ID": "00000000-0000-0000-0000-00000000000a"}\n'

root = Path(__file__).resolve().parents[1] / "tests" / "integration"
for name in FILES:
    path = root / name
    text = path.read_text(encoding="utf-8")
    if OLD_AUTH not in text:
        print("skip", name)
        continue
    text = text.replace(OLD_AUTH, AUTH_DEF)
    if IMPORT.strip() not in text:
        anchor = "from backend.api.main import app\n"
        if anchor in text:
            text = text.replace(anchor, anchor + "\n" + IMPORT, 1)
    for old in (
        'client.post("/cases", json=',
        'save_resp = client.post("/cases", json=',
        'case_resp = client.post("/cases", json=',
    ):
        new = old.replace('json=', 'headers=_LEGACY_AUTH, json=')
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("updated", name)
