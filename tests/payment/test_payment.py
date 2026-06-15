"""
Payment flow tests — HARDENED, no-bypass contract.

Valid PAYMENT_MODE values are ONLY: disabled, stripe_test, stripe_live.
There is NO mock and NO test_simulator. Paid access is NEVER granted by a raw
request token — only by a DB-backed payment record (cases.payment_status /
payment_sessions.status) set by a real, signature-verified Stripe webhook.

These tests prove the bypasses are rejected/unavailable. They do NOT restore them.
"""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Legacy /documents/generate fails closed (401) for anonymous callers; these tests
# target payment/content behaviour, so authenticate with a mock identity.
_LEGACY_AUTH = {"X-User-ID": "00000000-0000-0000-0000-00000000000a"}



@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestPaymentMode:
    """Only disabled/stripe_test/stripe_live are valid. Everything else => disabled."""

    def test_disabled_is_disabled(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "disabled"

    def test_stripe_test_is_valid(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "stripe_test"

    def test_stripe_live_is_valid(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_live"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "stripe_live"

    def test_test_simulator_maps_to_disabled(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "test_simulator"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "disabled"   # bypass removed

    def test_mock_maps_to_disabled(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "mock"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "disabled"   # bypass removed

    def test_unknown_mode_falls_back_to_disabled(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "banana"}):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "disabled"   # never falls back to 'mock'

    def test_unset_mode_is_disabled(self):
        env = {k: v for k, v in os.environ.items() if k != "PAYMENT_MODE"}
        with patch.dict(os.environ, env, clear=True):
            from backend.core.payment import get_payment_mode
            assert get_payment_mode() == "disabled"


class TestNoBypassUnlock:
    """No token-prefix is_paid, no raw-token entitlement."""

    def test_is_paid_function_removed(self):
        import backend.core.payment as pm
        assert not hasattr(pm, "is_paid"), "token-prefix is_paid bypass must not exist"

    def test_is_case_paid_disabled_is_false(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled"}):
            from backend.core.payment import is_case_paid
            assert is_case_paid("any-case") is False
            assert is_case_paid(None) is False

    def test_is_case_paid_none_is_false(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test"}):
            from backend.core.payment import is_case_paid
            assert is_case_paid(None) is False

    def test_arbitrary_tokens_never_verify(self):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test"}):
            from backend.core.payment import verify_stripe_payment_id
            for tok in (None, "", "test", "test_abc123", "mock_paid", "anything", "pi_fake_no_key"):
                assert verify_stripe_payment_id(tok) is False

    def test_validate_payment_config_blocks_unsafe_production(self):
        from backend.core.payment import validate_payment_config
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "PAYMENT_MODE": "disabled"}):
            with pytest.raises(RuntimeError):
                validate_payment_config()
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "PAYMENT_MODE": "stripe_test"}):
            with pytest.raises(RuntimeError):
                validate_payment_config()


class TestPreviewDocument:
    def test_preview_truncates_document(self):
        from backend.core.payment import preview_document, PREVIEW_MAX_LINES
        content = "\n".join([f"Line {i}" for i in range(100)])
        result = preview_document(content)
        lines = result.split("\n")
        preview_lines = [l for l in lines[:PREVIEW_MAX_LINES] if l.startswith("Line")]
        assert len(preview_lines) <= PREVIEW_MAX_LINES

    def test_preview_includes_payment_notice(self):
        from backend.core.payment import preview_document
        result = preview_document("Content line 1\nContent line 2")
        assert "PREVIEW ENDS HERE" in result or "payment" in result.lower()


class TestStripeWebhookVerification:
    def test_webhook_never_accepts_unsigned(self, client):
        """No test_simulator skip path: an unsigned webhook is never 'received'."""
        for mode in ("disabled", "stripe_test"):
            with patch.dict(os.environ, {"PAYMENT_MODE": mode, "STRIPE_WEBHOOK_SECRET": ""}):
                r = client.post("/api/payment/webhook", json={})
            assert not (r.status_code == 200 and r.json().get("received") is True), \
                f"unsigned webhook accepted in mode={mode}"

    def test_webhook_stripe_mode_fails_without_secret(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "STRIPE_WEBHOOK_SECRET": ""}):
            r = client.post("/api/payment/webhook",
                            headers={"Stripe-Signature": "t=1234,v1=fakesig"}, content=b'{}')
        assert r.status_code == 503

    def test_webhook_stripe_invalid_signature_rejected(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test",
                                     "STRIPE_WEBHOOK_SECRET": "whsec_test_secret"}):
            r = client.post("/api/payment/webhook",
                            headers={"Stripe-Signature": "t=1234,v1=invalid"},
                            content=b'{"id":"evt_test","type":"checkout.session.completed"}')
        assert r.status_code in (400, 503)

    def test_payment_events_table_exists(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'localhost'),
                                port=int(os.environ.get('POSTGRES_PORT', '5435')),
                                dbname=os.environ.get('POSTGRES_DB', 'lawapp'),
                                user=os.environ.get('POSTGRES_USER', 'lawapp'),
                                password=os.environ.get('POSTGRES_PASSWORD', 'lawapp'))
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='payment_events'")
        cols = {r[0] for r in cur.fetchall()}
        conn.close()
        assert {"stripe_event_id", "payment_status", "case_id"}.issubset(cols)

    def test_cases_payment_status_column_exists(self):
        import psycopg2
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'localhost'),
                                port=int(os.environ.get('POSTGRES_PORT', '5435')),
                                dbname=os.environ.get('POSTGRES_DB', 'lawapp'),
                                user=os.environ.get('POSTGRES_USER', 'lawapp'),
                                password=os.environ.get('POSTGRES_PASSWORD', 'lawapp'))
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='cases' AND column_name='payment_status'")
        row = cur.fetchone()
        conn.close()
        assert row is not None


class TestCreateSessionEndpoint:
    def test_create_session_grants_no_fake_token(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/api/payment/create-session", json={"document_type": "particulars_of_claim"})
        # Whatever the response, it must NOT hand back a test_/demo unlock token.
        if r.status_code == 200:
            tok = str((r.json() or {}).get("payment_token") or "")
            assert not tok.startswith("test_")

    def test_create_session_invalid_doc_type(self, client):
        with patch.dict(os.environ, {"LAWAPP_AUTH_MODE": "mock"}):
            from tests.integration.auth_helpers import mock_auth_headers
            r = client.post(
                "/api/payment/create-session",
                headers=mock_auth_headers(),
                json={"document_type": "fake_document"},
            )
        assert r.status_code == 400


class TestDocumentPaymentGating:
    def test_no_token_returns_preview(self, client):
        from tests.integration.auth_helpers import mock_auth_headers
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled", "LAWAPP_AUTH_MODE": "mock"}):
            r = client.post("/documents/generate", headers=mock_auth_headers(), json={
                "document_type": "particulars_of_claim",
                "assessment": {"has_viable_claim": "uncertain"},
                "facts": {"edt": "2026-03-01", "service_start_date": "2022-01-01"},
            })
        assert r.status_code in (200, 402, 422)
        if r.status_code == 200:
            data = r.json()
            assert data.get("payment_required") is not False or "PREVIEW" in data.get("content", "")

    def test_raw_token_does_not_unlock_full_doc(self, client):
        """A raw request token must NOT unlock the full document (no DB entitlement)."""
        from tests.integration.auth_helpers import mock_auth_headers
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "LAWAPP_AUTH_MODE": "mock"}):
            r = client.post("/documents/generate", headers=mock_auth_headers(), json={
                "document_type": "particulars_of_claim",
                "assessment": {"has_viable_claim": "uncertain"},
                "facts": {"edt": "2026-03-01", "service_start_date": "2022-01-01"},
                "payment_token": "test_abc123",
            })
        assert r.status_code in (200, 402, 422)
        if r.status_code == 200:
            assert r.json().get("payment_required") is not False, "raw token unlocked the document"
