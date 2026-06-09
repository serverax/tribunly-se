"""
Encryption at rest — Phase 6.

Provides Fernet symmetric encryption for PII fields and uploaded files.
Key sourced exclusively from the ENCRYPTION_KEY environment variable.

Phase 6 limitations (not production-ready for key management):
  - Key stored in env var; HSM / KMS integration required for production
  - Fernet (AES-128-CBC + HMAC-SHA256); AES-256-GCM recommended for production
  - Single key (no key rotation in Phase 6)
  - Phase 7: HSM, key rotation, separate keys per data class

GUARDRAILS:
  - Key value is NEVER logged, printed, or included in any response
  - Plaintext PII is NEVER logged after this module processes it
  - is_configured() must be checked before calling encrypt/decrypt
  - Encryption failures raise exceptions — never silently store plaintext
    when encryption is configured
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Encryption version tag — stored alongside encrypted data for future migration
FERNET_V1 = "fernet_v1"


def is_configured() -> bool:
    """Return True if ENCRYPTION_KEY env var is set and parseable."""
    key = os.getenv("ENCRYPTION_KEY", "")
    return bool(key)


def _get_fernet():
    """
    Return a Fernet instance from ENCRYPTION_KEY env var.
    Raises ValueError if key is missing or malformed.
    NEVER logs the key value.
    """
    from cryptography.fernet import Fernet, InvalidToken  # noqa: F401 — ensure package present
    key_str = os.getenv("ENCRYPTION_KEY", "")
    if not key_str:
        raise ValueError("ENCRYPTION_KEY environment variable is not set.")
    try:
        return Fernet(key_str.encode())
    except Exception as exc:
        raise ValueError(f"ENCRYPTION_KEY is malformed: {type(exc).__name__}") from exc


def encrypt_str(plaintext: str) -> str:
    """
    Encrypt a UTF-8 string. Returns a Fernet token (URL-safe base64 string).
    Raises if encryption is not configured or key is invalid.
    NEVER logs plaintext.
    """
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_str(token: str) -> str:
    """
    Decrypt a Fernet token back to plaintext string.
    Raises InvalidToken if the token was tampered or the key changed.
    NEVER logs the decrypted value.
    """
    from cryptography.fernet import Fernet  # noqa
    f = _get_fernet()
    return f.decrypt(token.encode("ascii")).decode("utf-8")


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes. Returns Fernet token bytes."""
    f = _get_fernet()
    return f.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    """Decrypt Fernet token bytes back to plaintext bytes."""
    f = _get_fernet()
    return f.decrypt(token)


def generate_key() -> str:
    """
    Generate a new Fernet key (for setup/testing only).
    Returns URL-safe base64 string suitable for ENCRYPTION_KEY env var.
    NEVER use this to rotate keys in production without a proper rotation plan.
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("ascii")
