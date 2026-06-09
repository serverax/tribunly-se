"""Repo-wide pytest safety defaults.

Tests must not inherit a developer or deployment DATABASE_URL. Individual suites
can still override POSTGRES_* explicitly, but the default target is the local
lawapp Docker database.
"""

from __future__ import annotations

import os


os.environ.pop("DATABASE_URL", None)

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5435")
os.environ.setdefault("POSTGRES_DB", "lawapp")
os.environ.setdefault("POSTGRES_USER", "lawapp")
os.environ.setdefault("POSTGRES_PASSWORD", "lawapp")
os.environ.setdefault("LAWAPP_AUTH_MODE", "mock")
os.environ.setdefault("JWT_SECRET", "dev-jwt-secret-replace-in-production")
os.environ.setdefault("PAYMENT_MODE", "disabled")
