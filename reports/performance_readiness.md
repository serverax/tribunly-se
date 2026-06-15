# Performance And 100k Readiness

Date: 2026-06-14
Status: NO-GO

## Evidence

- `docker compose ps`: local backend, DB, Redis, rules, RAG, Graph RAG, redaction, audit, admin, case, notification, and outbox worker are healthy.
- `k6 run scripts\load\k6_100k_readiness.js` against `http://127.0.0.1:8000`: FAIL.
- Latest 50-VU local smoke result:
  - p95 `http_req_duration=1.05s`, threshold `<1000ms`.
  - `http_req_failed=64.45%`, threshold `<5%`.
  - Checks passed for homepage, health, anonymous save block, and anonymous document gate.
  - Checks failed under load for bad-login negative control and assessment responses.

## Interpretation

This is not a 100k-user test. It is a local 50-VU smoke test, and it still failed configured thresholds. Some HTTP failures are expected 4xx negative-control endpoints, but the assessment/login behavior under load needs tuning and the k6 script should separate expected 4xx controls from true transport/server failures.

## 100k Requirements Still Missing

- Distributed load generation for 100k users in five minutes.
- API horizontal scaling proof.
- DB pooler/PgBouncer or managed pool proof.
- Postgres capacity plan, slow query budget, and connection headroom.
- Redis/rate-limit/cache sizing proof.
- RAG/Graph RAG latency and queue/backpressure proof.
- Document generation async capacity proof.
- CDN/static asset strategy.
- Observability dashboards, alerting, and rollback runbook.

## Verdict

NO-GO for performance and launch scale.
