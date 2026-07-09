# Beta Security Hardening Sweep — WO009 Task 4

**Date:** 2026-07-09  
**Scope:** Backend + ingestion containers, working tree, HTTP surface

---

## (a) Dependency Vulnerability Scan

| Container | Tool | Result |
|-----------|------|--------|
| backend | `pip-audit` (122 packages) | **No known vulnerabilities found** |
| ingestion | `pip-audit` | **No known vulnerabilities found** |

Key security packages: `cryptography==49.0.0`, `PyJWT==2.13.0`, `certifi==2026.6.17`.

## (b) Secret Scan

| Finding | Path | Verdict |
|---------|------|---------|
| `password="Str0ngPass!23"` | `scripts/proof/prove_lawapp_full_workflows.sh:294` | QA script, `@example.invalid` — not a real secret |
| `password = "IntegrationTestPass123!"` | `tests/integration/auth_helpers.py:20` | Test fixture — not a real secret |
| `.tmp/frontendproof.env` | `.tmp/frontendproof.env` | Gitignored, local-dev-only, all values marked "not-prod" |

**No real secrets found** in working tree or recent git history.

## (c) Security Headers

Added via `_security_headers` middleware in `backend/api/main.py`.

```
x-content-type-options: nosniff
x-frame-options: DENY
referrer-policy: strict-origin-when-cross-origin
content-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'
permissions-policy: camera=(), microphone=(), geolocation=(), payment=()
```

Verified via `curl -D -` against `/health`.

## (d) Rate Limiting

| Endpoint | Limit | Verified |
|----------|-------|----------|
| `/auth/register` | 10/minute | 429 on request 11 — `{"error":"Rate limit exceeded: 10 per 1 minute"}` |
| `/assess` | 30/minute | Configured; not burst-tested (each call takes ~30s) |
| `/api/payments/*` | 60/minute | Configured via `@_limiter.limit` |
| Default | 200/minute | Global fallback |

slowapi is active with in-memory backend (Redis storage optional via `RATELIMIT_STORAGE_URI`).

## PARKED Items

None. No major dependency vulnerabilities to escalate.
