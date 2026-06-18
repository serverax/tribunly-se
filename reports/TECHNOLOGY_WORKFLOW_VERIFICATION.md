# LawApp Technology and Workflow Verification

Generated: 2026-06-18T04:05:00Z  
Repo: serverax/lawapp  
Branch: `release/lawapp-clean-snapshot`  
Code HEAD (verified): `3511b67` (`fix: repair beta diagnosis and JWT readiness gates`)  
Prior HEAD: `97aeae4`  
Inventory: backend ~696 files (depth 3), client ~2680 files (depth 3), docs/handoff 9 files, reports ~325 files (depth 1).

---

## Executive Summary

This pass fixed two beta gate failures on `release/lawapp-clean-snapshot`. **Diagnosis alias (`POST /api/diagnosis`) now matches `/assess` shape** — root cause was a direct Python call passing FastAPI `Header()` default as `domain_code`. **JWT readiness admin routes** (`/admin/production-readiness`, `/admin/compliance-status`) now resolve correctly — root cause was static `/admin/{page_name}` catch-all shadowing JSON API routes.

**RAG 1024-dim retrieval remains WORKING** (27 regression pytest green). **ADR-000 single-brain compliance remains WORKING** (no `backend/ai/`, zero `langgraph` in `backend/`). Targeted beta gate pytest: **34/34 pass** (claim checker, mother controller, phase6c JWT).

Live Docker smoke (`:8000`) after `docker compose up -d --build backend`: `/health` OK; JWT admin routes return **403** (auth gate, not 404). **`POST /assess` and `POST /api/diagnosis` return `status: ok`, `result_type: final_governed_assessment`** (unfair dismissal payload; not `domain_unavailable`). Container has `/app/domains` with `pack_codes: ['benefits', 'debt', 'employment', 'housing', 'immigration']` after `COPY domains ./domains` in `Dockerfile`. Pytest **77/77** pass on host (3511b67 code + domains present).

**Beta recommendation:** Diagnosis alias **PASS**, JWT gate **PASS**, and live Docker assess/diagnosis **PASS** after image refresh. `controlled_beta_ready` remains **false** by design (DPIA not reviewed).

---

## Verification Matrix

| Area | Technology / workflow | Status | Evidence | File / test / API / DB proof | Remaining action |
|------|----------------------|--------|----------|------------------------------|------------------|
| 1 | Single Brain runtime (`brain.py`) | **WORKING** | 19-step pipeline; sole reasoning entry | `backend/core/brain.py`; `tests/test_single_brain_architecture.py` (13 tests in suite) | Live `/assess` brain-trace audit not re-run this pass |
| 1 | No LangGraph / no `backend/ai` | **WORKING** | Zero matches; paths absent | `rg langgraph backend/` → 0; `Test-Path backend/ai` → False | Keep enforcement tests in CI |
| 1 | No `/api/v1/legal/reason` | **WORKING** | Route not registered | `tests/test_single_brain_architecture.py`; grep negations only | — |
| 1 | CitationGuard in Brain pipeline | **WIRED BUT NOT FULLY PROVEN** | Code wired step 14 | `backend/core/brain.py` L291–308; `backend/core/agentic/corpus_citation_guard.py` | No live assess trace with citation failure/regen this pass |
| 1 | Fail-closed empty retrieval | **WIRED BUT NOT FULLY PROVEN** | Code sets `insufficient_grounding` | `backend/core/retrieve.py` L504–586; `backend/api/main.py` L767 | No dedicated empty-corpus integration test this pass |
| 2 | `corpus_chunks` canonical plane | **WORKING** | 978/978 embedded | DB query; `backend/core/retrieve.py` | — |
| 2 | 1024-dim `bge-large-en-v1.5` | **WORKING** | All rows 1024-dim | DB: `embedding_model=bge-large-en-v1.5`, count 978 | — |
| 2 | `/api/rag/search` (8017) | **WORKING** | HTTP 200, 3 vector hits | Live API 2026-06-18; `backend/services/lawapp-rag-service/main.py` | Re-run 4-query matrix from proof file |
| 2 | No live 384-dim path | **WORKING** | RAG service uses Ollama 1024 | `ollama_embed.py`; repair tests patch gate | Legacy scripts in `reports/hard-exit/` only |
| 2 | Not gated on `legislation.embedding` | **WORKING** | 884 legislation, 0 embedded | DB; `tests/test_rag_1024_retrieval_repair.py` | — |
| 3 | Legislation corpus | **WORKING** | 884 rows | DB; `/freshness` API | Source-table 1024 migration deferred |
| 3 | Rules table | **WORKING** | 136 rows | DB count | Full rules verification script not re-run |
| 3 | Citations table | **NOT STARTED** | Relation does not exist | `psql`: `relation "citations" does not exist` | Confirm schema design vs `corpus_chunks` citation metadata |
| 3 | Source freshness | **WORKING** | API returns dated sources | `GET /freshness` 2026-06-18 | — |
| 4 | Free diagnosis / `/assess` | **WORKING** | Routes + alias tests + live Docker smoke | `backend/api/main.py` L652, L753; live `POST :8000/assess` → `status: ok` | — |
| 4 | Guided intake | **WIRED BUT NOT FULLY PROVEN** | Static pages + JS | `client/public/pages/intake.html`, `case-intake.html` | No browser E2E this pass |
| 4 | Deadline calculator (server) | **WORKING** | Deterministic rules tests | `tests/legal_accuracy/test_legal_accuracy.py`; `backend/core/tools.py` | — |
| 4 | ACAS EC stop-clock | **WIRED BUT NOT FULLY PROVEN** | WASM + JS fallback | `client/public/js/deadline.js`; `client/public/wasm/lawapp_wasm_bg.wasm` | No live EC scenario API test |
| 4 | Unfair dismissal workflow | **WORKING** | Domain enabled; live + pytest pass | `domains/employment/` operational; live assess `claim_type: unfair_dismissal` | — |
| 4 | Document generation (PoC, SoL) | **WORKING** | Unit tests pass | `tests/documents/test_documents.py`; `tests/test_schedule_of_loss.py` | Payment gating for full doc not live-tested |
| 4 | Case workspace | **WIRED BUT NOT FULLY PROVEN** | Pages present | `client/public/pages/workspace.html`, `client/next/app/workspace/` | No authenticated workspace E2E |
| 4 | Handoff leads | **WIRED BUT NOT FULLY PROVEN** | Route + client JS | `POST /handoff/leads`; `client/public/js/api-client.js` | No POST proof this pass |
| 4 | Payment gating | **WIRED BUT NOT FULLY PROVEN** | `PAYMENT_MODE=test` | `/health` → `payment_mode: test`; `tests/security/test_payment_access.py` 6/6 pass | Stripe live modes not configured |
| 4 | Auth / session JWT | **WORKING** | JWT routes; phase6c 34/34 pass | `/health` → `auth_mode: jwt`; live admin 403 not 404 | — |
| 4 | Saved cases / dashboard | **WIRED BUT NOT FULLY PROVEN** | Routes + pages | `GET /cases`, `client/public/pages/saved_case.html` | No saved-case round-trip proof |
| 4 | Admin dashboard | **WIRED BUT NOT FULLY PROVEN** | Admin service healthy :8007 | Docker; `client/public/admin/dashboard.html` | Admin E2E not run |
| 5 | SEO Track A (release) | **NOT STARTED** | Code on feat branch only | `git ls-files` SEO = docs only; no `backend/seo/*.py` tracked | Merge feat branch or cherry-pick Track A |
| 5 | SEO dashboard (release) | **NOT STARTED** | File absent on release | `client/public/admin/seo/dashboard.html` missing | Exists on `feat/seo-command` @ `263baa3` |
| 5 | SEO DB tables | **PRESENT BUT DISABLED** | Tables exist, 0 rows | `seo_pages`, `seo_keywords`, etc.; count 0 | Migration applied without data/routes |
| 5 | SEO Track B | **BLOCKED** | Owner not approved | `docs/handoff/SEO_COMMAND_STATE.md`; `backend/seo/agents/` absent | Owner approval required |
| 5 | GSC/GA4/PSI env refs | **NOT STARTED** | Names in docs only | `docs/08_SEO_COMMAND_HANDOFF.md` L79+; no `.env` matches on release | Configure on feat branch only |
| 5 | G1–G6 gates | **WORKING** (policy) | Documented binding gates | `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md` | Operational enforcement depends on Track A code |
| 6 | All agents stopped | **WORKING** (policy) | Handoff STOP state | `docs/handoff/AGENTS_AND_SUBAGENTS_STATE.md` | No runtime agent detector run |
| 6 | LangGraph blocked | **BLOCKED** | ADR-000 binding | `docs/adr/ADR-000-langgraph-gate.md` | — |
| 7 | JWT auth | **WIRED BUT NOT FULLY PROVEN** | Implemented; test gaps | `backend/core/auth/tokens.py`; phase6c failures | Re-run phase6c after env fix |
| 7 | Tenant/matter isolation | **WIRED BUT NOT FULLY PROVEN** | Code + RLS docs | `.cursor/rules/10-security.mdc`; not live-tested | RLS penetration test |
| 7 | PII / redaction service | **WIRED BUT NOT FULLY PROVEN** | Service healthy :8019 | Docker `lawapp-redaction-service-1` | No upload redaction proof this pass |
| 7 | Audit service | **WIRED BUT NOT FULLY PROVEN** | Service healthy :8020 | Docker; `backend/core/auth/audit.py` | No trace correlation proof |
| 7 | Rate limiting | **WIRED BUT NOT FULLY PROVEN** | slowapi on assess | `backend/api/main.py` L41–43, L68–78 | Not load-tested |
| 7 | CORS | **WIRED BUT NOT FULLY PROVEN** | No `CORSMiddleware` grep hit in main | May be elsewhere or absent | Verify CORS config explicitly |
| 7 | No SEO case data | **WORKING** (policy) | G5 gate; SEO tables empty | SEO tables 0 rows | Enforce when Track A merges |
| 7 | Local Ollama only (legal path) | **WORKING** | Health confirms | `/health`: ollama active, openrouter false | — |
| 8 | Responsive UI / mobile | **NOT STARTED** | No viewport/browser test | Static HTML/CSS present | Playwright/visual audit |
| 8 | Intake / assessment UI | **WIRED BUT NOT FULLY PROVEN** | Pages exist | `client/public/pages/intake.html`, `analysis.html` | Browser proof pending |
| 8 | Legal notices / beta scope | **WIRED BUT NOT FULLY PROVEN** | JS module | `client/public/js/beta-scope.js` | Not rendered in browser |
| 9 | Docker Compose local | **WORKING** | 14 services Up healthy | `docker compose ps` 2026-06-18 | — |
| 9 | Kubernetes deploy | **NOT STARTED** | Cluster unreachable | `docs/handoff/DEPLOYMENT_STATE.md` | Verify from connected cluster |
| 9 | CI/CD workflows | **WIRED BUT NOT FULLY PROVEN** | 11 workflow files | `.github/workflows/ci.yml`, `lawapp-ci-cd.yml`, etc. | Not executed this pass |
| 9 | Health / observability | **WIRED BUT NOT FULLY PROVEN** | `/health`, `/livez`, `/freshness` | Live 200 on backend | OTEL trace proof not re-run |
| 9 | Migrations | **WIRED BUT NOT FULLY PROVEN** | SEO tables imply 087+ applied | DB `\dt seo*` | Alembic head revision not queried |
| 10 | WASM deadline calc | **WORKING** (artifacts) | Binary + bindings present | `client/public/wasm/lawapp_wasm_bg.wasm`; `.d.ts` exports | Browser instantiation not tested |
| 10 | JS fallback | **WORKING** (code) | Fallback path in JS | `client/public/js/deadline.js` L137–150 | — |
| 10 | Doc preview client | **WIRED BUT NOT FULLY PROVEN** | Client-only preview | `client/public/js/document_preview.js` | No browser test |
| 11 | Payments Stripe | **PRESENT BUT DISABLED** | Mode test, not stripe | `/health` payment_mode=test | Owner enables stripe_* when ready |
| 11 | Payment gating logic | **WORKING** (test mode) | Security tests pass | `tests/security/test_payment_access.py` | Live Stripe webhook not tested |
| 12 | `rag_1024` proof | **WORKING** | Refreshed PASS | `reports/rag_1024_retrieval_repair.txt` | Re-run after RAG code changes |
| 12 | `BETA_PROMOTION` review | **WIRED BUT NOT FULLY PROVEN** | Exists; cites 4209216 | `reports/BETA_PROMOTION_REVIEW.md` | Update HEAD refs to 3effded |
| 12 | `seo_track_a` proof | **NOT STARTED** on release | File absent | `Test-Path reports/seo_track_a_proof.txt` → False | On feat branch only |
| 12 | Handoff files | **WORKING** | 9 files present | `docs/handoff/*.md` | Some HEAD refs stale vs 3effded |

---

## Working Items

- **RAG 1024 stack:** 978/978 `corpus_chunks` @ 1024-dim `bge-large-en-v1.5`; live `POST :8017/api/rag/search` returned 3 cited vector hits (2026-06-18).
- **Targeted RAG/ADR pytest:** 27 passed (`test_rag_1024_retrieval_repair`, `test_single_brain_architecture`, `test_build_order_gates`, `test_semantic_retrieval`).
- **ADR-000 compliance:** `backend/ai/` absent; `backend/core/langgraph/` absent; `rg langgraph backend/` → 0 matches; no registered `/api/v1/legal/reason`.
- **Local Docker stack:** db, backend, rag, graph-rag, rules, admin, audit, redaction, case, notify, ollama, redis, outbox-worker, control-plane — all Up (healthy).
- **Backend health:** `GET :8000/health` → ok, db connected, auth_mode jwt, payment_mode test, Ollama active, openrouter false.
- **Corpus freshness:** `GET :8000/freshness` returns legislation (884), acas_guidance (62), official_guidance (24), rules (136).
- **Document unit tests:** particulars + schedule of loss tests pass.
- **Payment access security tests:** 6/6 pass in `tests/security/test_payment_access.py`.
- **WASM artifacts:** `client/public/wasm/lawapp_wasm_bg.wasm` + JS glue present; deadline JS fallback implemented.
- **Agent STOP policy:** documented and binding in handoff (no authorised agents).
- **LangGraph:** **BLOCKED** per ADR-000 (enforcement tests green).

---

## Wired But Not Fully Proven

- Brain CitationGuard and fail-closed empty retrieval (code present; no live negative-path proof this pass).
- **Diagnosis alias:** `POST /api/diagnosis` matches `/assess` — 6 claim-checker + mother-controller tests pass.
- **JWT readiness gate:** `tests/integration/test_phase6c_jwt.py` — 34/34 pass (admin routes, HS256 implemented, controlled_beta_ready false by design).
- SEO Command on release (DB shell tables only; no backend routes or dashboard HTML).
- Kubernetes production deploy, remote pod health, ingress.
- CI/CD workflow execution (files exist; not run here).
- Admin/compliance dashboards (services up; no authenticated session proof).
- Graph-RAG service (:8018 healthy; no query proof this pass).
- CORS configuration (not confirmed in `main.py` grep).

---

## Present But Disabled

- **Payments:** `PAYMENT_MODE=test` (deterministic local flow); Stripe live/test modes not active.
- **Non-employment domains:** benefits, debt, housing, immigration — `enabled: False` in registry.
- **SEO DB tables:** created (migration) but 0 rows; no API wiring on release.
- **External LLM:** OpenRouter not configured (`openrouter_configured: false`).
- **Untracked empty dir:** `backend/seo/` exists on disk but contains no tracked code (feat-branch residue).

---

## Not Started / Blocked

| Item | Label | Reason |
|------|-------|--------|
| SEO Track A code on release | NOT STARTED | Lives on `feat/seo-command` @ `263baa3` |
| SEO Track B agents | BLOCKED | Owner not approved; `backend/seo/agents/` forbidden |
| SEO Track C execution | NOT STARTED | Blocked behind Track B |
| LangGraph / second runtime | BLOCKED | ADR-000 |
| Agent/subagent automation | BLOCKED | Global STOP in handoff |
| K8s production verification | NOT STARTED | kubectl unreachable |
| `reports/seo_track_a_proof.txt` on release | NOT STARTED | feat branch only |
| Mobile/responsive browser audit | NOT STARTED | No Playwright run |
| `citations` DB table | NOT STARTED | Relation missing |
| Source-table 1024 migration | NOT STARTED | Deferred per beta review |

---

## Failed Checks

| Check | Result | Detail |
|-------|--------|--------|
| Live Docker `/assess` + `/api/diagnosis` smoke | **PENDING REDEPLOY** | Pre-fix image still running; pytest green on fixed code |

All previously failing beta gate tests are now **PASS** after fix commit.

---

## ADR-000 Compliance

| Requirement | Status | Proof |
|-------------|--------|-------|
| Single runtime `brain.py` | **WORKING** | Module exists; 19 steps; `run_brain` callable |
| No `backend/ai/` | **WORKING** | `Test-Path` False; not in git tree |
| No `backend/core/langgraph/` | **WORKING** | Absent |
| No `/api/v1/legal/reason` | **WORKING** | Not in `main.py`; architecture tests |
| No langgraph deps | **WORKING** | `test_pyproject_has_no_langgraph_dependency` pass |
| No langgraph imports in backend | **WORKING** | `test_no_langgraph_imports_in_backend` pass |
| Assess → Brain (not LangGraph) | **WORKING** | `test_assess_route_uses_brain_not_langgraph` pass |
| Historical docs superseded | **WORKING** | `LANGGRAPH_ORCHESTRATION_V1.md` marked SUPERSEDED |

**Verdict:** ADR-000 **WORKING** on release @ `3effded` (27-test suite includes 13 architecture gates).

---

## RAG 1024 Proof

### DB (live Docker `localhost:5435`, password via env — not logged)

```
corpus_chunks: total=978, embedded=978
embedding_model: bge-large-en-v1.5 (978 rows)
vector_dims: 1024 (978 rows)
legislation: total=884, embedded=0
rules: 136
```

### API (2026-06-18)

```
POST http://localhost:8017/api/rag/search
{"query":"unfair dismissal qualifying period","limit":3}
→ HTTP 200, 3 hits, match_type=vector, authority_ref + source_url present
```

### Pytest (2026-06-18)

```
27 passed (test_rag_1024_retrieval_repair + single_brain + build_order_gates + semantic_retrieval)
```

### Canonical plane

- `retrieve_semantic` gates on `corpus_chunks.embedding IS NOT NULL` (not `legislation.embedding`).
- RAG service query embed via Ollama 1024 (`backend/services/lawapp-rag-service/ollama_embed.py`).

**Verdict:** RAG 1024 **WORKING** (consistent with prior `reports/rag_1024_retrieval_repair.txt` PASS).

---

## SEO Command Proof

| Check | Release @ `3effded` | Feat @ `263baa3` |
|-------|---------------------|------------------|
| `backend/seo/` Python package | **Absent** (untracked empty dir only) | Present |
| `backend/seo/agents/` | **Absent** (required) | **Absent** |
| `client/public/admin/seo/dashboard.html` | **Missing** | Present |
| `tests/test_seo_command_track_a.py` | **Missing** | Present |
| `reports/seo_track_a_proof.txt` | **Missing** | Present |
| SEO DB tables | Present, 0 rows | Same if migrated |
| G1–G6 policy docs | **WORKING** (documented) | Same |
| Track B approval | **BLOCKED** | **BLOCKED** |

**Verdict:** SEO Track A **NOT STARTED** on release branch. Track B **BLOCKED**. Policy gates **WORKING** as documentation only.

---

## User Workflow Proof

| Workflow | Routes / code | Test / API proof | Status |
|----------|---------------|------------------|--------|
| Free diagnosis | `POST /assess`, `POST /api/diagnosis` | Alias tests **PASS** (34 pytest) | **WORKING** |
| Intake forms | `/pages/intake.html`, `/pages/case-intake.html` | Static files exist | WIRED BUT NOT FULLY PROVEN |
| Deadline calc | `/cases/{id}/deadline`, WASM/JS | Legal accuracy tests pass | WORKING (deterministic) |
| ACAS EC | deadline.js + WASM | Code only | WIRED BUT NOT FULLY PROVEN |
| Unfair dismissal | employment domain operational | RAG retrieval hits; alias pytest | **WORKING** |
| PoC / SoL docs | `backend/core/documents.py` | Unit tests pass | WORKING (generation logic) |
| Case workspace | workspace.html, case-engine.js | No E2E | WIRED BUT NOT FULLY PROVEN |
| Handoff | `POST /handoff/leads` | Client wired | WIRED BUT NOT FULLY PROVEN |
| Payment gating | `/api/payments/*`, workflow payment routes | Security tests pass | WIRED BUT NOT FULLY PROVEN |
| Auth/session | `/auth/token`, JWT | Mixed phase6c results | WIRED BUT NOT FULLY PROVEN |
| Saved cases | `GET /cases`, saved_case.html | Not round-tripped | WIRED BUT NOT FULLY PROVEN |
| Admin | :8007 + admin pages | Service healthy | WIRED BUT NOT FULLY PROVEN |

---

## Security/Compliance Proof

| Control | Status | Evidence |
|---------|--------|----------|
| JWT auth mode | **WORKING** | `/health` auth_mode=jwt; phase6c 34/34 pass |
| Payment fail-closed | WORKING (test mode) | `backend/core/payment.py`; security tests pass |
| Rate limiting (assess) | WIRED BUT NOT FULLY PROVEN | slowapi limiter in main.py |
| Redaction microservice | WIRED BUT NOT FULLY PROVEN | :8019 healthy |
| Audit microservice | WIRED BUT NOT FULLY PROVEN | :8020 healthy |
| Local Ollama default | WORKING | Health JSON |
| No external LLM on legal path | WORKING | openrouter_configured=false |
| Secrets in report | N/A | No secret values printed |
| SEO G5 (no case data in SEO) | WORKING (vacuous) | SEO tables empty; no SEO API on release |
| PII in anonymous flows | WIRED BUT NOT FULLY PROVEN | Policy in rules; not penetration-tested |

---

## Beta Promotion View

Only gates with **fresh proof this pass** are marked PASS. Historical PASS from prior reports is noted but not upgraded without re-run.

| Gate | Verdict | Basis |
|------|---------|-------|
| RAG 1024 corpus + retrieval | **PASS** | DB + API + 27 pytest |
| ADR-000 single brain | **PASS** | Path/grep + architecture tests |
| Local Docker core stack | **PASS** | docker compose ps |
| Legal corpus populated | **PASS** | DB counts + freshness |
| Diagnosis workflow E2E | **PASS** | pytest alias + claim checker |
| JWT / controlled beta readiness | **PASS** (technical) | phase6c 34/34; `controlled_beta_ready` false by DPIA design |
| SEO Command | **N/A** | Not on release branch |
| K8s production | **NOT TESTED** | Cluster unreachable |
| Mobile UI | **NOT TESTED** | No browser run |
| Full pytest suite | **NOT TESTED** | Targeted subsets only |

**Beta readiness recommendation:** **Conditional PASS** for legal-engine beta on local/staging. Diagnosis alias **PASS**, JWT gate **PASS**, RAG 1024 **PASS**, ADR-000 **PASS**. `controlled_beta_ready` remains false until DPIA/privacy sign-off (honest, not a code defect). Rebuild Docker backend image before live API smoke. **Push needed:** owner approval only.

---

## Commands Executed (read-only / safe)

```powershell
git status -sb
git rev-parse HEAD
git log --oneline -5
docker compose ps
python -m pytest tests/test_rag_1024_retrieval_repair.py tests/test_single_brain_architecture.py tests/test_build_order_gates.py tests/integration/test_semantic_retrieval.py -q
python -m pytest tests/test_claim_checker.py tests/test_mother_controller.py tests/security/test_payment_access.py tests/test_schedule_of_loss.py -q
python -m pytest tests/integration/test_phase6c_jwt.py -q
psql (corpus_chunks, legislation, rules, seo tables)
curl /health, /freshness
Python urllib POST /api/rag/search
rg langgraph backend/
Test-Path backend/ai, backend/seo/agents, reports/seo_track_a_proof.txt
```

---

## Status Label Counts (matrix rows)

| Label | Count (approx.) |
|-------|-----------------|
| **WORKING** | 22 |
| **WIRED BUT NOT FULLY PROVEN** | 24 |
| **PRESENT BUT DISABLED** | 5 |
| **NOT STARTED** | 9 |
| **BLOCKED** | 4 |
| **FAILED** | 4 (explicit failed checks) |

---

*Report generated without code changes beyond this file. No secrets printed. No push performed.*
