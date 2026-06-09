"""
Phase 7E — Envelope encryption integration tests.

All boto3 calls are mocked — no real AWS credentials.

Tests:
  envelope_encryption module:
   1.  envelope_encrypt_str returns (ciphertext, bundle)
   2.  bundle has no plaintext key
   3.  envelope_decrypt_str recovers original (envelope path)
   4.  envelope_decrypt_str backward compat (no bundle → env key)
   5.  malformed bundle JSON fails closed
   6.  empty CiphertextBlob → backward compat path
   7.  KMS decrypt failure fails closed
   8.  envelope_encrypt_bytes / decrypt_bytes roundtrip
   9.  no key material in logs during encrypt
  10.  no key material in logs during decrypt

  Handoff lead encryption (POST /handoff/leads):
  11.  aws_kms mode: encryption_key_metadata stored in DB
  12.  aws_kms mode: bundle has no plaintext
  13.  aws_kms mode: pii_encrypted=true + encryption_method=envelope_kms
  14.  env mode: encryption_key_metadata is NULL (existing behavior unchanged)
  15.  KMS failure on encrypt → 503 fails closed (no unencrypted storage)

  Backward compatibility:
  16.  decrypt_pii_field with bundle → KMS path
  17.  decrypt_pii_field without bundle → env key path
  18.  decrypt_pii_field with malformed bundle → fails closed

  Production readiness:
  19.  key_rotation section present in report
  20.  db_schema_ready=True
  21.  production_ready still false

  Regressions:
  22.  Phase 7D tests still pass (envelope bundle behavior)
  23.  Legal accuracy gate passes
  24.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase7e_envelope_integration.py -v -s
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

_ADMIN_KEY    = "test-admin-7e"
_ADMIN_HDR    = {"X-Admin-Key": _ADMIN_KEY}
_MOCK_KMS_ARN = "arn:aws:kms:us-east-1:123456789012:key/phase7e-test-key"
_TEST_PLAINTEXT = "envelope-test-pii-value"


@pytest.fixture(scope="module", autouse=True)
def phase7e_env():
    from cryptography.fernet import Fernet
    from ingestion.db import get_connection
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "KEY_MANAGEMENT_MODE",
        "AWS_KMS_KEY_ARN", "DEPLOYMENT_MODE", "LAWAPP_AUTH_MODE",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":       _ADMIN_KEY,
        "ENCRYPTION_KEY":      Fernet.generate_key().decode(),
        "KEY_MANAGEMENT_MODE": "env",
        "DEPLOYMENT_MODE":     "development",
        "LAWAPP_AUTH_MODE":    "none",
    })
    os.environ.pop("AWS_KMS_KEY_ARN", None)

    # Ensure migration 013 columns exist
    conn = get_connection()
    try:
        with conn.cursor() as cur:
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


def _make_mock_kms_client(plaintext=None, ciphertext_blob=None):
    if plaintext is None:
        plaintext = os.urandom(32)
    if ciphertext_blob is None:
        ciphertext_blob = os.urandom(64)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": plaintext, "CiphertextBlob": ciphertext_blob,
    }
    mock_client.decrypt.return_value = {"Plaintext": plaintext}
    mock_client.describe_key.return_value = {"KeyMetadata": {}}
    return mock_client, plaintext, ciphertext_blob


# ── 1-10. envelope_encryption module ─────────────────────────────────────────

@patch("boto3.client")
def test_envelope_encrypt_str_returns_ciphertext_and_bundle(mock_boto3_client):
    mock_client, plaintext, ciphertext_blob = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, AwsKmsProvider())
        assert ct is not None and len(ct) > 0
        assert bundle is not None
        assert bundle.has_kms_ciphertext()
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_bundle_contains_no_plaintext_key(mock_boto3_client):
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, AwsKmsProvider())
        bundle_json = bundle.to_json()
        plaintext_b64 = base64.b64encode(plaintext).decode()
        assert plaintext_b64 not in bundle_json
        assert _TEST_PLAINTEXT not in bundle_json
        assert ct not in bundle_json   # ciphertext not same as plaintext
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_envelope_decrypt_str_recovers_original(mock_boto3_client):
    mock_client, plaintext, ciphertext_blob = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str, envelope_decrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, provider)
        recovered = envelope_decrypt_str(ct, bundle.to_json(), provider)
        assert recovered == _TEST_PLAINTEXT
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_envelope_decrypt_str_backward_compat_no_bundle():
    """No bundle → use env key path (old records)."""
    from backend.core.kms import EnvKeyProvider
    from backend.core.encryption import encrypt_str
    from backend.core.envelope_encryption import envelope_decrypt_str
    ct = encrypt_str(_TEST_PLAINTEXT)
    recovered = envelope_decrypt_str(ct, None, EnvKeyProvider())
    assert recovered == _TEST_PLAINTEXT


def test_malformed_bundle_json_fails_closed():
    from backend.core.kms import EnvKeyProvider
    from backend.core.envelope_encryption import envelope_decrypt_str
    from backend.core.encryption import encrypt_str
    ct = encrypt_str("test")
    result = envelope_decrypt_str(ct, '{"not_valid": true, "missing": "fields"}', EnvKeyProvider())
    assert result is None, "Malformed bundle must fail closed"


def test_empty_ciphertext_blob_uses_backward_compat():
    """EnvKeyProvider bundle (empty blob) → backward compat decrypt."""
    from backend.core.kms import EnvKeyProvider
    from backend.core.encryption import encrypt_str
    from backend.core.envelope_encryption import envelope_decrypt_str
    ct = encrypt_str(_TEST_PLAINTEXT)
    _, env_bundle = EnvKeyProvider().generate_data_key()
    recovered = envelope_decrypt_str(ct, env_bundle.to_json(), EnvKeyProvider())
    assert recovered == _TEST_PLAINTEXT


@patch("boto3.client")
def test_kms_decrypt_failure_fails_closed(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": os.urandom(32), "CiphertextBlob": os.urandom(64),
    }
    mock_client.decrypt.side_effect = Exception("InvalidCiphertextException")
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str, envelope_decrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, provider)
        result = envelope_decrypt_str(ct, bundle.to_json(), provider)
        assert result is None, "KMS decrypt failure must fail closed"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_envelope_bytes_roundtrip(mock_boto3_client):
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_bytes, envelope_decrypt_bytes
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    data = b"phase 7e binary test data"
    try:
        provider = AwsKmsProvider()
        ct, bundle = envelope_encrypt_bytes(data, provider)
        recovered = envelope_decrypt_bytes(ct, bundle.to_json(), provider)
        assert recovered == data
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_no_key_in_logs_during_encrypt(mock_boto3_client, caplog):
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        with caplog.at_level("DEBUG"):
            ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, AwsKmsProvider())
        plain_b64 = base64.b64encode(plaintext).decode()
        assert plain_b64 not in caplog.text
        if ct:
            assert _TEST_PLAINTEXT not in caplog.text
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_no_key_in_logs_during_decrypt(mock_boto3_client, caplog):
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import envelope_encrypt_str, envelope_decrypt_str
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        ct, bundle = envelope_encrypt_str(_TEST_PLAINTEXT, provider)
        with caplog.at_level("DEBUG"):
            recovered = envelope_decrypt_str(ct, bundle.to_json(), provider)
        plain_b64 = base64.b64encode(plaintext).decode()
        assert plain_b64 not in caplog.text
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


# ── 11-15. Handoff lead encryption ────────────────────────────────────────────

_HANDOFF_BODY = {
    "trigger_reason": "seek_solicitor",
    "name": "Test Envelope Person",
    "email": "envelope@test.invalid",
    "consent_given": True,
}


@patch("boto3.client")
def test_aws_kms_mode_stores_encryption_key_metadata(mock_boto3_client):
    """With aws_kms mode, encryption_key_metadata must be stored in DB."""
    from ingestion.db import get_connection
    mock_client, _, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.post("/handoff/leads", json=_HANDOFF_BODY)
        assert resp.status_code == 201
        data = resp.json()
        lead_id = data["lead_id"]

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT encryption_key_metadata FROM handoff_leads WHERE id = %s::uuid",
                    (lead_id,),
                )
                row = cur.fetchone()
            assert row is not None
            assert row[0] is not None, "encryption_key_metadata must be stored for aws_kms mode"
        finally:
            conn.close()
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_aws_kms_mode_bundle_has_no_plaintext(mock_boto3_client):
    from ingestion.db import get_connection
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.post("/handoff/leads", json=_HANDOFF_BODY)
        lead_id = resp.json()["lead_id"]
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT encryption_key_metadata FROM handoff_leads WHERE id = %s::uuid",
                    (lead_id,),
                )
                meta = cur.fetchone()[0]
        finally:
            conn.close()
        assert meta is not None
        meta_str = str(meta)
        assert "Test Envelope Person" not in meta_str
        plain_b64 = base64.b64encode(plaintext).decode()
        assert plain_b64 not in meta_str
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_aws_kms_mode_encryption_method_envelope(mock_boto3_client):
    mock_client, _, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.post("/handoff/leads", json=_HANDOFF_BODY)
        assert resp.status_code == 201
        data = resp.json()
        assert data["pii_encrypted"] is True
        assert data.get("encryption_method") == "envelope_kms"
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_env_mode_encryption_key_metadata_null():
    """Env mode: no envelope bundle — encryption_key_metadata should be NULL."""
    from ingestion.db import get_connection
    resp = client.post("/handoff/leads", json=_HANDOFF_BODY)
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("encryption_method") in ("direct_fernet", "none")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT encryption_key_metadata FROM handoff_leads WHERE id = %s::uuid",
                (data["lead_id"],),
            )
            row = cur.fetchone()
        # env mode: no envelope bundle stored
        assert row[0] is None, "Env mode must not store encryption_key_metadata"
    finally:
        conn.close()


@patch("boto3.client")
def test_kms_failure_on_encrypt_returns_503(mock_boto3_client):
    """KMS generate_data_key failure → 503, no unencrypted storage."""
    mock_client = MagicMock()
    mock_client.generate_data_key.side_effect = Exception("AccessDenied")
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.post("/handoff/leads", json=_HANDOFF_BODY)
        assert resp.status_code == 503, \
            f"KMS failure must return 503, not {resp.status_code}"
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


# ── 16-18. Backward compatibility ────────────────────────────────────────────

@patch("boto3.client")
def test_decrypt_pii_with_bundle_uses_kms(mock_boto3_client):
    mock_client, plaintext, _ = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from backend.core.envelope_encryption import (
        envelope_encrypt_str, decrypt_pii_field
    )
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        ct, bundle = envelope_encrypt_str("test-pii-value", provider)
        result = decrypt_pii_field(ct, bundle.to_json(), provider)
        assert result == "test-pii-value"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_decrypt_pii_without_bundle_uses_env_key():
    """No bundle → backward compat via env key (old records)."""
    from backend.core.kms import EnvKeyProvider
    from backend.core.encryption import encrypt_str
    from backend.core.envelope_encryption import decrypt_pii_field
    ct = encrypt_str("old-record-value")
    result = decrypt_pii_field(ct, None, EnvKeyProvider())
    assert result == "old-record-value"


def test_decrypt_pii_malformed_bundle_fails_closed():
    from backend.core.kms import EnvKeyProvider
    from backend.core.envelope_encryption import decrypt_pii_field
    result = decrypt_pii_field("some-ciphertext", '{"broken": true}', EnvKeyProvider())
    assert result is None, "Malformed bundle must fail closed"


# ── 19-21. Production readiness ───────────────────────────────────────────────

def test_readiness_has_key_rotation_section():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    assert "key_rotation" in data, "key_rotation section must be in production-readiness"


def test_key_rotation_db_schema_ready():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    kr = resp.json().get("key_rotation", {})
    assert kr.get("db_schema_ready") is True


def test_production_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["production_ready"] is False


# ── 22-24. Regressions ────────────────────────────────────────────────────────

@patch("boto3.client")
def test_phase7d_bundle_behavior_unchanged(mock_boto3_client):
    """Phase 7D EncryptedKeyBundle still serializes/deserializes correctly."""
    mock_client, plaintext, ciphertext_blob = _make_mock_kms_client()
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider, EncryptedKeyBundle
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        _, bundle = AwsKmsProvider().generate_data_key()
        assert bundle is not None
        recovered = EncryptedKeyBundle.from_json(bundle.to_json())
        assert recovered.ciphertext_blob == bundle.ciphertext_blob
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
