# LawApp Checkpoint Report

**Date:** 2026-06-15  
**Branch:** `release/lawapp-clean-snapshot`  
**Latest commit:** `0c1b1a7`  -  docs: record post-approval commit and verification in PROJECT_STATUS  
**Prior milestone commit:** `f38c22f`  -  fix(go-live): wire RAG corpus, bootstrap, and beta QA gates  
**Repository:** `F:\lawapp`  
**Canonical K8s namespaces:** `lawapp-api`, `lawapp-ai`, `lawapp-rag`, `lawapp-security`, `lawapp-monitoring`

---

## Executive summary

LawApp is a **real, wired** UK employment-law platform  -  FastAPI monolith, Postgres/pgvector, JWT auth, payment gating, Brain governance pipeline, and eight healthy Docker microservices  -  **not** a mock shell. A deep QA audit on 2026-06-14 found ~65% beta readiness with critical RAG failure (28 corpus chunks, zero search hits), 13/24 partial legal modules, and 59 pytest failures. A recovery session repaired RAG wiring (`lawapp-rag-service` queried wrong table), synced **323** corpus chunks with **315** embeddings, added beta-scoped DB integrity gates, fixed integration auth drift, and proved end-to-end user workflows. Post-approval commits `f38c22f` and `0c1b1a7` were **pushed** to `origin/release/lawapp-clean-snapshot`; Docker images were rebuilt and re-verified.

**Controlled beta (11 production modules, fail-closed partial)** is **GO WITH RISK**. **Public production** remains **NO-GO**: full pytest not green (22 failed + 20 errors), k6 load thresholds fail, K8s deploy unproven, 13 modules still `partial`, production secret rotation unproven.

---

## Go-live status

| Scope | Verdict | Rationale |
|-------|---------|-----------|
| Local Docker dev/demo | **GO** | 12/12 services healthy (verified 2026-06-15); `/health` db connected; workflows PASS |
| Controlled beta (invite-only, 11 modules) | **GO WITH RISK** | Beta DB integrity PASS; RAG returns grounded hits; auth/payment/cross-tenant proven; pytest debt + sparse corpus remain |
| Public production / K8s / scale | **NO-GO** | Gates 6, 9, 11, 12 open; 13 partial modules; 42 test failures/errors; k6 p95 1.05s / 64% http_req_failed |

---

## What was accomplished (timeline by phase)

### Phase 1  -  QA audit (2026-06-14)

- Produced architecture map: monolith + 8 compose microservices, static frontend, SQL migrations (no Alembic).
- Ran proof commands; documented 125 rules, 11 production / 13 partial modules, 28 corpus chunks, RAG 0 hits.
- Rated areas A–L; weighted ~65% beta / ~45% public go-live.
- Created repair backlog (QA-001–QA-015), go-live gates, E2E matrix, completion decision.
- **Artifacts:** `docs/qa/CURSOR_DEEP_QA_REPORT.md`, `CURSOR_REPAIR_BACKLOG.md`, `CURSOR_GO_LIVE_GATES.md`, `CURSOR_E2E_TEST_MATRIX.md`, `CURSOR_COMPLETION_DECISION.md`

### Phase 2  -  Recovery & repair (2026-06-14)

- **QA-001:** Fixed RAG service table mismatch; added `ingestion/sync_corpus_chunks.py`; bootstrap path repaired; corpus 28 → **323**, embedded **315**; search returns ACAS + ERA hits.
- **QA-002 (beta):** `GO_LIVE_MODE=beta` in `prove_database_integrity.sh`; API fail-closed for non-production modules via `backend/domains/employment/modules.py`.
- **QA-004 (partial):** Mock auth in `tests/conftest.py`; `auth_helpers.py`; batch header fixes; legal accuracy gate PASS; failures reduced 59 → **22 failed + 20 errors** (1572 passed).
- **QA-003 (partial):** `COPY tests ./tests` in Dockerfile; post-rebuild collect **1833** tests (2 import errors remain).
- Re-verified: full workflow proof PASS, beta DB integrity PASS.
- **Artifacts:** `docs/qa/CURSOR_GO_LIVE_READINESS_REPORT.md`, `reports/*_cursor.txt`

### Phase 3  -  Go-live repairs & commit/push (2026-06-15)

- User-approved commit `f38c22f` (84 files, +7112/−1626): RAG service, employment modules, migrations 058–068, proof scripts, QA docs, integration test repairs.
- Follow-up docs commit `0c1b1a7` updating `tasks/PROJECT_STATUS.md`.
- Pushed to `origin/release/lawapp-clean-snapshot` (20650a0..f38c22f per PROJECT_STATUS).
- Post-commit verification: Docker build backend/db-bootstrap/ingestion; workflow + beta integrity PASS.
- **Artifacts:** `reports/proof_full_workflows_postcommit.txt`, `reports/proof_database_integrity_postcommit.txt`

### Prior beta fixes (on branch, pre-checkpoint)

- `62b9146`  -  assessment page deadline warnings from backend
- `263966a`  -  homepage/checkout price alignment (£29.99)
- `28bb58f`  -  day-one / automatic-unfair rights on short service

---

## Current system state

### Docker / services (fresh: 2026-06-15)

```
12/12 containers healthy
```

| Service | Port | Status |
|---------|------|--------|
| backend | 8000 | healthy  -  `status: ok`, `db: connected`, `auth_mode: jwt` |
| db (pgvector:16) | 5432, 5435 | healthy |
| redis | 6379 | healthy |
| lawapp-rules-service | 8016 | healthy |
| lawapp-rag-service | 8017 | healthy (rebuilt ~15h ago) |
| lawapp-graph-rag-service | 8018 | healthy |
| lawapp-redaction-service | 8019 | healthy |
| lawapp-audit-service | 8020 | healthy |
| lawapp-admin-service | 8007 | healthy |
| lawapp-case-service | 8008 | healthy |
| lawapp-notification-service | 8009 | healthy |
| outbox-worker |  -  | healthy |

**Not in compose:** citation-guard, ingestion-worker, LLM gateway, crawler (manifests exist).

### Database (fresh query: 2026-06-15)

| Metric | Value |
|--------|-------|
| Rules | **125** |
| Corpus chunks | **323** |
| Embedded chunks | **315** |
| Employment modules | **24** total  -  **11 production**, **13 partial** |
| Migrations applied | **62** rows in `_migrations` |
| Legislation rows | **104** (per prior audit) |
| Beta integrity gate | **PASS** (`GO_LIVE_MODE=beta`) |
| Production module gate | **FAIL** (13 partial remain) |

**11 production modules:** agency_workers, employment_contracts, fixed_term_workers, flexible_working, holiday_pay, part_time_workers, redundancy, unfair_dismissal, unpaid_wages, working_time, wrongful_dismissal.

**13 partial modules:** constructive_dismissal, discrimination, equal_pay, health_and_safety, maternity_rights, national_minimum_wage, parental_leave, paternity_rights, pregnancy_maternity_discrimination, shared_parental_leave, trade_union_rights, tupe, whistleblowing.

### RAG

| Check | Status | Evidence |
|-------|--------|----------|
| Service health | PASS | `:8017/health` ok |
| Vector search | PASS | `reports/rag_search_proof_cursor.txt`  -  `total_found=10`, ACAS unfair dismissal + ERA s.98/111 |
| Corpus size | PARTIAL | 323 chunks (target >>1000 for comfortable coverage) |
| Brain citations in assess | PASS | Workflow proof  -  rules + graph context |
| db-bootstrap image | PARTIAL | Rebuild done; verify `sync_corpus_chunks` baked into image on fresh clone |

### Tests

| Suite | Result | Artifact |
|-------|--------|----------|
| Full host pytest | **1572 passed, 22 failed, 20 errors, 152 skipped** | `reports/pytest_full_cursor.txt` |
| Legal accuracy gate | **PASS** | `reports/legal_accuracy_cursor.txt` |
| Payment gating | **PASS** (2/2) | `reports/pytest_remaining_fixes.txt` |
| Targeted auth fix | **56 passed** | `reports/pytest_targeted_auth_fix.txt` |
| Docker pytest collect | **1833 collected, 2 import errors** | `test_rules_engine_scale`, `test_service_tracing_integration` |
| Pre-recovery full suite | 59 failed, 1619 passed | `reports/full_suite_results.txt` |

**Failure clusters (honest):**

1. `test_auth_db.py`  -  20 errors (host pytest DB connection; wrong port/password vs Docker on 5435)
2. `test_auth_flows.py`  -  8 failures (refresh/logout/email verify)
3. `test_phase5a_hardening.py`  -  5 failures
4. `test_phase6_production.py`  -  3 failures
5. Misc  -  6 (streaming inference needs live Qwen, etc.)

### Workflows

`bash scripts/proof/prove_lawapp_full_workflows.sh`  -  **PASS** (post-commit and current)

Confirmed: landing, assess with deadline, 11 module diagnoses, out-of-scope refusal, anonymous blocks, register/login, case save, cross-tenant 403, unpaid doc block, checkout, test payment confirm, paid POC/SoL generation, admin protection.

**Artifact:** `reports/proof_full_workflows_postcommit.txt`

---

## Commits pushed

| Commit | Summary | Pushed |
|--------|---------|--------|
| `0c1b1a7` | docs: post-approval verification in PROJECT_STATUS | Yes (`origin/release/lawapp-clean-snapshot`) |
| `f38c22f` | fix(go-live): RAG corpus, bootstrap, beta QA gates (84 files) | Yes |
| `62b9146` | fix(beta-B-ui): deadline warnings on assessment page | Yes (on branch) |
| `263966a` | fix(beta-D): homepage/checkout price £29.99 | Yes |
| `28bb58f` | fix(beta-C): day-one/automatic-unfair detection | Yes |

**Working tree note:** Substantial untracked files remain (`reports/`, `.agents/`, `.codex/`, `.local/` uploads)  -  not committed.

---

## Files / modules changed (summary categories)

| Category | Changes |
|----------|---------|
| **RAG / ingestion** | `lawapp-rag-service/main.py`, `ingestion/sync_corpus_chunks.py`, `docker-compose.yml` bootstrap |
| **Legal / brain** | `employment_assessment.py` refactor, `modules.py`, migrations 058–068, rules promotions |
| **API / auth / payment** | `main.py`, `payment_routes.py`, `document_routes.py`, JWT fail-closed |
| **Proof / QA** | `prove_database_integrity.sh`, `prove_lawapp_full_workflows.sh`, `prove_schema_readiness.py`, `run_legal_accuracy.py` |
| **Tests** | `conftest.py`, `auth_helpers.py`, phase3–6 integration repairs, `test_employment_module_scope.py` |
| **Frontend** | `case_detail.html`, assessment deadline UX (prior commits) |
| **Docs / tasks** | Full `docs/qa/CURSOR_*` suite, `tasks/PROJECT_STATUS.md`, `SUBAGENT_OPERATING_STATUS.md` |
| **CI / Docker** | `Dockerfile` COPY tests, db init scripts |

---

## P0 / P1 / P2 backlog status

| ID | Sev | Area | Summary | Status |
|----|-----|------|---------|--------|
| QA-001 | P0 | RAG | Corpus + search wiring | **FIXED** (search proven; corpus 323  -  below >>1000 target) |
| QA-002 | P0 | Modules | 13/24 partial | **MITIGATED (beta)** / **OPEN (production)** |
| QA-003 | P1 | Docker/CI | Container pytest parity | **MOSTLY FIXED**  -  1833 collect; 2 import errors |
| QA-004 | P1 | Tests | Full suite green | **IN PROGRESS**  -  22 fail + 20 err (was 59 fail) |
| QA-005 | P1 | Load | k6 thresholds | **OPEN**  -  p95 1.05s, 64% http_req_failed |
| QA-006 | P1 | K8s | Production deploy | **OPEN (owner)** |
| QA-015 | P1 | Secrets | Prod rotation | **OPEN (owner)** |
| QA-007 | P2 | DB password | `.env` vs override mismatch | **MITIGATED** |
| QA-008 | P2 | Alembic | Operator confusion | **DOCUMENTED** |
| QA-009 | P2 | psql | Proof script standardization | **DOCUMENTED** |
| QA-010 | P2 | OTEL | trace_id HTTP→DB | **OPEN** |
| QA-011 | P2 | Frontend | Mixed fetch auth patterns | **OPEN** |
| QA-012 | P3 | Deprecation | `datetime.utcnow` | **OPEN** |
| QA-013 | P3 | Services tree | `services/` vs `backend/services/` | **OPEN** |
| QA-014 | P3 | Ollama | Cluster DNS in compose | **OPEN** |

---

## Evidence index (`reports/*.txt` and key docs)

### Proof / verification (primary)

| Path | Contents |
|------|----------|
| `reports/proof_full_workflows_postcommit.txt` | Full E2E workflow PASS (post-commit) |
| `reports/proof_full_workflows_cursor.txt` | Workflow PASS (recovery session) |
| `reports/proof_database_integrity_postcommit.txt` | Beta DB integrity PASS |
| `reports/proof_database_integrity_cursor.txt` | Beta integrity (recovery) |
| `reports/rag_search_proof_cursor.txt` | RAG search 10 hits, ACAS + ERA |
| `reports/legal_accuracy_cursor.txt` | Legal accuracy gate PASS |
| `reports/pytest_full_cursor.txt` | 1572 pass / 22 fail / 20 err |
| `reports/docker_pytest_collect_cursor.txt` | Pre-rebuild 85 collected |
| `reports/docker_compose_ps_cursor.txt` | 12/12 healthy snapshot |
| `reports/k6_100k_readiness.txt` | Load FAIL  -  thresholds crossed |

### QA baselines

| Path | Contents |
|------|----------|
| `reports/full_suite_results.txt` | Pre-recovery 59 failures |
| `reports/deep_qa_secret_scan.txt` | Secret scan clean |
| `reports/deep_qa_baseline.txt` | Deep QA baseline |
| `reports/smoke_local_journey_latest.txt` | Smoke journey |
| `reports/pytest_targeted_auth_fix.txt` | Auth fix batch |
| `reports/bootstrap_run_latest.txt` | Bootstrap run log |

### Authoritative docs

| Path | Contents |
|------|----------|
| `docs/qa/CURSOR_DEEP_QA_REPORT.md` | Initial audit (pre-RAG fix numbers) |
| `docs/qa/CURSOR_GO_LIVE_READINESS_REPORT.md` | Recovery verdict |
| `docs/qa/CURSOR_REPAIR_BACKLOG.md` | Tracked repairs |
| `docs/qa/CURSOR_GO_LIVE_GATES.md` | Gate checklist (some gates stale pre-recovery) |
| `docs/qa/CURSOR_E2E_TEST_MATRIX.md` | Feature→proof map |
| `docs/qa/CURSOR_COMPLETION_DECISION.md` | Finishability decision |
| `tasks/PROJECT_STATUS.md` | Live project board |
| `tasks/SUBAGENT_OPERATING_STATUS.md` | Subagent session contract |

---

## Remaining blockers for production

1. **13 partial employment modules**  -  discrimination, TUPE, whistleblowing, family leave, etc. require rules/workflows/legal review or permanent beta scope cut with UI enforcement.
2. **Pytest not green**  -  42 failing/error tests block CI confidence; `test_auth_db.py` needs host DB env (`POSTGRES_PORT=5435`).
3. **k6 load gate**  -  p95 latency and 64% `http_req_failed` (mix of expected 401/402 and real latency).
4. **K8s / Talos deploy**  -  manifests exist; no live pod/ingress/TLS proof.
5. **Production secrets**  -  JWT, Stripe live, encryption keys not rotated via vault.
6. **RAG corpus depth**  -  323 chunks functional but below comfortable scale; full legal-data pipeline incomplete.
7. **OTEL / backup / restore**  -  not proven end-to-end.
8. **Accessibility / mobile**  -  not audited.

---

## Beta scope (11 modules) vs full scope (24)

| Aspect | Beta (11 production) | Full (24 production) |
|--------|----------------------|------------------------|
| Module count | 11 exposed; 13 fail-closed in API | All 24 `production` in DB |
| DB gate | `GO_LIVE_MODE=beta` PASS | `GO_LIVE_MODE=production` FAIL |
| Workflow proof | All 11 production modules exercised | Partial modules untested in E2E |
| RAG | Works for core dismissal/redundancy queries | Needs corpus for all module domains |
| Product claim | "Controlled beta  -  11 employment topics" | "Full UK employment law coverage"  -  **not honest today** |
| Legal-data pipeline | Bootstrap legislation + ACAS only | Scraper → engineer → ingest → CitationGuard chain incomplete |

---

## Escalations requiring owner

| Item | Owner | Why agent cannot close |
|------|-------|------------------------|
| **G2 leaked PAT rotation** | security-auth-payment-agent / owner | Destructive credential ops |
| **K8s/Talos production deploy** | platform-devops-scale-agent / owner | Cluster access, ingress, secrets |
| **Stripe live + webhook in prod** | owner | Live payment keys |
| **Public marketing / legal sign-off** | product owner | 24-module accuracy claim |
| **Backup/restore drill** | platform-devops | Production data risk |

---

## Recommended next 10 actions

1. **Fix host pytest DB env**  -  `POSTGRES_PORT=5435`, password aligned → clear 20 `test_auth_db.py` errors.
2. **Triage `test_auth_flows.py`**  -  refresh rotation / session table vs migrations 047/050.
3. **Repair phase5a funnel tests**  -  add `mock_auth_headers()` to case-creation helpers.
4. **Fix 2 pytest import errors** in container  -  `test_rules_engine_scale`, `test_service_tracing_integration`.
5. **Expand corpus toward >>1000 chunks**  -  full domain pack via legal-data pipeline (scraper → engineer → ingest).
6. **UI: hide partial modules** in intake claim-type picker (product-ux).
7. **Re-run k6** after assess-path tuning; save `reports/k6_100k_readiness_cursor.txt`.
8. **Prove OTEL trace_id**  -  one assess curl + `brain_traces` SQL match.
9. **Owner: staging K8s deploy**  -  pod Ready + ingress `/health` only.
10. **qa-release-gatekeeper re-review** when QA-004 green or signed waiver list exists.

---

## Verdict

### Can we ship beta?

**Yes  -  controlled, invite-only beta with explicit scope.**

Conditions:

- Document and enforce **11 production modules only**; partial modules fail-closed in API (proven).
- Do not claim full UK employment law coverage or production-scale readiness.
- Accept pytest debt (monitor regressions via workflow + legal accuracy gates).
- Run on Docker/staging with documented password/bootstrap path.
- RAG works but corpus is modest (323 chunks).

**Rating: GO WITH RISK**

### Can we ship production?

**No.**

Blockers: 13 partial modules, pytest not green, k6 fail, K8s unproven, production secrets unrotated, sparse RAG vs scale claims, OTEL/backup unproven.

**Rating: NO-GO**

---

## Fresh verification log (this checkpoint)

```text
# 2026-06-15
git log -3 --oneline
0c1b1a7 docs: record post-approval commit and verification in PROJECT_STATUS
f38c22f fix(go-live): wire RAG corpus, bootstrap, and beta QA gates
62b9146 fix(beta-B-ui): render backend deadline warnings on the assessment page

git branch -vv
* release/lawapp-clean-snapshot 0c1b1a7 [origin/release/lawapp-clean-snapshot]

docker compose ps → 12/12 healthy

docker compose exec -T db psql …
  rules: 125 | corpus_chunks: 323 | embedded: 315 | modules: 11 production, 13 partial

curl localhost:8000/health → status ok, db connected, auth jwt

docker compose run --rm backend pytest --collect-only -q
  1833 collected, 2 errors (import)
```

---

*Synthesized from: `docs/qa/CURSOR_*`, `tasks/PROJECT_STATUS.md`, `tasks/SUBAGENT_OPERATING_STATUS.md`, and fresh commands on 2026-06-15. No fake PASS  -  stale gate docs (pre-RAG-fix) reconciled against post-recovery evidence.*
