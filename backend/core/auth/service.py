"""
Auth service layer  -  the real orchestration behind /api/auth/*.

Ties together: users table, auth_sessions (refresh tokens / logout-all),
auth_tokens (single-use magic-link / verify / reset), oauth_identities (provider
linkage), auth_events (audit), passwords, tokens, email, providers.

Design notes:
  * A "session" is one auth_sessions row keyed by SHA-256(refresh token). The
    access token is a short-lived JWT carrying that session id (sid).
  * Refresh = rotation: the old refresh token is revoked ('rotated') and a new one
    issued. Replaying an already-rotated token is REUSE → the whole user's sessions
    are revoked and the attempt is audited (refresh_reuse).
  * Magic-link / OAuth prove email control → email_verified is set true.
  * Password reset revokes ALL sessions (force global re-login).
  * MFA-ready: if a user has mfa_enabled, password login returns mfa_required and
    withholds tokens (no TOTP-verify endpoint is shipped yet  -  documented).

GUARDRAILS:
  * Generic responses for magic-link / password-reset (no account enumeration).
  * Raw tokens never persisted (only hashes) and never logged.
  * Every action writes an auth_events row.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import psycopg2

from ingestion.db import get_connection
from . import audit, email as email_mod, tokens
from .passwords import (
    WeakPasswordError,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from .providers import (
    OAuthIdentity,
    ProviderNotConfigured,
    ProviderVerificationError,
    get_provider,
)

logger = logging.getLogger(__name__)

_MAGIC_LINK_TTL = int(os.getenv("AUTH_MAGIC_LINK_TTL_SECONDS", str(15 * 60)))
_EMAIL_VERIFY_TTL = int(os.getenv("AUTH_EMAIL_VERIFY_TTL_SECONDS", str(24 * 60 * 60)))
_PASSWORD_RESET_TTL = int(os.getenv("AUTH_PASSWORD_RESET_TTL_SECONDS", str(60 * 60)))


# ── exceptions (mapped to HTTP status by the router) ─────────────────────────

class AuthError(Exception):
    status_code = 400

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class InvalidCredentials(AuthError):
    def __init__(self, message: str = "Invalid email or password."):
        super().__init__(message, status_code=401)


class EmailExists(AuthError):
    def __init__(self, message: str = "Email already registered."):
        super().__init__(message, status_code=409)


class InvalidToken(AuthError):
    def __init__(self, message: str = "Invalid or expired token."):
        super().__init__(message, status_code=400)


class EmailNotVerified(AuthError):
    def __init__(self, message: str = "Email address is not verified."):
        super().__init__(message, status_code=403)


class ProviderUnavailable(AuthError):
    def __init__(self, message: str):
        super().__init__(message, status_code=503)


# ── request context + result bundle ──────────────────────────────────────────

@dataclass
class RequestContext:
    trace_id: Optional[str] = None
    ip_hash: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class SessionBundle:
    user_id: str
    access_token: Optional[str]
    refresh_token: Optional[str]
    access_expires_at: Optional[str]
    refresh_expires_at: Optional[str]
    session_id: Optional[str]
    mfa_required: bool = False
    email_verified: bool = False

    def to_response(self) -> dict:
        if self.mfa_required:
            return {
                "mfa_required": True,
                "user_id": self.user_id,
                "message": "Multi-factor authentication is required to complete sign-in.",
            }
        return {
            "user_id": self.user_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "bearer",
            "access_expires_at": self.access_expires_at,
            "refresh_expires_at": self.refresh_expires_at,
            "session_id": self.session_id,
            "email_verified": self.email_verified,
        }


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _require_verified_email() -> bool:
    return os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "false").lower() == "true"


def _public_base_url() -> str:
    return os.getenv("AUTH_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


# ── session issuance / rotation ──────────────────────────────────────────────

def _issue_session(
    cur,
    user_id: str,
    *,
    amr: list[str],
    mfa_satisfied: bool,
    ctx: RequestContext,
) -> SessionBundle:
    raw_refresh = tokens.generate_opaque_token()
    refresh_hash = tokens.hash_token(raw_refresh)
    refresh_exp = tokens.refresh_expiry()
    cur.execute(
        """
        INSERT INTO auth_sessions
            (user_id, refresh_token_hash, expires_at, mfa_satisfied, user_agent, ip_hash)
        VALUES (%s::uuid, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, refresh_hash, refresh_exp, mfa_satisfied, ctx.user_agent, ctx.ip_hash),
    )
    session_id = str(cur.fetchone()[0])
    access_token, access_exp = tokens.create_access_token(
        user_id, session_id, amr=amr, mfa_satisfied=mfa_satisfied,
    )
    return SessionBundle(
        user_id=user_id,
        access_token=access_token,
        refresh_token=raw_refresh,
        access_expires_at=access_exp.isoformat(),
        refresh_expires_at=refresh_exp.isoformat(),
        session_id=session_id,
    )


# ── single-use token helpers (magic-link / verify / reset) ───────────────────

def _issue_single_use_token(cur, user_id: str, purpose: str, ttl_seconds: int) -> str:
    raw = tokens.generate_opaque_token()
    cur.execute(
        """
        INSERT INTO auth_tokens (user_id, token_hash, purpose, expires_at)
        VALUES (%s::uuid, %s, %s, %s)
        """,
        (user_id, tokens.hash_token(raw), purpose, tokens.single_use_expiry(ttl_seconds)),
    )
    return raw


def _consume_single_use_token(cur, raw_token: str, purpose: str) -> Optional[str]:
    """Atomically redeem a single-use token. Returns user_id or None."""
    cur.execute(
        """
        UPDATE auth_tokens
           SET consumed_at = now()
         WHERE token_hash = %s
           AND purpose = %s
           AND consumed_at IS NULL
           AND expires_at > now()
        RETURNING user_id
        """,
        (tokens.hash_token(raw_token or ""), purpose),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def _send_link_email(to: str, subject: str, intro: str, path: str, raw_token: str) -> None:
    url = f"{_public_base_url()}{path}?token={raw_token}"
    body = (
        f"{intro}\n\n{url}\n\n"
        "If you did not request this, you can safely ignore this email.\n"
        "This link can be used once and will expire shortly."
    )
    email_mod.send_email(to, subject, body)


# ── registration / login ─────────────────────────────────────────────────────

def register(email: str, password: str, display_name: Optional[str], *, ctx: RequestContext) -> SessionBundle:
    norm = _norm_email(email)
    if not norm or "@" not in norm:
        raise AuthError("A valid email address is required.", status_code=400)
    try:
        validate_password_strength(password)
    except WeakPasswordError as exc:
        raise AuthError(str(exc), status_code=400)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users
                        (email, password_hash, display_name, primary_auth_provider, password_updated_at)
                    VALUES (%s, %s, %s, 'password', now())
                    RETURNING id
                    """,
                    (norm, hash_password(password), display_name),
                )
            except psycopg2.IntegrityError:
                conn.rollback()
                audit.record_event(event_type="register", success=False, email_attempted=norm,
                                   provider="password", trace_id=ctx.trace_id,
                                   ip_hash=ctx.ip_hash, user_agent=ctx.user_agent,
                                   detail={"reason": "email_exists"})
                raise EmailExists()
            user_id = str(cur.fetchone()[0])
            verify_raw = _issue_single_use_token(cur, user_id, "email_verify", _EMAIL_VERIFY_TTL)
            bundle = _issue_session(cur, user_id, amr=["pwd"], mfa_satisfied=True, ctx=ctx)
        conn.commit()
    except (EmailExists, AuthError):
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("register failed: %s", type(exc).__name__)
        raise AuthError("Registration failed.", status_code=500)
    finally:
        conn.close()

    # Side effects after commit (email delivery must not roll back the account).
    try:
        _send_link_email(norm, "Verify your lawapp email",
                         "Confirm your email address by visiting:",
                         "/pages/login.html", verify_raw)
    except Exception:
        logger.warning("verification email send failed during registration (account created).")
    audit.record_event(event_type="register", success=True, user_id=user_id,
                       provider="password", trace_id=ctx.trace_id,
                       ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    bundle.email_verified = False
    return bundle


def login_password(email: str, password: str, *, ctx: RequestContext) -> SessionBundle:
    norm = _norm_email(email)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, mfa_enabled, COALESCE(email_verified, false) "
                "FROM users WHERE lower(email) = %s",
                (norm,),
            )
            row = cur.fetchone()
            if not row or not verify_password(password, row[1]):
                audit.record_event(event_type="login_failure", success=False,
                                   email_attempted=norm, provider="password",
                                   trace_id=ctx.trace_id, ip_hash=ctx.ip_hash,
                                   user_agent=ctx.user_agent,
                                   detail={"reason": "bad_credentials"})
                raise InvalidCredentials()

            user_id, stored_hash, mfa_enabled, email_verified = (
                str(row[0]), row[1], bool(row[2]), bool(row[3]),
            )

            if _require_verified_email() and not email_verified:
                audit.record_event(event_type="login_failure", success=False, user_id=user_id,
                                   email_attempted=norm, provider="password",
                                   trace_id=ctx.trace_id, ip_hash=ctx.ip_hash,
                                   user_agent=ctx.user_agent, detail={"reason": "email_unverified"})
                raise EmailNotVerified()

            if needs_rehash(stored_hash):
                cur.execute("UPDATE users SET password_hash = %s WHERE id = %s::uuid",
                            (hash_password(password), user_id))

            if mfa_enabled:
                # MFA-ready: withhold tokens until a second factor is satisfied.
                conn.commit()
                audit.record_event(event_type="login_success", success=True, user_id=user_id,
                                   provider="password", trace_id=ctx.trace_id,
                                   ip_hash=ctx.ip_hash, user_agent=ctx.user_agent,
                                   detail={"mfa_required": True})
                return SessionBundle(user_id=user_id, access_token=None, refresh_token=None,
                                     access_expires_at=None, refresh_expires_at=None,
                                     session_id=None, mfa_required=True,
                                     email_verified=email_verified)

            cur.execute("UPDATE users SET last_login_at = now() WHERE id = %s::uuid", (user_id,))
            bundle = _issue_session(cur, user_id, amr=["pwd"], mfa_satisfied=True, ctx=ctx)
            bundle.email_verified = email_verified
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("login failed: %s", type(exc).__name__)
        raise AuthError("Login failed.", status_code=500)
    finally:
        conn.close()

    audit.record_event(event_type="login_success", success=True, user_id=bundle.user_id,
                       provider="password", trace_id=ctx.trace_id,
                       ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    return bundle


# ── logout / logout-all ──────────────────────────────────────────────────────

def logout(refresh_token: str, *, ctx: RequestContext) -> None:
    conn = get_connection()
    user_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE auth_sessions
                   SET revoked_at = now(), revoked_reason = 'logout'
                 WHERE refresh_token_hash = %s AND revoked_at IS NULL
                RETURNING user_id
                """,
                (tokens.hash_token(refresh_token or ""),),
            )
            row = cur.fetchone()
            user_id = str(row[0]) if row else None
        conn.commit()
    finally:
        conn.close()
    audit.record_event(event_type="logout", success=True, user_id=user_id,
                       trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)


def logout_all(user_id: str, *, ctx: RequestContext) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE auth_sessions
                   SET revoked_at = now(), revoked_reason = 'logout_all'
                 WHERE user_id = %s::uuid AND revoked_at IS NULL
                """,
                (user_id,),
            )
            count = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    audit.record_event(event_type="logout_all", success=True, user_id=user_id,
                       trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent,
                       detail={"sessions_revoked": count})
    return count


# ── refresh (rotation + reuse detection) ─────────────────────────────────────

def refresh(refresh_token: str, *, ctx: RequestContext) -> SessionBundle:
    token_hash = tokens.hash_token(refresh_token or "")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, revoked_at, revoked_reason, expires_at
                  FROM auth_sessions WHERE refresh_token_hash = %s
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                raise InvalidToken("Refresh token not recognised.")
            sid, user_id, revoked_at, revoked_reason, expires_at = (
                str(row[0]), str(row[1]), row[2], row[3], row[4],
            )

            if revoked_at is not None:
                # A previously-rotated (or logged-out) refresh token replayed.
                # Treat rotation-replay as reuse: revoke every session for the user.
                cur.execute(
                    """
                    UPDATE auth_sessions
                       SET revoked_at = COALESCE(revoked_at, now()),
                           revoked_reason = CASE WHEN revoked_at IS NULL
                                                 THEN 'reuse_detected' ELSE revoked_reason END
                     WHERE user_id = %s::uuid AND revoked_at IS NULL
                    """,
                    (user_id,),
                )
                conn.commit()
                audit.record_event(event_type="refresh_reuse", success=False, user_id=user_id,
                                   trace_id=ctx.trace_id, ip_hash=ctx.ip_hash,
                                   user_agent=ctx.user_agent,
                                   detail={"replayed_reason": revoked_reason})
                raise InvalidToken("Refresh token has been revoked.")

            if expires_at <= tokens.now_utc():
                cur.execute("UPDATE auth_sessions SET revoked_at = now(), "
                            "revoked_reason = 'expired' WHERE id = %s::uuid", (sid,))
                conn.commit()
                raise InvalidToken("Refresh token has expired.")

            # Rotate: issue a new session, mark old as rotated → new.
            bundle = _issue_session(cur, user_id, amr=["refresh"], mfa_satisfied=True, ctx=ctx)
            cur.execute(
                """
                UPDATE auth_sessions
                   SET revoked_at = now(), revoked_reason = 'rotated', rotated_to = %s::uuid
                 WHERE id = %s::uuid
                """,
                (bundle.session_id, sid),
            )
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("refresh failed: %s", type(exc).__name__)
        raise AuthError("Token refresh failed.", status_code=500)
    finally:
        conn.close()

    audit.record_event(event_type="refresh", success=True, user_id=bundle.user_id,
                       trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    return bundle


# ── magic link ───────────────────────────────────────────────────────────────

def request_magic_link(email: str, *, ctx: RequestContext) -> None:
    """Issue a passwordless sign-in link. Always succeeds generically (no enumeration)."""
    norm = _norm_email(email)
    if not norm or "@" not in norm:
        return  # generic: do not reveal validation outcome
    conn = get_connection()
    raw = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = %s", (norm,))
            row = cur.fetchone()
            if row:
                user_id = str(row[0])
            else:
                # Passwordless signup: create a shell user (no password).
                cur.execute(
                    "INSERT INTO users (email, primary_auth_provider) VALUES (%s, 'magic_link') "
                    "RETURNING id", (norm,),
                )
                user_id = str(cur.fetchone()[0])
            raw = _issue_single_use_token(cur, user_id, "magic_link", _MAGIC_LINK_TTL)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("magic link issue failed: %s", type(exc).__name__)
        return
    finally:
        conn.close()

    if raw:
        try:
            _send_link_email(norm, "Your lawapp sign-in link",
                             "Sign in to lawapp by visiting:",
                             "/pages/login.html", raw)
        except Exception:
            logger.warning("magic link email send failed.")
        audit.record_event(event_type="magic_link_issued", success=True,
                           email_attempted=norm, provider="magic_link",
                           trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)


def consume_magic_link(raw_token: str, *, ctx: RequestContext) -> SessionBundle:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            user_id = _consume_single_use_token(cur, raw_token, "magic_link")
            if not user_id:
                raise InvalidToken("Magic link is invalid or has expired.")
            # Magic link proves email control.
            cur.execute("UPDATE users SET email_verified = true, last_login_at = now() "
                        "WHERE id = %s::uuid", (user_id,))
            bundle = _issue_session(cur, user_id, amr=["magic_link"], mfa_satisfied=True, ctx=ctx)
            bundle.email_verified = True
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("magic link consume failed: %s", type(exc).__name__)
        raise AuthError("Sign-in failed.", status_code=500)
    finally:
        conn.close()

    audit.record_event(event_type="magic_link_consumed", success=True, user_id=bundle.user_id,
                       provider="magic_link", trace_id=ctx.trace_id,
                       ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    return bundle


# ── email verification ───────────────────────────────────────────────────────

def request_email_verification(email: str, *, ctx: RequestContext) -> None:
    norm = _norm_email(email)
    conn = get_connection()
    raw = None
    user_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = %s", (norm,))
            row = cur.fetchone()
            if row:
                user_id = str(row[0])
                raw = _issue_single_use_token(cur, user_id, "email_verify", _EMAIL_VERIFY_TTL)
        conn.commit()
    except Exception:
        conn.rollback()
        raw = None
    finally:
        conn.close()
    if raw:
        try:
            _send_link_email(norm, "Verify your lawapp email",
                             "Confirm your email address by visiting:",
                             "/pages/login.html", raw)
        except Exception:
            logger.warning("verification email send failed.")
        audit.record_event(event_type="email_verify_issued", success=True, user_id=user_id,
                           email_attempted=norm, trace_id=ctx.trace_id,
                           ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)


def verify_email(raw_token: str, *, ctx: RequestContext) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            user_id = _consume_single_use_token(cur, raw_token, "email_verify")
            if not user_id:
                raise InvalidToken("Verification link is invalid or has expired.")
            cur.execute("UPDATE users SET email_verified = true WHERE id = %s::uuid", (user_id,))
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("verify email failed: %s", type(exc).__name__)
        raise AuthError("Verification failed.", status_code=500)
    finally:
        conn.close()
    audit.record_event(event_type="email_verified", success=True, user_id=user_id,
                       trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    return {"verified": True, "user_id": user_id}


# ── password reset ───────────────────────────────────────────────────────────

def request_password_reset(email: str, *, ctx: RequestContext) -> None:
    """Issue a reset token. Always generic success (no enumeration)."""
    norm = _norm_email(email)
    conn = get_connection()
    raw = None
    user_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = %s", (norm,))
            row = cur.fetchone()
            if row:
                user_id = str(row[0])
                raw = _issue_single_use_token(cur, user_id, "password_reset", _PASSWORD_RESET_TTL)
        conn.commit()
    except Exception:
        conn.rollback()
        raw = None
    finally:
        conn.close()
    if raw:
        try:
            _send_link_email(norm, "Reset your lawapp password",
                             "Reset your password by visiting:",
                             "/pages/reset.html", raw)
        except Exception:
            logger.warning("password reset email send failed.")
        audit.record_event(event_type="password_reset_requested", success=True, user_id=user_id,
                           email_attempted=norm, trace_id=ctx.trace_id,
                           ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)


def confirm_password_reset(raw_token: str, new_password: str, *, ctx: RequestContext) -> None:
    try:
        validate_password_strength(new_password)
    except WeakPasswordError as exc:
        raise AuthError(str(exc), status_code=400)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            user_id = _consume_single_use_token(cur, raw_token, "password_reset")
            if not user_id:
                raise InvalidToken("Reset link is invalid or has expired.")
            cur.execute(
                "UPDATE users SET password_hash = %s, password_updated_at = now() WHERE id = %s::uuid",
                (hash_password(new_password), user_id),
            )
            # Force global re-login after a password change.
            cur.execute(
                "UPDATE auth_sessions SET revoked_at = now(), revoked_reason = 'password_reset' "
                "WHERE user_id = %s::uuid AND revoked_at IS NULL",
                (user_id,),
            )
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("password reset failed: %s", type(exc).__name__)
        raise AuthError("Password reset failed.", status_code=500)
    finally:
        conn.close()
    audit.record_event(event_type="password_reset_completed", success=True, user_id=user_id,
                       trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)


# ── OAuth (Google / Microsoft / Apple / LinkedIn) ────────────────────────────

def oauth_login(provider_name: str, id_token: str, *, ctx: RequestContext) -> SessionBundle:
    try:
        provider = get_provider(provider_name)
        identity: OAuthIdentity = provider.verify_id_token(id_token)
    except ProviderNotConfigured as exc:
        raise ProviderUnavailable(str(exc))
    except ProviderVerificationError as exc:
        audit.record_event(event_type="oauth_login", success=False, provider=provider_name,
                           trace_id=ctx.trace_id, ip_hash=ctx.ip_hash, user_agent=ctx.user_agent,
                           detail={"reason": "verification_failed"})
        raise InvalidCredentials(str(exc))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) Existing provider linkage?
            cur.execute(
                "SELECT user_id FROM oauth_identities WHERE provider = %s AND subject = %s",
                (identity.provider, identity.subject),
            )
            row = cur.fetchone()
            if row:
                user_id = str(row[0])
                cur.execute("UPDATE oauth_identities SET last_login_at = now() "
                            "WHERE provider = %s AND subject = %s",
                            (identity.provider, identity.subject))
            else:
                # 2) Link to an existing user by email, else 3) create a new user.
                user_id = None
                if identity.email:
                    cur.execute("SELECT id FROM users WHERE lower(email) = %s",
                                (identity.email.lower(),))
                    erow = cur.fetchone()
                    if erow:
                        user_id = str(erow[0])
                if user_id is None:
                    cur.execute(
                        """
                        INSERT INTO users (email, display_name, email_verified, primary_auth_provider)
                        VALUES (%s, %s, %s, %s) RETURNING id
                        """,
                        (identity.email, identity.name, identity.email_verified, identity.provider),
                    )
                    user_id = str(cur.fetchone()[0])
                cur.execute(
                    """
                    INSERT INTO oauth_identities (user_id, provider, subject, email, last_login_at)
                    VALUES (%s::uuid, %s, %s, %s, now())
                    """,
                    (user_id, identity.provider, identity.subject, identity.email),
                )

            if identity.email_verified:
                cur.execute("UPDATE users SET email_verified = true, last_login_at = now() "
                            "WHERE id = %s::uuid", (user_id,))
            else:
                cur.execute("UPDATE users SET last_login_at = now() WHERE id = %s::uuid", (user_id,))

            bundle = _issue_session(cur, user_id, amr=[identity.provider], mfa_satisfied=True, ctx=ctx)
            bundle.email_verified = identity.email_verified
        conn.commit()
    except AuthError:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("oauth login failed: %s", type(exc).__name__)
        raise AuthError("OAuth sign-in failed.", status_code=500)
    finally:
        conn.close()

    audit.record_event(event_type="oauth_login", success=True, user_id=bundle.user_id,
                       provider=identity.provider, trace_id=ctx.trace_id,
                       ip_hash=ctx.ip_hash, user_agent=ctx.user_agent)
    return bundle
