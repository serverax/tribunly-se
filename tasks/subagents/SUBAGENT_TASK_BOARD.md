# LAWAPP SUBAGENT TASK BOARD
Owner: project-manager.md · Source of truth: CLAUDE.md + reports/hard-exit/*
Statuses: NOT STARTED · RUNNING · PASS · FAIL · OWNER-ACTION REQUIRED

Delegation chain (no skipped stage):
`uk-government-law-scraper-agent → legal-dataset-engineer-agent → db-rag-ingestion-agent
→ ai-brain-citationguard-agent → qa-release-gatekeeper-agent`

Canonical agent files (reused; the two new names are the delegation targets):
- uk-government-law-scraper-agent.md  (raw fetch only)
- legal-dataset-engineer-agent.md     (transform + additive DB insert only)
- db-rag-ingestion-agent.md           (embed + retrieval proof)
- ai-brain-citationguard-agent.md     (runtime Brain + CitationGuard proof)
- qa-release-gatekeeper.md            (accept/reject on command proof)

---

## SA-005  -  Runtime repair / G1   [PASS (core) + 2 residual owner items]
- Assigned: project-manager (runtime workflow)
- Evidence: reports/hard-exit/evidence/g1-live-failure/
- Commands: kubectl patch/scale/migrate (see continuation report)
- Result:
  - lawapp-brain 1/1 Ready, 0 restarts, /health 200, trace PERSISTED (brain_traces 0→1)  -  PASS
  - lawapp-backend new RS 1/1 Ready, db:connected (KEY_MANAGEMENT_MODE + JWT/ADMIN + DSN fixed)  -  PASS
  - rules-engine, crawler 1/1 (control-plane toleration)  -  PASS
  - lawapp-reasoning-worker: no valid entrypoint (`backend.core.pipeline` not a daemon)  -  OWNER-ACTION (scale-0 or implement worker; classifier-gated)
  - old backup-proof Job pods 0/1 Error: historical artifacts  -  OWNER-ACTION (cleanup; classifier-gated)
- Next: owner decision on reasoning-worker + job cleanup.

## SA-001  -  UK government law scraper   [PASS]
- Result: 9/9 official sources fetched, all HTTP 200, real sha256 hashes, manifest + raw/ (3.8MB),
  no derived data. ERA 1996 / Equality Act 2010 / ETA 1996 (CLML/XML) + ACAS dismissals,
  disciplinary-grievance, early-conciliation + GOV.UK make-a-claim, redundancy, holiday-entitlement.
  Evidence: reports/hard-exit/evidence/legal-data-scrape/. Hashes re-verified via `sha256sum -c`.
- Next: SA-002 (legal-dataset-engineer)  -  transform → legal_sources + corpus_chunks (spine ready).

## SA-001  -  UK government law scraper (original spec)   [superseded by PASS above]
- Assigned: uk-government-law-scraper-agent
- Goal: fetch RAW official UK employment-law sources only (no rules/chunks/embeddings).
- Sources: ERA 1996; Equality Act 2010; ET Act 1996; ET Rules/procedure; ACAS unfair-dismissal;
  ACAS disciplinary & grievance; GOV.UK ET time-limits/early-conciliation; GOV.UK redundancy;
  GOV.UK holiday-pay/wages.
- Inputs: legislation.gov.uk, gov.uk, acas.org.uk (official only).
- Outputs (reports/hard-exit/evidence/legal-data-scrape/): fetch-plan.md, raw-source-manifest.json,
  raw-source-records-proof.txt, hash-proof.txt, scraper-agent-report.md (+ raw/ files).
- Acceptance: every source has URL/HTTP-status/timestamp/content-hash; manifest exists; raw stored;
  NO rules/chunks/embeddings created by scraper.
- Next dependency: SA-002.

## SA-002  -  Legal dataset engineer   [BLOCKED on SA-001]
- Assigned: legal-dataset-engineer-agent
- Goal: transform validated raw sources → additive legal rows + corpus_chunks with full provenance.
- Pre-req (DONE by PM): apply additive spine migrations to lawapp-rag (028 legal_sources_registry,
  032 corpus_chunks_and_audits, + 026/029/030/031/033/034/036/037/038/039).
- Inputs: legal-data-scrape/raw-source-manifest.json (+ raw_source_records / raw files).
- Outputs (reports/hard-exit/evidence/legal-dataset-engineering/): dataset-transform-plan.md,
  dataset-insert-proof.txt, legal-rows-proof.txt, corpus-chunks-proof.txt, orphan-chunk-check.txt,
  source-linkage-proof.txt, db-proof.txt, dataset-engineer-agent-report.md.
- Acceptance: legal rows link raw_source_id + source_hash; corpus_chunks link legal_row_id +
  source_hash; orphan chunks = 0; chunks-without-hash = 0; rules-without-source = 0; no fake rows.

## SA-003  -  DB/RAG ingestion   [BLOCKED on SA-002]
- Assigned: db-rag-ingestion-agent
- Goal: embed corpus_chunks (ingestion/embeddings/embedder.py) + prove RAG retrieval.
- Outputs (reports/hard-exit/evidence/rag-ingestion/): embedding-proof.txt, vector-index-proof.txt,
  retrieval-proof.txt, source-id-return-proof.txt, rag-agent-report.md.
- Acceptance: embeddings exist + link corpus_chunk_id; retrieval returns chunk IDs + source IDs from
  official UK data; no placeholder vectors; no fake retrieval.

## SA-004  -  AI Brain + CitationGuard   [BLOCKED on SA-003]
- Assigned: ai-brain-citationguard-agent
- Goal: prove runtime Brain uses RAG + CitationGuard for a real answer.
- Outputs (reports/hard-exit/evidence/brain-citationguard/): brain-trace-proof.txt,
  citationguard-valid-source-proof.txt, citationguard-fake-source-rejection.txt,
  unsupported-claim-rejection-proof.txt, brain-answer-proof.txt, agent-report.md.
- Acceptance: trace created+persisted; RAG + CitationGuard stages in trace; valid source accepted;
  fake source rejected; unsupported claim blocked/caveated; final answer has verified citations;
  deadline/risk warning where relevant.

---

# ⚠️ BINDING CROSS-CUTTING NFR  -  100k CONCURRENT (owner directive 2026-06-07)
Spec: `docs/SCALE_ARCHITECTURE_100K.md`. EVERY task T-001..T-014 must satisfy its slice
(pooling, replicas≥3+HPA, Redis cache, CDN, async LLM, edge DDoS) OR record the gap as
owner-blocked. **Current live baseline: /health P95=2505ms, 51 RPS  -  ~200× short (T-014 FAIL).**
No task is PASS for release while it regresses the 100k path. QA T-013 gates §8 acceptance items.

# NEW TECHNOLOGIES AND WORKFLOW ASSIGNMENTS (T-001..T-013)

Master workflow (no Brain bypass; no CitationGuard bypass; no mock legal data):
frontend → auth/session → workspace/RLS → entitlement → case → question → backend → Brain trace →
intent/jurisdiction/issue classification → fact/date extraction → PII minimise → injection guard →
RAG planner → RAG retrieve (official UK sources) → trust rank → rule engine → deadline/remedy →
local-LLM router → draft → CitationGuard → hallucination guard → caveats → audit/OTel persist →
response (answer + citations + deadline/risk + trace_id + next steps) → Docker/K8s runtime proof.

| ID | Technology | Subagent | Workflow position | Status | Next dependency |
|----|-----------|----------|-------------------|--------|-----------------|
| T-001 | Workflow orchestrator / Brain pipeline | workflow-orchestrator-agent | backend→Brain→all stages→answer | PASS (core)  -  `/api/brain/trace` runs 19-step, persists `brain_traces` (proven). Per-stage span + bypass-fail test pending. | T-005/T-011 |
| T-002 | UK legal source scraping | uk-government-law-scraper-agent | source→raw→manifest | **PASS**  -  9 sources, HTTP 200, hashes, manifest | T-003 |
| T-003 | Legal dataset engineering | legal-dataset-engineer-agent | raw→legal_sources→corpus_chunks | **PASS**  -  9 legal_sources + 798 corpus_chunks (source_url+content_hash+chunk_hash+authority_ref), **0 orphans** | T-004 |
| T-004 | DB/RAG ingestion + hybrid search | db-rag-ingestion-agent | chunks→embeddings→retrieval | **PASS**  -  890/890 embedded (bge-small 384-dim, HNSW), real vectors; retrieval → ERA 1996 s.108/s.27BH w/ source_id+url, 0 orphans | T-005 |
| T-005 | CitationGuard / hallucination guard | ai-brain-citationguard-agent | draft→guard→answer | **PASS (local-runtime)**  -  3 evidence layers vs LIVE Docker stack: unit 5/5 (DB-gated), live-DB function (fake rejected/real accepted/uncited→fallback), live `/api/brain/trace` (8 retrieved, 3 verified, **5 fake rejected**, trace persisted to brain_traces). Large 798-chunk AKS corpus re-confirm owner-blocked (G1/G9). Evidence: reports/hard-exit/evidence/brain-citationguard/T-005-citationguard-final-proof.md | T-013 |
| T-006 | Legal rule engine | legal-rule-engine-agent | facts→rules→signals | PARTIAL-EXISTS (rules table=20; constructive-dismissal workflow proven fail-closed). Source-linkage + trace surfacing pending. | T-007 |
| T-007 | Deadline/remedy calculator | deadline-remedy-calculator-agent | dates→calc→warning | PARTIAL-EXISTS  -  WASM compute_deadline proven (13 tests, fail-closed). Trace+frontend surfacing pending. |  -  |
| T-008 | Local LLM router / external-LLM guard | local-llm-router-agent | Brain→router→model | **PASS**  -  brain reasoning now = Local Inference Fabric (qwen2.5:3b @ ollama-inference), real local model, no external LLM (logs prove, not stub). Manifest persisted + dead-service selector fixed. |  -  |
| T-009 | Frontend UI/UX | frontend-uiux-designer-agent | journey→API→presentation | RUNNING  -  real lint/build/test gates now PASS (echo stubs replaced; 58 asset refs validated); wiring gate PASS. Render-proof of citations/deadline/trace + a11y/responsive still pending. | T-013 |
| T-010 | Security/privacy/RLS/PII | security-auth-payment-agent (≡security-privacy) | auth→RLS→PII→safe-log | **PASS**  -  cross-user RLS e2e DONE (tests/e2e/test_t010_cross_user_rls_e2e.py  -  27 tests, real DB+HTTP+JWT). FIXED a real jwt-mode RLS bypass: check_case_ownership early-returned on user_id=None → anonymous read of ANY case (get_case/deadline/reminders/bundle…); now 401 in jwt (backend/core/user_auth.py). Proves A↮B isolation on list/get/sub-routes + paid-entitlement bound to owning case row; services proven stateless (tenancy mandatory, doc-GET 501 no store, no user data/PII in rag/rules responses, gateway PII 422). Security+service suites green (127 pass/3 skip). NOTE: 23 PRE-EXISTING unrelated phase failures (content/payment-mode assertions, not RLS). | T-013 |
| T-011 | Observability/audit/trace | observability-audit-agent | request→trace→DB→response | **PASS**  -  same trace_id in HTTP response + DB brain_traces + pod logs (request_id); stages logged; no secrets/PII | T-013 |
| T-012 | CI/CD/Docker/Kubernetes | platform-devops-scale-agent (≡ci-cd-kubernetes) | code→CI→image→k8s→smoke | PARTIAL  -  runtime repaired (G1); CI G3 green; Docker/K8s final-gate scripts to author | T-013 |
| T-013 | QA release gatekeeper | qa-release-gatekeeper | all evidence→verdict | BLOCKED on T-001..012; final-*.sh gates to author (no `|| true`/`echo PASS`); MUST gate 100k §8 items |  -  |
| T-014 | 100k scale readiness (load/spike/soak/chaos) | platform-devops + data + security + uiux | NFR across all layers | **FAIL (baseline captured)**  -  live /health P95=2505ms @ 51 RPS (~200× short). Gaps: no pool/PgBouncer, replicas:1 (no HPA), no Redis cache, no CDN. Harness: scripts/load/baseline_load.py. Spec: docs/SCALE_ARCHITECTURE_100K.md. Full 100k run owner-blocked (AKS down + load fleet). | T-013 |

Agent-name mapping (no duplicates created): security-privacy→`security-auth-payment-agent`;
ci-cd-kubernetes→`platform-devops-scale-agent`. New agents created: workflow-orchestrator,
legal-rule-engine, deadline-remedy-calculator, local-llm-router, observability-audit.

## SA-014  -  Microservices dev / distributed services wiring   [RUNNING]
- Assigned: microservices-dev-agent (executing via microservices-integration-agent).
- Goal: prove every distributed service is real+wired+reachable (not "pod Running"). Service map +
  connectivity matrix + repo/docker/k8s/env inventories + fail-closed wiring script + placeholder scan
  + full distributed request proof.
- Outputs: reports/hard-exit/evidence/microservices/* + scripts/lawapp/prove-microservices-wiring.sh
  + scripts/lawapp/scan-microservice-placeholders.sh (to be wired into final gates).
- Known issue to record: `llm-inference-service` has NO endpoints (dead); `ollama-inference` is the
  working svc (T-008). reasoning-worker scaled 0/0 (documented, not a failure).
- Acceptance: all active critical services Ready + endpoints; critical paths smoke-tested; full
  distributed request proven; placeholder scan clean.

## T-008 status  -  OWNER-ACTION (harness-gated)
Brain reasoning currently fails-soft to StubReasoningModel: `LOCAL_INFERENCE_URL` points at the DEAD
`llm-inference-service` (no endpoints). The working model service is `ollama-inference`
(3 endpoints, qwen2.5:3b loaded). Repointing the brain env to `ollama-inference` is a 1-line
`kubectl set env`  -  but the auto-mode classifier gated it as a production brain-config change.
Needs explicit owner go-ahead. No-external-LLM policy remains correctly enforced meanwhile.

---

## SA-007  -  Frontend UI/UX designer   [RUNNING  -  audit first, wiring with backend]
- Assigned: frontend-uiux-designer-agent
- Goal: best-in-class UK legal-AI UI; every page wired to a REAL backend route; remove mock UI.
- Dependencies: audit/design-system can start now; real wiring coordinates with backend/Brain agents;
  cannot PASS until frontend/backend wiring proof exists.
- Outputs (reports/hard-exit/evidence/frontend-uiux/): frontend-uiux-audit.md, frontend-page-map.md,
  frontend-backend-wiring-map.md, design-system-proof.md, responsive-proof.md, accessibility-proof.md,
  mock-data-removal-proof.txt, frontend-build-proof.txt, agent-report.md.
- Acceptance: mock data removed/disabled; case/question/answer flow professional; citations +
  deadline/risk + trace ID displayed; responsive; a11y proof; build passes; no fake legal workflow.

## SA-006  -  QA release gatekeeper   [BLOCKED on SA-001..005,007]
- Assigned: qa-release-gatekeeper
- Goal: ACCEPT/REJECT full hard-exit state on command proof; run final-*.sh gates (to be created).
- Outputs: reports/hard-exit/evidence/qa-release-gate/
- Acceptance: gates fail on mock/placeholder/Brain-bypass/direct-LLM/missing-RLS/missing-entitlement/
  missing-provenance/missing-CitationGuard/frontend-fake-API/k8s-not-ready/CI-red/secret-leak.
  No `|| true`, `continue-on-error`, `echo PASS`, static PASS, mock success.
