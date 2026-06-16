"""
Login-gate tests  -  funnel signals only (no anonymous special-category persist).

Owner decision 2026-06-16 Feature §5 #8.
"""

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


def _uid() -> str:
    return str(uuid.uuid4())


_TOOL = "employment_rights_check"
_ANSWERS = {
    "coarse_outcome": "may_have_claim",
    "step": "2",
}


class TestGateRegistry:
    def test_gated_capabilities_cover_the_brief(self):
        from backend.core import login_gate as g
        for cap in ("full_result", "upload_document", "save_case",
                    "timeline", "redaction", "save_citations"):
            assert g.is_gated(cap)

    def test_public_capabilities_are_not_gated(self):
        from backend.core import login_gate as g
        for cap in ("browse", "teaser", "preview"):
            assert not g.is_gated(cap)


class TestRequireCapability:
    def test_anonymous_blocked_from_gated_capabilities(self):
        from fastapi import HTTPException
        from backend.core import login_gate as g
        with pytest.raises(HTTPException) as exc:
            g.require_capability(None, "full_result")
        assert exc.value.status_code == 401
        assert exc.value.detail["login_required"] is True

    def test_message_does_not_claim_answers_saved(self):
        from fastapi import HTTPException
        from backend.core import login_gate as g
        with pytest.raises(HTTPException) as exc:
            g.require_capability(None, "save_case")
        assert "do not store" in exc.value.detail["message"].lower()


class TestFunnelSignalsOnly:
    def test_save_does_not_persist_case_facts(self):
        from backend.core import login_gate as g
        from ingestion.db import get_connection

        secret = "dismissed without warning after safety concern"
        answers = {"what_happened": secret, "coarse_outcome": "may_have_claim"}
        token = g.save_teaser_state(_TOOL, answers)
        loaded = g.load_teaser_state(token)
        assert loaded is not None
        assert loaded["answers"] == {}
        assert loaded.get("answers_not_stored") is True

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM funnel_signals WHERE session_id = %s",
                    (g.hash_resume_token(token),),
                )
                assert cur.fetchone()[0] >= 1
        finally:
            conn.close()

    def test_claim_returns_no_answers(self):
        from backend.core import login_gate as g
        token = g.save_teaser_state(_TOOL, _ANSWERS)
        claimed = g.claim_teaser_state(token, _uid())
        assert claimed["answers"] == {}
        assert claimed.get("answers_not_stored") is True
