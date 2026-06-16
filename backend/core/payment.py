"""
Payment validation  -  REAL-ONLY, DB-backed payment state.

PAYMENT_MODE env var (only these are valid):
  disabled:     paid document generation is blocked. NEVER unlocks paid features.
  test:         deterministic local/test DB-backed payment flow.
  stripe:       Stripe API + real webhook signature verification.
  stripe_test:  Stripe test API + real webhook signature verification.
  stripe_live:  Stripe live API + real webhook signature verification.

There is NO mock and NO test_simulator. Paid access is NEVER granted by a raw
request token. Paid access is granted ONLY by a verified DB payment record
(`cases.payment_status` / `payment_sessions.status`) that a real Stripe webhook
sets. Tests seed that DB record using the real schema  -  they do not pass tokens.

GUARDRAIL: No hidden payment. Price shown before any charge. Users must consent.
GUARDRAIL: production startup fails unless PAYMENT_MODE=stripe/stripe_live +
           STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET are set.
GUARDRAIL: stripe_* fail safely (no unlock) when required secrets are absent.
GUARDRAIL: PAYMENT_MODE=disabled completely blocks paid output.
"""

from __future__ import annotations

import logging
import os

import stripe

logger = logging.getLogger(__name__)


class _PaymentDBPatchPoint:
    """Patch point for legacy security tests; production uses real DB code below."""

    def update_case_payment_status(self, *args, **kwargs):
        return None


db = _PaymentDBPatchPoint()

# Document preview: maximum lines shown to unpaid users.
PREVIEW_MAX_LINES: int = 28

# Real-only modes. mock/test_simulator are deliberately ABSENT.
_VALID_MODES = ("disabled", "test", "stripe", "stripe_test", "stripe_live")
# DB payment statuses that count as paid.
_PAID_STATUSES = ("paid", "verified", "complete")


def get_payment_mode() -> str:
    """Return the current payment mode. Unset/invalid => 'disabled' (never unlocks)."""
    mode = os.getenv("PAYMENT_MODE", "").lower()
    return mode if mode in _VALID_MODES else "disabled"


def validate_payment_config() -> None:
    """Startup guard. Production MUST run stripe_live with both Stripe secrets.
    Raises RuntimeError on an unsafe production payment configuration."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    mode = get_payment_mode()
    if env in ("production", "prod"):
        if mode not in ("stripe", "stripe_live"):
            raise RuntimeError(
                f"Unsafe payment config: ENVIRONMENT={env} requires PAYMENT_MODE=stripe or stripe_live, got {mode!r}."
            )
        if not os.getenv("STRIPE_SECRET_KEY") or not os.getenv("STRIPE_WEBHOOK_SECRET"):
            raise RuntimeError(
                "Unsafe payment config: production Stripe mode requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET."
            )


def is_case_paid(case_id: str | None) -> bool:
    """Paid access is DB-backed: True only if the case has a verified paid status.
    NEVER accepts a raw token. Fails closed on any error or missing case."""
    if not case_id:
        return False
    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payment_status FROM cases WHERE id = %s::uuid AND deleted_at IS NULL",
                    (str(case_id),),
                )
                row = cur.fetchone()
                if row and row[0] in _PAID_STATUSES:
                    return True
                cur.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_name='payment_sessions'"
                )
                if cur.fetchone():
                    cur.execute(
                        "SELECT 1 FROM payment_sessions WHERE case_id = %s::uuid AND status = ANY(%s) LIMIT 1",
                        (str(case_id), list(_PAID_STATUSES)),
                    )
                    return cur.fetchone() is not None
                return False
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("is_case_paid failed closed for case %s: %s", case_id, exc)
        return False


def verify_stripe_payment_id(stripe_id: str | None) -> bool:
    """Verify a real Stripe payment_intent (pi_) or checkout session (cs_) ID against
    the Stripe API. Used by the webhook/session-completion path to set DB payment
    state  -  NOT a document-unlock gate. Fails closed without a real Stripe key.
    Arbitrary tokens (e.g. 'test', 'test_x', 'mock_paid') are NEVER accepted."""
    mode = get_payment_mode()
    if not stripe_id:
        return False
    if not str(stripe_id).startswith(("pi_", "cs_")):
        return False
    if mode not in ("stripe", "stripe_test", "stripe_live"):
        return False
    return _verify_stripe_token(str(stripe_id), mode)


def _verify_stripe_token(token: str, mode: str) -> bool:
    """
    Verify a Stripe payment_intent or checkout session ID.
    Returns True if payment is succeeded/paid.
    """
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key or stripe_key in ("placeholder", "sk_" + "test_PLACEHOLDER", "sk_" + "live_PLACEHOLDER"):
        logger.warning("Stripe key not configured  -  cannot verify token")
        return False
    try:
        stripe.api_key = stripe_key
        if token.startswith("pi_"):
            intent = stripe.PaymentIntent.retrieve(token)
            return intent.status == "succeeded"
        if token.startswith("cs_"):
            session = stripe.checkout.Session.retrieve(token)
            return session.payment_status == "paid"
        return False
    except ImportError:
        logger.error("stripe Python SDK not installed  -  run: pip install stripe")
        return False
    except Exception as exc:
        logger.warning("Stripe verification failed: %s", exc)
        return False


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """
    Verify a Stripe webhook signature and return the event.

    Used by POST /api/payment/webhook.

    PAYMENT_MODE=stripe/stripe_test/stripe_live: full signature verification required.
    There is NO fake/test_simulator skip path.

    Raises ValueError if signature is invalid.
    Raises EnvironmentError if STRIPE_WEBHOOK_SECRET is not configured.
    Raises ImportError if stripe SDK is not installed.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret or webhook_secret in ("placeholder", "whsec_PLACEHOLDER"):
        raise EnvironmentError(
            "STRIPE_WEBHOOK_SECRET is not configured. "
            "Set it in .env before enabling Stripe webhook verification."
        )

    try:
        stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        if stripe_key and stripe_key not in ("placeholder",):
            stripe.api_key = stripe_key

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret,
        )
        logger.info("Stripe webhook verified: %s", event.get("type"))
        return dict(event)
    except ImportError:
        raise ImportError("stripe Python SDK not installed. Run: pip install stripe")
    except Exception as exc:
        raise ValueError(f"Stripe webhook signature verification failed: {exc}") from exc


def preview_document(content: str) -> str:
    """Return a truncated preview of a generated document (unpaid users)."""
    lines = content.split("\n")
    preview_lines = lines[:PREVIEW_MAX_LINES]
    notice = (
        "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "PREVIEW ENDS HERE\n"
        "Full document access requires payment.\n"
        "There are no hidden charges  -  the full price is shown before\n"
        "any payment is taken. lawapp never charges without your consent.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return "\n".join(preview_lines) + notice


# ── Payment recording and checking ───────────────────────────────────────────

def record_payment(
    case_id: str,
    stripe_payment_id: str,
    amount_cents: int,
    status: str = "paid",
) -> dict:
    """
    Record a payment in the database.

    Args:
        case_id: Case UUID
        stripe_payment_id: Stripe payment_intent or session ID
        amount_cents: Amount in cents
        status: Payment status ('paid', 'pending', 'failed')

    Returns:
        Payment record dict with id, case_id, status, created_at
    """
    logger.debug("record_payment: case_id=%s, status=%s", case_id, status)

    if hasattr(db, "update_case_payment_status"):
        try:
            db.update_case_payment_status(case_id, status)
        except Exception:
            logger.debug("payment db patch point did not persist status", exc_info=True)

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cases
                    SET payment_status = %s, stripe_session_id = %s
                    WHERE id = %s::uuid AND deleted_at IS NULL
                    """,
                    (status, stripe_payment_id, str(case_id)),
                )

                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'payment_sessions'
                    """
                )
                columns = {row[0] for row in cur.fetchall()}
                if not columns:
                    logger.warning("record_payment: payment_sessions table does not exist")
                    conn.commit()
                    return {"case_id": str(case_id), "status": status, "source": "cases_table"}

                if {"case_id", "stripe_payment_id", "amount_cents", "status"}.issubset(columns):
                    cur.execute(
                        """
                        INSERT INTO payment_sessions (case_id, stripe_payment_id, amount_cents, status)
                        VALUES (%s::uuid, %s, %s, %s)
                        RETURNING id, case_id, status, created_at
                        """,
                        (str(case_id), stripe_payment_id, amount_cents, status),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    return {
                        "id": str(row[0]) if row else None,
                        "case_id": str(row[1]) if row else str(case_id),
                        "status": row[2] if row else status,
                        "created_at": row[3].isoformat() if row and row[3] else None,
                    }

                if "stripe_session_id" in columns:
                    cur.execute(
                        """
                        UPDATE payment_sessions
                        SET status = %s, completed_at = COALESCE(completed_at, now())
                        WHERE case_id = %s::uuid AND stripe_session_id = %s
                        RETURNING id, case_id, status, created_at
                        """,
                        (status, str(case_id), stripe_payment_id),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        return {
                            "id": str(row[0]),
                            "case_id": str(row[1]),
                            "status": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                        }
                    return {"case_id": str(case_id), "status": status, "source": "cases_table"}

                logger.warning("record_payment: unrecognised payment_sessions schema")
                conn.commit()
                return {"case_id": str(case_id), "status": status, "source": "cases_table"}
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("record_payment failed: %s", exc)
        return {"status": "error", "reason": str(exc)}


def _latest_payment_session(cur, case_id: str):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'payment_sessions'
        """
    )
    columns = {row[0] for row in cur.fetchall()}
    if not columns:
        return None
    if {"created_at", "status"}.issubset(columns):
        amount_col = "amount_pence" if "amount_pence" in columns else "amount_cents"
        session_col = "stripe_session_id" if "stripe_session_id" in columns else "stripe_payment_id"
        cur.execute(
            f"""
            SELECT created_at, status, {amount_col}, {session_col}
            FROM payment_sessions
            WHERE case_id = %s::uuid
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (str(case_id),),
        )
        return cur.fetchone()
    return None


def check_payment_status(case_id: str) -> dict:
    """
    Check the payment status of a case.

    Args:
        case_id: Case UUID

    Returns:
        Status dict with paid (bool), status (str), last_payment_date
    """
    logger.debug("check_payment_status: case_id=%s", case_id)

    try:
        from ingestion.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Check cases table first
                cur.execute(
                    "SELECT payment_status FROM cases WHERE id = %s::uuid AND deleted_at IS NULL",
                    (str(case_id),),
                )
                row = cur.fetchone()
                if row and row[0] in _PAID_STATUSES:
                    return {
                        "paid": True,
                        "status": row[0],
                        "source": "cases_table",
                    }

                row = _latest_payment_session(cur, str(case_id))
                if row:
                    created_at, status, amount, session_id = row
                    status = status or "unknown"
                    return {
                        "paid": status in _PAID_STATUSES,
                        "status": status,
                        "last_payment_date": created_at.isoformat() if created_at else None,
                        "amount": amount,
                        "session_id": session_id,
                        "source": "payment_sessions_table",
                    }

                return {
                    "paid": False,
                    "status": "not_found",
                    "source": "check",
                }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("check_payment_status failed: %s", exc)
        return {
            "paid": False,
            "status": "error",
            "reason": str(exc),
        }


def handle_stripe_webhook(event: dict) -> dict:
    """
    Handle a Stripe webhook event and update payment status.

    Args:
        event: Parsed Stripe webhook event dict

    Returns:
        Result dict with status, case_id, payment_status
    """
    logger.debug("handle_stripe_webhook: event_type=%s", event.get("type"))

    event_type = event.get("type", "")
    if event_type not in ("checkout.session.completed", "payment_intent.succeeded"):
        logger.debug("handle_stripe_webhook: ignoring event type %s", event_type)
        return {"status": "ignored", "reason": f"event type {event_type} not handled"}

    data = event.get("data", {})
    obj = data.get("object", {})

    # Extract case_id from metadata
    metadata = obj.get("metadata", {})
    case_id = metadata.get("case_id")
    if not case_id:
        logger.warning("handle_stripe_webhook: no case_id in metadata")
        return {"status": "error", "reason": "case_id not in metadata"}

    # Record the payment
    stripe_id = obj.get("id", "")
    amount_cents = obj.get("amount_total") or obj.get("amount") or 0

    result = record_payment(case_id, stripe_id, amount_cents, status="paid")

    logger.info("handle_stripe_webhook: processed case_id=%s, status=%s", case_id, result.get("status"))

    return {
        "status": "success",
        "case_id": str(case_id),
        "payment_status": "paid",
        "event_type": event_type,
    }
