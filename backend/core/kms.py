"""
Key Management Service abstraction  -  Phase 7D.

Provides a KeyProvider interface with concrete implementations and full
envelope encryption support:

  EnvKeyProvider    -  reads ENCRYPTION_KEY from env var (dev/test, not production-grade)
  KmsStubProvider   -  represents a real KMS key reference; Phase 7B stub (no real API call)
  AwsKmsProvider    -  real AWS KMS via boto3; full envelope encryption (Phase 7D)
  DisabledProvider  -  no encryption; development only

Envelope Encryption (Phase 7D):
  1. generate_data_key() calls KMS.GenerateDataKey → (plaintext_key, EncryptedKeyBundle)
     - plaintext_key: use transiently for encryption ONLY  -  NEVER log, store, or return
     - EncryptedKeyBundle: safe to persist (contains CiphertextBlob encrypted by KMS)
  2. decrypt_data_key(bundle) calls KMS.Decrypt(CiphertextBlob) → plaintext_key
     - Used for decryption path
     - Returned plaintext_key: use transiently  -  NEVER log or store

  EncryptedKeyBundle fields (all safe to persist):
    ciphertext_blob:     base64-encoded CiphertextBlob from KMS (NOT the plaintext key)
    provider:            KeyProvider class name
    provider_key_id:     KMS key ARN (identifies the master key, NOT the data key)
    algorithm:           encryption algorithm
    encryption_version:  schema version

GUARDRAILS:
  - Plaintext data keys are NEVER logged, stored in DB, or returned in API responses.
  - CiphertextBlob values are NEVER logged (could expose key topology).
  - AWS KMS ARNs are NEVER logged (internal infrastructure reference).
  - AWS credentials are NEVER logged or committed.
  - Failures always fail closed (return None, never skip encryption).
"""

from __future__ import annotations

import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ── EncryptedKeyBundle ────────────────────────────────────────────────────────

@dataclass
class EncryptedKeyBundle:
    """
    Metadata about an envelope-encrypted data key.
    SAFE to persist (plaintext data key is NOT included).

    ciphertext_blob:     base64-encoded KMS CiphertextBlob (encrypted data key)
    provider:            KeyProvider name (e.g. 'AwsKmsProvider')
    provider_key_id:     KMS master key ARN or 'env' for dev mode
    algorithm:           data encryption algorithm
    encryption_version:  schema version for future migration

    GUARDRAIL: plaintext data key is NEVER included here.
    """
    ciphertext_blob:     str
    provider:            str
    provider_key_id:     str
    algorithm:           str = "AES_256_FERNET"
    encryption_version:  str = "7D"

    def to_json(self) -> str:
        """Serialize for safe DB storage. Never includes plaintext key."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "EncryptedKeyBundle":
        return cls(**json.loads(s))

    def ciphertext_bytes(self) -> bytes:
        """Return raw CiphertextBlob bytes. Empty bytes if none (env mode)."""
        if not self.ciphertext_blob:
            return b""
        return base64.b64decode(self.ciphertext_blob)

    def has_kms_ciphertext(self) -> bool:
        """True if this bundle contains a real KMS-encrypted data key."""
        return bool(self.ciphertext_blob)


# ── KeyProvider interface ─────────────────────────────────────────────────────

class KeyProvider(ABC):
    """Abstract base for all key providers."""

    @abstractmethod
    def get_encryption_key(self) -> Optional[bytes]:
        """Return key bytes or None. GUARDRAIL: key material never logged."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if a key is accessible."""

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    def is_production_grade(self) -> bool:
        """True only if this provider meets production security requirements."""

    def health_check(self) -> bool:
        """Test live provider connectivity. Default: not applicable."""
        return False

    # ── Phase 7D: envelope encryption methods ────────────────────────────────

    def generate_data_key(self) -> Tuple[Optional[bytes], Optional[EncryptedKeyBundle]]:
        """
        Generate a new data key for envelope encryption.

        Returns:
          (plaintext_key, bundle)  -  both non-None on success.
          (None, None)  -  on failure.

        CALLER CONTRACT:
          - Use plaintext_key TRANSIENTLY for encryption ONLY.
          - NEVER log, store, or return plaintext_key.
          - Persist bundle (safe  -  contains CiphertextBlob, not plaintext).

        Default: not supported by this provider.
        """
        logger.warning("%s.generate_data_key(): not supported by this provider.", self.provider_name())
        return None, None

    def decrypt_data_key(self, bundle: EncryptedKeyBundle) -> Optional[bytes]:
        """
        Decrypt a CiphertextBlob to recover the plaintext data key.

        CALLER CONTRACT:
          - Use returned key TRANSIENTLY for decryption ONLY.
          - NEVER log or store the returned bytes.

        Default: not supported by this provider.
        """
        logger.warning("%s.decrypt_data_key(): not supported by this provider.", self.provider_name())
        return None

    def supports_envelope_encryption(self) -> bool:
        """True if generate_data_key / decrypt_data_key are implemented."""
        return False

    def status(self, run_health_check: bool = False) -> dict:
        """Return structured status dict for production-readiness reporting."""
        connected: object = "N/A"
        if run_health_check:
            connected = self.health_check()
        return {
            "provider":                        self.provider_name(),
            "available":                       self.is_available(),
            "production_grade":                self.is_production_grade(),
            "kms_connected":                   connected,
            "envelope_encryption_supported":   self.supports_envelope_encryption(),
            "ciphertext_blob_persistence":     self.supports_envelope_encryption(),
        }


# ── EnvKeyProvider ────────────────────────────────────────────────────────────

class EnvKeyProvider(KeyProvider):
    """
    Reads ENCRYPTION_KEY from env var. NOT production-grade.
    Phase 7D: implements generate_data_key / decrypt_data_key in dev mode.
    No real KMS  -  CiphertextBlob is empty (envelope encryption is simulated).
    """

    def get_encryption_key(self) -> Optional[bytes]:
        key_str = os.getenv("ENCRYPTION_KEY", "")
        if not key_str:
            return None
        try:
            from cryptography.fernet import Fernet
            Fernet(key_str.encode())
            return key_str.encode()
        except Exception:
            logger.error("ENCRYPTION_KEY is malformed. (value not logged)")
            return None

    def generate_data_key(self) -> Tuple[Optional[bytes], Optional[EncryptedKeyBundle]]:
        """Dev mode: use env key as data key; no real KMS CiphertextBlob."""
        key = self.get_encryption_key()
        if not key:
            return None, None
        bundle = EncryptedKeyBundle(
            ciphertext_blob="",   # empty  -  no KMS encryption of data key in dev mode
            provider=self.provider_name(),
            provider_key_id="env",
        )
        logger.debug("EnvKeyProvider.generate_data_key(): using env key (dev mode, value not logged).")
        return key, bundle

    def decrypt_data_key(self, bundle: EncryptedKeyBundle) -> Optional[bytes]:
        """Dev mode: return env key (no KMS decryption needed)."""
        if bundle.provider not in ("EnvKeyProvider", "env"):
            logger.warning("EnvKeyProvider.decrypt_data_key(): bundle provider mismatch.")
            return None
        return self.get_encryption_key()

    def supports_envelope_encryption(self) -> bool:
        return True   # dev mode  -  simulated (no real KMS blob)

    def is_available(self) -> bool:
        return bool(os.getenv("ENCRYPTION_KEY"))

    def provider_name(self) -> str:
        return "EnvKeyProvider"

    def is_production_grade(self) -> bool:
        return False

    def status(self, run_health_check: bool = False) -> dict:
        base = super().status(run_health_check)
        base["note"] = (
            "env var key  -  not production-grade. "
            "Envelope encryption simulated (no real KMS CiphertextBlob)."
        )
        return base


# ── KmsStubProvider (Phase 7B, preserved) ────────────────────────────────────

class KmsStubProvider(KeyProvider):
    """Phase 7B stub  -  no real KMS API call. Phase 7C/7D: use AwsKmsProvider."""

    def get_encryption_key(self) -> Optional[bytes]:
        if not os.getenv("KMS_KEY_ID"):
            return None
        logger.warning("KmsStubProvider: using env key (stub  -  value not logged).")
        return EnvKeyProvider().get_encryption_key()

    def is_available(self) -> bool:
        return bool(os.getenv("KMS_KEY_ID"))

    def provider_name(self) -> str:
        return "KmsStubProvider"

    def is_production_grade(self) -> bool:
        return bool(os.getenv("KMS_KEY_ID"))

    @property
    def kms_connected(self) -> bool:
        return False

    def status(self, run_health_check: bool = False) -> dict:
        base = super().status(run_health_check)
        base.update({
            "kms_key_id_configured": bool(os.getenv("KMS_KEY_ID")),
            "kms_connected":         False,
            "note": "Phase 7B stub: KMS_KEY_ID configured; no real API call. Use aws_kms mode.",
        })
        return base


# ── AwsKmsProvider (Phase 7C/7D  -  full implementation) ───────────────────────

class AwsKmsProvider(KeyProvider):
    """
    AWS KMS provider  -  full envelope encryption support (Phase 7D).

    Required:
      AWS_KMS_KEY_ARN  -  KMS key ARN
    Optional:
      KMS_REGION / AWS_DEFAULT_REGION  -  AWS region (default: us-east-1)
    AWS credentials via standard chain (NEVER stored in repo).

    Phase 7D operations:
      generate_data_key(): KMS.GenerateDataKey → (plaintext_key, EncryptedKeyBundle)
      decrypt_data_key(bundle): KMS.Decrypt(CiphertextBlob) → plaintext_key

    GUARDRAILS:
      - Plaintext data keys NEVER logged, stored, or returned in API.
      - CiphertextBlob values NEVER logged.
      - AWS credentials NEVER logged.
    """

    _BOTO3_IMPORT_ERROR = "boto3 required for aws_kms mode. Install: pip install boto3>=1.34"

    def _get_client(self):
        try:
            import boto3
        except ImportError:
            raise RuntimeError(self._BOTO3_IMPORT_ERROR)
        region = (
            os.getenv("KMS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        return boto3.client("kms", region_name=region)

    # ── Phase 7D: envelope encryption ────────────────────────────────────────

    def generate_data_key(self) -> Tuple[Optional[bytes], Optional[EncryptedKeyBundle]]:
        """
        Generate a new envelope-encrypted data key.
        Returns (plaintext_key, bundle). Both None on failure.

        GUARDRAIL: plaintext_key is transient  -  NEVER log, store, or return.
        GUARDRAIL: CiphertextBlob in bundle is safe to persist.
        """
        key_arn = os.getenv("AWS_KMS_KEY_ARN", "")
        if not key_arn:
            logger.error("AwsKmsProvider.generate_data_key(): AWS_KMS_KEY_ARN not set.")
            return None, None
        try:
            client = self._get_client()
            resp = client.generate_data_key(KeyId=key_arn, KeySpec="AES_256")
            plaintext:       bytes = resp["Plaintext"]
            ciphertext_blob: bytes = resp["CiphertextBlob"]

            # Derive Fernet key from plaintext (transient)
            fernet_key = base64.urlsafe_b64encode(plaintext[:32])

            # Bundle: safe to persist (CiphertextBlob + metadata, NO plaintext)
            bundle = EncryptedKeyBundle(
                ciphertext_blob=base64.b64encode(ciphertext_blob).decode("ascii"),
                provider=self.provider_name(),
                provider_key_id=key_arn,   # master key ARN (not data key!)
            )
            logger.debug("AwsKmsProvider.generate_data_key(): data key generated. (values not logged)")
            return fernet_key, bundle
        except RuntimeError:
            raise
        except Exception:
            logger.warning("AwsKmsProvider.generate_data_key(): failed. Failing closed.")
            return None, None

    def decrypt_data_key(self, bundle: EncryptedKeyBundle) -> Optional[bytes]:
        """
        Decrypt a CiphertextBlob to recover the plaintext data key.
        Returns plaintext_key (transient) or None on failure.

        GUARDRAIL: returned key is transient  -  NEVER log or store.
        GUARDRAIL: CiphertextBlob not logged.
        """
        if not bundle.has_kms_ciphertext():
            logger.error("AwsKmsProvider.decrypt_data_key(): bundle has no CiphertextBlob.")
            return None
        try:
            client = self._get_client()
            ciphertext = bundle.ciphertext_bytes()
            resp = client.decrypt(CiphertextBlob=ciphertext)
            plaintext: bytes = resp["Plaintext"]
            fernet_key = base64.urlsafe_b64encode(plaintext[:32])
            logger.debug("AwsKmsProvider.decrypt_data_key(): decryption succeeded. (value not logged)")
            return fernet_key
        except RuntimeError:
            raise
        except Exception:
            logger.warning("AwsKmsProvider.decrypt_data_key(): failed. Failing closed.")
            return None

    def supports_envelope_encryption(self) -> bool:
        return bool(os.getenv("AWS_KMS_KEY_ARN"))

    # ── Phase 7C: backward compat ─────────────────────────────────────────────

    def get_encryption_key(self) -> Optional[bytes]:
        """
        Backward-compat: generate a key via KMS (no CiphertextBlob persisted).
        Phase 7D: prefer generate_data_key() for new operations.
        """
        key, _ = self.generate_data_key()
        return key

    def health_check(self) -> bool:
        key_arn = os.getenv("AWS_KMS_KEY_ARN", "")
        if not key_arn:
            return False
        try:
            client = self._get_client()
            client.describe_key(KeyId=key_arn)
            logger.debug("AwsKmsProvider.health_check(): reachable. (ARN not logged)")
            return True
        except Exception:
            logger.warning("AwsKmsProvider.health_check(): failed. (ARN not logged)")
            return False

    def is_available(self) -> bool:
        return bool(os.getenv("AWS_KMS_KEY_ARN"))

    def provider_name(self) -> str:
        return "AwsKmsProvider"

    def is_production_grade(self) -> bool:
        return bool(os.getenv("AWS_KMS_KEY_ARN"))

    def status(self, run_health_check: bool = False) -> dict:
        base = super().status(run_health_check=run_health_check)
        connected = base.get("kms_connected")
        if run_health_check:
            connected = self.health_check()
        base.update({
            "provider_configured":             bool(os.getenv("AWS_KMS_KEY_ARN")),
            "aws_region_configured":           bool(
                os.getenv("KMS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            ),
            "kms_connected":                   connected,
            "envelope_encryption_supported":   self.supports_envelope_encryption(),
            "ciphertext_blob_persistence":     (
                "IMPLEMENTED" if self.supports_envelope_encryption() else "NOT_CONFIGURED"
            ),
            "note": "Phase 7D: full envelope encryption (GenerateDataKey + Decrypt).",
        })
        return base


# ── DisabledProvider ──────────────────────────────────────────────────────────

class DisabledProvider(KeyProvider):
    """No encryption. Development/testing only. Production blocker."""

    def get_encryption_key(self) -> Optional[bytes]:
        logger.warning("DisabledProvider: encryption OFF. (dev only)")
        return None

    def is_available(self) -> bool:
        return False

    def provider_name(self) -> str:
        return "DisabledProvider"

    def is_production_grade(self) -> bool:
        return False

    def status(self, run_health_check: bool = False) -> dict:
        base = super().status(run_health_check)
        base["note"] = "Encryption disabled. Development/testing only. Production blocker."
        return base


# ── Factory ───────────────────────────────────────────────────────────────────

def get_key_management_mode() -> str:
    return os.getenv("KEY_MANAGEMENT_MODE", "env").lower()


def get_key_provider() -> KeyProvider:
    mode = get_key_management_mode()
    if mode == "aws_kms":
        return AwsKmsProvider()
    elif mode == "kms_stub":
        return KmsStubProvider()
    elif mode == "disabled":
        return DisabledProvider()
    else:
        return EnvKeyProvider()


def is_production_grade_key_management() -> bool:
    return get_key_provider().is_production_grade()


def get_encryption_key() -> Optional[bytes]:
    return get_key_provider().get_encryption_key()


def get_kms_status(run_health_check: bool = False) -> dict:
    provider = get_key_provider()
    status   = provider.status(run_health_check=run_health_check)
    status["mode"] = get_key_management_mode()
    return status
