"""
Password hashing for the lawapp auth stack.

Uses PBKDF2-HMAC-SHA256 from the Python standard library (no external crypto
dependency — bcrypt/argon2 are not in the project's dependency set). Format:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

GUARDRAILS:
  * Constant-time comparison (hmac.compare_digest) — no early-exit timing leak.
  * Per-password random salt (os.urandom).
  * Backward-compatible verification of the legacy `<salt_hex>:<hash_hex>` format
    written by the original backend/api/main.py register endpoint, so existing
    users can still log in.
  * Plaintext passwords are NEVER logged or persisted.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 240_000          # OWASP-aligned floor for PBKDF2-HMAC-SHA256
_SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 10


class WeakPasswordError(ValueError):
    """Raised when a candidate password fails the strength policy."""


def validate_password_strength(password: str) -> None:
    """
    Enforce a minimal password policy. Raises WeakPasswordError on failure.

    Policy: length >= MIN_PASSWORD_LENGTH and at least one letter and one digit.
    Deliberately conservative — magic-link / OAuth users avoid passwords entirely.
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if not any(c.isalpha() for c in password):
        raise WeakPasswordError("Password must contain at least one letter.")
    if not any(c.isdigit() for c in password):
        raise WeakPasswordError("Password must contain at least one digit.")


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    """Return an encoded PBKDF2 hash string for the given plaintext password."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def _verify_pbkdf2_encoded(password: str, encoded: str) -> bool:
    try:
        algo, iter_s, salt_hex, hash_hex = encoded.split("$", 3)
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    try:
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest.hex(), hash_hex)


def _verify_legacy_salt_colon(password: str, encoded: str) -> bool:
    # Legacy format from the original main.py: "<salt_hex>:<hash_hex>", 100k iters.
    try:
        salt_hex, hash_hex = encoded.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(digest.hex(), hash_hex)


def verify_password(password: str, encoded: str | None) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Returns False (never raises) for missing/garbage hashes or OAuth/magic-link
    users with no password set. Constant-time at the digest comparison.
    """
    if not encoded or not isinstance(encoded, str):
        return False
    if encoded.startswith(f"{_ALGO}$"):
        return _verify_pbkdf2_encoded(password, encoded)
    if ":" in encoded:
        return _verify_legacy_salt_colon(password, encoded)
    return False


def needs_rehash(encoded: str | None) -> bool:
    """True if the stored hash is legacy or below the current iteration floor."""
    if not encoded or not encoded.startswith(f"{_ALGO}$"):
        return True
    try:
        iterations = int(encoded.split("$", 3)[1])
    except (ValueError, IndexError):
        return True
    return iterations < _ITERATIONS
