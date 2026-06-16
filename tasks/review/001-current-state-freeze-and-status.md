# Task 001  -  Current State Freeze and Status

**Mode:** Autonomous LawApp Recovery  -  read-only freeze (no application code changes)
**Branch:** `recovery/lawapp-autonomous-stabilisation`
**Date:** 2026-06-04
**Author:** Autonomous recovery agent
**Method:** 6 read-only analysis subagents (backend routes, service map, platform/CI/K8s completed; frontend, db-rag, security aborted on an injected hook and were synthesized from command-proven session evidence) + direct repo/git/docker/cluster inspection performed this session.

---

## 1. Scope & Method

This is a **freeze**: a point-in-time, evidence-backed snapshot of what actually exists and works versus what is claimed. No application code was modified in this task. Only `tasks/` control documents and task folders were created.

Evidence classes used:
- **PROVEN**  -  verified by command (HTTP code, DB row, test pass, kubectl output) this session.
- **CODE-VERIFIED**  -  confirmed by reading source this task; not runtime-proven.
- **CLAIMED**  -  asserted in repo docs/commits, not independently confirmed.

---

## 2. Repository State

- Active branch: `recovery/lawapp-autonomous-stabilisation` (branched from `main` HEAD).
- Working tree (uncommitted): `client/public/css/styles.css` (full professional redesign), `client/public/index.html` (2 inline boxes → CSS vars), `.claude/settings.local.json`; untracked scaffolding/evidence dirs (`docs/design/`, `reports/hard-exit/`, `audit/`, `.playwright-mcp/`, screenshots, `tasks/LAWAPP_BEHAVIOUR_CONSTITUTION.md`).
- `docker compose config`: **VALID** (PROVEN this session).
- `.github/workflows/`: 11 workflow files present (PROVEN  -  file count).
- `pyproject.toml`, `package.json`: present; leaked tokens redacted in working tree (PROVEN) **but remain in git history** (see §10).

---

## 3. Backend API (monolith)  -  `backend/api/main.py` (+ routers)

**Status: REAL, broad surface. CODE-VERIFIED.**

- **~57 routes** across: health/info, auth (register/token/me, JWT real), assessment (`/assess`, `/api/diagnosis`  -  real orchestrator + path-splitter), reasoning (`/reasoning/route`, `/reasoning/stream` SSE), sovereign (`/api/v1/lawapp/ingest` reverse-extraction → `user_legal_profiles`; `/api/v1/lawapp/query` DB-first hybrid + SSE + WASM citation guard, fail-closed ESCALATED), documents (real template generation + Critic citation-pin gate + payment gating), cases CRUD (encryption at rest, ownership-checked), uploads/extraction (OCR, fail-closed if no facts), timeline/escalation/reminders/deadlines, handoff leads (KMS-envelope PII), funnel, payment (session/status/webhook), admin (key-gated), test/debug (admin-gated in prod), static client.
- Auth deps: `get_current_user` (X-User-ID or Bearer JWT), `_require_case_owner`, `_require_admin_key`, `_require_admin_in_production`.
- **Flags:** `POST /api/payment/create-session` with `PAYMENT_MODE=disabled` returns hardcoded `payment_required:true` (intended free-mode behavior, not a bypass). `/api/test/*` return mock responses, admin-gated in prod.

---

## 4. Distributed Services  -  `services/` (CODE-VERIFIED + 7/8 PROVEN in-cluster)

All HTTP services use `services/_common.create_service()` (standard `/health`, `/ready`, X-Trace-ID, JSON logs, real `_db_ready()`).

| Service | Endpoints | Backend wiring | Class |
|---|---|---|---|
| brain | assess, workflow/execute | `backend.core.brain.*` | REAL+WIRED |
| rules_engine | rules/evaluate, deadline, compensation | `backend.core.retrieve`, `domains.employment.*` | REAL+WIRED |
| rag_retrieval | retrieve | `backend.core.retrieve.retrieve` | REAL+WIRED |
| rag_ingestion | ingest/legal-source | `perpetual_law_brain.ingest_url` (whitelist+critic, 422 on reject) | REAL+WIRED |
| citation_guard | citations/validate | `corpus_citation_guard.valid_corpus_uuids` | REAL+WIRED |
| llm_gateway | generate | `LocalInferenceReasoningModel` (PII 422, 503 no-fallback) | REAL+WIRED |
| crawler | crawl/approved-source | `WhitelistCrawler.fetch` (403 pre-network) | REAL+WIRED |
| document_service | POST generate / GET {id} | real generators; **GET = honest 501** | REAL, GET not wired |
| worker | none (sleep loop) | none | **STUB** |

Dead: dash-named dirs (`lawapp-brain` etc.) = migration debris, no code.

**In-cluster PROVEN:** 7/8 services return real HTTP 200 over cluster DNS. **brain = only failing** (see §8).

---

## 5. DB / RAG / Ingestion (CODE-VERIFIED)

- Schema: `db/migrations/*`  -  `rules`, `corpus_chunks`, legislation/acas/case_law corpus, `cases`, `user_legal_profiles`, legal graph nodes/edges, `payment_events`.
- Retrieval (`backend/core/retrieve.py`): rules table + pgvector + BM25 hybrid; **fail-closed / insufficient_grounding** when corpus empty  -  does not fabricate authorities.
- Citation guard validates LLM claims against **real `corpus_chunks` UUIDs**; fabricated UUID → invalid.
- Legal values (deadlines/caps/qualifying period): **read from rules table, not hardcoded** (PROVEN earlier this session via rules-driven assess + tests).
- Ingestion: whitelist + critic + graph + embed gates; uncited rows rejected (authority_ref required).
- **Open:** real corpus population on the live cluster DB not re-confirmed this task (DB blocked, §8).

---

## 6. Inference Policy  -  LOCAL OLLAMA ONLY (PROVEN GREEN)

- Central `backend/core/inference_policy.py`: `assert_no_external_llm_enabled`, fail-closed `InferenceUnavailable`, allowed backend = `ollama`, base URL + model from env (`qwen2.5:3b-instruct-q6_K`).
- External providers (OpenAI/Anthropic/OpenRouter) neutralized in `models.py`/`classify`/`litellm_adapter`; constructors raise `ExternalLLMForbidden`.
- CI/compose stripped of external LLM secrets.
- **Tests: 30 passed** in Docker ingestion (13 policy + 17 sovereign/path/streaming)  -  PROVEN.

---

## 7. Security / Auth / Payment (PROVEN test pass + CODE-VERIFIED)

- **Security suite: 134 passed** (PROVEN this session).
- Auth modes: none/mock/jwt; mock blocked in production; X-User-ID trusted only in mock.
- Ownership: `_require_case_owner` on all `/cases/{id}/*`  -  cross-user access prevented (CODE-VERIFIED).
- Payment: webhook signature enforced; no raw-token unlock; disabled-mode = free, not bypass.
- PII: de-identified before model boundary; handoff leads KMS-enveloped.
- XSS: home (`index.html`) uses static markup + `auth.js`; no user-data `innerHTML` on home. **Full client XSS sweep not completed** (frontend subagent aborted)  -  carry to a later task.

---

## 8. Live Cluster (Talos K8s)  -  PARTIAL (PROVEN)

- 3 control-plane nodes; namespaces lawapp-{ai,rag,api,security,monitoring}.
- 7/8 in-cluster services HTTP 200 (PROVEN).
- **brain `/health` = 503**, root-caused through 5 layers to: `FATAL: password authentication failed for user "lawapp"`  -  the live Postgres password was rotated post-init; secret values no longer match the DB role. **Fix = owner-side DB `ALTER USER` / password reconcile  -  NOT performed** (live DB mutation is in the MUST-NOT-without-approval set). This is the single blocker to 8/8.

---

## 9. CI / CD & GitHub→Cluster (PROVEN + CODE-VERIFIED)

- Path: push `main` → GHCR `ghcr.io/serverax/*` → Talos via `lawapp-deploy-talos.yml` (kubectl apply `infra/k8s/`). Secrets created in-workflow from GH Actions secrets (POSTGRES_PASSWORD/JWT_SECRET/ENCRYPTION_KEY/ADMIN_API_KEY), guarded against empty overwrite.
- **Gate status (PROVEN):** `lawapp build images` = GREEN. `lawapp-ci` / `lawapp-ci-cd` = RED  -  pre-existing (WASM binary integrity check missing artifact + `pip-audit-local`).

---

## 10. Secrets / Leaks (PROVEN  -  OPEN RISK)

- Leaked GitHub PATs found in `package.json` + `tasks/multiagentlawapp.md`; **redacted in working tree** (PROVEN).
- **Remain in git history** → rotation + history scrub required (not done; rotation is approval-gated).

---

## 11. Frontend / UI-UX (PROVEN home; rest PENDING)

- Static `client/public/` served by monolith. Professional redesign applied: navy `#16314f` + brass `#b08d4f`, serif display, frosted sticky nav, dark footer, badges, focus rings, dark-mode/print/reduced-motion. Class names preserved.
- **Home page redesign PROVEN** live at `localhost:8000` (screenshot). Other pages (intake, results, saved_case, etc.) **not individually re-verified** against the new system  -  carry forward.

---

## 12. Tests Summary (PROVEN this session)

- Local-Ollama policy + sovereign/path/streaming: **30 passed** (Docker ingestion).
- Security: **134 passed**.
- Distributed + ingestion service contracts: present and exercised.
- **Not run this task:** full repo pytest sweep; e2e browser journeys beyond home; load test (10k target unmet, no run).

---

## 13. Gaps / Risks Register

| # | Gap | Severity | Owner action needed |
|---|---|---|---|
| G1 | brain 503  -  live DB password mismatch | **BLOCKER** | DB `ALTER USER` / password reconcile (owner) |
| G2 | Leaked PATs in git history | **HIGH** | rotate tokens + scrub history |
| G3 | CI red: WASM integrity + pip-audit-local | HIGH | provide WASM artifact / triage audit |
| G4 | worker service = stub | MED | implement or remove |
| G5 | document_service GET = 501 | MED | wire persistent doc store |
| G6 | Full client XSS sweep incomplete | MED | dedicated security task |
| G7 | Non-home pages not verified vs new design | MED | UI acceptance task |
| G8 | 10k load target unproven | MED | load test task |
| G9 | Live corpus reality unconfirmed (DB blocked) | MED | re-confirm after G1 |
| G10 | Legal corpus provenance chain unproven end-to-end (fetch→hash→parse→chunk→embed→retrieve→CitationGuard) | HIGH | tasks 007a–007d |

---

## 14. What IS solid (do not regress)

- Local-Ollama-only enforcement (green tests).
- 8 real+wired distributed services; 7/8 live 200.
- Rules-first, fail-closed retrieval; citation guard against real corpus UUIDs; no hardcoded legal values.
- Security suite green; ownership + payment integrity + PII de-identification.
- Professional home UI live.
- docker compose valid; build-images CI green.

---

## 15. VERDICT

### REJECT CURRENT STATE

**Rationale:** The platform is architecturally sound and largely real  -  not a stub farm  -  but it is **not in an acceptable, releasable state**. Hard items block acceptance:

1. **G1  -  production brain is down** (503, DB password mismatch). The core orchestrator does not serve in the live cluster; 8/8 in-cluster smoke is unmet.
2. **G2  -  leaked credentials persist in git history**  -  an unresolved security exposure.
3. **G3  -  CI gates are red**  -  no green pipeline to certify releases.
4. **G10  -  legal data provenance chain not proven end-to-end**  -  ingestion reality unverified against the full source→CitationGuard chain.

Acceptance requires at minimum G1 + G2 + G3 + G10 resolved (G1 owner/approval-gated), then re-freeze. Until then: **REJECT**.

**Next task:** 002 should target G2/G3 (in-repo, autonomously actionable) and the 007a–007d legal-data provenance chain; G1 requires an owner DB action outside autonomous authority.
