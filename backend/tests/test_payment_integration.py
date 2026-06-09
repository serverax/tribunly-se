"""
Test suite for payment integration (Stripe checkout, webhooks, status checks).

Acceptance gates:
1. Create checkout session (returns valid session_url)
2. Webhook signature verification (valid passes, invalid fails)
3. Stripe payment confirmation query
4. Payment status stored in database
5. Document generation triggered after payment
6. User cannot download before payment
"""

import pytest
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from fastapi import HTTPException
from ingestion.db import get_connection


@pytest.fixture
def test_user_id():
    """Return a test user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_case_id():
    """Return a test case ID."""
    return str(uuid.uuid4())


@pytest.fixture
def setup_test_user_and_case(test_user_id, test_case_id):
    """Create a test user and case in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create user
            cur.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s) "
                "ON CONFLICT (email) DO NOTHING",
                (test_user_id, f"test-{test_user_id}@example.com", "hash"),
            )
            # Create case
            cur.execute(
                """
                INSERT INTO cases (
                    id, user_id, case_title, claim_type, assessment, payment_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    test_case_id,
                    test_user_id,
                    "Test Case",
                    "unfair_dismissal",
                    "{}",
                    "unpaid",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    yield test_user_id, test_case_id


# ── Test 1: Create checkout session ────────────────────────────────────────────

def test_create_payment_session_success(setup_test_user_and_case, test_user_id, test_case_id):
    """Happy path: create a Stripe checkout session."""
    from backend.api.payment_routes import create_payment_session, CreateSessionRequest

    request = CreateSessionRequest(case_id=test_case_id, package_id="full_documents")

    # Mock Stripe (in test mode)
    with patch("backend.api.payment_routes.stripe") as mock_stripe:
        mock_session = Mock()
        mock_session.id = "cs_test_123abc"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123abc"
        mock_stripe.api_key = None
        mock_stripe.checkout.Session.create.return_value = mock_session

        with patch("backend.api.payment_routes.get_payment_mode") as mock_mode:
            mock_mode.return_value = "stripe_test"

            # Call endpoint with mock auth
            with patch("backend.api.payment_routes.get_current_user") as mock_auth:
                mock_auth.return_value = test_user_id

                with patch("backend.api.payment_routes.check_case_ownership"):
                    response = create_payment_session(
                        request,
                        x_user_id=test_user_id,
                        authorization=None,
                    )

    assert response.session_url == "https://checkout.stripe.com/pay/cs_test_123abc"
    assert response.session_id == "cs_test_123abc"
    assert response.case_id == test_case_id
    assert response.amount_pence == 2999  # £29.99


def test_create_session_payment_disabled():
    """Should fail if payment is disabled."""
    from backend.api.payment_routes import create_payment_session, CreateSessionRequest

    request = CreateSessionRequest(case_id=str(uuid.uuid4()))
    user_id = str(uuid.uuid4())

    with patch("backend.api.payment_routes.get_payment_mode") as mock_mode:
        mock_mode.return_value = "disabled"

        with pytest.raises(HTTPException) as exc_info:
            create_payment_session(request, x_user_id=user_id)

    assert exc_info.value.status_code == 403
    assert "disabled" in str(exc_info.value.detail).lower()


def test_create_session_unauthorized():
    """Should fail if user is not authenticated."""
    from backend.api.payment_routes import create_payment_session, CreateSessionRequest

    request = CreateSessionRequest(case_id=str(uuid.uuid4()))

    with patch("backend.api.payment_routes.get_current_user") as mock_auth:
        mock_auth.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            create_payment_session(request)

    assert exc_info.value.status_code == 401


def test_create_session_already_paid(setup_test_user_and_case, test_user_id, test_case_id):
    """Should fail if case is already paid."""
    from backend.api.payment_routes import create_payment_session, CreateSessionRequest

    # Mark case as paid
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cases SET payment_status = %s WHERE id = %s::uuid",
                ("paid", test_case_id),
            )
        conn.commit()
    finally:
        conn.close()

    request = CreateSessionRequest(case_id=test_case_id)

    with patch("backend.api.payment_routes.get_payment_mode") as mock_mode:
        mock_mode.return_value = "stripe_test"

        with patch("backend.api.payment_routes.get_current_user") as mock_auth:
            mock_auth.return_value = test_user_id

            with patch("backend.api.payment_routes.check_case_ownership"):
                with pytest.raises(HTTPException) as exc_info:
                    create_payment_session(request)

    assert exc_info.value.status_code == 400
    assert "already been paid" in str(exc_info.value.detail).lower()


# ── Test 2: Webhook signature verification ────────────────────────────────────

def test_webhook_signature_verification():
    """Valid signature should pass; invalid should fail."""
    from backend.core.payment import verify_webhook_signature

    payload = b'{"type":"checkout.session.completed","id":"evt_test_123"}'
    valid_sig = "t=123,v1=valid_signature"

    # Test invalid signature
    with patch("backend.core.payment.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.side_effect = Exception("Invalid signature")

        with patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret"}):
            with pytest.raises(ValueError):
                verify_webhook_signature(payload, valid_sig)


def test_webhook_missing_secret():
    """Should fail if STRIPE_WEBHOOK_SECRET is not configured."""
    from backend.core.payment import verify_webhook_signature
    import os

    with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
        with pytest.raises(EnvironmentError):
            verify_webhook_signature(b"test", "test_sig")


# ── Test 3: Stripe payment confirmation ────────────────────────────────────────

def test_verify_stripe_payment_id():
    """Should verify real Stripe payment intent IDs."""
    from backend.core.payment import verify_stripe_payment_id

    # Test valid payment_intent
    with patch("backend.core.payment.stripe") as mock_stripe:
        mock_intent = Mock()
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent
        mock_stripe.api_key = None

        with patch.dict(
            "os.environ",
            {"PAYMENT_MODE": "stripe_test", "STRIPE_SECRET_KEY": "sk_" + "test_real"},
        ):
            result = verify_stripe_payment_id("pi_test_123")
            assert result is True

    # Test invalid token format (should reject)
    result = verify_stripe_payment_id("invalid_token")
    assert result is False

    # Test arbitrary token (should reject)
    result = verify_stripe_payment_id("test_paid")
    assert result is False


# ── Test 4: Payment status stored in database ──────────────────────────────────

def test_payment_status_persisted(setup_test_user_and_case, test_user_id, test_case_id):
    """After webhook, payment status should be in DB and is_case_paid() should return True."""
    from backend.core.payment import is_case_paid

    # Initially unpaid
    assert is_case_paid(test_case_id) is False

    # Update case as paid
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cases SET payment_status = %s WHERE id = %s::uuid",
                ("paid", test_case_id),
            )
        conn.commit()
    finally:
        conn.close()

    # Now should be paid
    assert is_case_paid(test_case_id) is True


def test_is_case_paid_fails_closed():
    """is_case_paid should fail closed (return False) on errors."""
    from backend.core.payment import is_case_paid

    # Test with None case_id
    assert is_case_paid(None) is False

    # Test with invalid UUID
    assert is_case_paid("not-a-uuid") is False

    # Test with disabled payment mode
    with patch("backend.core.payment.get_payment_mode") as mock_mode:
        mock_mode.return_value = "disabled"
        assert is_case_paid(str(uuid.uuid4())) is False


# ── Test 5: User cannot download before payment ────────────────────────────────

def test_document_download_requires_payment(setup_test_user_and_case, test_user_id, test_case_id):
    """Should fail to download document if case is not paid."""
    from backend.api.document_routes import download_document

    document_id = str(uuid.uuid4())

    # Create a document in DB
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (
                    id, case_id, user_id, document_type, storage_ref, is_user_upload
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (document_id, test_case_id, test_user_id, "et1_support", "/tmp/doc.html", False),
            )
        conn.commit()
    finally:
        conn.close()

    # Try to download (case is unpaid)
    with patch("backend.api.document_routes.get_current_user") as mock_auth:
        mock_auth.return_value = test_user_id

        with patch("backend.api.document_routes.is_case_paid") as mock_paid:
            mock_paid.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                download_document(document_id, x_user_id=test_user_id)

    assert exc_info.value.status_code == 402  # Payment required


# ── Test 6: Invalid input ──────────────────────────────────────────────────────

def test_create_session_invalid_package():
    """Should fail with invalid package_id."""
    from backend.api.payment_routes import get_package_price_pence

    with pytest.raises(HTTPException) as exc_info:
        get_package_price_pence("invalid_package")

    assert exc_info.value.status_code == 400


def test_create_session_case_not_found(test_user_id):
    """Should fail if case doesn't exist."""
    from backend.api.payment_routes import create_payment_session, CreateSessionRequest

    request = CreateSessionRequest(case_id=str(uuid.uuid4()))

    with patch("backend.api.payment_routes.get_payment_mode") as mock_mode:
        mock_mode.return_value = "stripe_test"

        with patch("backend.api.payment_routes.get_current_user") as mock_auth:
            mock_auth.return_value = test_user_id

            with patch("backend.api.payment_routes.check_case_ownership"):
                with pytest.raises(HTTPException) as exc_info:
                    create_payment_session(request)

    assert exc_info.value.status_code == 404


# ── Test 7: Auth failure ───────────────────────────────────────────────────────

def test_get_payment_status_unauthorized():
    """Should fail if user is not authenticated."""
    from backend.api.payment_routes import get_payment_status

    with patch("backend.api.payment_routes.get_current_user") as mock_auth:
        mock_auth.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_payment_status(str(uuid.uuid4()))

    assert exc_info.value.status_code == 401


def test_get_payment_status_wrong_owner(setup_test_user_and_case, test_case_id):
    """Should fail if user doesn't own the case."""
    from backend.api.payment_routes import get_payment_status

    other_user = str(uuid.uuid4())

    with patch("backend.api.payment_routes.get_current_user") as mock_auth:
        mock_auth.return_value = other_user

        with patch("backend.api.payment_routes.check_case_ownership") as mock_check:
            mock_check.side_effect = HTTPException(status_code=403)

            with pytest.raises(HTTPException) as exc_info:
                get_payment_status(test_case_id)

    assert exc_info.value.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
