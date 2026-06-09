import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
import uuid
import os

client = TestClient(app)

@pytest.fixture(autouse=True)
def auth_env():
    """Ensure auth mode is jwt and secret is set for these tests."""
    saved = {k: os.environ.get(k) for k in ["LAWAPP_AUTH_MODE", "JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE"]}
    os.environ.update({
        "LAWAPP_AUTH_MODE": "jwt",
        "JWT_SECRET": "test-secret-key-at-least-32-chars-long!!",
        "JWT_ISSUER": "lawapp-issuer",
        "JWT_AUDIENCE": "lawapp-audience",
    })
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

def test_register_login_flow():
    email = f"test-{uuid.uuid4()}@example.com"
    password = "test-password-123"
    
    # 1. Register
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    assert "user_id" in resp.json()
    
    # 2. Login
    resp = client.post("/auth/token", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token
    
    # 3. Get Me
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email
    
    # 4. List cases (should be empty but 200)
    resp = client.get("/cases", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "cases" in resp.json()
    assert len(resp.json()["cases"]) == 0

def test_login_invalid_password():
    email = f"test-{uuid.uuid4()}@example.com"
    client.post("/auth/register", json={"email": email, "password": "right-password"})
    
    resp = client.post("/auth/token", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 401

def test_auth_pages_exist():
    # temporarily disable auth for static check if needed, or just check 200
    for page in ["/pages/login.html", "/pages/register.html", "/pages/dashboard.html"]:
        resp = client.get(page)
        assert resp.status_code == 200
        assert "lawapp" in resp.text.lower()
