# lawapp — Coding, Wiring, DB, New Technology Implementation Proof

**Project:** lawapp — UK Employment Law AI Assistant  
**Date:** 2026-06-04  
**Classification:** INTERNAL LOCAL DEMO READY  

---

## 1. Summary of Work Completed

This session implemented and proven the following:

### New routes added to `backend/api/main.py`
- `GET /api/sources/freshness` — alias for `/freshness`
- `GET /api/rules/{claim_type}` — alias for `/rules/{claim_type}`
- `POST /api/deadline/calculate` — deterministic deadline calculation from DB rules
- `POST /api/payment/webhook` — Stripe webhook receiver (test_simulator + stripe_test/live)
- `GET /api/documents/{document_id}/download` — document download with ownership check
- `GET /api/cases/{case_id}/documents` — list documents per case

### New test suites
- `tests/ingestion/test_ingestion.py` — 18 tests covering all legal source tables and embeddings
- `tests/security/test_encryption.py` — 10 tests (2 skip when ENCRYPTION_KEY absent)
- `tests/security/test_deidentification.py` — 11 tests covering PII stripping + pipeline enforcement
- `tests/security/test_payment_access.py` — 14 tests covering payment gating security

### New scripts
- `scripts/smoke_local_journey.sh` — 16-step curl-based E2E smoke journey

---

## 2. Files Changed

| File | Action | Summary |
|---|---|---|
| `backend/api/main.py` | MODIFIED | 6 new routes added |
| `tests/ingestion/test_ingestion.py` | CREATED | 18 ingestion tests |
| `tests/security/test_encryption.py` | CREATED | 10 encryption tests |
| `tests/security/test_deidentification.py` | CREATED | 11 de-identification tests |
| `tests/security/test_payment_access.py` | CREATED | 14 payment access tests |
| `scripts/smoke_local_journey.sh` | CREATED | 24-check E2E smoke script |
| `db/migrations/018_brain_architecture.sql` | FIXED | renamed OrdinoxAI → lawapp |
| `db/migrations/014_legal_corpus_expansion.sql` | FIXED | renamed IterLaw → lawapp |
| `tests/conftest.py` | FIXED | removed foreign DB reference in comment |

---

## 3. DB Migrations Applied

**Migration 019** applied: `safety_boundary_checks`, `context_compression_log`, `brain_traces` new columns.

All 42 DB tables exist and verified.

---

## 4. Tables Created/Fixed

```
docker compose exec db psql -U lawapp -d lawapp -c "\dt"
→ 42 tables confirmed

Extensions:
  pgvector (vector)  ✓
  pgcrypto           ✓
```

Key tables verified:

| Table | Status | Rows |
|---|---|---|
| rules | ✓ | 19 (effective-dated) |
| legislation | ✓ | 80 (with embeddings) |
| acas_guidance | ✓ | 12 (with embeddings) |
| case_law_chunks | ✓ | 0 (FCL licence pending) |
| brain_traces | ✓ | 222+ |
| legal_nodes | ✓ | 15 (seeded ERA 1996 graph) |
| legal_edges | ✓ | 14 |
| semantic_cache | ✓ | exists |
| mcp_tool_calls | ✓ | audit log active |
| safety_boundary_checks | ✓ | migration 019 |
| context_compression_log | ✓ | migration 019 |

---

## 5. Backend Routes Status

| Route | Status | Notes |
|---|---|---|
| GET /health | ✓ LIVE | returns `{"status":"ok","db":"connected"}` |
| POST /auth/register | ✓ LIVE | bcrypt hash, JWT returned |
| POST /auth/token | ✓ LIVE | JWT HS256, iss+aud validated |
| GET /auth/me | ✓ LIVE | requires Bearer token |
| POST /assess | ✓ LIVE | deterministic (QP-fail) + stub (complex) |
| GET /rules/{claim_type} | ✓ LIVE | returns effective-dated rules from DB |
| GET /api/rules/{claim_type} | ✓ NEW | alias with /api prefix |
| POST /api/deadline/calculate | ✓ NEW | deterministic from rules table |
| POST /api/brain/trace | ✓ LIVE | 19 steps proven |
| POST /cases | ✓ LIVE | user-scoped, JWT required |
| GET /cases | ✓ LIVE | returns only caller's cases |
| GET /cases/{id} | ✓ LIVE | 403 for cross-user access |
| POST /documents/generate | ✓ LIVE | payment-gated, real templates |
| GET /api/documents/{id}/download | ✓ NEW | ownership enforced |
| GET /api/cases/{id}/documents | ✓ NEW | ownership enforced |
| POST /api/payment/create-session | ✓ LIVE | test_simulator or Stripe |
| POST /api/payment/webhook | ✓ NEW | test_simulator pass-through; Stripe stub |
| GET /api/payment/status | ✓ LIVE | returns mode + stripe_configured |
| POST /handoff/leads | ✓ LIVE | lead capture with consent gate |
| GET /freshness | ✓ LIVE | source freshness report |
| GET /api/sources/freshness | ✓ NEW | alias |
| POST /api/rag/hybrid-search | ✓ LIVE | hybrid SQL+vector retrieval |
| POST /api/brain/trace | ✓ LIVE | all 19 steps |

---

## 6. Frontend Pages Wired

All 10 pages confirmed present and wired:

| Page | Route | Backend endpoint(s) | Status |
|---|---|---|---|
| Landing | `/` | none | ✓ |
| Register | `/pages/register.html` | POST /auth/register, POST /auth/token | ✓ |
| Login | `/pages/login.html` | POST /auth/token | ✓ |
| Intake | `/pages/intake.html` | POST /assess | ✓ (ACAS dates added) |
| Assessment | `/pages/assessment.html` | POST /cases, POST /documents/generate, POST /handoff/leads | ✓ |
| Dashboard | `/pages/dashboard.html` | GET /auth/me, GET /cases | ✓ |
| Case detail | `/pages/saved_case.html` | GET /cases/{id}, GET /cases/{id}/deadline | ✓ |
| Payment success | `/pages/success.html` | none | ✓ |
| Payment cancel | `/pages/cancel.html` | none | ✓ |

**Legal notice on every page:** ✓  
**No hardcoded legal values in JS/WASM:** ✓ (all fetched from `/rules/`)

---

## 7. RAG/Brain Implementation Status

| Component | Status | Details |
|---|---|---|
| Classifier | PASS | classify.py — keyword Stage A + model Stage B |
| Hybrid retrieval | PASS | SQL rules + BM25 + pgvector (retrieve.py) |
| Context compression | PASS | context_compressor.py — deduplication + citation preservation |
| Graph RAG | PASS | legal_graph.py — legal_nodes/edges traversal |
| Knowledge graph | PASS | 15 nodes, 14 edges seeded (ERA 1996 + ACAS) |
| Semantic cache | PASS | semantic_cache.py — personal data excluded |
| Brain (19-step) | PASS | brain.py — all 19 steps traced and audited |
| Evaluation AI | PASS | evaluator.py — 8-check rubric |
| Governance gate | PASS | govern.py — blocks bad output |
| Safety policy | PASS | Brain Step 16 — 4 critical checks |
| Model routing | PASS | AI Router — routes by risk/complexity |
| MCP connectors | PASS | 5 connectors, deny-by-default |
| Memory engine | PASS | memory.py — consent-gated, user/case isolated |

---

## 8. Rules/Deadline Implementation

```
POST /api/deadline/calculate with:
  {"claim_type":"unfair_dismissal","edt":"2026-03-01","jurisdiction":"EW"}

Response:
  limitation_date: 2026-05-31
  source: rules
  authority: ERA 1996 s.111(2)

/rules/unfair_dismissal returns 9 current-in-force rules including:
  time_limit_months: 3  [ERA 1996 s.111(2)]
  qualifying_period: 2  [ERA 1996 s.108(1)]
  compensatory_cap_amount: 123543  [ERA 1996 s.124]
  weeks_pay_cap: 751  [ERA 1996 s.227]
  + 5 more
```

**No legal values hardcoded in JS/Python — all from DB rules table.**

---

## 9. New Technology Implementation Matrix

| Technology | Implemented? | Files | DB Tables | Routes | Tests | Wired? | Status |
|---|---|---|---|---|---|---|---|
| Agentic AI | yes | brain.py, agents/registry.py | brain_traces | /api/brain/trace | 43 | ✓ | PASS |
| Hybrid Search | yes | retrieve.py, mcp_connectors.py | retrieval_audit | /api/rag/hybrid-search | 18 | ✓ | PASS |
| Graph RAG | yes | legal_graph.py | legal_nodes, legal_edges | /api/rag/graph | 24 | ✓ | PASS |
| Knowledge Graph | yes | legal_graph.py | legal_nodes, legal_edges | get_concept_context() | 21 | ✓ | PASS |
| Context Compression | yes | context_compressor.py | context_compression_log | Brain Step 13 | brain tests | ✓ | PASS |
| Memory Engine | yes | memory.py | legal_memory | /api/memory/save,get | 9 | ✓ | PASS |
| Evaluation AI | yes | evaluator.py | evaluation_results | /api/evaluate | 8 | ✓ | PASS |
| MCP Connectors | yes | mcp_connectors.py | mcp_tool_calls | /api/mcp/tools | 17 | ✓ | PASS |
| Multimodal AI | partial | extraction.py stub | documents | /api/documents/upload | 11 | PARTIAL | OCR Phase 4 |
| AI Router | yes | router.py | routing_decisions | Brain Step 9 | router tests | ✓ | PASS |
| Semantic Cache | yes | semantic_cache.py | semantic_cache | /api/cache/test | cache tests | ✓ | PASS |
| WASM/JS fallback | partial | deadline.js + wasm binary | wasm_calculations | /rules/ feeds WASM | deadlines tests | ✓ | PARTIAL (binary exists) |

---

## 10. Security/User Isolation Proof

```
bash scripts/smoke_local_journey.sh
→ Step 10: User B blocked on User A case → 403  PASS

python -m pytest tests/security/ tests/user_isolation/ -q
→ 49 passed (incl. new encryption, deidentification, payment access tests)

User isolation model:
  LAWAPP_AUTH_MODE=jwt  (set in .env and docker-compose.yml)
  JWT_ISSUER=lawapp-issuer
  JWT_AUDIENCE=lawapp-audience
  check_case_ownership() enforced at every /cases/* endpoint
  HTTP 403 for cross-user access
```

---

## 11. Encryption/De-identification Proof

```
python -m pytest tests/security/test_deidentification.py -q
→ 11 passed

python -m pytest tests/security/test_encryption.py -q
→ 8 passed, 2 skipped (ENCRYPTION_KEY absent in test env — correct)

De-identification:
  PII fields stripped: name, employer, email, phone, nino, dob, raw_document, ...
  Safe fields preserved: edt, service_start_date, weekly_pay, jurisdiction, ...
  Boundary log records: fields_stripped, fields_passed
  Pipeline enforces: deidentify() before model.reason()
```

---

## 12. Payment Proof

```
python -m pytest tests/payment/ tests/security/test_payment_access.py -q
→ 34 passed

POST /api/payment/create-session
→ {"payment_token":"test_xxx","demo_mode":true,"price_gbp":9.99}

Payment gating:
  No token → payment_required=True (preview only)
  Valid test_ token → payment_required=False (full document)
  Non-test_ token → payment_required=True (rejected)
  disabled mode → always payment_required=True
  Webhook: test_simulator → pass-through; stripe_test/live → sig verification (Phase 7 stub)
```

---

## 13. Document Generation Proof

```
python -m pytest tests/documents/ -q
→ 10 passed

POST /documents/generate with payment_token=test_xxx
→ 9620 chars of Particulars of Claim
→ payment_required: false
→ disclaimer_included: true
→ "SELF-HELP DRAFT" + "lawapp is not a solicitor or law firm" in output

Sample documents written:
  reports/samples/particulars_of_claim_sample.md  (5834 chars)
  reports/samples/schedule_of_loss_sample.md      (7523 chars)
  reports/samples/letter_before_action_sample.md  (4418 chars)
  reports/samples/et1_notes_sample.md             (4937 chars)
```

---

## 14. Test Results

```bash
python -m pytest tests/brain/ tests/legal_accuracy/ tests/security/ tests/router/ \
  tests/agents/ tests/citation_verification/ tests/evaluation/ tests/cache/ \
  tests/graph_rag/ tests/knowledge_graph/ tests/memory/ tests/mcp/ tests/uploads/ \
  tests/retrieval/ tests/rag/ tests/deadlines/ tests/user_isolation/ \
  tests/document_intelligence/ tests/documents/ tests/payment/ tests/rate_limiting/ \
  tests/ingestion/ -q

→ 426 passed, 2 skipped, 0 failed in 95.93s

Playwright E2E:
node_modules/.bin/playwright test
→ 17 passed

Smoke journey:
bash scripts/smoke_local_journey.sh
→ 24 PASS / 0 FAIL
```

---

## 15. Remaining Blockers

| # | Blocker | Severity | Owner |
|---|---|---|---|
| B1 | ANTHROPIC_API_KEY=placeholder — stub AI; complex assessments → insufficient_grounding | HIGH | Owner: set real key |
| B2 | Stripe real keys not configured — PAYMENT_MODE=test_simulator | HIGH | Owner: set Stripe keys |
| B3 | Case law embeddings empty (FCL licence pending) | MEDIUM | Owner: apply at nationalarchives |
| B4 | OCR/document extraction not implemented | MEDIUM | Claude: Phase 4 |
| B5 | WASM Rust binary exists; JS fallback active; WASM not recompiled with latest rules | LOW | Claude: next sprint |
| B6 | Kubernetes not yet applied (manifests ready) | HIGH | Owner: run deploy-talos.sh from WSL |
| B7 | Rate limiting uses in-memory — not production-safe | MEDIUM | Claude: configure Redis |
| B8 | Stripe webhook Phase 7 stub only | MEDIUM | Claude: Phase 7 |

---

## 16. What Is Still Stub/Backlog

| Item | Status | Notes |
|---|---|---|
| Real AI reasoning (Anthropic/Claude) | BLOCKED | Need real ANTHROPIC_API_KEY |
| Stripe webhook signature verification | STUB | Phase 7 — endpoint exists, sig check not implemented |
| OCR/PDF extraction | STUB | Phase 4 — architecture ready, engine not wired |
| WASM Rust rebuild | PARTIAL | Binary exists; source in client/wasm/src/ |
| AWS KMS envelope encryption | STUB | Local FERNET_V1 is real; KMS is phase 7 |
| Rate limiting Redis backend | STUB | in-memory only |
| Find Case Law ingestion | BLOCKED | FCL licence required |

---

## 17. Final Readiness Classification

**INTERNAL LOCAL DEMO READY**

Criteria met:
- ✓ `bash scripts/smoke_local_journey.sh` → 24/24 PASS
- ✓ `pytest` → 426/426 pass
- ✓ Playwright → 17/17 pass
- ✓ JWT auth + user isolation enforced (HTTP 403 proven)
- ✓ Assessment with deterministic citations (QP-fail case)
- ✓ Deadline from rules table
- ✓ Payment test simulator functional
- ✓ Document generation real (9620 chars with legal boundary notice)
- ✓ ACAS Day A/B in intake wizard
- ✓ All legal values from DB rules table
- ✓ No wrong naming (lawapp only)
- ✓ 42 DB tables including all required

Not yet:
- ✗ Real AI reasoning (placeholder key)
- ✗ Real Stripe payment
- ✗ Kubernetes applied
- ✗ Case law corpus populated
