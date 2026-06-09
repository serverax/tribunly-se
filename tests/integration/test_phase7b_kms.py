"""
Phase 7B — KMS/HSM-ready key management provider tests.

Tests:
  Provider interface:
   1.  EnvKeyProvider available when ENCRYPTION_KEY set
   2.  EnvKeyProvider unavailable when ENCRYPTION_KEY not set
   3.  EnvKeyProvider is NOT production-grade
   4.  KmsStubProvider available when KMS_KEY_ID set
   5.  KmsStubProvider unavailable when KMS_KEY_ID not set
   6.  KmsStubProvider IS production-grade when KMS_KEY_ID configured
   7.  KmsStubProvider kms_connected is always False (stub)
   8.  DisabledProvider is NOT production-grade
   9.  DisabledProvider is never available

  Config validation:
  10.  kms_stub in production requires KMS_KEY_ID
  11.  kms_stub in production with KMS_KEY_ID passes
  12.  disabled mode in production fails

  Encryption still works:
  13.  encrypt_str / decrypt_str roundtrip unchanged
  14.  encrypt_bytes / decrypt_bytes roundtrip unchanged

  No key material logged:
  15.  get_kms_status() does not log key values

  Production readiness:
  16.  key_management section shows provider name
  17.  kms_stub with KMS_KEY_ID shows production_grade=true
  18.  kms_stub without KMS_KEY_ID shows production_grade=false
  19.  encryption_at_rest shows key_provider field
  20.  production_ready remains false

  Regressions:
  21.  Legal accuracy gate passes
  22.  Rules verification gate passes
  23.  Health check

Run:
    docker compose run --rm ingestion python -m pytest \
        tests/integration/test_phase7b_kms.py -v -s
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app, raise_server_exceptions=True)

_ADMIN_KEY = "test-admin-7b"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}
_MOCK_KMS_KEY_ID = "arn:aws:kms:us-east-1:123456789:key/phase7b-test-key"


@pytest.fixture(scope="module", autouse=True)
def phase7b_env():
    from cryptography.fernet import Fernet
    saved = {k: os.environ.get(k) for k in [
        "ADMIN_API_KEY", "ENCRYPTION_KEY", "LAWAPP_AUTH_MODE",
        "KEY_MANAGEMENT_MODE", "KMS_KEY_ID", "DEPLOYMENT_MODE",
        "POSTGRES_PASSWORD",
    ]}
    os.environ.update({
        "ADMIN_API_KEY":       _ADMIN_KEY,
        "ENCRYPTION_KEY":      Fernet.generate_key().decode(),
        "LAWAPP_AUTH_MODE":    "none",
        "KEY_MANAGEMENT_MODE": "env",
        "DEPLOYMENT_MODE":     "development",
    })
    os.environ.pop("KMS_KEY_ID", None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ── 1-9. Provider interface ───────────────────────────────────────────────────

def test_env_key_provider_available_when_key_set():
    from backend.core.kms import EnvKeyProvider
    provider = EnvKeyProvider()
    assert provider.is_available() is True   # ENCRYPTION_KEY set by fixture


def test_env_key_provider_unavailable_without_key():
    from backend.core.kms import EnvKeyProvider
    saved = os.environ.pop("ENCRYPTION_KEY", None)
    try:
        assert EnvKeyProvider().is_available() is False
    finally:
        if saved:
            os.environ["ENCRYPTION_KEY"] = saved


def test_env_key_provider_not_production_grade():
    from backend.core.kms import EnvKeyProvider
    assert EnvKeyProvider().is_production_grade() is False


def test_env_key_provider_returns_key_bytes():
    from backend.core.kms import EnvKeyProvider
    key = EnvKeyProvider().get_encryption_key()
    assert key is not None
    assert isinstance(key, bytes)


def test_kms_stub_available_when_key_id_set():
    from backend.core.kms import KmsStubProvider
    os.environ["KMS_KEY_ID"] = _MOCK_KMS_KEY_ID
    try:
        assert KmsStubProvider().is_available() is True
    finally:
        os.environ.pop("KMS_KEY_ID", None)


def test_kms_stub_unavailable_without_key_id():
    from backend.core.kms import KmsStubProvider
    os.environ.pop("KMS_KEY_ID", None)
    assert KmsStubProvider().is_available() is False


def test_kms_stub_is_production_grade_when_configured():
    from backend.core.kms import KmsStubProvider
    os.environ["KMS_KEY_ID"] = _MOCK_KMS_KEY_ID
    try:
        assert KmsStubProvider().is_production_grade() is True
    finally:
        os.environ.pop("KMS_KEY_ID", None)


def test_kms_stub_kms_connected_always_false():
    """kms_connected is always False in Phase 7B — honest about stub limitation."""
    from backend.core.kms import KmsStubProvider
    os.environ["KMS_KEY_ID"] = _MOCK_KMS_KEY_ID
    try:
        provider = KmsStubProvider()
        assert provider.kms_connected is False
        status = provider.status()
        assert status["kms_connected"] is False
    finally:
        os.environ.pop("KMS_KEY_ID", None)


def test_disabled_provider_not_production_grade():
    from backend.core.kms import DisabledProvider
    assert DisabledProvider().is_production_grade() is False
    assert DisabledProvider().is_available() is False
    assert DisabledProvider().get_encryption_key() is None


# ── 10-12. Config validation ──────────────────────────────────────────────────

def test_kms_stub_in_production_requires_kms_key_id():
    """In production mode, kms_stub without KMS_KEY_ID must fail validation."""
    from backend.core.config_validation import validate_startup_config
    os.environ.update({
        "DEPLOYMENT_MODE":     "production",
        "KEY_MANAGEMENT_MODE": "kms_stub",
        "POSTGRES_PASSWORD":   "test",
        "APP_BASE_URL":        "https://app.test",
        "LAWAPP_AUTH_MODE":    "jwt",
        "JWT_ISSUER":          "https://iss.test",
        "JWT_AUDIENCE":        "api-test",
        "JWT_JWKS_URL":        "https://jwks.test/.well-known/jwks.json",
    })
    os.environ.pop("KMS_KEY_ID", None)
    try:
        result = validate_startup_config(fail_fast=False)
        assert any("KMS_KEY_ID" in m for m in result["missing_required"]), \
            f"KMS_KEY_ID should be required: {result['missing_required']}"
    finally:
        os.environ["DEPLOYMENT_MODE"]     = "development"
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        for k in ["POSTGRES_PASSWORD", "APP_BASE_URL", "JWT_ISSUER",
                  "JWT_AUDIENCE", "JWT_JWKS_URL"]:
            os.environ.pop(k, None)


def test_kms_stub_in_production_with_key_id_passes_kms_check():
    """kms_stub + KMS_KEY_ID in production should not flag KMS_KEY_ID missing."""
    from backend.core.config_validation import validate_startup_config
    os.environ.update({
        "DEPLOYMENT_MODE":     "production",
        "KEY_MANAGEMENT_MODE": "kms_stub",
        "KMS_KEY_ID":          _MOCK_KMS_KEY_ID,
        "POSTGRES_PASSWORD":   "test",
        "APP_BASE_URL":        "https://app.test",
        "LAWAPP_AUTH_MODE":    "jwt",
        "JWT_ISSUER":          "https://iss.test",
        "JWT_AUDIENCE":        "api-test",
        "JWT_JWKS_URL":        "https://jwks.test/.well-known/jwks.json",
    })
    try:
        result = validate_startup_config(fail_fast=False)
        assert not any("KMS_KEY_ID" in m for m in result["missing_required"]), \
            f"KMS_KEY_ID should not be missing when set: {result['missing_required']}"
    finally:
        os.environ["DEPLOYMENT_MODE"]     = "development"
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        for k in ["KMS_KEY_ID", "POSTGRES_PASSWORD", "APP_BASE_URL",
                  "JWT_ISSUER", "JWT_AUDIENCE", "JWT_JWKS_URL"]:
            os.environ.pop(k, None)


def test_disabled_mode_fails_in_production():
    """KEY_MANAGEMENT_MODE=disabled in production must be a blocker."""
    from backend.core.config_validation import validate_startup_config
    _pg_pw = os.environ.get("POSTGRES_PASSWORD")
    os.environ.update({
        "DEPLOYMENT_MODE":     "production",
        "KEY_MANAGEMENT_MODE": "disabled",
        "POSTGRES_PASSWORD":   "test",
    })
    try:
        result = validate_startup_config(fail_fast=False)
        assert any("disabled" in m.lower() or "encryption" in m.lower()
                   for m in result["missing_required"])
    finally:
        os.environ["DEPLOYMENT_MODE"]     = "development"
        os.environ["KEY_MANAGEMENT_MODE"] = "env"
        if _pg_pw is not None:
            os.environ["POSTGRES_PASSWORD"] = _pg_pw
        else:
            os.environ.pop("POSTGRES_PASSWORD", None)


# ── 13-14. Encryption still works ────────────────────────────────────────────

def test_encrypt_decrypt_str_roundtrip():
    from backend.core.encryption import encrypt_str, decrypt_str
    plaintext = "Phase 7B test — encryption unchanged"
    ciphertext = encrypt_str(plaintext)
    assert ciphertext != plaintext
    assert len(ciphertext) > len(plaintext)
    assert decrypt_str(ciphertext) == plaintext


def test_encrypt_decrypt_bytes_roundtrip():
    from backend.core.encryption import encrypt_bytes, decrypt_bytes
    data = b"Phase 7B binary test data"
    enc  = encrypt_bytes(data)
    assert enc != data
    assert decrypt_bytes(enc) == data


# ── 15. No key material logged ────────────────────────────────────────────────

def test_get_kms_status_does_not_log_key_values(caplog):
    from backend.core.kms import get_kms_status
    enc_key = os.getenv("ENCRYPTION_KEY", "")
    with caplog.at_level("DEBUG"):
        get_kms_status()
    if enc_key:
        assert enc_key not in caplog.text, "ENCRYPTION_KEY value must not appear in logs"


# ── 16-20. Production readiness ───────────────────────────────────────────────

def test_readiness_shows_key_provider_name():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    enc  = data.get("encryption_at_rest", {})
    assert "key_provider" in enc, "encryption_at_rest must include key_provider"
    assert enc["key_provider"] in ("EnvKeyProvider", "KmsStubProvider", "DisabledProvider")


def test_kms_stub_with_key_id_shows_production_grade():
    from backend.core.kms import KmsStubProvider
    os.environ["KMS_KEY_ID"] = _MOCK_KMS_KEY_ID
    try:
        provider = KmsStubProvider()
        assert provider.is_production_grade() is True
        status = provider.status()
        assert status["production_grade"] is True
        assert status["kms_key_id_configured"] is True
    finally:
        os.environ.pop("KMS_KEY_ID", None)


def test_kms_stub_without_key_id_not_production_grade():
    from backend.core.kms import KmsStubProvider
    os.environ.pop("KMS_KEY_ID", None)
    provider = KmsStubProvider()
    assert provider.is_production_grade() is False


def test_readiness_key_management_section_present():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    data = resp.json()
    km   = data.get("key_management", {})
    assert "mode" in km
    assert "provider" in km
    assert "production_grade" in km


def test_production_ready_still_false():
    resp = client.get("/admin/production-readiness", headers=_ADMIN_HDR)
    assert resp.json()["production_ready"] is False


# ── 21-23. Regressions ────────────────────────────────────────────────────────

def test_legal_accuracy_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/run_legal_accuracy.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_rules_verification_gate_regression():
    result = subprocess.run(
        [sys.executable, "scripts/check_rules_verification.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_health_regression():
    assert client.get("/health").json()["status"] == "ok"
