"""
Transactional email transport for the lawapp auth stack.

Used to deliver magic-link, email-verification, and password-reset messages.
Backend is selected by AUTH_EMAIL_BACKEND:

    smtp     — real SMTP (SMTP_HOST/PORT/USERNAME/PASSWORD/FROM, STARTTLS).
    console  — log to the application logger (DEV ONLY; rejected in jwt/production).
    memory   — append to an in-process outbox (TESTS ONLY).

Default: 'memory' under pytest, else 'console' in dev, else fail closed.

GUARDRAILS:
  * In production (LAWAPP_AUTH_MODE=jwt) only the 'smtp' backend is permitted;
    'console'/'memory' raise EmailNotConfigured so a misconfig fails closed rather
    than silently dropping verification/reset mail.
  * Raw magic-link / reset tokens live inside the message body. The body is sent
    to the transport but is NEVER written to the application log at INFO (only the
    recipient-redacted subject is logged).
"""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    """Raised when the configured email backend cannot deliver (fail closed)."""


@dataclass
class AuthEmail:
    to: str
    subject: str
    text_body: str


# In-process outbox for the 'memory' backend (tests assert against this).
_OUTBOX: list[AuthEmail] = []


def get_outbox() -> list[AuthEmail]:
    return _OUTBOX


def clear_outbox() -> None:
    _OUTBOX.clear()


def _backend() -> str:
    explicit = os.getenv("AUTH_EMAIL_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "memory"
    return "console"


def _is_production() -> bool:
    return os.getenv("LAWAPP_AUTH_MODE", "none").lower() == "jwt"


def _send_smtp(msg: AuthEmail) -> None:
    host = os.getenv("SMTP_HOST", "")
    if not host:
        raise EmailNotConfigured("SMTP backend selected but SMTP_HOST is not set.")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username or "no-reply@lawapp.local")
    use_tls = os.getenv("SMTP_STARTTLS", "true").lower() != "false"

    email = EmailMessage()
    email["From"] = sender
    email["To"] = msg.to
    email["Subject"] = msg.subject
    email.set_content(msg.text_body)

    timeout = float(os.getenv("SMTP_TIMEOUT", "15"))
    with smtplib.SMTP(host, port, timeout=timeout) as server:
        if use_tls:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(email)
    logger.info("Auth email sent via SMTP (recipient redacted) subject=%r", msg.subject)


def send_email(to: str, subject: str, text_body: str) -> None:
    """
    Deliver a transactional auth email via the configured backend.

    Raises EmailNotConfigured if the environment cannot deliver (fail closed).
    """
    msg = AuthEmail(to=to, subject=subject, text_body=text_body)
    backend = _backend()

    if _is_production() and backend != "smtp":
        raise EmailNotConfigured(
            f"Email backend '{backend}' is not permitted in production "
            "(LAWAPP_AUTH_MODE=jwt). Configure AUTH_EMAIL_BACKEND=smtp + SMTP_*."
        )

    if backend == "smtp":
        _send_smtp(msg)
    elif backend == "memory":
        _OUTBOX.append(msg)
    elif backend == "console":
        # Dev convenience: the body (containing the link) is logged at DEBUG so a
        # developer can retrieve it; the INFO line never carries the token.
        logger.info("Auth email (console backend) subject=%r", msg.subject)
        logger.debug("Auth email body:\n%s", msg.text_body)
    else:
        raise EmailNotConfigured(f"Unknown AUTH_EMAIL_BACKEND '{backend}'.")
