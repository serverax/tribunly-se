# LawApp Current State

Generated: 2026-07-07

## Authority

- Root: `F:\lawapp-restore`
- Working branch: `codex/phase-0`
- Base branch: `main-restored`
- Base commit: `8432368` (`fix(beta): package domains in backend image`)
- Forbidden stale bases: `origin/master`, `origin/main`
- Authoritative reset plan: `docs/handoff/phases/LAWAPP_RESET_AND_EXECUTION_PLAN.md`

All pre-recovery floor numbers, branch names, and file paths from the destroyed tree are VOID, including any references to `E:\lawapp`, `F:\lawapp`, `1866/16/49`, or stale branches outside `main-restored`.

## Reset Decisions

- D1 - Beta scope frozen: unfair dismissal, England & Wales only. No new features, modules, or refactors outside the phase files until beta ships.
- D2 - The 13 partial modules stay cut from beta. Out-of-scope queries must return not supported, never a guess.
- D3 - Stripe test mode only behind controlled access. Live keys remain permanently owner-gated.
- D4 - No bulk case-law ingestion until the FCL computational-analysis licence is granted. OGL sources remain permitted.

## Handoff Summary

- `HANDOFF.md`: Snapshot recorded a near-beta release line with RAG/ingestion verification complete and beta promotion pending owner decision. It also recorded local Docker health evidence and AKS remote visibility as unverified.
- `RELEASE_STATE.md`: Historical release context recorded RAG 1024 repair and stated verification should be re-run before beta promotion.
- `KNOWN_ISSUES.md`: Open issues included AKS DNS/remote ops, stale handover docs, untracked workspace noise, and unknown full test state pending verification.
- `NEXT_TASKS.md`: Immediate priority was RAG 1024 verification, ADR-000 checks, forbidden path checks, and ingestion/RAG metrics before beta promotion.
- `PROOF_INDEX.md`: Indexed beta gate evidence, Docker domain packaging, targeted pytest, RAG 1024 proof, and known historical path checks.

## Phase 0 Floor Baseline

- Commit tested: `8432368`
- Command: `docker compose -f docker-compose.yml run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion sh -c "cd /app && python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/integration/test_semantic_retrieval.py"`
- Environment note: base compose file used to avoid local `docker-compose.override.yml` publishing the already-allocated host port `5435`; tests used the internal `db` service.
- New baseline summary: `ERROR tests/test_knowledge_proposals.py`; `Interrupted: 1 error during collection`; `2 warnings, 1 error in 83.08s`.
- Aggregated baseline count: `0 passed / 0 failed / 0 skipped / 1 collection error`.

This is the Phase 0 floor baseline for the recovered tree. Do not substitute pre-recovery floor numbers.

## Survival Results

| Check | Result | Evidence |
| --- | --- | --- |
| PII/model boundary on RAG/embed path | Present in code; runtime proof deferred to Phase 2 | `backend/services/lawapp-rag-service/ollama_embed.py:24`, `backend/services/lawapp-rag-service/main.py:261`, `backend/core/deidentify.py:67`, `backend/core/agentic/litellm_adapter.py:57` |
| Stripe webhook proof path | Present | `backend/api/payment_routes.py:419`, `scripts/proof/prove_lawapp_full_workflows.sh:384`, `tests/security/test_payment_access.py:72` |
| 13-module scope-cut fencing | Present at tip | `client/public/js/beta-scope.js:21`, `tests/test_ui_beta_scope.py:13`, `reports/track_b_scope_cut_response.json:1`, `reports/ui_scope_enforcement_cursor.txt:8` |
| 1024-dim embedding config | Present at tip | `backend/services/lawapp-rag-service/ollama_embed.py:13`, `scripts/reembed_corpus_1024.py:27`, `backend/core/retrieve.py:291`, `tests/test_rag_1024_retrieval_repair.py:14` |

## Price Decision

- Live document-pack config: `backend/api/payment_routes.py:85` has `"full_documents": 2999,  # £29.99`.
- Matching user-facing copy remains in `backend/api/main.py`, `client/public/index.html`, and `client/public/pages/assessment.html`.
- Open owner decision: reset plan records a discrepancy between repo-shipped £29.99 and an owner decision on record of £99. Owner reconfirmation remains pending; no price change was made in Phase 0.

## Phase 0 Commits

- Task 1 phase-plan commit: `e25e0dc` (`docs: add phase reset plan`)

## Phase 1 Floor Repair State

- Phase 1 branch: `codex/phase-1`, cut from `codex/phase-0`.
- Stage 1 collection unlock: `tests/test_knowledge_proposals.py --collect-only` collected 7 tests; whole-suite collect collected 1875 tests with zero collection errors.
- Stage 2 real floor baseline after collection/bootstrap fixes: `6 failed, 1814 passed, 61 skipped, 6 warnings in 380.31s` at `a14f263`.
- Final Phase 1 floor after authorized fixes: `3 failed, 1821 passed, 57 skipped, 6 warnings in 408.45s` at `7fc5144`.
- The final floor is above the Stage 2 baseline with no unexplained regression. Remaining failures are owner-gated behavior conflicts, not collection or environment blockers.

### Phase 1 Fix Commits

- `5a4c786` - restored `propose_knowledge_gap()` so `tests/test_knowledge_proposals.py` collects.
- `00b05c5` - defined the Brain module logger for fail-soft paths.
- `fe0293a` - publishes proposal approval events to the outbox.
- `3c08e60` - restored schema bootstrap compatibility for payment events and audit events.
- `a14f263` - disables graph Redis cache when Redis is not configured in one-off test containers.
- `63fe17b` - factual lane fails closed on rules lookup outages and proposal inserts satisfy recovered schema columns.
- `670ccef` - relaxes recovered graph-only proposal type constraint.
- `00ae393` - marks zero source-table embeddings as an environment precondition skip; partial embeddings still fail.
- `7fc5144` - canonicalizes legal graph node types.

### Phase 1 Owner-Gated Items

- `tests/test_assess_orchestrator.py::test_missing_rule_fails_closed`: NI/no-rule factual lane currently returns `insufficient_grounding`; changing it to `not_supported` is legal-output status behavior and needs owner approval.
- `tests/test_brain_outbox.py::test_brain_publishes_assessment_complete_then_worker_processes`: legal-truth validation demotes an uncited/nested-citation patched `"ok"` assessment to `insufficient_grounding`; changing that gate is legal-output/citation-integrity behavior and needs owner approval.
- `tests/test_integration_tools.py::TestAnonymousFunnel::test_resume_after_login_restores_answers_exactly`: test expects anonymous special-category answers to be restored, but owner decision 2026-06-16 says anonymous flows persist only non-sensitive funnel signals. Changing this needs owner approval.

## Work Order 006 - Convergence (2026-07-08)

Branch: `cc/convergence`, cut from `main-restored@526cbcc`.

### Stack Self-Contained

- Ollama service promoted from optional profile to default compose — starts with `docker compose up`.
- All `LAWAPP_OLLAMA_BASE_URL` defaults repointed from `host.docker.internal:11434` to `http://ollama:11434` (compose service DNS) across: `docker-compose.yml`, `control-plane/src/core/config.ts`, `backend/services/lawapp-rag-service/ollama_embed.py`.
- Backend `depends_on: ollama: condition: service_healthy` ensures model availability before backend starts.
- Env-var override preserved: setting `LAWAPP_OLLAMA_BASE_URL=http://host.docker.internal:11434` still routes to a host-side Ollama.
- First-run model pulls required: `docker compose exec ollama ollama pull qwen2.5:3b-instruct-q6_K` (inference) + embedding model when available.
- Embedding model note: `bge-large-en-v1.5` is not natively in the Ollama registry. RAG embedding queries will fail until the model is imported or an Ollama-native alternative is configured.

### Live Brain Proof

- All 15 services healthy including ollama (compose ps evidence in WO006 close).
- `/health` shows `ai_provider.active=true`, `base_url=http://ollama:11434`.
- Live `POST /assess` with synthetic unfair-dismissal facts returned:
  - `status: ok`, 8 legislation-backed citations with URLs
  - `deadline.source: rules`, `authority: ERA 1996 s.111(2)`, `limitation_date: 2026-06-14`
  - CitationGuard: 5/5 citations verified via `legislation_db`
  - Governance: all 3 checks passed
  - `model_provider: LocalInferenceReasoningModel`, `base_url: http://ollama:11434`

### Hygiene

- `.tmp/` added to `.gitignore` — previously untracked, never committed, no history purge needed.
- `.tmp/frontendproof.env` contains throwaway dev values only.

### Floor

- `1834 passed / 0 failed / 44 skipped / 8 errors in 241.80s` at `42fdab5`.
- 8 errors: pre-existing `ExternalLLMForbidden` from `test_phase2_real_model.py` (external LLM forbidden by policy — not regressions).

### Data Scope (Owner Directive A7 - 2026-07-08)

- Statute spine: PENDING FULL INGESTION — owner authorized full UK employment statute + SI ingestion from OGL sources.
- `case_law` table: EMPTY — Find Case Law bulk extraction licence-gated until granted (D4, expected ~13 July 2026).
- UI scope: unchanged at 11 topics.
- Full directive: `docs/handoff/phases/A7_FULL_STATUTE_SPINE.md`.

## Work Order 009 — Final Hardening (2026-07-09)

Branch: `cc/convergence` (unchanged).

### Task 1 — Statute Spine

- Ingestion re-run processed all 26 resolved manifest entries. Census: 27 acts, 3066 legislation rows, 6038 corpus chunks (up from 22/2242/4069).
- Source-less rules: 0 genuinely missing. 4 URL-mismatch (act present, URL format differs). 11 SI schedule rules (owner-seeded constants). 2 ERA 2025 (suppressed).
- See `reports/RULES_VERIFICATION_SHEET.md` Section B (updated).

### Task 2 — ERA 2025 Suppression

- `is_prospective = true` gate confirmed in `retrieve_rules()`. Today-dated regression test: 11 passed.
- RULES_VERIFICATION_SHEET flags → RESOLVED-SUPPRESSED.

### Task 3 — Freshness Automation

- `freshness-monitor` compose service added (monitoring profile). Weekly cadence.
- ERA 2025 commencement check hits legislation.gov.uk for commencement SIs.
- One full run proven: `reports/freshness_proof.md`.

### Task 4 — Security Hardening

- pip-audit clean, no real secrets, 5 security headers deployed, rate limiting proven (429 on request 11).
- Full report: `reports/security_sweep.md`.

### Task 5 — Test-Lock (k6 Smoke)

- Health p95 = 926ms (cold-start artifact, median 130ms). Assess p95 = 28.5s (under 60s threshold).
- 0% failure rate, all citations verified.
- Full report: `reports/k6_smoke_latency_report.md`.

### Task 6 — Accessibility + Plain-English

- 5 P2/P3 markup fixes from `frontend_accessibility_log.md`.
- 6 jargon fixes: "EDT" acronym removed from labels, "ACAS EC" expanded to "ACAS early conciliation" in all user-facing text.
- Full log: `reports/frontend_accessibility_log.md` (WO009 sections).

### Task 7 — Ship Package

- Floor: pending (run in progress).
- 15/15 services healthy.
- Owner runbook: `reports/OWNER_RUNBOOK.md`.
- State docs: this file + `reports/SHIP_READINESS.md` + `reports/PROGRESS_BOARD.md`.
