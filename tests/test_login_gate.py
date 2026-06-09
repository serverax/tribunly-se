"""
Login-gate tests — free-tool login wall.

Proves the free-tool funnel's authentication gate:

  PUBLIC (anonymous) MAY:    browse, view teaser, preview the tool.
  PUBLIC (anonymous) MAY NOT: generate the full result, upload documents,
                              save a case, access the timeline, use redaction,
                              save citations.

  FLOW: user starts tool → answers teaser questions → login required →
        after login, resume EXACTLY where the user stopped.

Hard requirements proven here:
  - anonymous is blocked from the full result (and every gated capability),
  - the temporary teaser state is ENCRYPTED at rest (Fernet), keyed off a
    high-entropy resume token whose raw value is never stored,
  - resume-after-login restores the saved answers EXACTLY (no lost answers),
  - a claimed state binds to the claiming user (no cross-user theft).

Auth mode is 'mock' (conftest): X-User-ID is the identity header.
DB is the local Docker Postgres (conftest). ENCRYPTION_KEY is set below so the
temporary state is genuinely encrypted (fail-closed if absent).
"""

import os

# Encryption MUST be configured before the app/module import so save_teaser_state
# encrypts (it fails closed when ENCRYPTION_KEY is absent). A throwaway Fernet key
# is fine for tests — it never touches production data.
if not os.getenv("ENCRYPTION_KEY"):
    from backend.core.encryption import generate_key
    os.environ["ENCRYPTION_KEY"] = generate_key()

import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


def _uid() -> str:
    return str(uuid.uuid4())


# Representative free-tool answers used across the suite.
_TOOL = "employment_rights_check"
_ANSWERS = {
    "what_happened": "I was dismissed without warning after raising a safety concern.",
    "employment_start": "2021-03-01",
    "dismissal_date": "2026-05-20",
    "employer": "Acme Ltd",
    "raised_grievance": "no",
}


# ── Core gate: capability registry ────────────────────────────────────────────

class TestGateRegistry:
    def test_gated_capabilities_cover_the_brief(self):
        from backend.core import login_gate as g
        # Every capability the brief forbids to the public must be gated.
        for cap in ("full_result", "upload_document", "save_case",
                    "timeline", "redaction", "save_citations"):
            assert g.is_gated(cap), f"{cap} must be gated"

    def test_public_capabilities_are_not_gated(self):
        from backend.core import login_gate as g
        for cap in ("browse", "teaser", "preview"):
            assert not g.is_gated(cap), f"{cap} must be public"


# ── Core gate: enforcement ────────────────────────────────────────────────────

class TestRequireCapability:
    def test_anonymous_blocked_from_every_gated_capability(self):
        from fastapi import HTTPException
        from backend.core import login_gate as g
        for cap in sorted(g.GATED_CAPABILITIES):
            with pytest.raises(HTTPException) as exc:
                g.require_capability(None, cap)
            assert exc.value.status_code == 401
            detail = exc.value.detail
            assert isinstance(detail, dict)
            assert detail.get("login_required") is True
            assert detail.get("capability") == cap

    def test_authenticated_allowed_through_gate(self):
        from backend.core import login_gate as g
        # Returns None (no raise) for an authenticated user.
        assert g.require_capability(_uid(), "full_result") is None

    def test_public_capability_open_to_anonymous(self):
        from backend.core import login_gate as g
        assert g.require_capability(None, "teaser") is None


# ── Encrypted temporary state ─────────────────────────────────────────────────

class TestEncryptedTeaserState:
    def test_state_round_trips_through_encryption(self):
        from backend.core import login_gate as g
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        assert token and len(token) > 20  # high-entropy opaque token
        loaded = g.load_teaser_state(token)
        assert loaded is not None
        assert loaded["tool"] == _TOOL
        assert loaded["answers"] == _ANSWERS  # nothing lost

    def test_state_is_encrypted_at_rest(self):
        """The stored bytes must NOT contain the plaintext answer text."""
        from backend.core import login_gate as g
        from ingestion.db import get_connection
        secret_phrase = "safety concern"
        assert secret_phrase in _ANSWERS["what_happened"]

        token = g.save_teaser_state(_TOOL, _ANSWERS)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state_encrypted, encryption_version FROM teaser_sessions "
                    "WHERE resume_token_hash = %s",
                    (g.hash_resume_token(token),),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        raw = bytes(row[0])
        assert row[1] == "fernet_v1"
        assert secret_phrase.encode() not in raw, "plaintext leaked into DB at rest"
        assert b"Acme Ltd" not in raw, "plaintext employer leaked into DB at rest"

    def test_raw_resume_token_is_not_stored(self):
        from backend.core import login_gate as g
        from ingestion.db import get_connection
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT resume_token_hash FROM teaser_sessions WHERE resume_token_hash = %s",
                    (g.hash_resume_token(token),),
                )
                row = cur.fetchone()
                # The raw token must never be persisted — only its hash.
                cur.execute(
                    "SELECT count(*) FROM teaser_sessions WHERE resume_token_hash = %s",
                    (token,),
                )
                raw_hits = cur.fetchone()[0]
        finally:
            conn.close()
        assert row is not None
        assert raw_hits == 0

    def test_load_unknown_token_returns_none(self):
        from backend.core import login_gate as g
        assert g.load_teaser_state("definitely-not-a-real-token") is None

    def test_save_then_update_same_token_preserves_answers(self):
        from backend.core import login_gate as g
        token = g.save_teaser_state(_TOOL, {"step1": "a"})
        token2 = g.save_teaser_state(_TOOL, {"step1": "a", "step2": "b"}, resume_token=token)
        assert token2 == token
        loaded = g.load_teaser_state(token)
        assert loaded["answers"] == {"step1": "a", "step2": "b"}


# ── Claim (resume) binds to user ──────────────────────────────────────────────

class TestClaimTeaserState:
    def test_claim_returns_answers_and_marks_owner(self):
        from backend.core import login_gate as g
        user = _uid()
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        claimed = g.claim_teaser_state(token, user)
        assert claimed["answers"] == _ANSWERS
        loaded = g.load_teaser_state(token)
        assert str(loaded["claimed_by_user_id"]) == user

    def test_claim_unknown_token_raises_404(self):
        from fastapi import HTTPException
        from backend.core import login_gate as g
        with pytest.raises(HTTPException) as exc:
            g.claim_teaser_state("no-such-token", _uid())
        assert exc.value.status_code == 404

    def test_claim_by_second_user_is_rejected(self):
        from fastapi import HTTPException
        from backend.core import login_gate as g
        user_a, user_b = _uid(), _uid()
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        g.claim_teaser_state(token, user_a)
        with pytest.raises(HTTPException) as exc:
            g.claim_teaser_state(token, user_b)
        assert exc.value.status_code == 403

    def test_reclaim_by_same_user_is_idempotent(self):
        from backend.core import login_gate as g
        user = _uid()
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        g.claim_teaser_state(token, user)
        again = g.claim_teaser_state(token, user)  # no raise
        assert again["answers"] == _ANSWERS


# ── HTTP: teaser is public, full result is gated ──────────────────────────────

class TestFreeToolRoutes:
    def test_anonymous_can_get_teaser(self, client):
        r = client.post("/api/free-tool/teaser",
                        json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["login_required"] is True
        assert body.get("resume_token")
        assert "teaser" in body
        # The teaser is a PREVIEW only — it must NOT contain the full governed result.
        assert "full_result" not in body
        assert set(body["gated_capabilities"]) >= {
            "full_result", "upload_document", "save_case",
            "timeline", "redaction", "save_citations",
        }

    def test_anonymous_blocked_from_full_result(self, client):
        r = client.post("/api/free-tool/full-result",
                        json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 401, r.text
        detail = r.json()["detail"]
        assert detail["login_required"] is True
        assert detail["capability"] == "full_result"

    def test_authenticated_gets_full_result(self, client):
        r = client.post("/api/free-tool/full-result",
                        headers={"X-User-ID": _uid()},
                        json={"tool": _TOOL, "answers": _ANSWERS})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "result" in body

    def test_anonymous_blocked_from_resume(self, client):
        # Save state anonymously first.
        t = client.post("/api/free-tool/teaser",
                        json={"tool": _TOOL, "answers": _ANSWERS}).json()
        token = t["resume_token"]
        # Anonymous resume attempt must be blocked.
        r = client.post("/api/free-tool/resume", json={"resume_token": token})
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["login_required"] is True

    def test_resume_after_login_restores_answers_exactly(self, client):
        # 1. Anonymous user answers the teaser questions → state saved.
        t = client.post("/api/free-tool/teaser",
                        json={"tool": _TOOL, "answers": _ANSWERS}).json()
        token = t["resume_token"]
        # 2. User logs in (mock identity) and resumes with the token.
        user = _uid()
        r = client.post("/api/free-tool/resume",
                        headers={"X-User-ID": user},
                        json={"resume_token": token})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["resumed"] is True
        assert body["tool"] == _TOOL
        # No lost answers — restored EXACTLY where the user stopped.
        assert body["answers"] == _ANSWERS

    def test_full_result_with_resume_token_uses_saved_answers(self, client):
        # Anonymous saves partial answers, logs in, gets the full result without
        # re-entering anything (no lost answers across the login boundary).
        t = client.post("/api/free-tool/teaser",
                        json={"tool": _TOOL, "answers": _ANSWERS}).json()
        token = t["resume_token"]
        user = _uid()
        r = client.post("/api/free-tool/full-result",
                        headers={"X-User-ID": user},
                        json={"tool": _TOOL, "answers": {}, "resume_token": token})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answers_used"] == _ANSWERS

    def test_resume_invalid_token_after_login_404(self, client):
        r = client.post("/api/free-tool/resume",
                        headers={"X-User-ID": _uid()},
                        json={"resume_token": "bogus-token-value"})
        assert r.status_code == 404, r.text
