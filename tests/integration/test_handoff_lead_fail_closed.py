from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.encryption import decrypt_str
from ingestion.db import get_connection


client = TestClient(app, raise_server_exceptions=True)

_REQUEST = {
    "trigger_reason": "seek_solicitor",
    "name": "Encrypted Handoff User",
    "email": "encrypted-handoff@test.invalid",
    "phone": "07000000000",
    "consent_given": True,
}


def _ensure_handoff_encryption_columns() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS deleted_at timestamptz")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS name_encrypted text")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS email_encrypted text")
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS phone_encrypted text")
            cur.execute(
                "ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS pii_encrypted boolean NOT NULL DEFAULT false"
            )
            cur.execute("ALTER TABLE handoff_leads ADD COLUMN IF NOT EXISTS encryption_key_metadata jsonb")
        conn.commit()
    finally:
        conn.close()


def _handoff_count() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM handoff_leads")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def _handoff_row(lead_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, email, phone, name_encrypted, email_encrypted, phone_encrypted, pii_encrypted
                FROM handoff_leads
                WHERE id = %s::uuid
                """,
                (lead_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def test_handoff_lead_requires_valid_encryption_key(monkeypatch):
    _ensure_handoff_encryption_columns()
    monkeypatch.setenv("KEY_MANAGEMENT_MODE", "env")
    monkeypatch.delenv("AWS_KMS_KEY_ARN", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    before = _handoff_count()

    response = client.post("/handoff/leads", json=_REQUEST)

    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Encryption service unavailable."}
    assert _handoff_count() == before


def test_handoff_lead_rejects_malformed_encryption_key(monkeypatch):
    _ensure_handoff_encryption_columns()
    monkeypatch.setenv("KEY_MANAGEMENT_MODE", "env")
    monkeypatch.delenv("AWS_KMS_KEY_ARN", raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "malformed-key")
    before = _handoff_count()

    response = client.post(
        "/handoff/leads",
        json={**_REQUEST, "email": "malformed-key@test.invalid"},
    )

    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Encryption service unavailable."}
    assert _handoff_count() == before


def test_handoff_lead_persists_encrypted_pii_with_valid_key(monkeypatch):
    _ensure_handoff_encryption_columns()
    monkeypatch.setenv("KEY_MANAGEMENT_MODE", "env")
    monkeypatch.delenv("AWS_KMS_KEY_ARN", raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    response = client.post("/handoff/leads", json={**_REQUEST, "email": "roundtrip@test.invalid"})

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["pii_encrypted"] is True
    assert payload["encryption_method"] == "direct_fernet"

    row = _handoff_row(payload["lead_id"])
    assert row is not None
    name, email, phone, name_encrypted, email_encrypted, phone_encrypted, pii_encrypted = row
    assert name == "[encrypted]"
    assert email == "[encrypted]"
    assert phone == "[encrypted]"
    assert pii_encrypted is True
    assert decrypt_str(name_encrypted) == _REQUEST["name"]
    assert decrypt_str(email_encrypted) == "roundtrip@test.invalid"
    assert decrypt_str(phone_encrypted) == _REQUEST["phone"]
