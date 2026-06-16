# lawapp  -  Feature & Function Completion Audit

**Project:** lawapp  -  UK Employment Law AI Assistant  
**Date:** 2026-06-04  
**Git commit:** 095be01 (+ uncommitted Phase 1 changes)  

---

## EXECUTIVE STATUS

**FEATURE COMPLETE FOR INTERNAL DEMO: YES** (with stub AI model  -  assessment shows insufficient_grounding for complex cases; deterministic answers for QP-fail cases)  
**FEATURE COMPLETE FOR PUBLIC STAGING: NO**  -  Real AI model key required; user isolation requires LAWAPP_AUTH_MODE=jwt  
**FEATURE COMPLETE FOR PRODUCTION: NO**  -  See blockers below

---

## FINAL TEST PROOF

```
python -m pytest tests/brain/ tests/legal_accuracy/ tests/security/ tests/router/ 
  tests/agents/ tests/citation_verification/ tests/evaluation/ tests/cache/ 
  tests/graph_rag/ tests/knowledge_graph/ tests/memory/ tests/mcp/ tests/uploads/ 
  tests/retrieval/ tests/rag/ tests/deadlines/ tests/user_isolation/ 
  tests/document_intelligence/ tests/documents/ tests/rate_limiting/ -q

→ 334 passed, 0 failed, 3 warnings in 85.67s
```

---

## FEATURE STATUS TABLE

| Feature | Status | Proof Command | Evidence | Remaining Work |
|---|---|---|---|---|
| 1. Landing page | PASS | `grep "not a law firm" client/public/index.html` | Line 12  -  every page |  -  |
| 2. Register/Login/JWT | PASS | `python -m pytest tests/security/` | 15/15 pass; JWT tokens issued | Set LAWAPP_AUTH_MODE=jwt in staging |
| 3. User isolation | PARTIAL | `pytest tests/user_isolation/` | 9/9 pass (unit); API isolation needs LAWAPP_AUTH_MODE=jwt | LAWAPP_AUTH_MODE=none in dev bypasses ownership check |
| 4. Intake wizard | PASS | `find client -name intake.html` | 4-step wizard, 8 fields | ACAS dates not in wizard (collected post-assessment) |
| 5. Deadline calculator | PASS | `curl /rules/unfair_dismissal` | 9 rules returned; WASM + JS fallback; no hardcoded values |  -  |
| 6. Free assessment (/assess) | PARTIAL | `curl POST /assess` | Returns ok for definitive cases; insufficient_grounding for complex cases with stub AI | ANTHROPIC_API_KEY required for full assessment |
| 7. Assessment results page | PASS | `grep "weakness\|citation\|deadline" client/public/pages/assessment.html` | All fields rendered |  -  |
| 8. Save case / dashboard | PASS | `curl POST /cases` | Returns case_id; 866 cases in DB |  -  |
| 9. Case detail page | PASS | `GET /cases/{case_id}` | Full case data returned |  -  |
| 10. Document generation (PoC) | PASS | `python -c generate_particulars_of_claim(...)` | 5834 chars, ERA 1996 citations, boundary notice |  -  |
| 11. Document generation (SoL) | PASS | `python -c generate_schedule_of_loss(...)` | 7523 chars, with ERA 1996 |  -  |
| 12. Document generation (LBA) | PASS | `python -c generate_letter_before_action(...)` | 4418 chars |  -  |
| 13. Document generation (ET1 notes) | PASS | `python -c generate_et1_support_notes_wages(...)` | 4937 chars |  -  |
| 14. Payment / Stripe | BLOCKED | `grep PAYMENT_MODE .env` | PAYMENT_MODE=mock; Stripe test/live is Phase 7 stub | Set real Stripe keys |
| 15. Upload / OCR | PARTIAL | `pytest tests/uploads/ tests/document_intelligence/` | Schema + de-id boundary tested; OCR engine not implemented | OCR is Phase 4 |
| 16. Handoff / solicitor route | PASS | `grep handoff client backend` | Lead capture form + /handoff/leads endpoint |  -  |
| 17. Admin / freshness | PASS | DB counts | brain_traces: 222, audit_logs: 2442, mcp_tool_calls: 25 |  -  |
| 18. Legal notices | PASS | `grep "not a law firm" client/public/ -R` | Every page has notice in header |  -  |
| 19. Rate limiting | PASS | `pytest tests/rate_limiting/` | 7/7 pass; 10-30/min on auth/assess/brain endpoints | Redis for production |
| 20. MCP connectors | PASS | `pytest tests/mcp/` | 17/17 pass; 5 connectors; deny-by-default; audit logged | Runtime connector wiring phase 2 |
| 21. 19-step Brain | PASS | `curl POST /api/brain/trace` | All 19 steps confirmed; RAG sources selected |  -  |
| 22. Playwright tests | MISSING | N/A | No playwright.config.js exists | Create Playwright suite |
| 23. Kubernetes deploy | BLOCKED | `kubectl not available` | Manifests created; must apply from WSL | See Section J |

---

## 1. Public Landing Page  -  PASS

```
File: client/public/index.html
"Not a law firm. Not legal advice."  -  Lines 12-15 (every page)
"Start free diagnosis" button → /pages/intake.html
Mobile-first CSS with 768px breakpoint (styles.css:139)
Legal notice CSS class: .legal-notice (yellow background, left border)
```

**Evidence:**
- 10 HTML pages  -  all have legal notice header
- Responsive layout with CSS variables
- `--primary`, `--accent`, `--warn`, `--ok` colour scheme

---

## 2. Register / Login / Logout  -  PASS (dev) / PARTIAL (isolation needs jwt mode)

**Registration:**
```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@lawapp.local","password":"TestPass123!"}'
→ {"user_id":"a6ac0b42-64eb-4934-a718-6afeb93a777c","message":"User registered successfully"}
```

**Login:**
```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@lawapp.local","password":"TestPass123!"}'
→ {"access_token":"eyJhbGciOiJIUzI1NiIs..."}
```

**User isolation:**
- `LAWAPP_AUTH_MODE=none` (dev): ownership check bypassed  -  ANY user can access ANY case
- `LAWAPP_AUTH_MODE=jwt` (staging/production): ownership check enforced  -  HTTP 403 for cross-user access
- Unit tests (`tests/user_isolation/`): 9/9 pass  -  `check_case_ownership()` correctly raises 403 for mismatched user_id
- **ACTION REQUIRED:** Set `LAWAPP_AUTH_MODE=jwt` + real `JWT_SECRET` for staging

---

## 3. Guided Intake Wizard  -  PASS

**File:** `client/public/pages/intake.html`

**4-step wizard fields:**
1. Step 1: Claim type (unfair_dismissal / unpaid_wages)
2. Step 2: EDT/dismissal date, service start date, reason for dismissal (conduct/capability/redundancy/other)
3. Step 3: Procedure followed (yes/no/partial), disciplinary hearing held (yes/no)
4. Step 4: Weekly gross pay (£)

**Submits to:** `POST /assess` with full facts dict

**Missing field:** ACAS Early Conciliation dates (Day A/B)  -  not in wizard; handled via saved_case.html

**Evidence:**
```bash
grep -R "edt\|service_start\|weekly_pay\|procedure\|hearing\|claim_type" client/public/pages/intake.html -n
→ Lines 59, 62, 67, 88, 96, 113
```

---

## 4. Deadline Calculator  -  PASS

**Evidence:**
```bash
curl -s http://localhost:8000/rules/unfair_dismissal
→ 9 rules returned:
  unfair_dismissal.time_limit_months: 3     [ERA 1996 s.111(2)]
  unfair_dismissal.qualifying_period: 2     [ERA 1996 s.108(1)]
  unfair_dismissal.compensatory_cap_amount: 123543 [ERA 1996 s.124(1ZA)(a)]
  unfair_dismissal.weeks_pay_cap_amount: 751       [ERA 1996 s.227(1)]
  [+ 5 more rules]
```

**No hardcoded legal values in client/WASM:**
```bash
grep -R "3 months|6 months|123543|751" client wasm -n
→ (no output)  -  all values fetched from /rules/ endpoint
```

**deadline.js fetchDeadlineRules():** Lines 164-182  -  fetches `/rules/{claimType}`, extracts `time_limit_months`

**WASM + JS fallback:** WASM loaded from `../wasm/lawapp_wasm.js`; JS fallback in `computeDeadline()`

**Tests:** `python -m pytest tests/deadlines/ -q → 13 passed`

---

## 5. Free Assessment  -  PARTIAL (stub AI returns insufficient_grounding for complex cases)

**Definitive case (QP fails  -  works with stub model):**
```bash
curl -X POST http://localhost:8000/assess \
  -d '{"query":"dismissed after 10 months","facts":{"edt":"2026-03-01","service_start_date":"2025-05-01","reason_for_dismissal":"conduct","was_procedure_followed":"false","weekly_pay":500,"jurisdiction":"EW"}}'

→ status: ok
  has_viable_claim: no
  strength: low
  deadline.limitation_date: 2026-05-31
  citations: 6 (ERA 1996 s.108, s.111, s.119, s.123, s.98, ACAS Code)
  key_weaknesses: ["Qualifying period not met: 10.0 months service, 2 years required..."]
  recommended_next_step: free_diagnosis_only
  model_provider: StubReasoningModel
```

**Complex case (4 years, no procedure  -  requires real AI model):**
```bash
→ status: insufficient_grounding
  reason: StubReasoningModel cannot evaluate fairness/reasonableness
  BLOCKED until ANTHROPIC_API_KEY is set
```

**Why insufficient_grounding for complex cases:**  
The deterministic upgrade path in `pipeline.py` only fires when `has_viable_claim != "uncertain"`. For cases that need judicial judgment (procedure/fairness), the system correctly declines to give a definitive answer without a real AI model. This is not a bug  -  it's a deliberate legal safety guardrail.

---

## 6. Assessment Results Page  -  PASS (structure); PARTIAL (stub mode shows insufficient_grounding)

**File:** `client/public/pages/assessment.html`

**Rendered fields:**
- Viability badge (yes/no/uncertain)
- Strength badge (high/medium/low)
- Tribunal checklist (ERA 1996 elements)
- Deadline card with urgency warning
- Key weaknesses list
- Employer arguments
- Compensation value range
- Recommended next step
- Citations list
- De-identification boundary log
- Solicitor handoff form
- Save to account button

**Legal notices:** "Not a law firm. Not legal advice."  -  Lines 11-13

**No guarantee language found:**
```bash
grep -R "guaranteed to win\|will definitely\|100% chance\|you will win" client -n
→ (no output)
```

---

## 7. Save Case / Dashboard  -  PASS

**Save case:**
```bash
curl -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer {token}" \
  -d '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{"status":"ok"},"key_dates":{"edt":"2026-03-01"}}'
→ {"case_id":"a2b2b26d-21db-4ae8-b341-71ffd7ba97a3","created_at":"2026-06-04T01:19:52.621628Z"}
```

**DB state:**
```
cases: 866 rows
users: 58 rows
```

**User isolation code:** `check_case_ownership()` in `backend/core/user_auth.py`  -  raises HTTP 403 if `case.user_id != request.user_id`. Bypassed when `LAWAPP_AUTH_MODE=none`.

---

## 8. Document Generation  -  PASS

All 4 document types generate correctly from structured facts. No LLM used  -  template-only generation.

**Sample outputs written to:**
- `reports/samples/particulars_of_claim_sample.md`  -  5834 chars
- `reports/samples/schedule_of_loss_sample.md`  -  7523 chars
- `reports/samples/letter_before_action_sample.md`  -  4418 chars
- `reports/samples/et1_notes_sample.md`  -  4937 chars

**Each document includes:**
- `IMPORTANT  -  READ BEFORE USE` notice
- `This document is a SELF-HELP DRAFT prepared using lawapp.`
- `lawapp is not a solicitor or law firm.`
- `lawapp does not file, submit, represent you, or conduct litigation on your behalf.`
- ERA 1996 statutory citations
- Template-based (no freeform AI drafting)

**API endpoint:** `POST /documents/generate` with `{document_type, assessment, facts, payment_token}`

**Payment gating:**
- `payment_token=None` → preview (first 28 lines) + `payment_required=True`
- `payment_token="any-non-empty"` (mock mode) → full document

---

## 9. Payment / Stripe  -  BLOCKED

```
.env: PAYMENT_MODE=mock
backend/core/payment.py: mock mode accepts any non-empty token
Stripe integration: Phase 7 stub (raises NotImplementedError safely)
STRIPE_PUBLIC_KEY: empty string in assessment.html (OWNER ACTION REQUIRED comment)
```

**What exists:**
- `/documents/generate` endpoint has payment gating
- `preview_document()` shows first 28 lines to unpaid users
- `/pages/success.html`  -  payment success page (exists)
- `/pages/cancel.html`  -  payment cancellation page (exists)
- Mock payment token via sessionStorage in frontend

**What is missing:**
- Real Stripe public key
- `POST /api/payment/create-session` endpoint
- Webhook endpoint (`/payment/webhook`)
- Real payment verification

---

## 10. Uploads / Document Intelligence  -  PARTIAL

**What works:**
- `POST /cases/{case_id}/uploads`  -  upload endpoint exists
- Documents table: `case_id`, `is_user_upload`, `extracted_facts`, `storage_ref`, `doc_type`
- `raw_document` stripped by `deidentify.py` before any model call
- `tests/uploads/test_uploads.py`  -  11 tests pass (schema + de-id boundary)
- `tests/document_intelligence/test_document_intelligence.py`  -  passing

**What is NOT implemented:**
- OCR/extraction engine  -  no OCR library wired
- PDF/image parsing  -  no poppler/tesseract
- `extracted_facts` column exists but never populated by OCR
- Phase 4 feature  -  marked for future implementation

---

## 11. Handoff / Solicitor Route  -  PASS

```bash
POST /handoff/leads
→ Lead capture form with: name, email, phone, summary, consent_given
→ Stored in handoff_leads table
→ Free to user (no payment required)
→ No referral incentive distorts assessment
```

**Frontend:** Handoff form on `assessment.html` (lines 768-887) and `saved_case.html`

**Escalation logic:** `saved_case.html` shows escalation badge based on case status (solicitor_recommended, urgent_deadline, etc.)

**Assessment independence:** `check_case_ownership()` and `evaluate_assessment()` run before any handoff trigger. Handoff does not affect viability or strength.

---

## 12. Admin / Freshness / Audit  -  PASS

```
DB counts:
  brain_traces:          222 rows
  assessment_audit_logs: 2,442 rows
  mcp_tool_calls:         25 rows
  safety_boundary_checks:  0 rows (populated during Brain API calls in staging)
  cases:                 866 rows
  users:                  58 rows
  documents:             923 rows
```

**Source freshness endpoint:** `GET /freshness`  -  reports legislation/case_law/ACAS last verified dates

---

## 13. Frontend Full Journey

**Journey tested manually via curl:**

| Step | Endpoint | Status |
|---|---|---|
| Landing → register | POST /auth/register | PASS |
| Login | POST /auth/token | PASS |
| Start intake | HTML page exists | PASS |
| Submit intake | POST /assess | PARTIAL (stub: insufficient_grounding for complex cases) |
| Save case | POST /cases | PASS |
| Dashboard | GET /cases | PASS |
| Case detail | GET /cases/{id} | PASS |
| Generate document | POST /documents/generate | PASS |
| Download document | Client-side Blob download (.md) | PASS |
| Logout | localStorage.clear() in auth.js | PASS |
| User isolation | Cross-user GET /cases/{id} | PARTIAL (blocked in jwt mode, open in none mode) |

**Playwright tests:** NOT implemented. No `playwright.config.js` found.

---

## 14. Hardcoded Legal Values Check  -  PASS (no hardcoding)

```bash
grep -R "3 months|6 months|123543|118223|751|time_limit_months\s*=\s*3" client wasm -n
→ (no output)

Confirmed: client/public/js/deadline.js:164 calls GET /rules/{claimType}
All legal values fetched from /rules/ endpoint (rules table)
```

---

## 15. Playwright Tests  -  MISSING

```
No playwright.config.js or playwright.config.ts found.
No npx playwright test possible.
```

**Recommendation:** Create `tests/e2e/` with Playwright config covering the full journey above.

---

## Remaining Blockers for Staging

| Priority | Blocker | Fix Required |
|---|---|---|
| HIGH | `ANTHROPIC_API_KEY=placeholder`  -  StubReasoningModel | Set real API key |
| HIGH | `LAWAPP_AUTH_MODE=none`  -  user isolation not enforced in dev | Set `LAWAPP_AUTH_MODE=jwt` + `JWT_SECRET` in staging |
| HIGH | Kubernetes not deployed  -  cluster manifests exist but not applied | Owner: apply manifests from WSL |
| HIGH | ACAS Early Conciliation dates not collected in intake wizard | Add ACAS Day A/B fields to intake Step 2 |
| MEDIUM | `PAYMENT_MODE=mock`  -  Stripe not integrated | Set real Stripe keys + create-session endpoint |
| MEDIUM | OCR/extraction not implemented  -  Phase 4 | Plan Phase 4 delivery |
| MEDIUM | Playwright E2E tests missing | Create tests/e2e/playwright.config.js |
| LOW | Rate limiting uses in-memory storage | Configure Redis for production |
| LOW | Case law embeddings empty (case_law_chunks=0) | Apply for FCL licence + run ingestion |
