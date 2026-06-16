"""
Token minting/verification for the lawapp auth stack.

Two token families:

  1. ACCESS TOKEN  -  short-lived signed JWT (HS256). Carries the user id (sub),
     the session id (sid), and the authentication methods reference (amr). It is
     intentionally compatible with backend/core/user_auth.get_current_user so that
     existing protected routes (cases, documents, …) accept tokens minted here.

  2. REFRESH TOKEN / single-use TOKENS  -  opaque high-entropy random strings
     (secrets.token_urlsafe). The RAW value is returned to the client exactly once;
     only its SHA-256 hash is stored in the DB (auth_sessions / auth_tokens).

GUARDRAILS:
  * Signing secret read at call time from JWT_SECRET (fail closed if absent).
  * Raw token values are NEVER logged.
  * Opaque tokens use secrets (CSPRNG), not random/uuid.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import secrets
from typing import Optional

import jwt as _jwt
from fastapi import HTTPException

ACCESS_TOKEN_TYPE = "access"

_DEFAULT_ACCESS_TTL_SECONDS = 15 * 60            # 15 minutes
_DEFAULT_REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def access_ttl_seconds() -> int:
    return int(os.getenv("AUTH_ACCESS_TTL_SECONDS", str(_DEFAULT_ACCESS_TTL_SECONDS)))


def refresh_ttl_seconds() -> int:
    return int(os.getenv("AUTH_REFRESH_TTL_SECONDS", str(_DEFAULT_REFRESH_TTL_SECONDS)))


def _signing_secret() -> str:
    secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
    if not secret:
        # Fail closed  -  never mint a token under a hardcoded/guessable key.
        raise HTTPException(
            status_code=503,
            detail="Auth is not configured on this server (JWT_SECRET missing).",
        )
    return secret


def create_access_token(
    user_id: str,
    session_id: str,
    *,
    amr: Optional[list[str]] = None,
    mfa_satisfied: bool = True,
    ttl_seconds: Optional[int] = None,
) -> tuple[str, _dt.datetime]:
    """
    Mint a short-lived HS256 access JWT. Returns (token, expires_at_utc).

    Claims: sub, sid, typ=access, amr, mfa, iat, exp, and iss/aud when configured.
    """
    ttl = ttl_seconds if ttl_seconds is not None else access_ttl_seconds()
    issued = now_utc()
    expires = issued + _dt.timedelta(seconds=ttl)
    payload: dict = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": ACCESS_TOKEN_TYPE,
        "amr": amr or ["pwd"],
        "mfa": bool(mfa_satisfied),
        "iat": issued,
        "exp": expires,
    }
    issuer = os.getenv("JWT_ISSUER", "")
    audience = os.getenv("JWT_AUDIENCE", "")
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    token = _jwt.encode(payload, _signing_secret(), algorithm="HS256")
    return token, expires


def decode_access_token(token: str) -> dict:
    """
    Verify an access JWT minted by create_access_token and return its claims.

    Validates signature, exp, typ==access, and iss/aud when configured.
    Raises HTTPException(401) on any failure. Used by routes that need the sid
    (e.g. /logout)  -  ownership routes use user_auth.get_current_user instead.
    """
    issuer = os.getenv("JWT_ISSUER", "")
    audience = os.getenv("JWT_AUDIENCE", "")
    options = {"require": ["sub", "exp"]}
    kwargs: dict = {"algorithms": ["HS256"], "options": options}
    if issuer:
        kwargs["issuer"] = issuer
    if audience:
        kwargs["audience"] = audience
    try:
        claims = _jwt.decode(token, _signing_secret(), **kwargs)
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    if claims.get("typ") != ACCESS_TOKEN_TYPE:
        raise HTTPException(status_code=401, detail="Wrong token type.")
    return claims


# ── Opaque tokens (refresh / magic-link / verify / reset) ─────────────────────

def generate_opaque_token(nbytes: int = 48) -> str:
    """Return a URL-safe high-entropy opaque token (CSPRNG)."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest used as the at-rest representation of an opaque token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_expiry() -> _dt.datetime:
    return now_utc() + _dt.timedelta(seconds=refresh_ttl_seconds())


def single_use_expiry(ttl_seconds: int) -> _dt.datetime:
    return now_utc() + _dt.timedelta(seconds=ttl_seconds)
