"""Shared auth helpers for integration tests (mock + jwt)."""

from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

TEST_USER_ID = "00000000-0000-0000-0000-00000000000a"


def mock_auth_headers(user_id: str = TEST_USER_ID) -> dict[str, str]:
    return {"X-User-ID": user_id}


def jwt_auth_headers(client: TestClient, email: str | None = None) -> dict[str, str]:
    """Register + login and return Bearer headers."""
    addr = email or f"integration_{uuid.uuid4().hex[:12]}@lawapp.test"
    password = "IntegrationTestPass123!"
    reg = client.post("/auth/register", json={"email": addr, "password": password})
    if reg.status_code not in (200, 201, 409):
        reg.raise_for_status()
    login = client.post("/auth/token", json={"email": addr, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def auth_headers(client: TestClient | None = None, user_id: str = TEST_USER_ID) -> dict[str, str]:
    mode = os.environ.get("LAWAPP_AUTH_MODE", "mock").lower()
    if mode == "jwt":
        if client is None:
            raise ValueError("jwt auth requires TestClient for register/login")
        return jwt_auth_headers(client)
    return mock_auth_headers(user_id)
