# CURSOR GO-LIVE READINESS REPORT — lawapp

**Date:** 2026-06-14  
**Assessor:** Cursor recovery session (autonomous repair + re-proof)  
**Repository:** `F:\lawapp`  
**Namespaces (canonical):** `lawapp-api`, `lawapp-ai`, `lawapp-rag`, `lawapp-security`, `lawapp-monitoring`

---

## Executive verdict

| Scope | Verdict | Rationale |
|-------|---------|-----------|
| **Local Docker (dev/demo)** | **GO** | 12/12 services healthy; full workflow proof PASS; RAG search returns hits; 125 rules / 323 corpus chunks |
| **Controlled beta (11 production modules, fail-closed partial)** | **GO WITH RISK** | Beta DB integrity gate PASS; auth/payment gates proven in workflows; pytest 1572 pass but 22 fail + 20 errors remain |
| **Public production / K8s** | **NO-GO** | K8s deploy unproven; k6 thresholds not met (prior run); full pytest not green; 13 modules still `partial`; production secret rotation unproven |

**Overall recommendation:** Ship a **limited controlled beta** on local/staging Docker with explicit scope (11 supported employment modules). Do **not** promote to public production or claim full 24-module coverage until P0/P1 items below close.

---

## Fixed issues (with evidence)

| ID | Issue | Fix | Evidence |
|----|-------|-----|----------|
| QA-001 | RAG corpus empty (28 chunks, 0 search hits) | Fixed `docker-compose.yml` bootstrap (removed non-existent seed modules); added `ingestion/sync_corpus_chunks.py`; ran legislation + ACAS + embedder + sync via ingestion container | `corpus_chunks=323`, `embedded=315` (DB query 2026-06-14); `reports/rag_search_proof_cursor.txt` → `total_found=10`, top hit ACAS unfair dismissal + ERA s.111 |
| QA-002 (beta) | 13/24 modules partial blocked naive go-live gate | Added `GO_LIVE_MODE=beta` to `prove_database_integrity.sh`; backend already fail-closed to 11 production modules via `backend/domains/employment/modules.py` | `reports/` terminal proof → `PASS: beta: partial modules must have verified DB rules`, `PASS: beta: production module count matches supported scope`, `PASS: database integrity proof completed` |
| QA-004 (partial) | Integration tests 401 under JWT compose override | `tests/conftest.py` forces `LAWAPP_AUTH_MODE=mock`; `tests/integration/auth_helpers.py`; auth headers on case/document routes | `reports/pytest_targeted_auth_fix.txt` 56 pass; `reports/pytest_legal_accuracy_fix.txt` legal accuracy CI gate pass; payment gating tests pass |
| QA-004 (legal accuracy) | `run_legal_accuracy.py` Unicode/subprocess failures on Windows | `json.dumps(..., ensure_ascii=True)`; fixed `deadline_info` variable order | `reports/legal_accuracy_cursor.txt` → `PASS: LEGAL ACCURACY GATE PASSED` |
| Syntax regressions | Duplicate `headers=` kwargs in phase6a/phase6b after batch auth fix | Merged header dicts in `_make_case` and `test_case_owner_protection_regression` | Collection succeeds; phase6b 28 tests collected |
| Workflow | — (already passing; re-verified) | — | `reports/proof_full_workflows_cursor.txt` → all steps PASS including auth, payment, cross-tenant deny |
| Docker test tree | Dockerfile missing root `tests/` | `COPY tests ./tests` in Dockerfile | **Code fixed; image rebuild required** — see remaining blockers |

---

## Remaining blockers

### P0

| ID | Blocker | Evidence | Owner action |
|----|---------|----------|--------------|
| QA-002 (production) | 13 employment modules remain `partial` in DB | `prove_database_integrity.sh` with `GO_LIVE_MODE=production` would fail; only 11 exposed in product | Complete rules/workflows per module OR keep beta scope documented |
| QA-006 | K8s/Talos production deploy unproven | No cluster access this session | **Owner:** deploy to `lawapp-*` namespaces; prove pod Ready + ingress health |

### P1

| ID | Blocker | Evidence | Owner action |
|----|---------|----------|--------------|
| QA-003 | Docker backend pytest still collects **85** tests (not full tree) | `reports/docker_pytest_collect_cursor.txt` — needs image rebuild after Dockerfile change | `docker compose build backend && docker compose run --rm backend python -m pytest --collect-only -q` → expect 1600+ |
| QA-004 | Full pytest **not green**: 1572 passed, **22 failed**, **20 errors**, 152 skipped | `reports/pytest_full_cursor.txt` (968s run) | Triage: `test_auth_db.py` (20 DB connection errors), `test_auth_flows.py` refresh/logout, `test_phase5a_hardening.py`, `test_phase6_production.py`, streaming inference |
| QA-005 | k6 load thresholds not met | `reports/k6_100k_readiness.txt` (prior) — p95 ~1.05s, elevated `http_req_failed` | Re-run after perf tuning; warm caches |
| QA-015 | Production secrets / Stripe live unproven | Dev keys in `docker-compose.override.yml` only for local | **Owner:** vault rotation before prod |

### P2 (non-blocking for controlled beta)

| ID | Blocker | Notes |
|----|---------|-------|
| QA-010 | trace_id HTTP→DB not re-proven | Prior workflow shows trace_id in assess JSON |
| QA-011 | `assessment.html` mixed fetch patterns | Manual/E2E follow-up |
| Bootstrap image | `db-bootstrap` image lacks new `sync_corpus_chunks` until rebuild | Use mounted ingestion container path documented below |

---

## Test evidence

| Suite | Command | Result | Artifact |
|-------|---------|--------|----------|
| Full workflow proof | `bash scripts/proof/prove_lawapp_full_workflows.sh` | **PASS** | `reports/proof_full_workflows_cursor.txt` |
| DB integrity (beta) | `GO_LIVE_MODE=beta bash scripts/proof/prove_database_integrity.sh` | **PASS** | terminal `291439.txt` / proof output |
| Legal accuracy gate | `python scripts/run_legal_accuracy.py` | **PASS** | `reports/legal_accuracy_cursor.txt` |
| Legal accuracy CI test | `pytest tests/integration/test_phase5b_unpaid_wages.py::test_legal_accuracy_ci_gate_passes` | **PASS** | `reports/pytest_legal_accuracy_fix.txt` |
| Payment gating | `pytest tests/payment/test_payment.py::TestDocumentPaymentGating` | **PASS** (2/2) | `reports/pytest_remaining_fixes.txt` |
| Full pytest | `python -m pytest tests/ -q --tb=no -p no:cacheprovider` | **1572 passed, 22 failed, 20 errors, 152 skipped** | `reports/pytest_full_cursor.txt` |
| Docker pytest collect | `docker compose run --rm backend python -m pytest --collect-only -q` | **85 collected** (stale image) | `reports/docker_pytest_collect_cursor.txt` |

**Failure clusters (honest):**

1. **`test_auth_db.py` (20 errors)** — `psycopg2` connection failures from host pytest (likely wrong port/password vs Docker DB on 5435).
2. **`test_auth_flows.py` (8 failures)** — refresh rotation / logout / email verify / password reset flows.
3. **`test_phase5a_hardening.py` (5 failures)** — funnel events + phase4 regressions (likely missing auth on case create).
4. **`test_phase6_production.py` (3 failures)** — encrypted upload / soft-delete.
5. **Misc (6)** — `test_auth_none`, JWT bearer parse, domain modularity baseline, integrity fake-law flag, streaming inference (needs live Qwen).

---

## Workflow evidence

`scripts/proof/prove_lawapp_full_workflows.sh` — **PASS** (2026-06-14)

Confirmed end-to-end:

- Landing + `/health`
- Governed `/assess` with deadline field
- 11 production module diagnoses (wrongful dismissal, redundancy, working time, holiday, flexible working, contracts, fixed-term, part-time, agency workers, etc.)
- Out-of-scope refusal
- Anonymous document/case blocked (401)
- Register/login (User A/B)
- Case save + dashboard visibility
- Cross-tenant case deny (403)
- Unpaid document block → checkout → invalid payment reject → test confirm paid → paid document generation

Artifact: `reports/proof_full_workflows_cursor.txt`

---

## Security evidence

| Check | Result | Evidence |
|-------|--------|----------|
| Unauthenticated case access | Blocked | workflow proof `anonymous case creation blocked`, `401 for case access` |
| Cross-tenant isolation | 403 | workflow proof `User B cannot access User A case` |
| Payment no-bypass | Fail-closed until DB paid | workflow + payment gating pytest |
| Admin routes | Protected | workflow `admin/reporting pages protected` |
| Secret scan (prior) | Clean | `reports/deep_qa_secret_scan.txt` (baseline QA) |
| Auth mode in tests | Mock forced | `tests/conftest.py` prevents accidental JWT override |

**Not proven this session:** production JWT rotation, live Stripe webhook, OTEL trace persistence across HTTP→DB.

---

## Database evidence

| Metric | Value | Command / artifact |
|--------|-------|-------------------|
| Rules | **125** | `docker compose exec -T db psql ... SELECT COUNT(*) FROM rules` |
| Corpus chunks | **323** (was 28) | same session |
| Embedded chunks | **315** | `embedding IS NOT NULL` filter |
| Employment modules | **24** total: **11 production**, **13 partial** | `prove_database_integrity.sh` output |
| Beta integrity gate | **PASS** | `GO_LIVE_MODE=beta` |
| Migrations | Applied (backend healthy) | compose startup + schema proof (prior) |

**Canonical RAG bootstrap path (until `db-bootstrap` image rebuilt):**

```bash
docker compose run --rm ingestion bash -c "
  python -m ingestion.legislation.ingest &&
  python -m ingestion.acas.ingest &&
  python -m ingestion.embeddings.embedder &&
  python -m ingestion.sync_corpus_chunks
"
```

**RAG search proof:**

```bash
python -c "import urllib.request,json; ..."
# → reports/rag_search_proof_cursor.txt (total_found=10)
```

---

## Runtime evidence

| Check | Result | Artifact |
|-------|--------|----------|
| `docker compose ps` | **12/12 healthy** | `reports/docker_compose_ps_cursor.txt` |
| RAG service | healthy :8017 | compose ps |
| Graph-RAG | healthy :8018 | compose ps |

---

## Files changed (this recovery session)

| Path | Change |
|------|--------|
| `ingestion/sync_corpus_chunks.py` | **NEW** — sync corpus_chunks from legislation/ACAS tables |
| `docker-compose.yml` | Fixed db-bootstrap ingestion command |
| `Dockerfile` | `COPY tests ./tests` |
| `tests/conftest.py` | Force `LAWAPP_AUTH_MODE=mock` |
| `tests/integration/auth_helpers.py` | **NEW** |
| `scripts/fix_integration_auth.py` | **NEW** batch auth header repair |
| `scripts/proof/prove_database_integrity.sh` | `GO_LIVE_MODE=beta|production` gates |
| `scripts/run_legal_accuracy.py` | UTF-8-safe deadline_info output |
| `tests/integration/test_phase*.py` (multiple) | Mock auth headers on `/cases`, `/documents/generate` |
| `tests/integration/test_phase6a_deployment.py` | Fix duplicate headers syntax |
| `tests/integration/test_phase6b_beta_readiness.py` | Fix duplicate headers syntax |
| `tests/payment/test_payment.py` | Mock auth for gating tests |
| `tests/test_compensation.py` | Auth helper wiring |
| `docs/qa/CURSOR_GO_LIVE_READINESS_REPORT.md` | **THIS FILE** |
| `docs/qa/CURSOR_REPAIR_BACKLOG.md` | Status updates |

---

## Commands run (key)

```bash
docker compose ps
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules; SELECT COUNT(*) FROM corpus_chunks;"
GO_LIVE_MODE=beta bash scripts/proof/prove_database_integrity.sh
bash scripts/proof/prove_lawapp_full_workflows.sh
python scripts/run_legal_accuracy.py
python -m pytest tests/ -q --tb=no -p no:cacheprovider
python -m pytest tests/integration/test_phase5b_unpaid_wages.py::test_legal_accuracy_ci_gate_passes -q
docker compose run --rm backend python -m pytest --collect-only -q
# RAG: Python urllib POST localhost:8017/api/rag/search → reports/rag_search_proof_cursor.txt
```

---

## Recommended next actions (before GitHub push)

1. **Rebuild images:** `docker compose build backend db-bootstrap ingestion` — unlock full in-container pytest + automated bootstrap.
2. **Fix pytest DB env for host runs:** point `POSTGRES_PORT=5435` / password consistently so `test_auth_db.py` connects (20 errors → 0).
3. **Repair phase5a funnel tests:** add `mock_auth_headers()` to case-creation helpers (same pattern as phase3–4).
4. **Triage `test_auth_flows.py`:** refresh rotation / session table — likely test DB fixture or migration 047/050 drift.
5. **Re-run k6** after assess-path tuning: `k6 run scripts/load/k6_100k_readiness.js` → save to `reports/k6_100k_readiness_cursor.txt`.
6. **Owner: K8s deploy proof** to `lawapp-api`, `lawapp-rag`, `lawapp-ai` namespaces — document pod/ingress health only (no secret rotation without approval).
7. **Product comms:** document beta scope = **11 production modules**; partial modules fail-closed in API/UI.
8. **User approval** before `git push` — substantial uncommitted diff; no commit made in this session per instructions.

---

## Honest summary

LawApp moved from **~65% beta-ready** to **deployable for a controlled local/staging beta** with real RAG retrieval, proven user workflows, and honest fail-closed handling of incomplete legal modules. It is **not** ready for unrestricted public production: pytest debt, load test thresholds, K8s proof, and full 24-module legal coverage remain open.

**Signed verdict: GO WITH RISK (controlled beta only) / NO-GO (public production)**
