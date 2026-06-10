"""
Envelope encryption integration layer — Phase 7E.

Provides encrypt/decrypt functions that wire the KeyProvider interface
into the existing Fernet encryption path.

Encryption with envelope (aws_kms mode):
  1. provider.generate_data_key() → (plaintext_key_transient, EncryptedKeyBundle)
  2. Fernet(plaintext_key_transient).encrypt(data) → ciphertext
  3. Store (ciphertext, bundle.to_json()) — bundle is safe; plaintext_key discarded

Decryption with envelope:
  1. Load (ciphertext, bundle_json) from storage
  2. bundle = EncryptedKeyBundle.from_json(bundle_json)
  3. provider.decrypt_data_key(bundle) → plaintext_key_transient
  4. Fernet(plaintext_key_transient).decrypt(ciphertext) → plaintext

Backward compatibility (old records without bundle):
  Records where encryption_key_metadata IS NULL were encrypted with the env key.
  safe_decrypt_* functions handle both paths.

Key rotation lifecycle (Phase 7E foundation):
  EncryptedKeyBundle already tracks: encryption_version, provider_key_id.
  Rotation: generate new data key, re-encrypt record, update bundle.
  Rotation API is Phase 7F.

GUARDRAILS:
  - Plaintext data keys are NEVER stored, logged, or returned in API responses.
  - del key is called after Fernet construction (best-effort GC in CPython).
  - Missing or malformed bundle always fails closed.
  - KMS failures fail closed (return None, not stale plaintext).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from backend.core.kms import EncryptedKeyBundle

logger = logging.getLogger(__name__)


# ── String envelope encrypt/decrypt ──────────────────────────────────────────

def envelope_encrypt_str(
    plaintext: str,
    provider,   # KeyProvider — avoiding circular import with type annotation
) -> Tuple[Optional[str], "Optional[EncryptedKeyBundle]"]:
    """
    Encrypt a UTF-8 string using envelope encryption.

    Returns (ciphertext_str, bundle) on success; (None, None) on failure.
    GUARDRAIL: plaintext_key is transient — del'd after Fernet construction.
    """
    from backend.core.kms import EncryptedKeyBundle
    from cryptography.fernet import Fernet

    key, bundle = provider.generate_data_key()
    if not key or not bundle:
        logger.warning("envelope_encrypt_str: generate_data_key failed. Failing closed.")
        return None, None
    try:
        fernet    = Fernet(key)
        ciphertext = fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return ciphertext, bundle
    except Exception:
        logger.warning("envelope_encrypt_str: Fernet encrypt failed. Failing closed.")
        return None, None
    finally:
        del key   # best-effort clear from CPython reference count


def envelope_decrypt_str(
    ciphertext: str,
    bundle_json: Optional[str],
    provider,
) -> Optional[str]:
    """
    Decrypt a string using envelope decryption.

    bundle_json: JSON-serialized EncryptedKeyBundle from storage, or None.
    Returns plaintext or None (fails closed on any error).
    GUARDRAIL: plaintext_key transient — del'd after use.
    """
    from backend.core.kms import EncryptedKeyBundle

    bundle = _parse_bundle(bundle_json)
    if bundle is None and bundle_json is not None:
        # Malformed bundle JSON — fail closed
        logger.warning("envelope_decrypt_str: malformed bundle_json. Failing closed.")
        return None

    if bundle is None or not bundle.has_kms_ciphertext():
        # No bundle (old record) or env-mode bundle (no KMS blob) → backward compat
        return _backward_compat_decrypt_str(ciphertext, provider)

    # Envelope path: decrypt via KMS
    key = provider.decrypt_data_key(bundle)
    if not key:
        logger.warning("envelope_decrypt_str: KMS decrypt_data_key failed. Failing closed.")
        return None
    try:
        from cryptography.fernet import Fernet, InvalidToken
        return Fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        logger.warning("envelope_decrypt_str: Fernet decrypt failed. Failing closed.")
        return None
    finally:
        del key


def _backward_compat_decrypt_str(ciphertext: str, provider) -> Optional[str]:
    """
    Backward compat: decrypt using direct env key (old records without bundle).
    GUARDRAIL: fails closed if env key unavailable or decryption fails.
    """
    key = provider.get_encryption_key()
    if not key:
        logger.warning("_backward_compat_decrypt_str: no encryption key available. Failing closed.")
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        logger.warning("_backward_compat_decrypt_str: decryption failed. Failing closed.")
        return None
    finally:
        del key


# ── Bytes envelope encrypt/decrypt ────────────────────────────────────────────

def envelope_encrypt_bytes(
    data: bytes,
    provider,
) -> Tuple[Optional[bytes], "Optional[EncryptedKeyBundle]"]:
    """
    Encrypt raw bytes using envelope encryption.
    Returns (ciphertext_bytes, bundle) or (None, None) on failure.
    """
    from cryptography.fernet import Fernet

    key, bundle = provider.generate_data_key()
    if not key or not bundle:
        logger.warning("envelope_encrypt_bytes: generate_data_key failed. Failing closed.")
        return None, None
    try:
        ciphertext = Fernet(key).encrypt(data)
        return ciphertext, bundle
    except Exception:
        logger.warning("envelope_encrypt_bytes: Fernet encrypt failed. Failing closed.")
        return None, None
    finally:
        del key


def envelope_decrypt_bytes(
    ciphertext: bytes,
    bundle_json: Optional[str],
    provider,
) -> Optional[bytes]:
    """
    Decrypt bytes using envelope decryption.
    Returns plaintext bytes or None (fails closed).
    """
    bundle = _parse_bundle(bundle_json)
    if bundle is None and bundle_json is not None:
        logger.warning("envelope_decrypt_bytes: malformed bundle_json. Failing closed.")
        return None

    if bundle is None or not bundle.has_kms_ciphertext():
        return _backward_compat_decrypt_bytes(ciphertext, provider)

    key = provider.decrypt_data_key(bundle)
    if not key:
        logger.warning("envelope_decrypt_bytes: KMS decrypt_data_key failed. Failing closed.")
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key).decrypt(ciphertext)
    except Exception:
        logger.warning("envelope_decrypt_bytes: Fernet decrypt failed. Failing closed.")
        return None
    finally:
        del key


def _backward_compat_decrypt_bytes(ciphertext: bytes, provider) -> Optional[bytes]:
    """Backward compat: decrypt bytes using direct env key."""
    key = provider.get_encryption_key()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key).decrypt(ciphertext)
    except Exception:
        logger.warning("_backward_compat_decrypt_bytes: decryption failed. Failing closed.")
        return None
    finally:
        del key


# ── PII helper (handoff leads) ────────────────────────────────────────────────

def decrypt_pii_field(
    encrypted_value: Optional[str],
    bundle_json: Optional[str],
    provider,
) -> Optional[str]:
    """
    Safely decrypt a single PII field from a handoff lead record.
    Returns plaintext or None (fails closed on any error).

    Handles:
      - envelope-encrypted (bundle_json present, KMS ciphertext in bundle)
      - env-key-encrypted (bundle_json absent or empty KMS blob)
      - plaintext (encrypted_value is None)
    """
    if not encrypted_value:
        return None
    if encrypted_value == "[deleted]":
        return None   # PII was cleared by Art.17 deletion
    return envelope_decrypt_str(encrypted_value, bundle_json, provider)


# ── Bundle parsing ────────────────────────────────────────────────────────────

def _parse_bundle(bundle_json: Optional[str]):
    """
    Safely parse an EncryptedKeyBundle from JSON.
    Returns None if bundle_json is None or fails to parse.
    GUARDRAIL: parse errors always return None (fail closed).
    """
    if not bundle_json:
        return None
    try:
        from backend.core.kms import EncryptedKeyBundle
        return EncryptedKeyBundle.from_json(bundle_json)
    except Exception:
        logger.warning("_parse_bundle: failed to parse EncryptedKeyBundle JSON. Failing closed.")
        return None
