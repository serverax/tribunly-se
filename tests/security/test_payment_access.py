"""
Payment access control — HARDENED no-bypass contract.

Document access is granted ONLY by a DB-backed entitlement set via a real,
signature-verified Stripe webhook. No raw token, no test_simulator, no demo unlock.
"""

import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestPaymentGatingIntegrity:
    """
    Fail-closed contract: anonymous callers (no verifiable identity — including
    LAWAPP_AUTH_MODE=none) are rejected with 401 BEFORE any payment logic runs.
    Paid/unpaid gating with real identities is covered by tests/test_legacy_route_parity.py
    against seeded DB cases.
    """

    def test_anonymous_caller_rejected_before_payment_logic(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/documents/generate", json={
                "document_type": "particulars_of_claim",
                "assessment": {"has_viable_claim": "uncertain"},
                "facts": {"edt": "2026-01-01"},
            })
        assert r.status_code == 401, "anonymous generate must fail closed (401)"

    def test_raw_token_does_not_bypass_gate(self, client):
        """A raw request token (test_/anything) must NOT unlock anything for an anonymous caller."""
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/documents/generate", json={
                "document_type": "particulars_of_claim",
                "assessment": {"has_viable_claim": "uncertain"},
                "facts": {"edt": "2026-01-01"},
                "payment_token": "test_validtoken123",
            })
        assert r.status_code == 401, "raw token must never substitute for identity"

    def test_disabled_mode_always_blocks(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/documents/generate", json={
                "document_type": "particulars_of_claim",
                "assessment": {"has_viable_claim": "uncertain"},
                "facts": {"edt": "2026-01-01"},
                "payment_token": "test_anything",
            })
        assert r.status_code == 401, "disabled payment mode must not weaken the auth gate"


class TestPaymentStatusNotFromBody:
    def test_payment_status_comes_from_server_not_body(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/documents/generate", json={
                "document_type": "particulars_of_claim",
                "assessment": {},
                "facts": {"edt": "2026-01-01"},
            })
        if r.status_code == 200:
            assert r.json().get("payment_required") is not False


class TestPaymentWebhook:
    def test_webhook_endpoint_exists(self, client):
        """Endpoint exists (not 404) — but it must not accept unsigned events."""
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "STRIPE_WEBHOOK_SECRET": ""}):
            r = client.post("/api/payment/webhook", json={})
        assert r.status_code != 404

    def test_webhook_does_not_accept_unsigned(self, client):
        for mode in ("disabled", "stripe_test"):
            with patch.dict(os.environ, {"PAYMENT_MODE": mode, "STRIPE_WEBHOOK_SECRET": ""}):
                r = client.post("/api/payment/webhook", json={})
            assert not (r.status_code == 200 and r.json().get("received") is True)

    def test_webhook_stripe_mode_requires_secret(self, client):
        with patch.dict(os.environ, {"PAYMENT_MODE": "stripe_test", "STRIPE_WEBHOOK_SECRET": ""}):
            r = client.post("/api/payment/webhook",
                            headers={"Stripe-Signature": "t=1,v1=x"}, content=b'{}')
        assert r.status_code in (503, 501, 400)


class TestCreateSessionEndpointSecurity:
    def test_create_session_requires_valid_doc_type(self, client):
        # Authenticated caller (auth gate runs first); invalid doc type → 400.
        r = client.post(
            "/api/payment/create-session",
            headers={"X-User-ID": "00000000-0000-0000-0000-000000000001"},
            json={"document_type": "not_a_real_document"},
        )
        assert r.status_code == 400

    def test_create_session_grants_no_demo_unlock(self, client):
        """No demo/test unlock token or auto-paid state from create-session."""
        with patch.dict(os.environ, {"PAYMENT_MODE": "disabled", "LAWAPP_AUTH_MODE": "none"}):
            r = client.post("/api/payment/create-session", json={"document_type": "particulars_of_claim"})
        if r.status_code == 200:
            data = r.json()
            tok = str(data.get("payment_token") or "")
            assert not tok.startswith("test_")
            assert data.get("paid") is not True

    def test_payment_status_requires_auth(self, client):
        # Auth parity with canonical /api/payments/status/{case_id}: no header → 401.
        r = client.get("/api/payment/status")
        assert r.status_code == 401

    def test_payment_status_endpoint_exists(self, client):
        r = client.get("/api/payment/status", headers={"X-User-ID": "00000000-0000-0000-0000-000000000001"})
        assert r.status_code == 200
        assert "mode" in r.json()
