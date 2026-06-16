"""
lawapp authentication stack.

A DB-backed, provider-abstracted auth layer exposed at /api/auth/* by
backend/api/auth_routes.py. Public surface:

  passwords   -  PBKDF2 hashing + strength policy
  tokens      -  access JWT + opaque refresh / single-use tokens
  providers   -  OIDC provider abstraction (google/microsoft/apple/linkedin)
  email       -  transactional email transport (smtp/console/memory)
  audit       -  append-only auth_events trail
  service     -  orchestration (register/login/logout/refresh/magic-link/oauth/…)
"""

from __future__ import annotations

from . import audit, email, passwords, providers, service, tokens  # noqa: F401

__all__ = ["audit", "email", "passwords", "providers", "service", "tokens"]
