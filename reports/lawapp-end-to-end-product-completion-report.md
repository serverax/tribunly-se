# lawapp — End-to-End Product Completion Report

**Project:** lawapp — UK Employment Law AI Assistant  
**Date:** 2026-06-04  
**Git commit:** 095be01 (+ uncommitted Phase 1–3 changes)

---

## A. Final Decision

**READY FOR LOCAL INTERNAL DEMO: YES**  
**READY FOR TALOS INTERNAL DEMO: NO** — owner must run `bash scripts/deploy-talos.sh` from WSL and smoke tests must pass  
**READY FOR PUBLIC STAGING: NO** — Talos + real AI key + public ingress + payment decision all required  
**READY FOR PRODUCTION: NO** — See blocker table Section J  

---

## B. User Story Status

| # | User Story | Status | Notes |
|---|---|---|---|
| US-1 | Diagnosis (intake → assessment) | **COMPLETE** | 4-step wizard, ACAS dates, assessment returned |
| US-2 | Honest truth (weaknesses + uncertainty) | **COMPLETE** | Weaknesses shown; no guarantee language; evaluation gate blocks overconfident output |
| US-3 | Deadline awareness | **COMPLETE** | Live preview; ACAS EC pause; EC floor; rules from DB; WASM + JS fallback |
| US-4 | Affordable documents (PoC, SoL, LBA, ET1) | **COMPLETE** | All 4 types; test payment simulator; boundary notice in every doc |
| US-5 | Honest handoff | **COMPLETE** | `/handoff/leads` endpoint; capture form; free to user; assessment unaffected |
| US-6 | Plain understanding | **COMPLETE** | Plain English on all pages; jargon avoided; visible citations |
| US-7 | Trust | **COMPLETE** | Legal notice on every page; citations; no guarantee language; rate limiting |
| US-8 | Upload instead of retype | **PARTIAL** | Upload schema + de-id boundary done; OCR extraction Phase 4 |
| US-9 | Full bundle | **FUTURE** | Witness statement, chronology, ET1 bundle planned Phase 4+ |
| US-10 | Track my dispute | **PARTIAL** | Case save/detail/timeline exists; reminder events table exists; UI notifications pending |
| US-11 | Funnel metrics | **PARTIAL** | `funnel_events` table exists; event logging not wired to all journeys |
| US-12 | Legal accuracy regression | **COMPLETE** | 38 legal accuracy tests; 13 deadline tests; citation verification tests |
| US-13 | Second claim type readiness | **PARTIAL** | Rules + templates for unpaid wages exist; intake wizard is UD-focused |
| US-14 | Solicitor partner leads | **PARTIAL** | `handoff_leads` table; capture form; no CRM integration yet |
| US-15 | White-label readiness | **FUTURE** | Not started — placeholder only |

---

## C. Product Journey Proof

### Full E2E Journey — Playwright (17/17 PASS)

```
node_modules/.bin/playwright test --reporter=list
→ 17 passed in 11.7s
```

| Step | Playwright Test | Result |
|---|---|---|
| Health check | backend health check | ✓ PASS |
| Rules API (no hardcoding) | rules endpoint returns unfair dismissal rules | ✓ PASS |
| Register User A | register user A | ✓ PASS |
| Register User B | register user B | ✓ PASS |
| Login User A → JWT token | login user A and receive token | ✓ PASS |
| Login User B → JWT token | login user B and receive token | ✓ PASS |
| Assessment (deterministic QP-fail) | assessment returns definitive answer for short service | ✓ PASS |
| Save case as User A | save case as user A | ✓ PASS |
| User A reads own case | user A can read own case | ✓ PASS |
| User B blocked on User A case | user B CANNOT read user A case (HTTP 403) | ✓ PASS |
| 19-step Brain trace | brain trace runs all 19 steps | ✓ PASS |
| Document with test payment token | document generation with test payment token | ✓ PASS |
| Preview only without token | document preview only without payment token | ✓ PASS |
| Landing page + legal notices | landing page loads with legal notice | ✓ PASS |
| Intake wizard with ACAS fields | intake page loads with ACAS fields | ✓ PASS |
| Rules API values correct (for WASM/JS deadline) | intake deadline preview: rules API returns correct values | ✓ PASS |
| Full browser journey | landing, register, login, intake, assessment | ✓ PASS |

---

## D. API Proof

```bash
# Health
curl http://localhost:8000/health
→ {"status":"ok","db":"connected"}

# Rules (no hardcoded values)
curl http://localhost:8000/rules/unfair_dismissal
→ 9 rules: time_limit_months=3 [ERA 1996 s.111], qualifying_period=2 [ERA 1996 s.108],
           compensatory_cap_amount=123543 [ERA 1996 s.124], weeks_pay_cap=751 [ERA 1996 s.227]

# Assessment (QP-fail case — deterministic full response)
curl -X POST http://localhost:8000/assess -d '{"query":"dismissed after 10 months","facts":{...}}'
→ status: ok, has_viable_claim: no, 6 citations, deadline: 2026-05-31, weaknesses: [QP not met...]

# Brain trace (19 steps)
curl -X POST http://localhost:8000/api/brain/trace -d '{"message":"dismissed after 4 years",...}'
→ 19 steps confirmed, rag_sources: ["hybrid","legal_graph"], safety_passed: true

# User isolation (JWT mode)
Register A, Login A → token_a
Register B, Login B → token_b
Create case with token_a → case_id
GET /cases/{case_id} with token_b → HTTP 403 BLOCKED

# Payment test simulator
POST /api/payment/create-session {"document_type":"particulars_of_claim"}
→ {"payment_token":"test_abc123...","demo_mode":true,"price_gbp":9.99}

POST /documents/generate {"payment_token":"test_abc123...",...}
→ full document, payment_required: false, 5834 chars, ERA 1996 citations
```

---

## E. DB Proof

```
brain_traces:           222+ rows  ✓
assessment_audit_logs: 2442+ rows  ✓
mcp_tool_calls:          25+ rows  ✓
rules:                   19 rows   ✓ (effective-dated, no hardcoding)
legal_nodes:             15 rows   ✓ (seeded ERA 1996 graph)
legal_edges:             14 rows   ✓ (requires/leads_to/applies_to)
legislation:             80 rows   ✓ (with embeddings)
acas_guidance:           12 rows   ✓ (with embeddings)
case_law_chunks:          0 rows   BLOCKED (FCL licence pending)
users:                   58+ rows  ✓
cases:                  866+ rows  ✓
documents:              923+ rows  ✓

Extensions: pgvector ✓, pgcrypto ✓
```

---

## F. Frontend Proof

| Page | URL | Features | Status |
|---|---|---|---|
| Landing | `/` | "Start free diagnosis", legal notice, feature cards | ✓ |
| Register | `/pages/register.html` | Email/password/confirm, validation, JWT auth | ✓ |
| Login | `/pages/login.html` | Email/password, Bearer token, redirect | ✓ |
| Intake | `/pages/intake.html` | 4-step wizard, ACAS Day A/B, live deadline preview, all 8 fields | ✓ |
| Assessment | `/pages/assessment.html` | Viability, deadline, weaknesses, citations, handoff, save | ✓ |
| Dashboard | `/pages/dashboard.html` | Saved cases list, viability badges, open detail | ✓ |
| Case detail | `/pages/saved_case.html` | Full assessment, uploads, timeline, escalation, docs | ✓ |
| Docs (PoC/SoL) | via `/documents/generate` | Template-based, boundary notice, test payment flow | ✓ |
| Payment success | `/pages/success.html` | Confirmation page | ✓ |
| Payment cancel | `/pages/cancel.html` | Cancellation page | ✓ |

**Legal notice on every page:** ✓  
**No hardcoded legal values in JS/WASM:** ✓ (rules fetched from `/rules/` endpoint)  
**Mobile-responsive:** ✓ (768px breakpoint, flex layout)

---

## G. New Technology Integration in Product Flow

| Technology | Where in Product Journey | Status |
|---|---|---|
| **lawapp Brain (19 steps)** | Every `/assess` and `/api/brain/trace` request | **PASS** |
| **Agentic AI** (9 agents) | Brain Step 8: EmploymentLaw, Deadline, Evidence, Citation, Compensation, Risk, Evaluation, HumanReview, DocumentDrafting | **PASS** |
| **Hybrid Search** | Brain Step 11: SQL rules + BM25 keyword + pgvector semantic | **PASS** |
| **Graph RAG** | Brain Step 9: `select_rag_source` → `legal_nodes/edges` enrichment | **PASS** |
| **Knowledge Graph** | legal_nodes (15 ERA sections) → legal_edges (14 relationships) used in assessment | **PASS** |
| **Context Compression** | Brain Step 13: deduplicates rules, truncates verbose text, preserves all citations | **PASS** |
| **Memory Engine** | Brain Step 17: consent-gated `legal_memory` save; user_id + case_id required | **PASS** |
| **Evaluation AI** | Brain Step 15: 8-check rubric (citations, jurisdiction, deadline source, guarantee language, PII) | **PASS** |
| **MCP Connectors** | 5 connectors: `rules_lookup`, `legislation_lookup`, `document_generate`, `acas_guidance_lookup`, `source_freshness_check`; deny-by-default; all calls audit-logged | **PASS** |
| **Multimodal Upload** | Documents table + de-id strips raw_document; upload endpoint exists; OCR = Phase 4 | **PARTIAL** |
| **AI Router** | Brain Step 9: deadline → rules_engine_only; complex → full_legal_pipeline; high-risk → human_review | **PASS** |
| **Semantic Cache** | `semantic_cache` table; only non-personal queries cached; personal facts never cached | **PASS** |

---

## H. Remaining Blockers

### HIGH (blocks real assessments)
| # | Blocker | Fix |
|---|---|---|
| H1 | `ANTHROPIC_API_KEY=placeholder` — stub model returns insufficient_grounding for complex cases | Owner: set real API key in `.env` and K8s secret |
| H2 | Kubernetes not applied — all manifests exist but not deployed | Owner: run `bash scripts/deploy-talos.sh` from WSL |
| H3 | Case law chunks empty (FCL licence pending) | Apply at caselaw.nationalarchives.gov.uk/computational_access |
| H4 | JWT_ISSUER/JWT_AUDIENCE env vars not in .env.example | Add to template for staging |

### MEDIUM (blocks public staging)
| # | Blocker | Fix |
|---|---|---|
| M1 | Stripe integration Phase 7 stub — real payments require Stripe keys | Set STRIPE_SECRET_KEY and implement `/api/payment/create-session` Stripe checkout |
| M2 | Ingress/DNS not configured in K8s | Configure domain + cert-manager |
| M3 | Rate limiting uses in-memory — won't survive pod restart | Configure Redis for production rate limiting |

### LOW
| # | Blocker | Fix |
|---|---|---|
| L1 | OCR/document extraction not implemented | Phase 4 delivery |
| L2 | ACAS EC dates missing from intake wizard (NOW FIXED — Day A/B added) | — |
| L3 | User isolation bypassed in `LAWAPP_AUTH_MODE=none` (NOW FIXED — set to jwt) | — |
| L4 | Funnel metrics not fully wired | Wire `funnel_events` to intake/diagnosis/conversion |
| L5 | Playwright tests need Chromium browser installed on CI | Add `npx playwright install chromium` to CI pipeline |

---

## J. Production Blocker Table

| Blocker | Current Status | Required Action | Owner or Claude | Blocks Internal Demo? | Blocks Public Staging? | Blocks Production? |
|---|---|---|---|---|---|---|
| **Talos deployment not applied** | Manifests created; kubectl not available in dev | Owner: run `bash scripts/deploy-talos.sh` from WSL | **OWNER** | YES (Talos demo) | YES | YES |
| **ANTHROPIC_API_KEY=placeholder** | Stub model active; complex cases → insufficient_grounding | Set real API key in .env and K8s secret | **OWNER** | YES (full reasoning) | YES | YES |
| **Stripe real mode not configured** | test_simulator mode; no real charges | Set STRIPE_SECRET_KEY + STRIPE_PUBLIC_KEY | **OWNER** | NO (demo works) | YES (if paid) | YES |
| **Find Case Law bulk licence pending** | case_law_chunks=0 rows | Apply at caselaw.nationalarchives.gov.uk | **OWNER** | NO | PARTIAL | YES (legal coverage) |
| **OCR/extraction Phase 4** | Architecture ready; no OCR engine | Implement Phase 4 OCR pipeline | **Claude** (Phase 4) | NO | NO | PARTIAL (upload) |
| **Public ingress/domain/TLS** | lawapp-ingress.yaml exists; no domain configured | Configure DNS + cert-manager in cluster | **OWNER** | NO | YES | YES |
| **Rate limiting uses in-memory** | slowapi in-memory; won't survive pod restart | Configure Redis: RATELIMIT_STORAGE_URI | **Claude** | NO | YES | YES |
| **JWT_ISSUER/JWT_AUDIENCE in .env.example** | Set in docker-compose; not in .env.example | Add to .env.example and K8s secrets | **Claude** (trivial) | NO | NO | NO |
| **Backend image tag stale in K8s manifest** | k8s YAML references old commit hash | Update image tag before deploying | **Owner+Claude** | NO | YES | YES |
| **Funnel metrics not wired** | funnel_events table exists; no inserts | Wire events to intake/conversion flows | **Claude** | NO | PARTIAL | PARTIAL |

---

## I. Next Implementation Tasks (Coding Required)

1. **Set real ANTHROPIC_API_KEY** — wire real AI model to get full assessments for complex cases
2. **Stripe checkout session** (`stripe` Python SDK) — implement `/api/payment/create-session` with real Stripe test mode
3. **Stripe webhook handler** — create `/api/payment/webhook` to update payment status on cases
4. **OCR/extraction pipeline** (Phase 4) — implement PDF/image extraction with user confirmation flow
5. **Funnel event wiring** — add `funnel_events` inserts at: intake_started, intake_submitted, diagnosis_viewed, case_saved, document_generated, handoff_triggered
6. **Redis rate limiting** — configure `RATELIMIT_STORAGE_URI=redis://...` in docker-compose + K8s
7. **Apply K8s manifests** — owner must apply from WSL with real secrets (see `scripts/deploy-talos.sh`)

---

## Final Test Proof

```bash
# Python tests
python -m pytest tests/brain/ tests/legal_accuracy/ tests/security/ tests/router/ 
  tests/agents/ tests/citation_verification/ tests/evaluation/ tests/cache/ 
  tests/graph_rag/ tests/knowledge_graph/ tests/memory/ tests/mcp/ tests/uploads/ 
  tests/retrieval/ tests/rag/ tests/deadlines/ tests/user_isolation/ 
  tests/document_intelligence/ tests/documents/ tests/payment/ tests/rate_limiting/ -q

→ 354 passed in 98.03s

# Playwright E2E
node_modules/.bin/playwright test --reporter=list

→ 17 passed in 11.7s

TOTAL: 371 tests PASS / 0 FAIL
```
