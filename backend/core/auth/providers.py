"""
OAuth / OpenID-Connect provider abstraction for the lawapp auth stack.

Single interface (`OIDCProvider.verify_id_token`) for every supported provider:

    google | microsoft | apple | linkedin

This is REAL verification, not a stub: the client obtains an OpenID-Connect
ID token from the provider (e.g. via Google Sign-In / MSAL / Sign in with Apple /
LinkedIn OIDC) and POSTs it to lawapp; the backend verifies the token's signature
against the provider's published JWKS, and validates issuer, audience (== our
client id) and expiry before trusting any identity claim.

Configuration is entirely from environment variables:

    OAUTH_GOOGLE_CLIENT_ID        (comma-separated allowed for web+native)
    OAUTH_MICROSOFT_CLIENT_ID
    OAUTH_MICROSOFT_TENANT        (optional; restricts the accepted issuer)
    OAUTH_APPLE_CLIENT_ID
    OAUTH_LINKEDIN_CLIENT_ID
    OAUTH_<PROVIDER>_JWKS_URL     (optional override of the default JWKS endpoint)

GUARDRAILS:
  * A provider with no client id configured is treated as DISABLED — its endpoint
    fails closed with 503 (ProviderNotConfigured), never a fake success.
  * Signature, issuer, audience and expiry are ALL verified. A token that fails any
    check raises ProviderVerificationError (401). No identity is trusted otherwise.
  * Facebook / Twitter-X / TikTok are deliberately NOT implemented.
  * Token values are NEVER logged.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("google", "microsoft", "apple", "linkedin")

# Explicitly unsupported (task constraint) — reject by name with a clear message.
BLOCKED_PROVIDERS = ("facebook", "twitter", "x", "tiktok")


class ProviderNotConfigured(Exception):
    """The requested provider is not configured on this server (→ 503)."""


class ProviderVerificationError(Exception):
    """The provider ID token failed verification (→ 401)."""


@dataclass
class OAuthIdentity:
    provider: str
    subject: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str]


# ── JWKS fetch cache (module-local; separate from user_auth's own-JWT cache) ──
_jwks_cache: dict[str, dict] = {}
_jwks_lock = threading.Lock()
_JWKS_TTL_SECONDS = 3600  # provider keys rotate slowly; 1h cache


def _fetch_jwks(jwks_url: str) -> list[dict]:
    """Fetch (and cache) a provider's JWKS key set. Fails closed on error."""
    with _jwks_lock:
        entry = _jwks_cache.get(jwks_url)
        if entry and time.monotonic() - entry["at"] < _JWKS_TTL_SECONDS:
            return entry["keys"]
    try:
        import httpx
        resp = httpx.get(jwks_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        if not isinstance(keys, list) or not keys:
            raise ValueError("JWKS response had no keys")
    except Exception as exc:
        logger.warning("Provider JWKS fetch failed (%s). Failing closed.", type(exc).__name__)
        raise ProviderVerificationError("Could not fetch provider signing keys.")
    with _jwks_lock:
        _jwks_cache[jwks_url] = {"keys": keys, "at": time.monotonic()}
    return keys


def _normalise_email_verified(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


@dataclass
class OIDCProvider:
    name: str
    default_jwks_url: str
    issuers: tuple[str, ...]
    client_id_env: str

    # ── configuration ────────────────────────────────────────────────────────
    def client_ids(self) -> list[str]:
        raw = os.getenv(self.client_id_env, "")
        return [c.strip() for c in raw.split(",") if c.strip()]

    def is_configured(self) -> bool:
        return bool(self.client_ids())

    def jwks_url(self) -> str:
        return os.getenv(f"OAUTH_{self.name.upper()}_JWKS_URL", "") or self.default_jwks_url

    def issuer_ok(self, iss: str) -> bool:
        return iss in self.issuers

    # ── verification ─────────────────────────────────────────────────────────
    def verify_id_token(self, id_token: str) -> OAuthIdentity:
        if not self.is_configured():
            raise ProviderNotConfigured(
                f"Provider '{self.name}' is not configured (set {self.client_id_env})."
            )

        import jwt as _jwt
        from jwt.algorithms import RSAAlgorithm, ECAlgorithm

        try:
            header = _jwt.get_unverified_header(id_token)
        except Exception:
            raise ProviderVerificationError("ID token header could not be decoded.")

        alg = header.get("alg", "")
        if alg not in ("RS256", "RS384", "RS512", "ES256", "ES384"):
            raise ProviderVerificationError(f"Unsupported token algorithm '{alg}'.")
        kid = header.get("kid")

        keys = _fetch_jwks(self.jwks_url())
        matching = [k for k in keys if not kid or k.get("kid") == kid]
        if not matching:
            raise ProviderVerificationError("No matching provider key (kid) found.")
        jwk = matching[0]

        try:
            if jwk.get("kty") == "EC":
                public_key = ECAlgorithm.from_jwk(jwk)
            else:
                public_key = RSAAlgorithm.from_jwk(jwk)
        except Exception:
            raise ProviderVerificationError("Could not construct provider public key.")

        # Verify signature + audience + expiry via pyjwt; issuer checked manually
        # (Microsoft's issuer is tenant-specific, so membership/prefix logic lives
        # in issuer_ok()).
        try:
            claims = _jwt.decode(
                id_token,
                public_key,
                algorithms=[alg],
                audience=self.client_ids(),
                options={"require": ["sub", "exp", "iss", "aud"], "verify_iss": False},
            )
        except _jwt.ExpiredSignatureError:
            raise ProviderVerificationError("Provider token has expired.")
        except _jwt.InvalidAudienceError:
            raise ProviderVerificationError("Provider token audience mismatch.")
        except _jwt.InvalidTokenError:
            raise ProviderVerificationError("Provider token verification failed.")

        iss = claims.get("iss", "")
        if not self.issuer_ok(iss):
            raise ProviderVerificationError("Provider token issuer not accepted.")

        sub = claims.get("sub")
        if not sub:
            raise ProviderVerificationError("Provider token missing 'sub'.")

        return OAuthIdentity(
            provider=self.name,
            subject=str(sub),
            email=claims.get("email"),
            email_verified=_normalise_email_verified(claims.get("email_verified")),
            name=claims.get("name") or claims.get("given_name"),
        )


class MicrosoftProvider(OIDCProvider):
    def issuer_ok(self, iss: str) -> bool:
        tenant = os.getenv("OAUTH_MICROSOFT_TENANT", "")
        if tenant:
            return iss == f"https://login.microsoftonline.com/{tenant}/v2.0"
        # Multi-tenant: accept any well-formed Microsoft v2.0 issuer.
        return (
            iss.startswith("https://login.microsoftonline.com/")
            and iss.endswith("/v2.0")
        )


_REGISTRY: dict[str, OIDCProvider] = {
    "google": OIDCProvider(
        name="google",
        default_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
        issuers=("https://accounts.google.com", "accounts.google.com"),
        client_id_env="OAUTH_GOOGLE_CLIENT_ID",
    ),
    "microsoft": MicrosoftProvider(
        name="microsoft",
        default_jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
        issuers=(),  # handled by MicrosoftProvider.issuer_ok
        client_id_env="OAUTH_MICROSOFT_CLIENT_ID",
    ),
    "apple": OIDCProvider(
        name="apple",
        default_jwks_url="https://appleid.apple.com/auth/keys",
        issuers=("https://appleid.apple.com",),
        client_id_env="OAUTH_APPLE_CLIENT_ID",
    ),
    "linkedin": OIDCProvider(
        name="linkedin",
        default_jwks_url="https://www.linkedin.com/oauth/openid/jwks",
        issuers=("https://www.linkedin.com/oauth", "https://www.linkedin.com"),
        client_id_env="OAUTH_LINKEDIN_CLIENT_ID",
    ),
}


def get_provider(name: str) -> OIDCProvider:
    key = (name or "").strip().lower()
    if key in BLOCKED_PROVIDERS:
        raise ProviderNotConfigured(
            f"Provider '{key}' is not supported by lawapp."
        )
    provider = _REGISTRY.get(key)
    if provider is None:
        raise ProviderNotConfigured(f"Unknown provider '{name}'.")
    return provider


def oidc_provider_status() -> list[dict]:
    """Per-OIDC-provider configured status, for GET /api/auth/providers."""
    return [
        {"name": p.name, "type": "oidc", "enabled": p.is_configured()}
        for p in _REGISTRY.values()
    ]
