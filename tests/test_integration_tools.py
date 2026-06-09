"""
Integration — the acquisition funnel + all four tools end-to-end (API level).

Maps the spec's INTEGRATION scenarios onto the REAL endpoints:

  "Anonymous user -> claim checker -> sees preview"
      POST /api/free-tool/teaser  (public)  -> login_required + preview, no full result
  "Anonymous user -> clicks 'Login to save' -> redirects to login"
      POST /api/free-tool/full-result (anon) -> 401 {login_required}  (the UI's gate)
  "Logged in user -> claim checker -> result saves to DB"
      POST /api/free-tool/full-result (auth) -> 200 result
      POST /cases (auth) -> 201, persisted, readable by owner, 403 cross-user
  "All 4 tools work end-to-end"
      claim checker   POST /assess
      deadline        POST /api/deadline/calculate
      compensation    POST /documents/generate (schedule_of_loss)
      acas prep       assess_acas_code() + the deadline EC stop-clock

Auth is 'mock' (conftest): X-User-ID is the identity header. DB is the local
Docker Postgres. ENCRYPTION_KEY is set before import so the teaser state is
genuinely encrypted at rest (the login_gate fails closed without it).
"""

from __future__ import annotations

import os

if not os.getenv("ENCRYPTION_KEY"):
    from backend.core.encryption import generate_key
    os.environ["ENCRYPTION_KEY"] = generate_key()

import uuid

import pytest
from fastapi.testclient import TestClient

_TOOL = "employment_rights_check"
_ANSWERS = {
    "what_happened": "I was dismissed without warning after raising a safety concern.",
    "employment_start": "2021-03-01",
    "dismissal_date": "2026-05-20",
    "employer": "Acme Ltd",
}


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    try:
        app.state.limiter.enabled = False
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=False)


def _uid() -> str:
    return str(uuid.uuid4())


# ── Funnel: anonymous preview -> login gate -> resume after login ─────────────────

class TestAnonymousFunnel:
    def test_anonymous_claim_checker_sees_preview_only(self, client):
        r = client.post("/api/free-tool/teaser", json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["login_required"] is True
        assert body.get("resume_token")
        assert "teaser" in body
        # The preview must NOT contain the full governed result.
        assert "full_result" not in body
        assert "result" not in body

    def test_anonymous_save_is_gated_to_login(self, client):
        # The "Login to save" gate: anonymous full-result -> 401 {login_required}.
        r = client.post("/api/free-tool/full-result", json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 401, r.text
        detail = r.json()["detail"]
        assert detail["login_required"] is True
        assert detail["capability"] == "full_result"

    def test_logged_in_gets_full_result(self, client):
        r = client.post("/api/free-tool/full-result",
                        headers={"X-User-ID": _uid()},
                        json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 200, r.text
        assert "result" in r.json()

    def test_resume_after_login_restores_answers_exactly(self, client):
        # Anonymous answers -> save -> login -> resume with no lost answers.
        token = client.post("/api/free-tool/teaser",
                            json={"tool": _TOOL, "answers": _ANSWERS}).json()["resume_token"]
        r = client.post("/api/free-tool/resume",
                        headers={"X-User-ID": _uid()},
                        json={"resume_token": token})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["resumed"] is True
        assert body["answers"] == _ANSWERS


# ── Logged-in result is persisted to the DB (with ownership) ──────────────────────

class TestResultSavesToDb:
    def _save_case(self, client, user_id):
        return client.post(
            "/cases",
            headers={"X-User-ID": user_id},
            json={
                "claim_type": "unfair_dismissal",
                "jurisdiction": "EW",
                "assessment": {"status": "ok", "claim_type": "unfair_dismissal"},
                "key_dates": {"edt": "2026-05-10", "deadline_date": "2026-08-09"},
                "recommended_next_step": "Consider ACAS early conciliation.",
            },
        )

    def test_logged_in_user_result_persists_and_is_owned(self, client):
        owner = _uid()
        created = self._save_case(client, owner)
        assert created.status_code == 201, created.text
        case_id = created.json().get("case_id") or created.json().get("id")
        assert case_id

        # Owner can read it back -> it really persisted.
        got = client.get(f"/cases/{case_id}", headers={"X-User-ID": owner})
        assert got.status_code == 200, got.text

    def test_cross_user_cannot_read_saved_case(self, client):
        owner, attacker = _uid(), _uid()
        created = self._save_case(client, owner)
        case_id = created.json().get("case_id") or created.json().get("id")
        r = client.get(f"/cases/{case_id}", headers={"X-User-ID": attacker})
        assert r.status_code in (403, 404), r.text  # never 200 for a non-owner


# ── All four tools reachable end-to-end ──────────────────────────────────────────

class TestAllFourToolsEndToEnd:
    def test_claim_checker(self, client):
        r = client.post("/assess",
                        json={"query": "unfair dismissal time limit", "facts": {}, "use_model": False})
        assert r.status_code == 200, r.text
        assert r.json()["status"] in ("ok", "not_supported")

    def test_deadline(self, client):
        r = client.post("/api/deadline/calculate",
                        json={"claim_type": "unfair_dismissal", "edt": "2026-05-10"})
        assert r.status_code == 200, r.text
        assert r.json()["limitation_date"]

    def test_compensation(self, client):
        r = client.post("/documents/generate",
                        json={"document_type": "schedule_of_loss",
                              "assessment": {"status": "ok", "claim_type": "unfair_dismissal",
                                             "citations": []},
                              "facts": {"edt": "2026-05-10", "weekly_pay": 700}})
        assert r.status_code == 200, r.text
        assert r.json()["document_type"] == "schedule_of_loss"

    def test_acas_prep(self, client):
        from backend.domains.employment.checklists.acas import assess_acas_code
        out = assess_acas_code("instant dismissal with no appeal")
        assert out["aligned_with_code"] in ("likely", "unclear", "unlikely")
        # and the ACAS EC stop-clock is reachable via the deadline endpoint
        ec = client.post("/api/deadline/calculate",
                         json={"claim_type": "unfair_dismissal", "edt": "2026-05-10",
                               "acas_start": "2026-06-01", "acas_end": "2026-06-20"})
        assert ec.json()["ec_applied"] is True
