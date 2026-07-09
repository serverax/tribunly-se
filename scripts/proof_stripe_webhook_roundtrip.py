#!/usr/bin/env python3
"""Proof harness for the Stripe payment round trip.

The script is intentionally strict:
- It exits 2 with a named-vars message when the required local Stripe env is
  missing.
- It only uses local/test credentials from the environment. It never fabricates
  secrets and never reaches for live keys.
- It exercises the same backend route the frontend uses, then attempts the
  webhook/status round trip.

This phase is blocked until the owner supplies the local Stripe test vars.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable

import jwt
import psycopg2
import requests


REQUIRED_ENV_VARS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLIC_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "JWT_SECRET",
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _missing_required_vars() -> list[str]:
    missing = [name for name in REQUIRED_ENV_VARS if not _env(name)]
    if _env("PAYMENT_MODE") not in {"stripe_test", "stripe_live"}:
        missing.append("PAYMENT_MODE=stripe_test|stripe_live")
    return missing


def _blocked(message: str, missing: Iterable[str]) -> int:
    print("BLOCKED-ON-OWNER:", message)
    print("Required local env vars:")
    for item in missing:
        print(f"  - {item}")
    return 2


def _db_connect():
    host = _env("POSTGRES_HOST", "localhost")
    port = int(_env("POSTGRES_PORT", "5432"))
    dbname = _env("POSTGRES_DB", "lawapp")
    user = _env("POSTGRES_USER", "lawapp")
    password = _env("POSTGRES_PASSWORD", "lawapp")
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


def _seed_case(user_id: str) -> str:
    case_id = str(uuid.uuid4())
    conn = _db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, f"stripe-proof-{user_id}@example.com", "hash"),
            )
            cur.execute(
                """
                INSERT INTO cases (
                    id, user_id, case_title, claim_type, assessment, payment_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    case_id,
                    user_id,
                    "Stripe proof case",
                    "unfair_dismissal",
                    "{}",
                    "unpaid",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return case_id


def _auth_token(user_id: str) -> str:
    secret = _env("JWT_SECRET")
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
    }
    issuer = _env("JWT_ISSUER")
    audience = _env("JWT_AUDIENCE")
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm="HS256")


def _stripe_signature(payload: str) -> str:
    secret = _env("STRIPE_WEBHOOK_SECRET")
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def main() -> int:
    missing = _missing_required_vars()
    if missing:
        return _blocked("missing local Stripe env for webhook proof", missing)

    base_url = _env("LAWAPP_BASE_URL", "http://localhost:8000").rstrip("/")
    payment_mode = _env("PAYMENT_MODE")
    user_id = str(uuid.uuid4())
    case_id = _seed_case(user_id)
    token = _auth_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    create_resp = requests.post(
        f"{base_url}/api/payments/create-session",
        headers=headers,
        json={"case_id": case_id, "package_id": "full_documents"},
        timeout=30,
    )
    print(f"create-session: HTTP {create_resp.status_code}")
    print(create_resp.text)
    if not create_resp.ok:
        return 1

    create_data = create_resp.json()
    session_id = create_data["session_id"]
    print(f"session_id={session_id}")
    print(f"session_url={create_data['session_url']}")

    webhook_event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "metadata": {
                    "case_id": case_id,
                    "user_id": user_id,
                },
            }
        },
    }
    webhook_payload = json.dumps(webhook_event, separators=(",", ":"))
    webhook_headers = {
        "stripe-signature": _stripe_signature(webhook_payload),
    }

    webhook_resp = requests.post(
        f"{base_url}/api/payments/webhook",
        data=webhook_payload.encode("utf-8"),
        headers=webhook_headers,
        timeout=30,
    )
    print(f"webhook: HTTP {webhook_resp.status_code}")
    print(webhook_resp.text)
    if not webhook_resp.ok:
        return 1

    status_resp = requests.get(
        f"{base_url}/api/payments/status/{case_id}",
        headers=headers,
        timeout=30,
    )
    print(f"status: HTTP {status_resp.status_code}")
    print(status_resp.text)
    if not status_resp.ok:
        return 1

    status_data = status_resp.json()
    if status_data.get("paid") is not True:
        print("FAIL: payment status did not flip to paid")
        return 1

    print(f"PASS: Stripe payment round trip complete in {payment_mode} mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
