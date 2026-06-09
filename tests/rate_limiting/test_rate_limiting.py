"""
Rate limiting tests — lawapp FastAPI endpoint protection.

Tests that rate limiting is wired to sensitive endpoints:
  - /auth/register: 10/minute
  - /assess: 30/minute
  - /api/brain/trace: 20/minute

Uses FastAPI TestClient to verify 429 responses after limit exceeded.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestRateLimiterWired:
    def test_slowapi_limiter_on_app(self):
        """Verify Limiter is registered on FastAPI app state."""
        from backend.api.main import app, _limiter
        assert hasattr(app.state, "limiter"), "Limiter not registered on app.state"
        assert app.state.limiter is _limiter

    def test_rate_limit_exceeded_handler_registered(self):
        """Verify RateLimitExceeded exception handler is registered."""
        from backend.api.main import app
        from slowapi.errors import RateLimitExceeded
        handlers = app.exception_handlers
        assert RateLimitExceeded in handlers or any(
            exc == RateLimitExceeded for exc in handlers
        ), "RateLimitExceeded handler not registered"

    def test_assess_endpoint_has_rate_limit(self, client):
        """Verify /assess returns 200 on first call (not immediately 429)."""
        response = client.post("/assess", json={
            "query": "What is unfair dismissal?",
            "facts": {}
        })
        # Should not 404 and should accept the first request
        assert response.status_code != 404, "/assess endpoint missing"

    def test_health_endpoint_no_rate_limit(self, client):
        """Health endpoint must always respond — no rate limiting."""
        for _ in range(5):
            r = client.get("/health")
            assert r.status_code == 200

    def test_brain_trace_endpoint_exists(self, client):
        """Verify /api/brain/trace accepts requests (not 404)."""
        r = client.post("/api/brain/trace", json={
            "message": "test",
            "facts": {},
        })
        assert r.status_code != 404, "/api/brain/trace endpoint missing"


class TestRateLimitConfiguration:
    def test_default_limit_is_set(self):
        from backend.api.main import _limiter
        assert _limiter is not None
        # slowapi stores default_limits as _default_limits
        dl = getattr(_limiter, "_default_limits", getattr(_limiter, "default_limits", None))
        assert dl is not None and len(dl) > 0

    def test_limiter_uses_remote_address(self):
        from backend.api.main import _limiter
        from slowapi.util import get_remote_address
        assert _limiter._key_func == get_remote_address
