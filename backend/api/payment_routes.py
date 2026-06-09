"""
Payment integration routes — Phase 7: Stripe checkout sessions, webhooks, and payment status.

ARCHITECTURE:
- POST /api/payments/create-session: Backend creates Stripe checkout session.
  Input: {case_id, package_id, user_id}
  Output: {session_url, session_id}
  User is redirected to Stripe by the frontend.

- POST /api/payments/webhook: Receives Stripe webhook events.
  Signature verification required (STRIPE_WEBHOOK_SECRET).
  Backend queries Stripe to confirm payment status.
  Updates cases.payment_status in DB if successful.

- GET /api/payments/status/{case_id}: Returns payment status.
  {paid, payment_date, amount, stripe_session_id}
  Used by frontend to show "Download" or "Unlock Documents" button.

GUARDRAIL: NO frontend token unlock. Payment is DB-backed only.
GUARDRAIL: Webhook signature verification is mandatory (fail closed).
GUARDRAIL: Backend queries Stripe to confirm, never trusts webhook alone.
GUARDRAIL: All payment events logged to audit table.
"""

from __future__ import annotations

import logging
import json
import os
import uuid
from typing import Optional
from datetime import datetime, timezone

import stripe

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.core.payment import (
    get_payment_mode,
    verify_stripe_payment_id,
    verify_webhook_signature,
    is_case_paid,
)
from backend.core.user_auth import get_current_user, check_case_ownership
from ingestion.db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ── Models ────────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    case_id: str = Field(..., description="UUID of the case to unlock")
    package_id: str = Field(default="full_documents", description="Document package: full_documents")
    user_id: Optional[str] = Field(None, description="User ID (from auth)")


class CreateSessionResponse(BaseModel):
    session_url: str
    session_id: str
    case_id: str
    amount_pence: int


class PaymentStatusResponse(BaseModel):
    case_id: str
    paid: bool
    payment_date: Optional[str] = None
    amount_pence: Optional[int] = None
    stripe_session_id: Optional[str] = None
    currency: str = "GBP"


# ── Pricing (centralized, fail-closed) ────────────────────────────────────

def get_package_price_pence(package_id: str) -> int:
    """Return package price in pence. Unknown packages raise 400."""
    prices = {
        "full_documents": 2999,  # £29.99
    }
    if package_id not in prices:
        raise HTTPException(status_code=400, detail=f"Unknown package: {package_id}")
    return prices[package_id]


def _record_payment_event(
    cur,
    *,
    event_id: str,
    event_type: str,
    session_id: str,
    case_id: str,
    user_id: str,
    amount_pence: int,
    status: str,
    package_id: str,
) -> None:
    """Best-effort payment audit against the canonical payment_events table."""
    cur.execute("SELECT to_regclass('public.payment_events')")
    if not cur.fetchone()[0]:
        return
    cur.execute(
        """
        INSERT INTO payment_events (
            stripe_event_id, event_type, payment_mode, session_id,
            case_id, user_id, amount_total, currency, payment_status,
            raw_event, received_at, processed_at
        ) VALUES (%s, %s, %s, %s, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (stripe_event_id) DO NOTHING
        """,
        (
            event_id,
            event_type,
            get_payment_mode(),
            session_id,
            case_id,
            user_id,
            amount_pence,
            "GBP",
            status,
            json.dumps({"session_id": session_id, "package_id": package_id}),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) if status == "paid" else None,
        ),
    )


def _store_payment_session(
    *,
    case_id: str,
    user_id: str,
    session_id: str,
    status: str,
    package_id: str,
    amount_pence: int,
) -> None:
    """Persist payment session state; this is the document-unlock source of truth."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payment_sessions (
                    case_id, user_id, stripe_session_id, status,
                    package_id, amount_pence, created_at, completed_at
                ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stripe_session_id) DO UPDATE SET
                    case_id = EXCLUDED.case_id,
                    user_id = EXCLUDED.user_id,
                    status = EXCLUDED.status,
                    package_id = EXCLUDED.package_id,
                    amount_pence = EXCLUDED.amount_pence,
                    completed_at = EXCLUDED.completed_at
                """,
                (
                    case_id,
                    user_id,
                    session_id,
                    status,
                    package_id,
                    amount_pence,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc) if status == "paid" else None,
                ),
            )
            _record_payment_event(
                cur,
                event_id=f"manual_session_created:{session_id}",
                event_type="checkout.session.created",
                session_id=session_id,
                case_id=case_id,
                user_id=user_id,
                amount_pence=amount_pence,
                status=status,
                package_id=package_id,
            )
        conn.commit()
    finally:
        conn.close()


def confirm_test_payment_session(session_id: str, user_id: str) -> dict:
    """
    Deterministic local payment confirmation for PAYMENT_MODE=test only.

    This deliberately does not run in disabled or stripe mode, and only accepts
    sessions created by the test-mode create-session path.
    """
    if get_payment_mode() != "test":
        raise HTTPException(status_code=403, detail="Deterministic payment confirmation is test-mode only")
    if not session_id.startswith("cs_test_"):
        raise HTTPException(status_code=400, detail="Invalid deterministic test payment ID")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT case_id, amount_pence, package_id, status
                FROM payment_sessions
                WHERE stripe_session_id = %s AND user_id = %s::uuid
                FOR UPDATE
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payment session not found")
            case_id, amount_pence, package_id, current_status = row
            if current_status != "paid":
                cur.execute(
                    """
                    UPDATE payment_sessions
                    SET status = %s, completed_at = %s
                    WHERE stripe_session_id = %s
                    """,
                    ("paid", datetime.now(timezone.utc), session_id),
                )
                cur.execute(
                    """
                    UPDATE cases
                    SET payment_status = %s, stripe_session_id = %s, updated_at = %s
                    WHERE id = %s::uuid AND user_id = %s::uuid
                    """,
                    ("paid", session_id, datetime.now(timezone.utc), str(case_id), user_id),
                )
                _record_payment_event(
                    cur,
                    event_id=f"manual_payment_confirmed:{session_id}",
                    event_type="checkout.session.completed",
                    session_id=session_id,
                    case_id=str(case_id),
                    user_id=user_id,
                    amount_pence=int(amount_pence or 0),
                    status="paid",
                    package_id=str(package_id or "full_documents"),
                )
            conn.commit()
            return {
                "status": "success",
                "session_id": session_id,
                "case_id": str(case_id),
                "payment_status": "paid",
            }
    finally:
        conn.close()


# ── Session creation ──────────────────────────────────────────────────────────

@router.post("/create-session", response_model=CreateSessionResponse)
def create_payment_session(
    req: CreateSessionRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Create a Stripe checkout session.

    Backend creates the session, NOT the frontend. This ensures the backend
    controls the price and cannot be bypassable by token manipulation.

    User is then redirected to the session URL in their browser.
    """
    # ── Authenticate and verify case ownership ──────────────────────────────
    uid = get_current_user(x_user_id, authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    mode = get_payment_mode()
    if mode == "disabled":
        raise HTTPException(status_code=403, detail="Payment is disabled on this deployment")

    try:
        check_case_ownership(req.case_id, uid, admin_override=False)
    except HTTPException:
        raise

    # ── Validate case exists and is unpaid ──────────────────────────────────
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payment_status FROM cases WHERE id = %s::uuid AND deleted_at IS NULL",
                (req.case_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            payment_status = row[0]
            if payment_status in ("paid", "verified", "complete"):
                raise HTTPException(
                    status_code=400,
                    detail="This case has already been paid for",
                )
    finally:
        conn.close()

    # ── Get price ──────────────────────────────────────────────────────────
    price_pence = get_package_price_pence(req.package_id)

    # ── Create Stripe session ──────────────────────────────────────────────
    try:
        stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        blocked_keys = {"placeholder", "sk_" + "test_PLACEHOLDER", "sk_" + "live_PLACEHOLDER"}
        if mode == "stripe" and (not stripe_key or stripe_key in blocked_keys):
            raise HTTPException(
                status_code=503,
                detail="Stripe is not configured on this deployment",
            )
        stripe.api_key = stripe_key

        # Use test or live based on payment mode
        base_url = os.getenv("LAWAPP_BASE_URL", "http://localhost:8000")
        success_url = f"{base_url}/pages/success.html?session_id={{CHECKOUT_SESSION_ID}}&case_id={req.case_id}"
        cancel_url = f"{base_url}/pages/cancel.html?case_id={req.case_id}"

        if mode == "test":
            session_id = f"cs_test_{uuid.uuid4().hex}"
            _store_payment_session(
                case_id=req.case_id,
                user_id=uid,
                session_id=session_id,
                status="pending",
                package_id=req.package_id,
                amount_pence=price_pence,
            )
            return CreateSessionResponse(
                session_url=f"{base_url}/test-payment/{session_id}",
                session_id=session_id,
                case_id=req.case_id,
                amount_pence=price_pence,
            )

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "gbp",
                        "unit_amount": price_pence,
                        "product_data": {
                            "name": "Full Employment Tribunal Documents",
                            "description": f"Complete document set for case {req.case_id}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "case_id": req.case_id,
                "user_id": uid,
                "package_id": req.package_id,
            },
        )

        # ── Store session in DB for tracking ───────────────────────────────
        _store_payment_session(
            case_id=req.case_id,
            user_id=uid,
            session_id=session.id,
            status="pending",
            package_id=req.package_id,
            amount_pence=price_pence,
        )

        logger.info(
            "Stripe checkout session created: %s for case %s (user masked)",
            session.id,
            req.case_id,
        )

        return CreateSessionResponse(
            session_url=session.url,
            session_id=session.id,
            case_id=req.case_id,
            amount_pence=price_pence,
        )

    except Exception as exc:
        logger.error("Stripe session creation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Payment service unavailable",
        )


# ── Webhook reception ──────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Receive Stripe webhook events.

    Mandatory steps:
    1. Verify webhook signature (fail closed if invalid).
    2. Query Stripe to confirm payment status (never trust webhook alone).
    3. Update case payment_status in DB.
    4. Log to audit table.

    STRIPE_WEBHOOK_SECRET must be set. No fallback to mock.
    FIX #4: VALIDATE metadata fields before updating case.
    """
    mode = get_payment_mode()
    if mode == "disabled":
        return Response(status_code=202)

    # ── Read request body ──────────────────────────────────────────────────
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")
    except Exception as exc:
        logger.error("Failed to read webhook body: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request body")

    # ── Verify signature ───────────────────────────────────────────────────
    try:
        event = verify_webhook_signature(payload, sig_header)
    except ValueError as exc:
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=403, detail="Invalid signature")
    except EnvironmentError as exc:
        logger.error("Stripe webhook secret not configured: %s", exc)
        raise HTTPException(status_code=503, detail="Webhook verification not configured")
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed")

    # ── Process only payment success events ─────────────────────────────────
    event_type = event.get("type", "")
    if event_type != "checkout.session.completed":
        logger.info("Ignoring webhook event type: %s", event_type)
        return Response(status_code=202)

    stripe_session_id = event.get("data", {}).get("object", {}).get("id", "")
    if not stripe_session_id:
        logger.warning("Webhook missing session ID")
        return Response(status_code=202)

    # ── Check for duplicate processing (idempotency) ────────────────────────
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM payment_events WHERE stripe_event_id = %s",
                (event.get("id", ""),),
            )
            if cur.fetchone():
                logger.info("Duplicate webhook event (already processed): %s", event.get("id"))
                return Response(status_code=202)
    finally:
        conn.close()

    # ── Query Stripe to confirm payment status ─────────────────────────────
    try:
        import stripe
        stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not stripe_key or stripe_key in ("placeholder",):
            logger.error("Stripe key not configured for webhook verification")
            raise HTTPException(status_code=503, detail="Stripe not configured")

        stripe.api_key = stripe_key
        session = stripe.checkout.Session.retrieve(stripe_session_id)

        # Extract metadata
        case_id = session.metadata.get("case_id", "")
        user_id = session.metadata.get("user_id", "")
        payment_status = session.payment_status

        # FIX #4: GUARDRAIL - Validate all required fields are present
        if not case_id or not user_id:
            logger.error(
                "Webhook payment session missing required metadata "
                "(case_id=%s, user_id=%s)",
                "present" if case_id else "missing",
                "present" if user_id else "missing"
            )
            return Response(status_code=202)

        if not isinstance(case_id, str) or not isinstance(user_id, str):
            logger.error("Webhook metadata has invalid types (not logged)")
            return Response(status_code=202)

    except Exception as exc:
        logger.error("Failed to verify payment with Stripe: %s", exc)
        raise HTTPException(status_code=503, detail="Payment verification failed")

    # ── If payment is confirmed, update case in DB ─────────────────────────
    if payment_status == "paid":
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # FIX #4: VALIDATION - Verify case exists and user owns it
                cur.execute(
                    """
                    SELECT user_id FROM cases
                    WHERE id = %s::uuid AND deleted_at IS NULL
                    """,
                    (case_id,)
                )
                case_row = cur.fetchone()

                if not case_row:
                    logger.error(
                        "Webhook payment for non-existent case (IDs not logged)"
                    )
                    return Response(status_code=202)

                case_owner_id = str(case_row[0]) if case_row[0] else None
                if case_owner_id != user_id:
                    logger.error(
                        "Webhook payment user mismatch (IDs not logged)"
                    )
                    return Response(status_code=202)

                # Update case payment status
                cur.execute(
                    """
                    UPDATE cases
                    SET payment_status = %s, stripe_session_id = %s
                    WHERE id = %s::uuid
                    """,
                    ("paid", stripe_session_id, case_id),
                )

                # Log to audit table
                cur.execute(
                    """
                    INSERT INTO payment_events (
                        stripe_event_id, event_type, payment_mode, session_id,
                        case_id, user_id, amount_total, currency, payment_status,
                        raw_event, received_at, processed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.get("id"),
                        event_type,
                        mode,
                        stripe_session_id,
                        case_id,
                        user_id,
                        session.amount_total,
                        (session.currency or "gbp").upper(),
                        "paid",
                        str(event),
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
            logger.info(
                "Payment confirmed for case via webhook (IDs not logged)"
            )
        except Exception as exc:
            logger.error("Failed to update case payment status: %s", exc)
            conn.rollback()
            raise HTTPException(status_code=500, detail="Payment recorded but database update failed")
        finally:
            conn.close()

    return Response(status_code=202)


# ── Status check ───────────────────────────────────────────────────────────────

@router.get("/status/{case_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    case_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Get payment status for a case.

    Used by frontend to show "Download Documents" or "Unlock Documents" button.
    Returns: {paid, payment_date, amount_pence, stripe_session_id}

    Fails closed if case not found or user doesn't own it.
    """
    uid = get_current_user(x_user_id, authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        check_case_ownership(case_id, uid, admin_override=False)
    except HTTPException:
        raise

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Check case payment status
            cur.execute(
                """
                SELECT payment_status, stripe_session_id, created_at
                FROM cases WHERE id = %s::uuid AND deleted_at IS NULL
                """,
                (case_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")

            payment_status, stripe_session_id, created_at = row
            paid = payment_status in ("paid", "verified", "complete")

            # Get payment amount and date from payment_sessions
            amount_pence = None
            payment_date = None
            if stripe_session_id:
                cur.execute(
                    """
                    SELECT amount_pence, created_at
                    FROM payment_sessions
                    WHERE stripe_session_id = %s
                    """,
                    (stripe_session_id,),
                )
                session_row = cur.fetchone()
                if session_row:
                    amount_pence, payment_date = session_row

            return PaymentStatusResponse(
                case_id=case_id,
                paid=paid,
                payment_date=payment_date.isoformat() if payment_date else None,
                amount_pence=amount_pence,
                stripe_session_id=stripe_session_id,
            )
    finally:
        conn.close()


def handle_stripe_webhook(payload: str | bytes, signature: str) -> dict:
    """Synchronous webhook verifier used by tests and non-ASGI adapters."""
    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    return verify_webhook_signature(body, signature)
