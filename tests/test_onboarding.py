"""
Onboarding wizard (SUBAGENT: Onboarding Engineer) — backend contract tests.

Proves the POST /onboarding/complete + GET /onboarding/status endpoints:
  * role is REQUIRED and validated (missing → 422, invalid/empty → 400)
  * auth is required (no identity → 401)
  * a first case is auto-created with status='new', created_from='onboarding'
  * case_title is auto-generated (from case type, else name, else fallback)
  * the operation is IDEMPOTENT — a second call returns the SAME case (no dup)
  * the onboarding case appears in GET /cases (dashboard list) with its title
  * GET /onboarding/status flips onboarded False → True

Runs against the local Docker DB (conftest sets POSTGRES_* + LAWAPP_AUTH_MODE=mock,
so X-User-ID carries identity). Each test uses a fresh UUID and cleans up after.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)


def _conn():
    from ingestion.db import get_connection
    return get_connection()


def _db_available() -> bool:
    try:
        c = _conn(); c.close(); return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


@pytest.fixture()
def user_id():
    """A fresh user UUID; deletes the user (cascading its cases) afterwards."""
    uid = str(uuid.uuid4())
    yield uid
    conn = _conn()
    try:
        with conn.cursor() as cur:
            # cases.user_id FK is ON DELETE CASCADE — removing the user clears cases.
            cur.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))
        conn.commit()
    finally:
        conn.close()


def _onboarding_cases(uid: str):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, case_title, claim_type, status, created_from
                  FROM cases
                 WHERE user_id = %s::uuid AND deleted_at IS NULL
                """,
                (uid,),
            )
            return cur.fetchall()
    finally:
        conn.close()


# ── Role required / validated ─────────────────────────────────────────────────

def test_missing_role_is_422(user_id):
    """role is a required body field → FastAPI validation rejects its absence."""
    r = client.post("/onboarding/complete", json={}, headers={"X-User-ID": user_id})
    assert r.status_code == 422
    assert _onboarding_cases(user_id) == []   # nothing created


def test_empty_role_is_400(user_id):
    r = client.post("/onboarding/complete", json={"role": "   "},
                    headers={"X-User-ID": user_id})
    assert r.status_code == 400
    assert "role" in r.json()["detail"].lower()
    assert _onboarding_cases(user_id) == []


def test_unknown_role_is_400(user_id):
    r = client.post("/onboarding/complete", json={"role": "ceo_of_everything"},
                    headers={"X-User-ID": user_id})
    assert r.status_code == 400
    assert _onboarding_cases(user_id) == []


# ── Auth required ─────────────────────────────────────────────────────────────

def test_auth_required_401():
    """No X-User-ID under mock auth → no identity → 401, no case created."""
    r = client.post("/onboarding/complete", json={"role": "employee"})
    assert r.status_code == 401


# ── First case auto-created ───────────────────────────────────────────────────

def test_creates_first_case(user_id):
    r = client.post(
        "/onboarding/complete",
        json={"role": "employee", "full_name": "Alex Taylor",
              "employer_name": "Acme Retail Ltd", "case_type": "unfair_dismissal"},
        headers={"X-User-ID": user_id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] is True
    assert body["status"] == "new"
    assert body["created_from"] == "onboarding"
    assert body["case_title"] == "Unfair dismissal claim"
    assert body["claim_type"] == "unfair_dismissal"
    assert body["redirect"] == "/pages/dashboard.html"
    assert body["suggested_tool"]["url"] == "/pages/intake.html"

    # Verify the row actually persisted with the right provenance + status.
    rows = _onboarding_cases(user_id)
    assert len(rows) == 1
    _id, title, claim_type, status, created_from = rows[0]
    assert status == "new"
    assert created_from == "onboarding"
    assert title == "Unfair dismissal claim"


def test_case_title_from_name_when_no_case_type(user_id):
    """No case_type (e.g. a solicitor) → title falls back to '{name}'s claim'."""
    r = client.post(
        "/onboarding/complete",
        json={"role": "solicitor", "full_name": "Jordan Lee"},
        headers={"X-User-ID": user_id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["case_title"] == "Jordan Lee's claim"
    # claim_type defaults to the system's primary supported claim (not fabricated).
    assert r.json()["claim_type"] == "unfair_dismissal"


def test_case_title_neutral_fallback(user_id):
    """No name and no case_type → neutral, non-empty fallback title."""
    r = client.post("/onboarding/complete", json={"role": "other"},
                    headers={"X-User-ID": user_id})
    assert r.status_code == 201, r.text
    assert r.json()["case_title"] == "My employment claim"


# ── Idempotency (no duplicate case) ───────────────────────────────────────────

def test_idempotent_second_call_returns_same_case(user_id):
    first = client.post("/onboarding/complete", json={"role": "employee"},
                        headers={"X-User-ID": user_id})
    assert first.status_code == 201
    first_id = first.json()["case_id"]
    assert first.json()["created"] is True

    second = client.post("/onboarding/complete",
                         json={"role": "employee", "case_type": "redundancy"},
                         headers={"X-User-ID": user_id})
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["case_id"] == first_id

    # Exactly ONE onboarding case exists — no duplicate.
    rows = _onboarding_cases(user_id)
    assert len(rows) == 1


def test_idempotent_resubmit_does_not_wipe_name(user_id):
    """A sparse double-submit (no full_name) must NOT clear the stored name."""
    client.post("/onboarding/complete",
                json={"role": "employee", "full_name": "Alex Taylor"},
                headers={"X-User-ID": user_id})
    # Second call omits full_name entirely.
    client.post("/onboarding/complete",
                json={"role": "employee", "case_type": "redundancy"},
                headers={"X-User-ID": user_id})

    status = client.get("/onboarding/status", headers={"X-User-ID": user_id})
    assert status.json()["full_name"] == "Alex Taylor"   # preserved, not nulled


# ── Dashboard list shows the case ─────────────────────────────────────────────

def test_onboarding_case_appears_in_cases_list(user_id):
    client.post("/onboarding/complete",
                json={"role": "former_employee", "full_name": "Sam Rivers",
                      "case_type": "discrimination"},
                headers={"X-User-ID": user_id})

    lst = client.get("/cases", headers={"X-User-ID": user_id})
    assert lst.status_code == 200
    cases = lst.json()["cases"]
    assert len(cases) == 1
    c = cases[0]
    assert c["case_title"] == "Discrimination claim"
    assert c["created_from"] == "onboarding"
    assert c["status"] == "new"


# ── Status endpoint ───────────────────────────────────────────────────────────

def test_status_flips_after_completion(user_id):
    before = client.get("/onboarding/status", headers={"X-User-ID": user_id})
    assert before.status_code == 200
    assert before.json()["onboarded"] is False

    client.post("/onboarding/complete",
                json={"role": "hr", "full_name": "Pat Doe"},
                headers={"X-User-ID": user_id})

    after = client.get("/onboarding/status", headers={"X-User-ID": user_id})
    assert after.status_code == 200
    assert after.json()["onboarded"] is True
    assert after.json()["role"] == "hr"
    assert after.json()["full_name"] == "Pat Doe"


def test_status_requires_auth():
    r = client.get("/onboarding/status")
    assert r.status_code == 401
