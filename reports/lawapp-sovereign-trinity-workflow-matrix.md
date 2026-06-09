# lawapp — Sovereign Trinity Workflow Matrix

**Generated:** 2026-06-04 | **Branch:** main | **Verdict:** `NOT READY — SOVEREIGN TRINITY WORKFLOWS NOT FULLY PROVEN`

This matrix is grounded in **raw inspection of the live repo + database**, not guesses.

## Cross-cutting blocker #1 — EMPTY LEGAL CORPUS (drives most "NOT PROVEN" statuses)

Raw DB proof (live `docker compose exec db psql`):
```
table               rows  embedded
legislation            0         0
acas_guidance          0         0
official_guidance      0         0
case_law_documents     0         0
rules                 19         0      (deterministic values seeded OK)
legal_nodes           15         0      (graph seed only)
```
Because the corpus is empty, `/assess` returns `insufficient_grounding` and no real citations can be produced. **Ingestion code exists** (`ingestion/legislation`, `/acas`, `/govuk`, `/case_law`, `/embeddings` using local fastembed `bge-small-en-v1.5`, 384-dim) but **has not been run to populate rows**. Closing this is the foundation for Workflows A, C, D, E, F, G, H.

## Trinity agent mapping (order §2 ↔ existing `backend/core/agents/registry.py`)

| Order agent | Role | Current code | Status |
|---|---|---|---|
| **AEE** Analysis & Evidence Extraction | parse evidence, chronology, PII scrub, timeline | `/cases/{id}/uploads/extract`, `document_facts`, `evidence_items`, `case_timeline_events` | partial — extraction route exists; not consolidated as an "AEE" agent; confirmation flow needs proof |
| **ART** Algorithmic Reasoning & Triage | viability, deadlines, risk, strict JSON | `pipeline.assess`, triage agents in `registry.py`, `rules`, `/api/deadline/calculate`, WASM | exists — corpus-gated for grounded output |
| **SEA** Strategic Execution & Automation | ET1/SoL/bundle/letters, outbox jobs | `DocumentGenerationAgent` (registry.py:317), `backend.core.documents`, `/documents/generate`, outbox | exists — async worker path needs wiring proof |

---

## Workflow matrix

Legend — Status: PROVEN (this/earlier session) · BUILT (not workflow-proven) · MISSING/EMPTY.

### Workflow A — Zero-friction multimodal intake / evidence timeline parser
- **User story:** dismissed worker uploads messy evidence -> automatic legal timeline of confirmed facts.
- **Frontend:** `intake.html`, `saved_case.html` (upload), confirmation screen (BUILT partial)
- **Backend route:** `POST /cases/{id}/uploads`, `POST /cases/{id}/uploads/{uid}/extract`, `POST /cases/{id}/uploads/{uid}/apply-confirmed`
- **Brain stage / Agent:** AEE (extraction) -> confirmation gate -> Brain
- **DB tables:** `evidence_items`, `case_timeline_events`, `document_facts` exist; order asks for `evidence_chronology`, `unconfirmed_facts` (MISSING under those names)
- **RAG/source:** n/a at intake
- **WASM/cache/queue:** outbox `evidence_parsed` (MISSING — not emitted yet)
- **Safety/validator:** PII scrub before logs/model (verify), injection guard on pasted text
- **Trace/metric:** brain_traces / OTEL request-id (BUILT)
- **Tests/gates:** MISSING — none proving non-static extraction
- **Status:** BUILT pieces, NOT workflow-proven
- **Missing gaps:** unconfirmed->confirmed gate proof; outbox `evidence_parsed`; AEE consolidation; tests rejecting fake extraction
- **Action to close:** add `evidence_chronology`/`unconfirmed_facts` (or map existing), wire AEE->outbox->trace, add extraction tests

### Workflow B — Constructive dismissal risk engine (ART)
- **User story:** deterministic breach/Kaur last-straw/affirmation/causation -> strict JSON.
- **Frontend:** Constructive Dismissal Risk Timeline (MISSING)
- **Backend route:** via `/assess` / `/api/brain/trace` (BUILT)
- **Brain stage / Agent:** ART deterministic matrix
- **DB tables:** `rules`, `assessment_audit_logs`, `brain_traces`
- **Safety/validator:** affirmation risk -> human_review_queue
- **Status:** MISSING — deterministic CD matrix + strict JSON schema not implemented
- **Action to close:** implement CD matrix in `backend/domains/employment/`, enforce JSON schema, wire to ART, add tests + frontend timeline

### Workflow C — Fast Opinion Case HUD (ART)
- **User story:** viability, traffic-light, deadline, weaknesses, value range, citations, trace_id.
- **Frontend:** `assessment.html` (BUILT — must bind real fields)
- **Backend route:** `POST /assess`, `POST /api/brain/trace`
- **DB tables:** `brain_traces`, `assessment_audit_logs`
- **RAG/source:** corpus (EMPTY -> no citations)
- **Status:** BUILT endpoint; HUD not proven dynamic + corpus-gated
- **Action to close:** populate corpus; assert HUD fields change when facts change; render citations

### Workflow D — Schedule of Loss calculator
- **Frontend:** SoL calculator (MISSING as live screen)
- **Backend route:** `/documents/generate` (SoL) + rules; `schedule_of_loss_calculations` table MISSING
- **Agent:** ART (calc) + SEA (document)
- **WASM:** `/api/test/wasm-deadline` exists; SoL WASM/JS BUILT-partial
- **Status:** BUILT doc generator; live calculator + rules-sourced caps not proven
- **Action to close:** add `schedule_of_loss_calculations`, rules-sourced weekly-cap, server validation, frontend sliders, trace

### Workflow E — Settlement calculator & strategy simulator
- **Status:** MISSING (`settlement_scenarios` table missing)
- **Action to close:** ART risk-adjusted value + caveated recommendation; SEA letter; human review on high value

### Workflow F — Vento band discrimination calculator
- **Status:** MISSING — Vento bands must come from rules/corpus, not hardcoded
- **Action to close:** seed Vento bands into `rules` with citations; calculator + human review

### Workflow G — Hybrid Search + local law DB  [FOUNDATION]
- **Frontend:** Hybrid Search weight viewer (MISSING); citations viewer (BUILT-partial)
- **Backend route:** `POST /api/rag/hybrid-search`, `POST /api/rag/graph` (exist)
- **Brain stage:** retrieval planner -> hybrid search -> trust ranking -> compression
- **DB tables:** `legislation`, `acas_guidance`, `official_guidance`, `case_law_documents/chunks`, `legal_nodes/edges`, `semantic_cache`, `retrieval_audit`
- **RAG/source:** **all corpus tables EMPTY** — retrieval returns nothing
- **Status:** code present, corpus empty -> NOT PROVEN
- **Action to close:** run ingestion + fastembed backfill, prove hybrid search returns real source rows + URLs, citations validate against DB

### Workflow H — ET1 / Particulars of Claim generator (SEA)
- **Frontend:** ET1 generator + document trace view (BUILT — `assessment.html` has generate)
- **Backend route:** `POST /documents/generate`, `GET /api/documents/{id}/download`
- **Agent:** SEA `DocumentGenerationAgent` (registry.py:317) -> `backend.core.documents.generate_particulars_of_claim`
- **DB tables:** `documents`, `document_readiness`; order wants `document_generation_jobs` (MISSING)
- **Queue:** async outbox `document_generation_pending` -> worker (MISSING — currently sync)
- **Safety/validator:** citation validator on document refs; self-help notice; cross-user download block (`/api/security/cross-user-test` exists)
- **Status:** BUILT sync generation; async worker + citation-block + 202 path not proven
- **Action to close:** wire SEA->outbox `document_generation_pending`->worker; citation-mismatch blocks; ownership download test

### Workflow I — Tribunal bundle assembler (SEA)
- **Backend route:** `POST /cases/{id}/bundle/generate|preview`, `GET /cases/{id}/bundle` (exist)
- **Status:** BUILT routes; confirmed-evidence-only + pagination + cross-user block not proven
- **Action to close:** prove bundle uses confirmed evidence, index/paginate, block cross-user

### Workflow J — ACAS Early Conciliation / negotiation
- **Backend route:** `/api/deadline/calculate` (ACAS clock), `/cases/{id}/deadline`
- **Status:** BUILT deadline logic; ACAS EC prep screen + caveats not proven

### Workflow K — OpenTelemetry Glass Engine  [in progress this session]
- **Backend route:** all routes via `RequestContextMiddleware`; `/metrics`, `/ready`
- **Trace:** X-Request-ID/X-Trace-ID == brain_traces.trace_id == logs == outbox (correlation PROVEN earlier this session); real OTEL spans pending image with `opentelemetry` installed (Dockerfile fixed, rebuild done)
- **Status:** correlation + counters + no-leak PROVEN; real SDK spans need final verify
- **Action to close:** verify console spans carry `lawapp.trace_id`; add frontend/admin trace waterfall view

### Workflow L — Automated red-team gate
- **DB:** `injection_guard_log`, `guardrail_events`; order wants `red_team_results` (MISSING)
- **Status:** MISSING red-team attack suite + CI gate (injection guard exists with 17 tests)
- **Action to close:** add malicious-evidence/JSON-break/fake-citation/cross-user attack tests + CI gate

### Workflow M — B2C paid document unlock
- **Backend route:** `/api/payment/create-session`, `/api/payment/webhook`, `/api/payment/status`; `payment_events`, `bills`
- **Status:** BUILT simulator path (`PAYMENT_MODE=test_simulator`); entitlement-gated generation + real Stripe owner-blocked
- **Action to close:** prove unpaid access blocked end-to-end; entitlement unlocks SEA; real keys = owner action

### Corpus ingestion (Addendum §1–§8)  [DO FIRST]
- **Modules:** `ingestion/legislation` (CLML parser), `/acas`, `/govuk`, `/case_law` (AKN parser + licence client), `/embeddings` (fastembed), `/freshness`, `/rules`
- **DB tables:** present: `legislation`, `acas_guidance`, `official_guidance`, `case_law_documents/chunks`, `ingestion_runs`; missing/needs-check: `govuk_guidance`, `tribunal_guidance`, `source_trust_scores`, `source_freshness`, `legal_corpus_chunks`, `legal_documents`
- **Status:** tables empty — ingestion never populated
- **Action to close:** add any missing corpus tables; run `scripts/ingest-employment-law-corpus.sh` (legislation+ACAS+GOV.UK+tribunal) + fastembed backfill; Find Case Law bulk fail-closed unless `FCL_COMPUTATIONAL_ANALYSIS_APPROVED=true`; prove counts>0, embeddings>0, freshness, hybrid RAG cites real rows; create `tests/ingestion/*`

---

## Cross-cutting infrastructure status (from prior session work)
| Capability | Status |
|---|---|
| §17 Outbox + worker (claim/processing/processed/retry/dead-letter, trace) | PROVEN (8/8 + 1/1 + 43/43 tests) |
| §18 OTEL correlation + /metrics + no-leak | PROVEN; real SDK spans pending final verify (Dockerfile fixed) |
| §21 SAST/SCA CI job | added, not yet green on a CI run |
| Feature flags, crash reporting, load test, eval dataset, gate scripts, backup/restore, K8s policies | not implemented |

## PROVEN this session (live, raw-command evidence)
- **Corpus foundation** — ACCEPTED: 80 legislation + 12 ACAS + 7 GOV.UK rows, 99 fastembed embeddings, content_hash/source_url/last_verified_at populated, FCL bulk fail-closed. `check-employment-law-corpus.sh` → PASSED. See `reports/lawapp-employment-law-corpus-proof.md`.
- **Workflow G Hybrid Search** — PROVEN LIVE: `/api/rag/hybrid-search` returns `keyword_results:5, vector_results:5, merged_results:9`, real citations (ERA 1996 s.98/111/122, ERA 2025 s.25, ACAS Code), `insufficient_grounding:false`. True hybrid (lexical+vector+hybrid tags).
- **Deterministic deadline (Workflow C/J core)** — PROVEN: `/api/deadline/calculate` → `time_limit_months:3 (source:rules, authority:ERA 1996 s.111(2))`, ACAS EC pause `paused_days:17`, `limitation_date:2026-08-26`; used in-force value, ignored prospective ERA 2025 value=6. Rules-sourced, not hardcoded.
- **§17 Outbox + worker** — PROVEN (8/8 + 1/1 + 43/43 tests).
- **§18 OTEL correlation** — PROVEN (trace_id across response/logs/DB/brain; /metrics counters; no leak). Real SDK spans live after Dockerfile OTEL deps.

## Remaining execution order
1. **Workflow C HUD** — Brain retrieval+citations grounded (`sources_retrieved:5, citations_verified:4`); final assessment TEXT is owner-gated (#11 ANTHROPIC key → stub returns insufficient_grounding, correct fail-closed). Bind frontend HUD fields.
2. **Workflow D** — Schedule of Loss (deterministic, rules-sourced weekly cap).
3. **Workflow A** — evidence intake -> AEE -> confirmation -> Brain.
4. Then B, E, F, H, I, K, L, M with raw proof each.
5. `tests/ingestion/*` + GOV.UK slug fixes.

**Verdict:** `NOT READY — SOVEREIGN TRINITY WORKFLOWS NOT FULLY PROVEN`
