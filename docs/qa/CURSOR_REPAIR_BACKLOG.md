# CURSOR REPAIR BACKLOG  -  lawapp

Format: ID | Severity | Area | Symptom | Root cause | Evidence | Files affected | Repair steps | Acceptance criteria | Test command | Owner | Status

**Last updated:** 2026-06-14 (Cursor recovery session)  
**Readiness report:** `docs/qa/CURSOR_GO_LIVE_READINESS_REPORT.md`

---

| ID | Sev | Area | Symptom | Root cause | Evidence | Files | Repair steps | Acceptance | Test | Owner | Status |
|----|-----|------|---------|------------|----------|-------|--------------|------------|------|-------|--------|
| QA-001 | P0 | RAG | `/api/rag/search` returns 0 results | Bootstrap referenced missing modules; corpus not synced from legislation/ACAS | **FIXED:** 323 chunks, 315 embedded; `reports/rag_search_proof_cursor.txt` total_found=10 | `ingestion/sync_corpus_chunks.py`, `docker-compose.yml` | Rebuild db-bootstrap image; document ingestion-container bootstrap | Search returns ≥3 grounded chunks | Python POST :8017/api/rag/search | legal-data + db-rag | **FIXED** (rebuild image pending) |
| QA-002 | P0 | Legal modules | 13/24 modules `partial`; go-live gate fails | Rules/corpus/workflows incomplete for discrimination, TUPE, whistleblowing, etc. | Beta gate PASS with `GO_LIVE_MODE=beta`; 11 production exposed fail-closed | `scripts/proof/prove_database_integrity.sh`, `backend/domains/employment/modules.py` | Promote modules OR keep beta scope | Beta: partial allowed with verified rules; Prod: 24×production | `GO_LIVE_MODE=beta bash scripts/proof/prove_database_integrity.sh` | legal-rule-engine | **MITIGATED (beta)** / OPEN (production) |
| QA-003 | P1 | Docker/CI | Container pytest runs 83 tests not 1700+ | Dockerfile did not copy root `tests/`; image not rebuilt | Dockerfile updated; **still 85 collected** on live image | `Dockerfile` | `docker compose build backend`; verify collect ≥1600 | Container suite matches local | `docker compose run --rm backend python -m pytest --collect-only -q` | platform-devops | **IN PROGRESS** (code fixed, rebuild pending) |
| QA-004 | P1 | Tests | 59 failures in full suite | Stale integration auth; legal accuracy Unicode; syntax duplicate headers | **Improved:** 1572 pass, 22 fail, 20 err (was 59 fail) | `tests/conftest.py`, `tests/integration/*`, `scripts/run_legal_accuracy.py` | Fix auth_db host DB env; phase5a auth; auth_flows refresh | Full suite green | `python -m pytest tests/ -q` exit 0 | backend-api | **IN PROGRESS** |
| QA-005 | P1 | Load | k6 smoke fails thresholds | p95 1.05s; 64% http_req_failed (mix of expected 401 + latency) | `reports/k6_100k_readiness.txt` thresholds crossed | `scripts/load/k6_100k_readiness.js` | Tune assess latency; adjust threshold accounting for auth gates | p95 <1s at 50 VU; failure rate excludes expected gates | `k6 run scripts/load/k6_100k_readiness.js` | platform-devops | **OPEN** |
| QA-006 | P1 | K8s | Production deploy unproven | No cluster access this session | Namespaces exist; no live pod proof | `infra/k8s/`, `k8s/` | Deploy to Talos; prove health + ingress + secrets | All pods Ready; `/health` via ingress | `kubectl get pods -A \| grep lawapp` | platform-devops | **OPEN** (owner) |
| QA-007 | P2 | DB password | Intermittent auth failure without override | `.env` may set `change_this_password` while DB volume initialized with different secret | User context FATAL; override fixes | `.env`, `docker-compose.override.yml` | Document single password source; add startup DB connect probe to README | Fresh clone + compose up → backend healthy without manual fix | `docker compose exec backend python -c psycopg2 connect` | platform-devops | MITIGATED |
| QA-008 | P2 | Alembic confusion | Operators expect Alembic | Project never used Alembic | `import alembic` ModuleNotFoundError; no alembic in repo | `db/init-migrations.sh` | Document SQL migration model in ops runbook | No operator attempts alembic upgrade | Read `docs/qa/CURSOR_DEEP_QA_REPORT.md` | docs | DOCUMENTED |
| QA-009 | P2 | psql container | Scripts fail when run in backend | Some docs say backend exec psql | Backend has postgresql-client but proof standard is db container | `scripts/proof/*` | Standardize on `docker compose exec -T db psql` | All proof scripts use db service | grep proof scripts | platform-devops | DOCUMENTED |
| QA-010 | P2 | OTEL/trace | Same trace_id not proven HTTP→DB→brain_traces | OTEL deps present; end-to-end not exercised | No proof artifact this session | `backend/core/otel.py`, `brain_traces` table | Run assess; grep logs + DB for trace_id | trace_id in response, logs, brain_traces row | workflow proof + SQL query | observability | OPEN |
| QA-011 | P2 | Frontend | assessment.html uses raw fetch for some calls | Mixed auth patterns | grep shows fetch without fetchWithAuth on `/cases` POST | `client/public/pages/assessment.html` | Wire all mutating calls through fetchWithAuth | No unauthenticated case create | Manual + E2E | frontend | OPEN |
| QA-012 | P3 | Deprecation | datetime.utcnow warnings in pytest | Legacy datetime API in services | warnings in full suite | `backend/core/user_auth.py`, services/*/main.py | Replace with `datetime.now(timezone.utc)` | pytest -W error::DeprecationWarning clean | `pytest -q` | backend-api | OPEN |
| QA-013 | P3 | Dual services tree | Confusion between `services/` and `backend/services/` | Historical refactor incomplete | Both trees exist with overlapping names | `services/`, `backend/services/` | Consolidate or document ownership matrix | Single source of truth doc | service-map skill | architect | OPEN |
| QA-014 | P3 | Ollama local | LLM points to K8s cluster URL in compose | `LAWAPP_OLLAMA_BASE_URL` defaults to cluster DNS | backend /health shows cluster.local URL | `docker-compose.yml` | Add local ollama service or stub for dev | Assess works offline with local model | `/assess` with Ollama running | local-llm-router | OPEN |
| QA-015 | P1 | Secrets/production | Production secret rotation unproven | Dev keys in override | ENCRYPTION_KEY in override for local only | `.env.example`, K8s secrets template | Rotate JWT/ADMIN/Stripe via vault; prove | Secret scan clean; no dev keys in prod | security scan + deploy | security-auth | OPEN (owner) |

---

## Priority summary (2026-06-14)

- **P0:** QA-001 **FIXED** (image rebuild); QA-002 **MITIGATED for beta** / OPEN for production
- **P1:** QA-003 in progress; QA-004 in progress (1572/1614 runnable pass); QA-005 OPEN; QA-006 OPEN; QA-015 OPEN
- **P2 (5):** QA-007–QA-011 (mostly documented or open polish)
- **P3 (4):** QA-012–QA-014

---

## Session repair log

| Date | Items | Outcome |
|------|-------|---------|
| 2026-06-14 | QA-001, QA-002 beta, QA-004 partial, workflows | RAG 323 chunks; beta DB PASS; workflows PASS; pytest 1572 pass |
