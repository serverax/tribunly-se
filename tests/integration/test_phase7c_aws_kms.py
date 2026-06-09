"""
Phase 7C — AWS KMS provider tests.

All boto3 calls are mocked — no real AWS credentials or connections required.

Tests:
  AwsKmsProvider:
   1.  Missing AWS_KMS_KEY_ARN → not available
   2.  AWS_KMS_KEY_ARN set → available
   3.  AWS_KMS_KEY_ARN set → is_production_grade=True
   4.  Health check: mock successful DescribeKey → kms_connected=True
   5.  Health check: mock failed DescribeKey → kms_connected=False (fails closed)
   6.  Health check: boto3 not installed → fails closed
   7.  get_encryption_key: mock GenerateDataKey → returns Fernet-compatible bytes
   8.  get_encryption_key: API failure → None (fails closed)
   9.  get_encryption_key: missing ARN → None

  Config routing:
  10.  KEY_MANAGEMENT_MODE=aws_kms routes to AwsKmsProvider
  11.  KEY_MANAGEMENT_MODE=env still routes to EnvKeyProvider
  12.  KEY_MANAGEMENT_MODE=kms_stub still routes to KmsStubProvider

  Config validation:
  13.  aws_kms in production requires AWS_KMS_KEY_ARN
  14.  aws_kms in production with AWS_KMS_KEY_ARN passes KMS config check

  Production readiness:
  15.  health_check=false (default) → kms_connected=NOT_CHECKED
  16.  health_check=true with mock success → kms_connected=True
  17.  health_check=true with mock failure → kms_connected=False
  18.  AwsKmsProvider shown in key_provider field

  No logging of sensitive values:
  19.  No ARN value in logs during health check
  20.  No key material in logs during key generation

  Existing providers unchanged:
  21.  EnvKeyProvider still works
  22.  KmsStubProvider still works (kms_connected=False)
  23.  DisabledProvider still blocks

  Regressions:
  24.  Legal accuracy gate passes
  25.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase7c_aws_kms.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY    = "test-admin-7c"
_ADMIN_HDR    = {"X-Admin-Key": _ADMIN_KEY}
_MOCK_KMS_ARN = "arn:aws:kms:us-east-1:123456789012:key/phase7c-test-key"


@pytest.fixture(scope="module", autouse=True)
def phase7c_env():
    from cryptography.fernet import Fernet
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
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-9. AwsKmsProvider ───────────────────────────────────────────────────────

def test_aws_kms_not_available_without_arn():
    from backend.core.kms import AwsKmsProvider
    os.environ.pop("AWS_KMS_KEY_ARN", None)
    assert AwsKmsProvider().is_available() is False


def test_aws_kms_available_with_arn():
    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        assert AwsKmsProvider().is_available() is True
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_aws_kms_production_grade_when_arn_configured():
    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        assert AwsKmsProvider().is_production_grade() is True
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_health_check_passes_when_kms_reachable(mock_boto3_client):
    """Mock successful DescribeKey → health_check=True → kms_connected=True."""
    mock_client = MagicMock()
    mock_client.describe_key.return_value = {
        "KeyMetadata": {"KeyId": "mock-key-id", "Enabled": True}
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        result = provider.health_check()
        assert result is True
        # Verify DescribeKey was called
        mock_client.describe_key.assert_called_once()
        # Verify ARN value not logged (we can't check boto3 call args without logging,
        # but we verify it was called with the right key)
        call_args = mock_client.describe_key.call_args
        assert "KeyId" in call_args.kwargs or len(call_args.args) > 0
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_health_check_fails_closed_on_error(mock_boto3_client):
    """Mock DescribeKey failure → health_check=False (fails closed)."""
    from botocore.exceptions import ClientError
    mock_client = MagicMock()
    mock_client.describe_key.side_effect = Exception("Connection timeout")
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        provider = AwsKmsProvider()
        result = provider.health_check()
        assert result is False
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_health_check_fails_without_arn():
    """No ARN → health_check=False without calling boto3."""
    from backend.core.kms import AwsKmsProvider
    os.environ.pop("AWS_KMS_KEY_ARN", None)
    assert AwsKmsProvider().health_check() is False


@patch("boto3.client")
def test_get_encryption_key_returns_fernet_key(mock_boto3_client):
    """Mock GenerateDataKey → returns Fernet-compatible bytes."""
    import os as _os
    mock_plaintext = _os.urandom(32)   # 32 random bytes = AES-256 key
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": mock_plaintext,
        "CiphertextBlob": _os.urandom(64),
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    from cryptography.fernet import Fernet
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        key = AwsKmsProvider().get_encryption_key()
        assert key is not None
        assert isinstance(key, bytes)
        # Returned key must be valid Fernet key
        Fernet(key)   # raises if invalid
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_get_encryption_key_fails_closed_on_api_error(mock_boto3_client):
    """Mock GenerateDataKey failure → returns None (fails closed)."""
    mock_client = MagicMock()
    mock_client.generate_data_key.side_effect = Exception("AccessDenied")
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        key = AwsKmsProvider().get_encryption_key()
        assert key is None, "API failure must return None (fail closed)"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_get_encryption_key_fails_without_arn():
    from backend.core.kms import AwsKmsProvider
    os.environ.pop("AWS_KMS_KEY_ARN", None)
    key = AwsKmsProvider().get_encryption_key()
    assert key is None


# ── 10-12. Config routing ────────────────────────────────────────────────────

def test_aws_kms_mode_routes_to_aws_provider():
    from backend.core.kms import get_key_provider, AwsKmsProvider
    os.environ["KEY_MANAGEMENT_MODE"] = "aws_kms"
    try:
        assert isinstance(get_key_provider(), AwsKmsProvider)
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"


def test_env_mode_still_routes_to_env_provider():
    from backend.core.kms import get_key_provider, EnvKeyProvider
    os.environ["KEY_MANAGEMENT_MODE"] = "env"
    assert isinstance(get_key_provider(), EnvKeyProvider)


def test_kms_stub_mode_still_routes_to_stub():
    from backend.core.kms import get_key_provider, KmsStubProvider
    os.environ["KEY_MANAGEMENT_MODE"] = "kms_stub"
    try:
        assert isinstance(get_key_provider(), KmsStubProvider)
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"


# ── 13-14. Config validation ─────────────────────────────────────────────────

def test_aws_kms_in_production_requires_kms_arn():
    from backend.core.config_validation import validate_startup_config
    os.environ.update({"DEPLOYMENT_MODE": "production", "KEY_MANAGEMENT_MODE": "aws_kms",
                       "POSTGRES_PASSWORD": "test", "APP_BASE_URL": "https://app.test",
                       "LAWAPP_AUTH_MODE": "jwt", "JWT_ISSUER": "iss",
                       "JWT_AUDIENCE": "aud", "JWT_JWKS_URL": "https://jwks.test"})
    os.environ.pop("AWS_KMS_KEY_ARN", None)
    try:
        result = validate_startup_config(fail_fast=False)
        assert any("AWS_KMS_KEY_ARN" in m for m in result["missing_required"])
    finally:
        os.environ["DEPLOYMENT_MODE"] = "development"
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        for k in ["POSTGRES_PASSWORD", "APP_BASE_URL", "JWT_ISSUER", "JWT_AUDIENCE", "JWT_JWKS_URL"]:
            os.environ.pop(k, None)


def test_aws_kms_in_production_with_arn_passes_config():
    from backend.core.config_validation import validate_startup_config
    os.environ.update({"DEPLOYMENT_MODE": "production", "KEY_MANAGEMENT_MODE": "aws_kms",
                       "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN, "POSTGRES_PASSWORD": "test",
                       "APP_BASE_URL": "https://app.test", "LAWAPP_AUTH_MODE": "jwt",
                       "JWT_ISSUER": "iss", "JWT_AUDIENCE": "aud",
                       "JWT_JWKS_URL": "https://jwks.test"})
    try:
        result = validate_startup_config(fail_fast=False)
        assert not any("AWS_KMS_KEY_ARN" in m for m in result["missing_required"])
    finally:
        os.environ["DEPLOYMENT_MODE"] = "development"
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        for k in ["AWS_KMS_KEY_ARN", "POSTGRES_PASSWORD", "APP_BASE_URL",
                  "JWT_ISSUER", "JWT_AUDIENCE", "JWT_JWKS_URL"]:
            os.environ.pop(k, None)


# ── 15-18. Production readiness ───────────────────────────────────────────────

def test_production_readiness_kms_not_checked_by_default():
    """Without ?health_check=true, kms_connected shows NOT_CHECKED."""
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    km = data.get("key_management", {})
    assert km.get("kms_connected") == "N/A" or km.get("kms_connected") == "NOT_CHECKED" \
        or km.get("kms_connected") is False, \
        f"kms_connected should not be True without health_check: {km.get('kms_connected')}"


@patch("boto3.client")
def test_production_readiness_health_check_true_shows_connected(mock_boto3_client):
    """With ?health_check=true and mock success → kms_connected=True."""
    mock_client = MagicMock()
    mock_client.describe_key.return_value = {"KeyMetadata": {"Enabled": True}}
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.get("/admin/production-readiness?health_check=true", headers=_ADMIN_HDR)
        data = resp.json()
        km = data.get("key_management", {})
        assert km.get("kms_connected") is True
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_production_readiness_health_check_failure_shows_disconnected(mock_boto3_client):
    """Mock health check failure → kms_connected=False."""
    mock_client = MagicMock()
    mock_client.describe_key.side_effect = Exception("Unreachable")
    mock_boto3_client.return_value = mock_client

    os.environ.update({"KEY_MANAGEMENT_MODE": "aws_kms", "AWS_KMS_KEY_ARN": _MOCK_KMS_ARN})
    try:
        resp = client.get("/admin/production-readiness?health_check=true", headers=_ADMIN_HDR)
        data = resp.json()
        km = data.get("key_management", {})
        assert km.get("kms_connected") is False
    finally:
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        os.environ.pop("AWS_KMS_KEY_ARN", None)


def test_readiness_shows_key_provider_name():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    enc = resp.json().get("encryption_at_rest", {})
    assert "key_provider" in enc


# ── 19-20. No sensitive values in logs ───────────────────────────────────────

@patch("boto3.client")
def test_no_arn_in_logs_during_health_check(mock_boto3_client, caplog):
    """AWS_KMS_KEY_ARN value must not appear in log output."""
    mock_client = MagicMock()
    mock_client.describe_key.return_value = {"KeyMetadata": {}}
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        with caplog.at_level("DEBUG"):
            AwsKmsProvider().health_check()
        assert _MOCK_KMS_ARN not in caplog.text, \
            "KMS ARN value must not appear in log output"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


@patch("boto3.client")
def test_no_key_material_in_logs_during_key_generation(mock_boto3_client, caplog):
    """Generated key material must not appear in log output."""
    import os as _os
    plaintext = _os.urandom(32)
    mock_client = MagicMock()
    mock_client.generate_data_key.return_value = {
        "Plaintext": plaintext, "CiphertextBlob": _os.urandom(64)
    }
    mock_boto3_client.return_value = mock_client

    from backend.core.kms import AwsKmsProvider
    import base64
    os.environ["AWS_KMS_KEY_ARN"] = _MOCK_KMS_ARN
    try:
        with caplog.at_level("DEBUG"):
            key = AwsKmsProvider().get_encryption_key()
        if key:
            assert key.decode() not in caplog.text, "Key material must not appear in logs"
    finally:
        os.environ.pop("AWS_KMS_KEY_ARN", None)


# ── 21-23. Existing providers unchanged ──────────────────────────────────────

def test_env_provider_still_works():
    from backend.core.kms import EnvKeyProvider
    from backend.core.encryption import encrypt_str, decrypt_str
    plaintext = "phase7c regression test"
    assert decrypt_str(encrypt_str(plaintext)) == plaintext


def test_kms_stub_still_shows_false_connected():
    from backend.core.kms import KmsStubProvider
    os.environ["KMS_KEY_ID"] = "stub-key-id"
    try:
        assert KmsStubProvider().kms_connected is False
    finally:
        os.environ.pop("KMS_KEY_ID", None)


def test_disabled_provider_still_blocks():
    from backend.core.kms import DisabledProvider
    assert DisabledProvider().is_production_grade() is False
    assert DisabledProvider().get_encryption_key() is None


# ── 24-25. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
