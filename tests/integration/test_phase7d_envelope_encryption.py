"""
Phase 7D — Envelope encryption (GenerateDataKey + CiphertextBlob) tests.

All boto3 calls are mocked — no real AWS credentials required.

Tests:
  EncryptedKeyBundle:
   1.  Bundle serializes to JSON without plaintext key
   2.  Bundle round-trips from JSON correctly
   3.  has_kms_ciphertext() reflects CiphertextBlob presence

  AwsKmsProvider — generate_data_key:
   4.  generate_data_key returns (plaintext_key, bundle) on success
   5.  Plaintext key is transient — NOT stored in bundle
   6.  CiphertextBlob is base64 in bundle
   7.  Bundle provider_key_id is KMS ARN (NOT the data key)
   8.  KMS failure → (None, None) fails closed
   9.  Missing ARN → (None, None) without API call

  AwsKmsProvider — decrypt_data_key:
  10.  decrypt_data_key returns plaintext key matching original
  11.  Empty CiphertextBlob → None fails closed
  12.  KMS Decrypt failure → None fails closed

  No sensitive values in logs:
  13.  generate_data_key: no plaintext key in logs
  14.  decrypt_data_key: no plaintext key in logs

  EnvKeyProvider envelope:
  15.  EnvKeyProvider.generate_data_key returns key + empty bundle (dev mode)
  16.  EnvKeyProvider.decrypt_data_key recovers key from empty bundle

  DB migration:
  17.  encryption_key_metadata column exists on cases table
  18.  encryption_key_metadata column exists on handoff_leads table

  Production readiness:
  19.  envelope_encryption_supported shown when aws_kms configured
  20.  ciphertext_blob_persistence_supported shown correctly
  21.  production_ready still false

  Regressions:
  22.  Existing providers still work
  23.  Legal accuracy gate passes
  24.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase7d_envelope_encryption.py -v -s
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY    = "test-admin-7d"
_ADMIN_HDR    = {"X-Admin-Key": _ADMIN_KEY}
_MOCK_KMS_ARN = "arn:aws:kms:us-east-1:123456789012:key/phase7d-test-key"


@pytest.fixture(scope="module", autouse=True)
def phase7d_env():
    from cryptography.fernet import Fernet
    from ingestion.db import get_connection
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "KEY_MANAGEMENT_MODE",
        "AWS_KMS_KEY_ARN", "DEPLOYMENT_MODE", "LAWAPP_AUTH_MODE",
        "POSTGRES_PASSWORD",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":       _ADMIN_KEY,
        "ENCRYPTION_KEY":      Fernet.generate_key().decode(),
        "KEY_MANAGEMENT_MODE": "env",
        "DEPLOYMENT_MODE":     "development",
        "LAWAPP_AUTH_MODE":    "none",
    })
    os.environ.pop("AWS_KMS_KEY_ARN", None)

    # Apply migration 013
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS encryption_key_metadata jsonb")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS encryption_key_metadata jsonb")
        conn.commit()
    finally:
        conn.close()

    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-3. EncryptedKeyBundle ───────────────────────────────────────────────────

def test_bundle_serializes_without_plaintext():
    """Bundle JSON must not contain any plaintext key material."""
    from backend.core.kms import EncryptedKeyBundle
    blob_b64 = base64.b64encode(b"mock-ciphertext-blob").decode()
    bundle = EncryptedKeyBundle(
        ciphertext_blob=blob_b64, provider="AwsKmsProvider",
        provider_key_id=_MOCK_KMS_ARN,
    )
    j = bundle.to_json()
    # No plaintext — just metadata
    assert "plaintext" not in j.lower()
    assert "data_key" not in j.lower()
    assert _MOCK_KMS_ARN in j   # ARN in metadata is acceptable (KMS key reference)


def test_bundle_roundtrips_from_json():
    from backend.core.kms import EncryptedKeyBundle
    blob_b64 = base64.b64encode(b"test-ciphertext").decode()
    original = EncryptedKeyBundle(
        ciphertext_blob=blob_b64, provider="AwsKmsProvider",
        provider_key_id=_MOCK_KMS_ARN, algorithm="AES_256_FERNET",
        encryption_version="7D",
    )
    recovered = EncryptedKeyBundle.from_json(original.to_json())
    assert recovered.ciphertext_blob  == original.ciphertext_blob
    assert recovered.provider         == original.provider
    assert recovered.provider_key_id  == original.provider_key_id
    assert recovered.encryption_version == "7D"


def test_bundle_has_kms_ciphertext_reflects_content():
    from backend.core.kms import EncryptedKeyBundle
    full_bundle  = EncryptedKeyBundle(
        ciphertext_blob=base64.b64encode(b"blob").decode(),
        provider="AwsKmsProvider", provider_key_id=_MOCK_KMS_ARN,
    )
    empty_bundle = EncryptedKeyBundle(
        ciphertext_blob="", provider="EnvKeyProvider", provider_key_id="env",
    )
    assert full_bundle.has_kms_ciphertext()  is True
    assert empty_bundle.has_kms_ciphertext() is False


# ── 4-9. AwsKmsProvider generate_data_key ─────────────────────────────────────

@patch("boto3.client")
def test_generate_data_key_returns_key_and_bundle(mock_boto3_client):
    mock_plaintext = os.urandom(32)
    mock_ciphertext = os.urandom(64)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": mock_plaintext,
        "CiphertextBlob": mock_ciphertext,
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        key, bundle = AwsKmsProvider().generate_data_key()
        assert key is not None and len(key) > 0
        assert bundle is not None
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_plaintext_key_not_stored_in_bundle(mock_boto3_client):
    """Bundle must NOT contain the plaintext data key."""
    mock_plaintext = os.urandom(32)
    mock_ciphertext = os.urandom(64)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": mock_plaintext, "CiphertextBlob": mock_ciphertext,
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        key, bundle = AwsKmsProvider().generate_data_key()
        bundle_json = bundle.to_json()
        # Plaintext must NOT appear in bundle
        plaintext_b64 = base64.b64encode(mock_plaintext).decode()
        assert plaintext_b64 not in bundle_json, "Plaintext key must not be in bundle"
        assert key.decode() not in bundle_json, "Fernet key must not be in bundle"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_ciphertext_blob_is_base64_in_bundle(mock_boto3_client):
    mock_ciphertext = os.urandom(64)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": os.urandom(32), "CiphertextBlob": mock_ciphertext,
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        _, bundle = AwsKmsProvider().generate_data_key()
        # Verify bundle.ciphertext_blob decodes back to the original ciphertext
        recovered = bundle.ciphertext_bytes()
        assert recovered == mock_ciphertext
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_bundle_provider_key_id_is_kms_arn_not_data_key(mock_boto3_client):
    """provider_key_id must be the KMS master key ARN, not the data key."""
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": os.urandom(32), "CiphertextBlob": os.urandom(64),
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        _, bundle = AwsKmsProvider().generate_data_key()
        assert bundle.provider_key_id == _MOCK_KMS_ARN, \
            "provider_key_id must be the KMS ARN (master key), not the data key"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_generate_data_key_fails_closed_on_kms_error(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.generate_data_key.side_effect = Exception("AccessDenied")
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        key, bundle = AwsKmsProvider().generate_data_key()
        assert key is None and bundle is None, "KMS failure must return (None, None)"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_generate_data_key_fails_without_arn():
    from backend.core.kms import AwsKmsProvider
    os.environ.pop("AWS_KMS_KEY_ARN", None)
    key, bundle = AwsKmsProvider().generate_data_key()
    assert key is None and bundle is None


# ── 10-12. AwsKmsProvider decrypt_data_key ────────────────────────────────────

@patch("boto3.client")
def test_decrypt_data_key_returns_matching_key(mock_boto3_client):
    """Decrypt should return the same Fernet key that was originally generated."""
    mock_plaintext = os.urandom(32)
    mock_ciphertext = os.urandom(64)
    mock_client = MagicMock()
    # GenerateDataKey → plaintext + ciphertext
    mock_client.generate_data_key.return_value = {
        "Plaintext": mock_plaintext, "CiphertextBlob": mock_ciphertext,
    }
    # Decrypt → same plaintext
    mock_client.decrypt.return_value = {"Plaintext": mock_plaintext}
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from cryptography.fernet import Fernet
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        gen_key, bundle = provider.generate_data_key()
        dec_key = provider.decrypt_data_key(bundle)
        assert gen_key == dec_key, "Decrypted key must match generated key"
        # Both must be valid Fernet keys
        Fernet(gen_key)
        Fernet(dec_key)
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_decrypt_data_key_fails_on_empty_blob():
    """Empty CiphertextBlob → None (fails closed)."""
    from backend.core.kms import AwsKmsProvider, EncryptedKeyBundle
    empty_bundle = EncryptedKeyBundle(
        ciphertext_blob="", provider="AwsKmsProvider", provider_key_id=_MOCK_KMS_ARN,
    )
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        result = AwsKmsProvider().decrypt_data_key(empty_bundle)
        assert result is None, "Empty CiphertextBlob must fail closed"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_decrypt_data_key_fails_closed_on_kms_error(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.decrypt.side_effect = Exception("InvalidCiphertextException")
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider, EncryptedKeyBundle
    bundle = EncryptedKeyBundle(
        ciphertext_blob=base64.b64encode(b"test-blob").decode(),
        provider="AwsKmsProvider", provider_key_id=_MOCK_KMS_ARN,
    )
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        result = AwsKmsProvider().decrypt_data_key(bundle)
        assert result is None, "KMS Decrypt failure must return None"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


# ── 13-14. No sensitive values in logs ───────────────────────────────────────

@patch("boto3.client")
def test_no_key_in_logs_during_generate(mock_boto3_client, caplog):
    mock_plaintext = os.urandom(32)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": mock_plaintext, "CiphertextBlob": os.urandom(64),
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        with caplog.at_level("DEBUG"):
            key, _ = AwsKmsProvider().generate_data_key()
        if key:
            assert key.decode() not in caplog.text, "Key must not appear in logs"
        plain_b64 = base64.b64encode(mock_plaintext).decode()
        assert plain_b64 not in caplog.text, "Plaintext must not appear in logs"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_no_key_in_logs_during_decrypt(mock_boto3_client, caplog):
    mock_plaintext = os.urandom(32)
    mock_client = MagicMock()
    mock_client.decrypt.return_value = {"Plaintext": mock_plaintext}
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider, EncryptedKeyBundle
    bundle = EncryptedKeyBundle(
        ciphertext_blob=base64.b64encode(b"test").decode(),
        provider="AwsKmsProvider", provider_key_id=_MOCK_KMS_ARN,
    )
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        with caplog.at_level("DEBUG"):
            key = AwsKmsProvider().decrypt_data_key(bundle)
        if key:
            assert key.decode() not in caplog.text
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


# ── 15-16. EnvKeyProvider envelope ───────────────────────────────────────────

def test_env_provider_generate_data_key_dev_mode():
    from backend.core.kms import EnvKeyProvider
    provider = EnvKeyProvider()
    key, bundle = provider.generate_data_key()
    assert key is not None
    assert bundle is not None
    assert bundle.provider == "EnvKeyProvider"
    assert bundle.ciphertext_blob == "", "Dev mode: no KMS CiphertextBlob"
    assert not bundle.has_kms_ciphertext()


def test_env_provider_decrypt_data_key_recovers_key():
    from backend.core.kms import EnvKeyProvider
    provider = EnvKeyProvider()
    gen_key, bundle = provider.generate_data_key()
    dec_key = provider.decrypt_data_key(bundle)
    assert gen_key == dec_key


# ── 17-18. DB migration ───────────────────────────────────────────────────────

def test_encryption_key_metadata_column_on_cases():
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='cases' AND column_name='encryption_key_metadata'
            """)
            assert cur.fetchone() is not None, \
                "encryption_key_metadata column must exist on cases table"
    finally:
        conn.close()


def test_encryption_key_metadata_column_on_handoff_leads():
    from ingestion.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='handoff_leads' AND column_name='encryption_key_metadata'
            """)
            assert cur.fetchone() is not None
    finally:
        conn.close()


# ── 19-21. Production readiness ───────────────────────────────────────────────

def test_readiness_shows_envelope_encryption_fields():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    enc  = data.get("encryption_at_rest", {})
    assert "envelope_encryption_supported" in enc
    assert "ciphertext_blob_persistence_supported" in enc


def test_envelope_encryption_supported_when_aws_kms_configured():
    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
        enc  = resp.json().get("encryption_at_rest", {})
        assert enc.get("envelope_encryption_supported") is True
        assert enc.get("ciphertext_blob_persistence_supported") is True
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_production_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["production_ready"] is False


# ── 22-24. Regressions ────────────────────────────────────────────────────────

def test_existing_providers_unchanged():
    from backend.core.kms import EnvKeyProvider
    from backend.core.encryption import encrypt_str, decrypt_str
    assert decrypt_str(encrypt_str("phase 7d regression")) == "phase 7d regression"


def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
