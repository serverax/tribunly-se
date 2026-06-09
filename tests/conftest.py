"""
Root test conftest — ensures all tests connect to the local lawapp DB.

DATABASE_URL may be set to a foreign cloud DB — cleared here to ensure lawapp tests use the local Docker DB.
LAWAPP_AUTH_MODE=mock enables real user identity in tests (X-User-ID header).
PAYMENT_MODE=disabled keeps paid output blocked unless a test explicitly seeds
DB-backed paid state or enables stripe_test.

GUARDRAIL: Never connect lawapp tests to a foreign database.
"""

import os

# Clear foreign DATABASE_URL — tests always use local Docker DB
os.environ.pop("DATABASE_URL", None)

# DB connection. Use setdefault so an explicit environment (e.g. the ingestion
# container, which sets POSTGRES_HOST=db / PORT=5432) is HONOURED; only host-based
# runs fall back to the published localhost:5435 mapping. Hard-assigning these
# broke in-container test runs (localhost:5435 is unreachable inside a container).
os.environ.setdefault("POSTGRES_HOST",     "localhost")
os.environ.setdefault("POSTGRES_PORT",     "5435")
os.environ.setdefault("POSTGRES_DB",       "lawapp")
os.environ.setdefault("POSTGRES_USER",     "lawapp")
os.environ.setdefault("POSTGRES_PASSWORD", "lawapp")

# Auth mode: mock enables real user identity checks in tests via X-User-ID header
# JWT mode would require a real JWT_SECRET; mock is correct for unit/integration tests
os.environ.setdefault("LAWAPP_AUTH_MODE",  "mock")
os.environ.setdefault("JWT_SECRET",        "dev-jwt-secret-replace-in-production")

# Payment mode: real-only. Safe default = disabled (paid generation blocked).
# Payment tests that need paid access set PAYMENT_MODE=stripe_test + seed the DB
# payment record (cases.payment_status='paid'); they do not use fake tokens.
os.environ.setdefault("PAYMENT_MODE",      "disabled")

import pytest


@pytest.fixture(autouse=True, scope="session")
def _disable_rate_limiters():
    """Disable slowapi per-route rate limiters for the whole test session.

    The register/login/magic-link routes are rate-limited (e.g. 10/minute) and
    keyed on the client IP. Under TestClient every call shares one IP, so running
    the auth suites together would trip the limit and 429. Rate limiting is a
    production concern proven by its own tests — it must not make functional
    suites flaky. Disable the actual Limiter instances the decorators are bound
    to (setting app.state.limiter alone does not affect them)."""
    for module_path, attr in (
        ("backend.api.auth_routes", "_limiter"),
        ("backend.api.main", "_limiter"),
    ):
        try:
            import importlib
            mod = importlib.import_module(module_path)
            getattr(mod, attr).enabled = False
        except Exception:
            pass  # limiter not present in this context — nothing to disable
    yield


@pytest.fixture(autouse=True)
def _reset_rules_engine_cache():
    """The rules-engine hot-path cache is module-global state. Reset it before every
    test so a value cached by one test (e.g. a stubbed rules row) can never leak into
    another test that asserts a cold-miss / fail-closed path."""
    try:
        from services.lawapp_rules_engine.cache import reset_caches
        reset_caches()
    except Exception:
        pass  # service module not importable in this test context — nothing to reset
    yield
