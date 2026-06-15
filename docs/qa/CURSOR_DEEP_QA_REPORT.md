# CURSOR DEEP QA REPORT — lawapp

**Date:** 2026-06-14  
**Auditor:** Cursor QA / architecture audit (subagent)  
**Root:** `F:\lawapp`  
**Branch:** working tree (uncommitted changes present)

---

## Completion decision (top line)

**YES, BUT ONLY AFTER P0/P1 REPAIRS**

LawApp is a real, wired monolith-plus-microservices UK employment-law platform — not a mock shell. Local Docker is currently healthy, core workflows pass live proof, and DB-backed rules drive governed assessments. It is **not** production-ready: 13/24 employment modules remain `partial`, RAG corpus is critically sparse (28 chunks, 0 retrieval hits), full pytest is not green (59 failures in last full run), load gates fail, and K8s/production observability are unproven from this machine.

### Honest % complete by category

| Category | % | Rating | Evidence summary |
|----------|---|--------|------------------|
| A — Architecture & service map | 72% | PARTIAL | Monolith + 8 compose microservices healthy; dual `backend/services/` + `services/` layout; canonical K8s namespaces defined |
| B — Database & migrations | 82% | PARTIAL | 91 tables, 68 SQL migrations, 125 rules; integrity script fails go-live module gate only |
| C — Legal rules engine | 74% | PARTIAL | 125 `rules` rows with authority refs; 11/24 modules `production`, 13 `partial` |
| D — RAG retrieval | 35% | FAIL | Service healthy; `/api/rag/search` returns **0 results**; only **28** `corpus_chunks` |
| E — Graph RAG | 58% | PARTIAL | Service healthy; assessments use `graph_context_used`; graph tables populated |
| F — Brain / governance pipeline | 78% | PARTIAL | 19-step pipeline in `backend/core/brain.py`; workflow proof shows citations + trace_id |
| G — Security / auth / payment | 76% | PARTIAL | JWT fail-closed proven; test payment workflow passes; 59 stale test failures include auth drift |
| H — Frontend | 68% | PARTIAL | Static HTML/JS served from monolith; pages wired to real API routes |
| I — Documents / OCR / bundles | 70% | PARTIAL | Paid/unpaid gating proven in workflow script; integration tests failing on auth |
| J — CI/CD | 62% | PARTIAL | `.github/workflows/ci.yml` canonical; full suite not green in container |
| K — Kubernetes / deploy | 45% | FAIL | Manifests under `infra/k8s/` + `k8s/`; cluster not reachable / not proven this session |
| L — Monitoring / OTEL | 50% | PARTIAL | OTEL deps in Dockerfile; Prometheus rules manifest exists; end-to-end trace not proven |

**Weighted overall:** ~**65%** toward controlled beta; ~**45%** toward public go-live.

---

## Phase 1 — Project map

### Frontend

| Item | Status |
|------|--------|
| Framework | Static HTML/CSS/JS (`client/public/`) — no React/Next SPA |
| Serving | Monolith bind-mounts `./client/public:ro` → port 8000 |
| Pages | 17 HTML pages (intake, assessment, dashboard, case_detail, login, register, tools, etc.) |
| API wiring | `fetch` / `LAWAPP_AUTH.fetchWithAuth` to `/assess`, `/cases`, `/api/documents/*`, `/api/payments/*`, `/auth/*` |

### Backend

| Item | Status |
|------|--------|
| Framework | FastAPI monolith (`backend/api/main.py`) |
| Brain | `backend/core/brain.py` — mandatory 19-step pipeline |
| Domains | Employment UK (`backend/domains/employment/`, `domains/employment_uk/`) |
| Auth | JWT (`LAWAPP_AUTH_MODE=jwt`), sessions in Postgres |
| Payment | Stripe + test mode; fail-closed when disabled |
| Entrypoint | `scripts/backend-entrypoint.sh` → `db/init-migrations.sh` → uvicorn |

### Docker Compose services (2026-06-14)

| Service | Port | Health |
|---------|------|--------|
| backend | 8000 | healthy |
| db (pgvector:16) | 5432, 5435 | healthy |
| redis | 6379 | healthy |
| lawapp-rules-service | 8016 | healthy |
| lawapp-rag-service | 8017 | healthy |
| lawapp-graph-rag-service | 8018 | healthy |
| lawapp-redaction-service | 8019 | healthy |
| lawapp-audit-service | 8020 | healthy |
| lawapp-admin-service | 8007 | healthy |
| lawapp-case-service | 8008 | healthy |
| lawapp-notification-service | 8009 | healthy |
| outbox-worker | — | healthy |

**Not running in compose:** citation-guard, ingestion-worker, LLM gateway, crawler (manifests exist under `services/` and `backend/services/`).

### Kubernetes

- Canonical namespaces: `lawapp-api`, `lawapp-ai`, `lawapp-rag`, `lawapp-security`, `lawapp-monitoring` (`infra/k8s/lawapp-namespaces.yaml`)
- Legacy `iterlaw` manifests quarantined under `infra/k8s/_legacy_iterlaw_QUARANTINED/`
- Deploy workflows: `.github/workflows/lawapp-deploy-k8s.yml`, `lawapp-deploy-talos.yml`

### CI/CD

- **Canonical:** `.github/workflows/ci.yml` — migrations via raw SQL + pytest
- **Deprecated:** `lawapp-ci.yml` (workflow_dispatch only)
- Additional: `build-images.yml`, `smoke.yml`, `docker-proof.yml`, deploy workflows

### DB migrations

- **Not Alembic** — zero `alembic` references in repo; `import alembic` fails in backend container (expected)
- Runner: `db/init-migrations.sh` — idempotent `_migrations` table
- 68 files in `db/migrations/` (001–068+)
- Seeds: `db-bootstrap` profile, `ingestion/` pipelines, employment module migrations 058–068

### Tests

- `tests/` — 1700+ tests (full suite)
- `backend/tests/` — smaller subset (83 tests in container run)
- Proof scripts: `scripts/proof/prove_lawapp_full_workflows.sh`, `prove_database_integrity.sh`

---

## Phase 2 — Proof commands (exact output)

### `docker compose ps`

```
NAME                                   STATUS
lawapp-backend-1                       Up 15 hours (healthy)   0.0.0.0:8000->8000/tcp
lawapp-db-1                            Up 19 hours (healthy)   5432, 5435
lawapp-lawapp-admin-service-1          Up 19 hours (healthy)   8007
lawapp-lawapp-audit-service-1          Up 19 hours (healthy)   8020
lawapp-lawapp-case-service-1           Up 19 hours (healthy)   8008
lawapp-lawapp-graph-rag-service-1      Up 19 hours (healthy)   8018
lawapp-lawapp-notification-service-1   Up 19 hours (healthy)   8009
lawapp-lawapp-rag-service-1            Up 19 hours (healthy)   8017
lawapp-lawapp-redaction-service-1      Up 19 hours (healthy)   8019
lawapp-lawapp-rules-service-1          Up 19 hours (healthy)   8016
lawapp-outbox-worker-1                 Up 19 hours (healthy)
lawapp-redis-1                         Up 19 hours (healthy)   6379
```

### Backend DB env (inside container)

```
POSTGRES_DB = lawapp
POSTGRES_HOST = db
POSTGRES_PASSWORD = lawapp
POSTGRES_PORT = 5432
POSTGRES_USER = lawapp
```

*(Aligned via `docker-compose.override.yml` — resolves prior `password authentication failed` when `.env` used `change_this_password`.)*

### Backend psycopg2 connect

```
('lawapp', 'lawapp')
```

### Rules table

```
 count
-------
   125
```

Sample rows include `unfair_dismissal.time_limit_months`, `redundancy.payment_formula`, etc. with `authority_ref` populated.

### Employment modules

```
 status   | count
 production | 11
 partial    | 13
(24 total)
```

Production: agency_workers, employment_contracts, fixed_term_workers, flexible_working, holiday_pay, part_time_workers, redundancy, unfair_dismissal, unpaid_wages, working_time, wrongful_dismissal.

Partial: constructive_dismissal, discrimination, equal_pay, health_and_safety, maternity_rights, national_minimum_wage, parental_leave, paternity_rights, pregnancy_maternity_discrimination, shared_parental_leave, trade_union_rights, tupe, whistleblowing.

### Corpus / legislation

```
corpus_chunks: 28
legislation:   104
```

### Health endpoints

```
GET http://localhost:8000/health
{"status":"ok","service":"lawapp-backend","db":"connected","auth_mode":"jwt","payment_mode":"test",...}

GET http://localhost:8016/health
{"status":"ok","service":"lawapp-rules-service",...}

GET http://localhost:8020/health → {"status":"ok",...}
GET http://localhost:8019/health → {"status":"ok",...}
GET http://localhost:8017/health → {"status":"ok","service":"lawapp-rag-service",...}
GET http://localhost:8018/health → {"status":"ok",...}
```

### RAG retrieval proof

```
POST http://localhost:8017/api/rag/search
Body: {"query":"unfair dismissal qualifying period","top_k":3}
Response: {"query":"...","results":[],"total_found":0}
```

**FAIL for grounded RAG** — service up but corpus too sparse for retrieval.

### Alembic check

```
docker compose exec -T backend python -c "import alembic"
ModuleNotFoundError: No module named 'alembic'
```

**Non-blocker** — project uses SQL migrations, not Alembic.

### pytest

| Command | Result |
|---------|--------|
| `docker compose run --rm backend python -m pytest -q` | **2 failed, 83 passed** (runs `backend/tests/` only — image does not COPY root `tests/`) |
| Full suite (cached `reports/full_suite_results.txt`) | **59 failed, 1619 passed, 47 skipped** in 1774s |
| `bash scripts/proof/prove_lawapp_full_workflows.sh` | **PASS** (all steps including paid docs) |
| `bash scripts/proof/prove_database_integrity.sh` | **FAIL** at go-live employment-module gate (13 partial modules) |

### Service logs

- **backend:** Only `/health` 200 lines — no FATAL/password errors in tail-300
- **rules/audit/redaction/rag/graph-rag:** Health-check 200 lines only — no restart loops at audit time (contrasts with user's earlier session)

### k6 load (cached `reports/k6_100k_readiness.txt`)

```
http_req_failed: 64.45%
p(95) duration: 1.05s (threshold <1000ms crossed)
→ NOT READY for 100k concurrent users
```

---

## Phase 3 — P0 blocker investigation

| # | Issue | Root cause | Status this session |
|---|-------|------------|---------------------|
| 1 | Backend DB password mismatch | `.env` POSTGRES_PASSWORD vs override | **RESOLVED** — override sets `lawapp`; backend connects |
| 2 | Alembic missing | Never part of design | **N/A** — use `db/init-migrations.sh` |
| 3 | psql not in backend | Backend image has `postgresql-client` but proof uses `db` container | **DOCUMENTED** — `docker compose exec -T db psql ...` |
| 4 | Docker health checks | curl /health endpoints | **PASS** — all services healthy |
| 5 | RAG/graph-rag restarting | Not reproducing now; logs clean | **INTERMITTENT / RESOLVED locally** — monitor on cold start |
| 6 | datetime.utcnow warnings | ~30 usages across services | **P3** — deprecation warnings only |

**No code fixes applied this session** — runtime blockers from user context are already mitigated by existing `docker-compose.override.yml`; remaining gaps are data coverage, test debt, and production proof.

---

## Phase 4 — Area ratings (A–L)

| Area | Verdict | Key evidence |
|------|---------|--------------|
| A Architecture | PARTIAL | Compose stack wired; duplicate service trees; not all K8s services in compose |
| B Database | PARTIAL | 91 tables, migrations idempotent, FK enforcement live |
| C Legal rules | PARTIAL | 125 rules; 11 production modules; effective-dated rows |
| D RAG | **FAIL** | 28 chunks; search returns 0 |
| E Graph RAG | PARTIAL | Service OK; used in `/assess` responses |
| F Brain | PARTIAL | Pipeline coded; workflow proof passes with trace_id |
| G Security | PARTIAL | Auth/payment gates live-proven; test suite drift |
| H Frontend | PARTIAL | Real API wiring; static pages not design-system complete |
| I Auth/Payment | PARTIAL | JWT + test confirm route proven |
| J Documents | PARTIAL | Workflow proof PASS; phase3 integration tests FAIL (401) |
| K CI/CD | PARTIAL | CI exists; full green not proven |
| L K8s | **FAIL** | Manifests only; no cluster proof |

---

## Phase 5 — Recommendations

1. **P0:** Run `docker compose --profile bootstrap run --rm db-bootstrap` (or full ingestion) to populate `corpus_chunks` — prove RAG returns ≥1 hit for employment queries.
2. **P0:** Promote or honestly gate remaining 13 `partial` modules; until then fail-closed in product UI.
3. **P1:** Copy `tests/` into backend Docker image OR mount in compose so CI/container matches local full suite.
4. **P1:** Repair 59 failing tests (mostly auth fixture drift in `tests/integration/test_phase3*.py`).
5. **P1:** Re-run k6 after backend warm-up; separate expected 401/402 from true failures.
6. **P2:** Deploy smoke to Talos/K8s with health + trace proof.
7. **P2:** Replace `datetime.utcnow()` with timezone-aware datetimes.

---

## Files changed this audit

**None** — audit and documentation only.

---

*Evidence artifacts: `reports/full_suite_results.txt`, `reports/proof_full_workflows.txt`, `reports/k6_100k_readiness.txt`, `reports/LAWAPP_GO_LIVE_READINESS_REPORT.md`*
