"""
End-user authentication — Phase 7A.

LAWAPP_AUTH_MODE env var:
  none  (default): no auth; all case endpoints open (backward compat / dev)
  mock:            X-User-ID header; any valid UUID accepted (dev/test only)
  jwt:             Authorization: Bearer <token> — HS256 or RS256/JWKS

JWT VERIFICATION (Phase 7A):
  Algorithm routing in 'jwt' mode:
    JWT_JWKS_URL set → RS256/JWKS key discovery (Phase 7A, production-grade)
    JWT_SECRET set   → HS256 (Phase 6C, test/dev quality — not production-grade)
    Neither          → 503 (server misconfigured)

  RS256/JWKS (JWT_JWKS_URL):
    - Fetches public keys from JWKS endpoint (with 5-minute in-memory cache)
    - Selects key by kid header claim
    - Verifies: signature (RS256), exp, iss (if JWT_ISSUER), aud (if JWT_AUDIENCE)
    - Required claims: sub, exp
    - Fails closed on JWKS fetch failure, unknown kid, or algorithm mismatch
    - JWKS URL and token values NEVER logged

  HS256 (JWT_SECRET):
    - Symmetric HMAC-SHA256 verification
    - Suitable for testing and development
    - Not recommended for production (env-var key, not HSM-backed)

PRODUCTION MODE:
  RS256+JWKS is the production-grade path.
  HS256 (JWT_SECRET only) is acceptable for controlled beta, not full production.

GUARDRAILS:
  - Token values NEVER logged.
  - JWKS URL NEVER logged (may be internal).
  - Sub claim NEVER logged.
  - Fails closed (401/503) on any verification error.
  - JWKS cache never bypasses signature verification.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid as _uuid
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

JWT_REQUIRED_VARS = ["JWT_ISSUER", "JWT_AUDIENCE"]
JWT_KEY_VARS      = ["JWT_SECRET", "JWT_JWKS_URL"]

# ── JWKS key cache (thread-safe, TTL-based) ───────────────────────────────────
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_jwks_lock  = threading.Lock()
_JWKS_CACHE_TTL_SECONDS = 300   # 5 minutes


def _fetch_jwks(jwks_url: str) -> list[dict]:
    """
    Fetch JWKS public keys from the given URL.
    Caches for _JWKS_CACHE_TTL_SECONDS. Thread-safe.

    GUARDRAIL: jwks_url is NEVER logged (may be an internal URL).
    GUARDRAIL: fails closed (raises HTTPException 503) on any fetch failure.
    """
    with _jwks_lock:
        now = time.monotonic()
        if (
            _jwks_cache["keys"] is not None
            and now - _jwks_cache["fetched_at"] < _JWKS_CACHE_TTL_SECONDS
        ):
            return _jwks_cache["keys"]

    try:
        import httpx as _httpx
        resp = _httpx.get(jwks_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        keys = data.get("keys", [])
        if not isinstance(keys, list):
            raise ValueError("JWKS 'keys' field is not a list")
        with _jwks_lock:
            _jwks_cache["keys"] = keys
            _jwks_cache["fetched_at"] = time.monotonic()
        logger.debug("JWKS fetched (%d keys). (URL not logged)", len(keys))
        return keys
    except HTTPException as exc:
        if exc.status_code == 401 and "decoded" in str(exc.detail).lower():
            raise HTTPException(status_code=401, detail="Invalid token.")
        raise
    except Exception:
        logger.warning("JWKS fetch failed. Failing closed. (URL not logged)")
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch JWKS. Check JWT_JWKS_URL configuration.",
        )


def _find_jwks_key(keys: list[dict], kid: Optional[str]) -> dict:
    """
    Select the JWKS key matching the JWT header's kid.
    Fails closed (401) if kid is unknown or selection is ambiguous.
    """
    if kid:
        matching = [k for k in keys if k.get("kid") == kid]
        if not matching:
            raise HTTPException(
                status_code=401,
                detail="Unknown key ID (kid) in token header — key not found in JWKS.",
            )
        return matching[0]
    if len(keys) == 1:
        return keys[0]
    raise HTTPException(
        status_code=401,
        detail="Token has no kid and JWKS has multiple keys — cannot select unambiguously.",
    )


# ── RS256/JWKS verification ───────────────────────────────────────────────────

def _verify_jwt_rs256(token: str) -> str:
    """
    Verify a JWT using RS256 key discovery via JWKS.

    Validates: signature (RS256), exp, iss (if JWT_ISSUER set),
               aud (if JWT_AUDIENCE set), kid (JWKS key selection).
    Returns: sub claim (user identity).

    GUARDRAIL: token value, JWKS URL, and sub value are NEVER logged.
    GUARDRAIL: fails closed (401/503) on any configuration or verification error.
    """
    import jwt as _jwt
    from jwt.algorithms import RSAAlgorithm
    from jwt.exceptions import (
        ExpiredSignatureError, InvalidIssuerError, InvalidAudienceError,
        InvalidSignatureError, DecodeError, MissingRequiredClaimError,
    )

    jwks_url = os.getenv("JWT_JWKS_URL", "")
    issuer   = os.getenv("JWT_ISSUER",  "")
    audience = os.getenv("JWT_AUDIENCE", "")

    if not jwks_url:
        raise HTTPException(status_code=503, detail="JWT_JWKS_URL is not configured on this server.")

    # Parse JWT header WITHOUT signature verification to read kid and alg
    try:
        header = _jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token header could not be decoded.")

    alg = header.get("alg", "")
    supported_rs_algs = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512")
    if alg not in supported_rs_algs:
        raise HTTPException(
            status_code=401,
            detail=f"Algorithm '{alg}' not supported for JWKS path. Expected RS256/PS256.",
        )

    kid = header.get("kid")

    # Fetch JWKS and find matching key
    keys   = _fetch_jwks(jwks_url)
    jwk    = _find_jwks_key(keys, kid)

    # Convert JWK dict to RSA public key
    try:
        public_key = RSAAlgorithm.from_jwk(jwk)
    except Exception:
        logger.warning("Failed to construct RSA public key from JWK. (key details not logged)")
        raise HTTPException(status_code=503, detail="Failed to process JWKS key.")

    # Verify and decode
    required_claims = ["sub", "exp"]
    decode_kwargs: dict = {
        "algorithms": [alg],
        "options": {"require": required_claims},
    }
    if issuer:
        decode_kwargs["issuer"] = issuer
        if "iss" not in required_claims:
            required_claims.append("iss")
    if audience:
        decode_kwargs["audience"] = audience
        if "aud" not in required_claims:
            required_claims.append("aud")

    try:
        payload = _jwt.decode(token, public_key, **decode_kwargs)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid token issuer.")
    except InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid token audience.")
    except InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid token signature.")
    except MissingRequiredClaimError:
        raise HTTPException(status_code=401, detail="Token is missing required claims.")
    except DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token: could not be decoded.")
    except Exception:
        logger.warning("RS256/JWKS verification failed (details suppressed for security).")
        raise HTTPException(status_code=401, detail="Token verification failed.")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing 'sub' claim.")

    logger.debug("RS256/JWKS verification successful. (sub value not logged)")
    return str(sub)


# ── HS256 verification (Phase 6C — test/dev quality) ─────────────────────────

def _verify_jwt_hs256(token: str) -> str:
    """
    Verify a JWT using HMAC-SHA256 (HS256).

    Validates: signature, exp, iss (if JWT_ISSUER), aud (if JWT_AUDIENCE).
    Returns: sub claim.

    NOTE: HS256 with env-var key is NOT production-grade key management.
    Use JWT_JWKS_URL + RS256 for production.

    GUARDRAIL: token value and sub value are NEVER logged.
    """
    import jwt as _jwt
    from jwt.exceptions import (
        ExpiredSignatureError, InvalidIssuerError, InvalidAudienceError,
        InvalidSignatureError, DecodeError, MissingRequiredClaimError,
    )

    secret   = os.getenv("JWT_SECRET", "")
    issuer   = os.getenv("JWT_ISSUER",  "")
    audience = os.getenv("JWT_AUDIENCE", "")

    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET is not configured on this server.")

    required_claims = ["sub", "exp"]
    decode_kwargs: dict = {
        "algorithms": ["HS256"],
        "options": {"require": required_claims},
    }
    if issuer:
        decode_kwargs["issuer"] = issuer
        if "iss" not in required_claims:
            required_claims.append("iss")
    if audience:
        decode_kwargs["audience"] = audience
        if "aud" not in required_claims:
            required_claims.append("aud")

    try:
        payload = _jwt.decode(token, secret, **decode_kwargs)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid token issuer.")
    except InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid token audience.")
    except InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid token signature.")
    except MissingRequiredClaimError:
        raise HTTPException(status_code=401, detail="Token is missing required claims.")
    except DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token: could not be decoded.")
    except Exception:
        logger.warning("JWT/HS256 verification failed (details suppressed for security).")
        raise HTTPException(status_code=401, detail="Token verification failed.")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing 'sub' claim.")

    logger.debug("JWT/HS256 verification successful. (sub value not logged)")
    return str(sub)


# ── JWT dispatcher ────────────────────────────────────────────────────────────

def _verify_jwt(token: str) -> str:
    """
    Dispatch JWT verification to RS256/JWKS or HS256 based on configuration.

    Priority:
      1. JWT_JWKS_URL set → RS256/JWKS (production-grade)
      2. JWT_SECRET set   → HS256 (current auth issuer path)
      3. Neither          → 503 (server not configured)

    RS256/JWKS remains the stronger target for a later dedicated identity
    issuer. The in-repo auth service currently mints HS256 access tokens, so
    verification must accept JWT_SECRET in production deployments that use that
    issuer.
    """
    jwks_url   = os.getenv("JWT_JWKS_URL", "")
    jwt_secret = os.getenv("JWT_SECRET", "")

    if jwks_url:
        return _verify_jwt_rs256(token)
    elif jwt_secret:
        return _verify_jwt_hs256(token)
    else:
        raise HTTPException(
            status_code=503,
            detail="Neither JWT_JWKS_URL nor JWT_SECRET is configured. "
                   "Set JWT_JWKS_URL (RS256, recommended) or JWT_SECRET (HS256, dev only).",
        )


# ── Auth mode readiness checks ────────────────────────────────────────────────

def get_auth_mode() -> str:
    return os.getenv("LAWAPP_AUTH_MODE", "none").lower()


def is_auth_production_ready() -> dict:
    """
    Check if auth config is production-ready.
    Phase 7A: RS256+JWKS is production-ready. HS256-only is not.
    """
    mode     = get_auth_mode()
    blockers: list[str] = []

    if mode == "none":
        blockers.append(
            f"LAWAPP_AUTH_MODE='{mode}' is not suitable for production. "
            "Set LAWAPP_AUTH_MODE=jwt with JWT_JWKS_URL + JWT_ISSUER + JWT_AUDIENCE."
        )
    elif mode == "jwt":
        jwks_url   = os.getenv("JWT_JWKS_URL", "")
        jwt_secret = os.getenv("JWT_SECRET", "")

        if jwks_url:
            # RS256/JWKS — production-grade
            missing_base = [v for v in JWT_REQUIRED_VARS if not os.getenv(v)]
            if missing_base:
                blockers.append(f"JWT+JWKS mode requires: {missing_base}")
            # RS256+JWKS with full config IS production-ready (no stub blocker)
        elif jwt_secret:
            # HS256-only: implemented but not production-grade
            blockers.append(
                "JWT_SECRET (HS256) is configured but not production-grade. "
                "Set JWT_JWKS_URL for RS256/JWKS verification (production-grade)."
            )
        else:
            blockers.append(
                "LAWAPP_AUTH_MODE=jwt but neither JWT_JWKS_URL nor JWT_SECRET is set."
            )
    else:
        blockers.append(
            f"LAWAPP_AUTH_MODE='{mode}' is not allowed in production. "
            "Set LAWAPP_AUTH_MODE=jwt with JWT_JWKS_URL + JWT_ISSUER + JWT_AUDIENCE."
        )

    return {"ready": len(blockers) == 0, "blockers": blockers}


def is_auth_controlled_beta_ready() -> dict:
    """
    Check if auth config is acceptable for controlled beta.
    jwt (HS256 or RS256) is acceptable for beta. 'none' is not.
    """
    mode     = get_auth_mode()
    blockers: list[str] = []
    if mode == "none":
        blockers.append(
            "LAWAPP_AUTH_MODE=none: no user identity enforcement. "
            "Set LAWAPP_AUTH_MODE=jwt (production)."
        )
    return {"ready": len(blockers) == 0, "blockers": blockers}


# ── Main entry point ──────────────────────────────────────────────────────────

def get_current_user(
    x_user_id:     Optional[str] = None,
    authorization: Optional[str] = None,
) -> Optional[str]:
    """
    Extract and verify user identity from request header values.
    Takes plain string values — NOT FastAPI Header() objects.
    GUARDRAIL: user identity values are NEVER logged.
    """
    mode = get_auth_mode()

    if mode == "none":
        return None

    if mode == "jwt":
        if authorization is not None and not isinstance(authorization, str):
            authorization = None
        if not authorization:
            return None
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'.")
        token = authorization[len("Bearer "):].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Bearer token is empty.")
        return _verify_jwt(token)

    if mode == "mock":
        # TEST/DEV ONLY: trust X-User-ID as identity. Production startup REJECTS
        # mock auth (config_validation.validate_startup_config requires 'jwt'), so
        # this branch is unreachable in production — X-User-ID is never trusted there.
        if not x_user_id:
            return None
        try:
            import uuid as _uuid
            _uuid.UUID(str(x_user_id))
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(status_code=401,
                                detail="X-User-ID must be a valid UUID (mock auth, dev/test only).")
        return str(x_user_id)

    return None


def ensure_user_exists(conn, user_id: str) -> None:
    """Upsert a minimal user row for the given UUID."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id) VALUES (%s::uuid) ON CONFLICT (id) DO NOTHING",
            (user_id,),
        )


def check_admin_role(user_id: str) -> bool:
    """Return True only for users with admin role; fail closed on errors."""
    try:
        from backend.core.access import user_has_admin_role
        return user_has_admin_role(user_id)
    except Exception:
        return False


def check_case_ownership(
    case_id:        str,
    user_id:        Optional[str],
    admin_override: bool = False,
) -> None:
    """
    Verify user owns the case.
    GUARDRAIL: user IDs never logged.
    """
    if admin_override:
        return

    if user_id is None:
        # PRODUCTION (jwt) MUST NOT fall through to an unguarded read. An anonymous
        # request (no Bearer token) yields user_id=None; a bare early-return here
        # would let ANY caller read/modify ANY case by id — an RLS bypass and
        # cross-user confidentiality breach. In jwt mode we therefore fail closed
        # with 401.
        #
        # 'mock' and 'none' are dev/test-only modes (production startup REJECTS them
        # via config_validation.validate_startup_config, which requires 'jwt'); they
        # keep the legacy pass-through so the local test harness can exercise case
        # routes without forging identity. admin_override is handled above.
        if get_auth_mode() == "jwt":
            raise HTTPException(status_code=401, detail="Authentication required")
        return

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        # SCALE: the ownership check is a single read-only point lookup on cases(id)
        # (primary key). Running it in autocommit avoids opening a transaction, so the
        # request costs ONE DB round trip instead of two (no trailing ROLLBACK on
        # connection return) — halving auth-path latency on the 100k hot path.
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM cases WHERE id = %s AND deleted_at IS NULL",
                (case_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        case_owner = str(row[0]) if row[0] else None
        if case_owner and case_owner != user_id:
            logger.warning("Case ownership check failed — identity mismatch (IDs not logged).")
            raise HTTPException(
                status_code=403,
                detail="Access denied — this case belongs to a different user.",
            )
    finally:
        conn.close()


# ── JWT validation helpers ───────────────────────────────────────────────────

def validate_jwt(token: str) -> dict:
    """
    Validate a JWT token and return its claims.

    Args:
        token: JWT token string (without 'Bearer ' prefix)

    Returns:
        Decoded claims dict

    Raises:
        HTTPException (401/503) on validation failure
    """
    logger.debug("validate_jwt called")
    try:
        sub = _verify_jwt(token)
        logger.debug("validate_jwt successful")
        return {"sub": sub, "valid": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("validate_jwt failed: %s", exc)
        raise HTTPException(status_code=401, detail="Token validation failed")


def create_expired_token(secret: str, payload: dict | None = None) -> str:
    """
    Create a token with an expiration time in the past (for testing).

    Args:
        secret: JWT signing secret
        payload: Token claims dict

    Returns:
        Signed JWT token string
    """
    import jwt as _jwt
    from datetime import datetime, timedelta

    # Set expiration to 1 hour ago
    exp_time = datetime.utcnow() - timedelta(hours=1)

    if payload is None:
        payload = {"sub": secret}
        secret = os.getenv("JWT_SECRET", "test-secret")

    claims = {
        **payload,
        "exp": int(exp_time.timestamp()),
    }

    token = _jwt.encode(claims, secret, algorithm="HS256")
    logger.debug("create_expired_token: created token with exp in past")
    return token


def is_jwt_expired(token: str) -> bool:
    """
    Check if a JWT token has expired without verifying the signature.

    Args:
        token: JWT token string

    Returns:
        True if token has expired, False otherwise
    """
    import jwt as _jwt
    try:
        header = _jwt.get_unverified_header(token)
        payload = _jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if exp:
            import time
            return int(time.time()) > exp
        return False
    except Exception:
        return True  # Treat decode errors as expired
