"""
Startup configuration validation — Phase 6C.

Validates required environment variables at startup.
Also provides static analysis (no server needed) for CI production-readiness check.

In DEPLOYMENT_MODE=development (default): warns about missing vars, does NOT fail.
In DEPLOYMENT_MODE=production: raises StartupConfigError if required vars missing.

GUARDRAIL: Never log the values of secrets, only their names.
GUARDRAIL: Call validate_startup_config() in the FastAPI lifespan handler.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ── Required vars for production deployment ───────────────────────────────────
REQUIRED_PRODUCTION_VARS: list[str] = [
    "POSTGRES_PASSWORD",    # database auth
    "ADMIN_API_KEY",        # admin endpoint protection
    "ENCRYPTION_KEY",       # PII encryption at rest
    "APP_BASE_URL",         # application base URL for CORS/redirects
]

# JWT config required when LAWAPP_AUTH_MODE=jwt in production
JWT_REQUIRED_VARS: list[str] = ["JWT_ISSUER", "JWT_AUDIENCE"]
JWT_KEY_VARS:     list[str] = ["JWT_SECRET", "JWT_JWKS_URL"]

# Recommended in production
RECOMMENDED_PRODUCTION_VARS: list[str] = [
    "SECRET_KEY",           # future JWT signing
    "LAWAPP_LLM_PROVIDER",  # must be ollama_local — local Ollama only, no external LLM
    "ALLOWED_ORIGINS",      # CORS config
    "DATABASE_URL",         # alternative DB connection string
]

VALID_PAYMENT_MODES = frozenset({"disabled", "test", "stripe", "stripe_test", "stripe_live"})
VALID_AUTH_MODES    = frozenset({"none", "jwt"})
VALID_KMS_MODES     = frozenset({"env", "kms_stub", "disabled"})


class StartupConfigError(Exception):
    """Raised when production config is incomplete."""


def validate_startup_config(fail_fast: bool = True) -> dict:
    """
    Validate environment variables for the current deployment mode.

    Args:
        fail_fast: if True and in production mode, raise StartupConfigError.
                   If False (test/CI mode), return result dict without raising.

    Returns:
        {"status": "OK"|"FAILED"|"WARNING", "missing": [...], "warnings": [...], ...}
    """
    deployment_mode = os.getenv("DEPLOYMENT_MODE", "development").lower()
    payment_mode    = os.getenv("PAYMENT_MODE", "disabled").lower()  # safe default — never test_simulator
    auth_mode       = os.getenv("LAWAPP_AUTH_MODE", "none").lower()
    kms_mode        = os.getenv("KEY_MANAGEMENT_MODE", "env").lower()

    missing_required: list[str] = []
    missing_recommended: list[str] = []
    warnings: list[str] = []

    # Required vars check
    for var in REQUIRED_PRODUCTION_VARS:
        if not os.getenv(var):
            missing_required.append(var)

    # Recommended vars
    for var in RECOMMENDED_PRODUCTION_VARS:
        if not os.getenv(var):
            missing_recommended.append(var)

    # Auth mode validation
    if auth_mode not in VALID_AUTH_MODES:
        warnings.append(f"LAWAPP_AUTH_MODE='{auth_mode}' invalid. Valid: {sorted(VALID_AUTH_MODES)}")

    if deployment_mode == "production":
        # Production REQUIRES jwt. mock/none/invalid are blocked → fail-to-start.
        # This guarantees X-User-ID is never trusted as identity in production
        # (mock is the only mode that trusts X-User-ID, and it is test/dev only).
        if auth_mode != "jwt":
            missing_required.append(
                f"LAWAPP_AUTH_MODE='{auth_mode}' not allowed in production — requires 'jwt' "
                "(mock/none/invalid auth modes are blocked: no X-User-ID trust in production)"
            )
        if auth_mode == "jwt":
            missing_jwt = [v for v in JWT_REQUIRED_VARS if not os.getenv(v)]
            if missing_jwt:
                missing_required.extend(missing_jwt)
            if not any(os.getenv(v) for v in JWT_KEY_VARS):
                missing_required.append(f"JWT_SECRET or JWT_JWKS_URL (one required)")

        # KMS mode validation in production
        if kms_mode == "env":
            warnings.append(
                "KEY_MANAGEMENT_MODE=env: env-var key is not production-grade. "
                "Use kms_stub or real KMS (Phase 7)."
            )
        if kms_mode == "disabled":
            missing_required.append(
                "KEY_MANAGEMENT_MODE=disabled not allowed in production — encryption required."
            )
        if kms_mode == "kms_stub" and not os.getenv("KMS_KEY_ID"):
            missing_required.append(
                "KMS_KEY_ID (required for KEY_MANAGEMENT_MODE=kms_stub in production)"
            )
        if kms_mode == "aws_kms" and not os.getenv("AWS_KMS_KEY_ARN"):
            missing_required.append(
                "AWS_KMS_KEY_ARN (required for KEY_MANAGEMENT_MODE=aws_kms — "
                "e.g. arn:aws:kms:us-east-1:123456789012:key/key-id)"
            )
        # AWS credential validation is handled by boto3 at runtime (not here).

        # Payment mode
        if payment_mode not in VALID_PAYMENT_MODES:
            warnings.append(f"PAYMENT_MODE='{payment_mode}' invalid.")
        if payment_mode not in ("stripe", "stripe_live"):
            missing_required.append(
                f"PAYMENT_MODE='{payment_mode}' not allowed in production — requires 'stripe' or 'stripe_live'"
            )
        if payment_mode in ("stripe", "stripe_live"):
            if not os.getenv("STRIPE_SECRET_KEY"):
                missing_required.append("STRIPE_SECRET_KEY (required for production Stripe payments)")
            if not os.getenv("STRIPE_WEBHOOK_SECRET"):
                missing_required.append("STRIPE_WEBHOOK_SECRET (required for production Stripe webhooks)")

    # Logging — names only, never values
    if missing_required:
        if deployment_mode == "production":
            logger.critical("STARTUP FAILED: Missing required production vars: %s", missing_required)
        else:
            logger.warning("Missing production vars (OK in %s mode): %s", deployment_mode, missing_required)

    status = "OK" if not missing_required else ("FAILED" if deployment_mode == "production" else "WARNING")

    result = {
        "status":              status,
        "deployment_mode":     deployment_mode,
        "payment_mode":        payment_mode,
        "auth_mode":           auth_mode,
        "kms_mode":            kms_mode,
        "missing_required":    missing_required,
        "missing_recommended": missing_recommended,
        "warnings":            warnings,
    }

    if fail_fast and deployment_mode == "production" and missing_required:
        raise StartupConfigError(
            f"Production startup failed — missing/invalid: {missing_required}"
        )

    return result
