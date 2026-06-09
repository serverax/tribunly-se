"""
/api/auth/* — the lawapp authentication API.

Thin HTTP layer over backend/core/auth/service.py. Responsibilities here:
  * parse/validate request bodies (Pydantic),
  * build a RequestContext (trace_id + hashed IP + user-agent) for audit,
  * map service AuthError → HTTPException,
  * apply per-route rate limits on sensitive endpoints,
  * echo the correlation trace_id on every response.

Endpoints:
  POST /api/auth/register        POST /api/auth/login         POST /api/auth/logout
  POST /api/auth/magic-link      GET  /api/auth/providers     POST /api/auth/refresh
  POST /api/auth/google          POST /api/auth/microsoft     POST /api/auth/apple
  POST /api/auth/linkedin        POST /api/auth/verify-email  POST /api/auth/password-reset
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core import otel as _otel
from backend.core.auth import audit, service
from backend.core.auth.providers import oidc_provider_status

router = APIRouter(prefix="/api/auth", tags=["auth"])
_ACCESS_COOKIE = "lawapp_access_token"
_REFRESH_COOKIE = "lawapp_refresh_token"

# Local limiter for sensitive endpoints. RateLimitExceeded is handled by the
# app-level handler registered in main.py.
_limiter = Limiter(key_func=get_remote_address)


# ── request models ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None
    all_sessions: bool = False


class MagicLinkRequest(BaseModel):
    email: Optional[str] = None
    token: Optional[str] = None


class OAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: Optional[str] = None
    token: Optional[str] = None
    new_password: Optional[str] = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _ctx(request: Request) -> service.RequestContext:
    client_ip = request.client.host if request.client else None
    return service.RequestContext(
        trace_id=_otel.get_request_id(),
        ip_hash=audit.hash_ip(client_ip),
        user_agent=request.headers.get("user-agent"),
    )


def _with_trace(payload: dict, ctx: service.RequestContext) -> dict:
    payload = dict(payload)
    payload["trace_id"] = ctx.trace_id
    return payload


def _handle(exc: service.AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip() or None
    return None


def _cookie_secure() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() in ("prod", "production")


def _set_session_cookies(response: Response, bundle: service.SessionBundle) -> None:
    from backend.core.auth import tokens as _tokens

    cookie_base = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "lax",
        "path": "/",
    }
    if bundle.access_token:
        response.set_cookie(
            _ACCESS_COOKIE,
            bundle.access_token,
            max_age=_tokens.access_ttl_seconds(),
            **cookie_base,
        )
    if bundle.refresh_token:
        response.set_cookie(
            _REFRESH_COOKIE,
            bundle.refresh_token,
            max_age=_tokens.refresh_ttl_seconds(),
            **cookie_base,
        )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/")


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
@_limiter.limit("10/minute")
def register(request: Request, response: Response, body: RegisterRequest) -> dict:
    ctx = _ctx(request)
    try:
        bundle = service.register(body.email, body.password, body.display_name, ctx=ctx)
    except service.AuthError as exc:
        raise _handle(exc)
    _set_session_cookies(response, bundle)
    return _with_trace(bundle.to_response(), ctx)


@router.post("/login")
@_limiter.limit("20/minute")
def login(request: Request, response: Response, body: LoginRequest) -> dict:
    ctx = _ctx(request)
    try:
        bundle = service.login_password(body.email, body.password, ctx=ctx)
    except service.AuthError as exc:
        raise _handle(exc)
    _set_session_cookies(response, bundle)
    return _with_trace(bundle.to_response(), ctx)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    body: LogoutRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    lawapp_access_token: Optional[str] = Cookie(None, alias=_ACCESS_COOKIE),
    lawapp_refresh_token: Optional[str] = Cookie(None, alias=_REFRESH_COOKIE),
) -> dict:
    ctx = _ctx(request)
    if body.all_sessions:
        token = _bearer_token(authorization) or lawapp_access_token
        if not token:
            raise HTTPException(status_code=401,
                                detail="Bearer access token required to log out all sessions.")
        from backend.core.auth import tokens as _tokens
        claims = _tokens.decode_access_token(token)  # raises 401 on bad token
        revoked = service.logout_all(str(claims["sub"]), ctx=ctx)
        _clear_session_cookies(response)
        return _with_trace({"logged_out": True, "scope": "all", "sessions_revoked": revoked}, ctx)

    refresh_token = body.refresh_token or lawapp_refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400,
                            detail="refresh_token is required (or set all_sessions=true with a Bearer token).")
    service.logout(refresh_token, ctx=ctx)
    _clear_session_cookies(response)
    return _with_trace({"logged_out": True, "scope": "session"}, ctx)


@router.post("/magic-link")
@_limiter.limit("10/minute")
def magic_link(request: Request, response: Response, body: MagicLinkRequest) -> dict:
    ctx = _ctx(request)
    # Consume path: a raw token redeems a passwordless session.
    if body.token:
        try:
            bundle = service.consume_magic_link(body.token, ctx=ctx)
        except service.AuthError as exc:
            raise _handle(exc)
        _set_session_cookies(response, bundle)
        return _with_trace(bundle.to_response(), ctx)
    # Issue path: always generic (no account enumeration). `link_sent` is always
    # true regardless of whether the address is registered — this preserves the
    # generic response (no enumeration) while giving the client a stable boolean.
    service.request_magic_link(body.email or "", ctx=ctx)
    return _with_trace(
        {"link_sent": True,
         "message": "If that email is registered, a sign-in link has been sent."}, ctx)


@router.get("/providers")
def providers(request: Request) -> dict:
    ctx = _ctx(request)
    items = [
        {"name": "email_password", "type": "password", "enabled": True,
         "login_path": "/api/auth/login"},
        {"name": "magic_link", "type": "magic_link", "enabled": True,
         "login_path": "/api/auth/magic-link"},
    ]
    for p in oidc_provider_status():
        items.append({
            "name": p["name"], "type": "oidc", "enabled": p["enabled"],
            "login_path": f"/api/auth/{p['name']}",
        })
    return _with_trace({"providers": items}, ctx)


def _oauth(request: Request, response: Response, provider_name: str, body: OAuthRequest) -> dict:
    ctx = _ctx(request)
    try:
        bundle = service.oauth_login(provider_name, body.id_token, ctx=ctx)
    except service.AuthError as exc:
        raise _handle(exc)
    _set_session_cookies(response, bundle)
    return _with_trace(bundle.to_response(), ctx)


@router.post("/google")
@_limiter.limit("30/minute")
def google(request: Request, response: Response, body: OAuthRequest) -> dict:
    return _oauth(request, response, "google", body)


@router.post("/microsoft")
@_limiter.limit("30/minute")
def microsoft(request: Request, response: Response, body: OAuthRequest) -> dict:
    return _oauth(request, response, "microsoft", body)


@router.post("/apple")
@_limiter.limit("30/minute")
def apple(request: Request, response: Response, body: OAuthRequest) -> dict:
    return _oauth(request, response, "apple", body)


@router.post("/linkedin")
@_limiter.limit("30/minute")
def linkedin(request: Request, response: Response, body: OAuthRequest) -> dict:
    return _oauth(request, response, "linkedin", body)


@router.post("/refresh")
@_limiter.limit("60/minute")
def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest,
    lawapp_refresh_token: Optional[str] = Cookie(None, alias=_REFRESH_COOKIE),
) -> dict:
    ctx = _ctx(request)
    refresh_token = body.refresh_token or lawapp_refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token is required.")
    try:
        bundle = service.refresh(refresh_token, ctx=ctx)
    except service.AuthError as exc:
        raise _handle(exc)
    _set_session_cookies(response, bundle)
    return _with_trace(bundle.to_response(), ctx)


@router.get("/me")
def me(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    lawapp_access_token: Optional[str] = Cookie(None, alias=_ACCESS_COOKIE),
) -> dict:
    ctx = _ctx(request)
    token = _bearer_token(authorization) or lawapp_access_token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from backend.core.auth import tokens as _tokens
    claims = _tokens.decode_access_token(token)
    user_id = str(claims["sub"])
    session_id = claims.get("sid")

    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if session_id:
                cur.execute(
                    """
                    SELECT 1
                      FROM auth_sessions
                     WHERE id = %s::uuid
                       AND user_id = %s::uuid
                       AND revoked_at IS NULL
                       AND expires_at > now()
                    """,
                    (session_id, user_id),
                )
                if cur.fetchone() is None:
                    raise HTTPException(status_code=401, detail="Session is no longer active")
            cur.execute(
                """
                SELECT id, email, created_at, subscription_status, display_name,
                       email_verified, role, full_name
                  FROM users
                 WHERE id = %s::uuid
                """,
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    return _with_trace(
        {
            "id": str(row[0]),
            "user_id": str(row[0]),
            "email": row[1],
            "created_at": row[2].isoformat() if row[2] else None,
            "subscription_status": row[3],
            "display_name": row[4],
            "email_verified": row[5],
            "role": row[6],
            "full_name": row[7],
        },
        ctx,
    )


@router.post("/verify-email")
def verify_email(request: Request, body: VerifyEmailRequest) -> dict:
    ctx = _ctx(request)
    try:
        result = service.verify_email(body.token, ctx=ctx)
    except service.AuthError as exc:
        raise _handle(exc)
    return _with_trace(result, ctx)


@router.post("/password-reset")
@_limiter.limit("10/minute")
def password_reset(request: Request, body: PasswordResetRequest) -> dict:
    ctx = _ctx(request)
    # Confirm path: token + new_password sets a new password.
    if body.token and body.new_password:
        try:
            service.confirm_password_reset(body.token, body.new_password, ctx=ctx)
        except service.AuthError as exc:
            raise _handle(exc)
        return _with_trace({"reset": True, "message": "Password updated. Please sign in."}, ctx)
    # Request path: always generic (no account enumeration).
    service.request_password_reset(body.email or "", ctx=ctx)
    return _with_trace(
        {"message": "If that email is registered, a password-reset link has been sent."}, ctx)
