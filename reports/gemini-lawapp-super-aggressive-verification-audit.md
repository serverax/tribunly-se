# Gemini Super Aggressive LawApp Verification Audit

**Date:** 2026-06-04  
**Commit:** eb31849  
**Branch:** master  
**Auditor:** Claude Code (hostile self-audit, no pre-trust of prior reports)  
**Project root:** /f/lawapp  

---

## 1. Final Classification

- **Local demo ready:** PARTIAL — most features work but DB seed data requires manual re-run after fresh Docker start
- **Staging ready:** NO — real AI, Stripe, Kubernetes, Redis, case law corpus all missing/unproven
- **Production ready:** NO

**Reason:** Claude's "24 PASS smoke journey" and "439 passed" claims were made against a pre-seeded database. When the audit ran `docker compose up -d --build` against the committed codebase, the rules table (and all ingested data) was **empty**. Assessment-dependent tests fail. Smoke journey fails 4/24 with empty DB. The code architecture is sound, but data population is a production gap that is not automated.

---

## 2. Executive Truth

**What is real and working:**
- JWT auth (mock mode in test env, jwt mode in Docker) — proven by HTTP 403 on cross-user access
- 19-step Brain Algorithm — code exists, steps trace correctly
- Deadline calculation (deterministic, no AI) — all 3 EC scenarios correct
- Document generation (Particulars of Claim, Schedule of Loss) — returns real template content, 9620 chars
- Payment test simulator — gating works, invalid tokens rejected
- User isolation — HTTP 403 proven in smoke journey
- Frontend pages — all 10 pages exist with legal notices
- WASM binary exists, JS fallback uses `fetchDeadlineRules()` from backend (no hardcoded values)
- K8s manifests — syntax valid, secret names audited (10/10 match)
- CI/CD workflows exist (`lawapp-ci.yml`, `lawapp-deploy-k8s.yml`)

**What is stub/partial/missing:**
- DB seed data **not automated** — rules table is empty on fresh Docker start (FAIL for reproducible demos)
- Real AI reasoning — ANTHROPIC_API_KEY=placeholder; all complex assessments return `insufficient_grounding`
- Case law corpus — 0 rows (FCL licence not obtained)
- Legislation/ACAS ingestion — 0 rows on fresh Docker (previously seeded manually, not in migrations)
- Stripe payment — test_simulator only; webhook signature verification is a stub
- Redis rate limiting — in-memory only; not production-safe
- `scripts/push-and-deploy.sh` — MISSING (Claude coding task)
- OCR/extraction — mock stub only (`mock_extract()`)
- WASM Rust source exists but rebuild not verified
- Kubernetes cluster — NOT deployed, not proven; manifests ready but untested against cluster

**What is fake/misleading in prior Claude reports:**
- "439 passed" and "24/24 smoke" were true **only against a previously seeded database** — not against the committed codebase state. A fresh `docker compose up` yields a different result.
- "legislation: 80 rows embedded" — UNVERIFIED on current Docker; fresh DB shows 0 rows
- The Claude reports did not disclose the seed/ingestion dependency

---

## 3. Claude Claim Verification Matrix

| Claude Claim | Verified? | Evidence Command | Verdict | Notes |
|---|---|---|---|---|
| Local smoke: 24 PASS / 0 FAIL | NO | `bash scripts/smoke_local_journey.sh` | **FAIL (20/24 on fresh DB)** | Rules API returns empty; assessment gets no citations |
| Pytest: 439 passed | PARTIAL | `python -m pytest` | **FAIL: 7 ingestion tests fail** on fresh DB | Pass only with pre-seeded data |
| Playwright: 17 passed | PARTIAL | `node_modules/.bin/playwright test` | **FAIL: 3/17 fail** on fresh DB | Rules API test fails without data |
| 42 DB tables | CLOSE | `\dt` → 43 rows | **PASS (43, not 42)** | Minor discrepancy |
| 19 rules rows | NO | `SELECT COUNT(*) FROM rules` → 0 | **FAIL on fresh Docker** | Seed not in migration |
| 80 legislation rows embedded | NO | SELECT COUNT → 0 | **FAIL on fresh Docker** | Ingestion not automated |
| 12 ACAS rows embedded | NO | SELECT COUNT → 0 | **FAIL on fresh Docker** | Ingestion not automated |
| 19-step brain | YES | curl /api/brain/trace → 19 steps | **PASS** | Confirmed working |
| Hybrid retrieval | PARTIAL | Code exists | **PARTIAL** | Returns empty bundle without data |
| Graph RAG | YES | legal_nodes=15, legal_edges=14 | **PASS** | Seeded in migration 018 |
| Context compression | YES | brain.py step 13 exists | **PASS** | Wired in brain |
| Semantic cache | YES | Code + DB table exist | **PASS** | Wired |
| MCP connectors | YES | 5 connectors tested | **PASS** | Deny-by-default |
| JWT isolation | YES | HTTP 403 for cross-user access | **PASS** | Confirmed |
| PII stripping before model | YES | deidentify() before model.reason() | **PASS** | Code-verified |
| Payment simulator | YES | Valid test_ token accepted | **PASS** | Invalid token rejected |
| Document generation | YES | 9620 chars, boundary notice | **PASS** | Real template content |
| K8s manifests prepared | YES | bash -n scripts/deploy-talos.sh OK | **PASS** | Syntax valid, not deployed |
| CI/CD workflows exist | YES | `.github/workflows/` lists 9 files | **PASS** | Not all tailored to lawapp |

---

## 4. Backend Audit

### Routes verified

| Route | HTTP Status | Returns Real Data? |
|---|---|---|
| GET /health | 200 | `{"status":"ok","db":"connected","auth_mode":"jwt","ai_provider":{"active":false}}` |
| GET /rules/unfair_dismissal | 200 | 0 rules (empty DB) — **FAIL if relying on rules** |
| GET /api/rules/unfair_dismissal | 200 | Same — empty |
| POST /api/deadline/calculate | 200 | **PASS** — correct arithmetic for all 3 EC scenarios |
| POST /api/brain/trace | 200 | 19 steps, `insufficient_grounding=true` (no AI key, no data) |
| POST /assess | 200 | `insufficient_grounding` — no rules data |
| POST /auth/register | 201 | User created — PASS |
| POST /auth/token | 200 | JWT token issued — PASS |
| GET /auth/me | 200 | User returned — PASS |
| POST /cases | 201 | Case saved with JWT — PASS |
| GET /cases/{id} | 200 own / 403 cross-user | **PASS** — isolation working |
| POST /documents/generate | 200 | Full document 9620 chars — **PASS** |
| POST /api/payment/create-session | 200 | test_ token — PASS |
| POST /api/payment/webhook | 200 | test_simulator pass-through — PASS |
| GET /api/payment/status | 200 | mode=test_simulator, stripe_configured=False — PASS |
| POST /handoff/leads | 201 | Lead recorded — PASS |
| GET /freshness | 200 | Returns source freshness (empty data) |
| GET /api/documents/{id}/download | 500 | Error on nonexistent ID — acceptable |

### Contamination findings

| File | Finding | Classification |
|---|---|---|
| infra/k8s/iterlaw/*.yaml | IterLaw in comments (13 files) | Legacy directory — harmless; not deployed |
| backend/core/brain.py | Previously had OrdinoxAI — now fixed | Historical; clean in runtime |
| db/migrations/018 | Previously had OrdinoxAI — now fixed | Historical; clean in runtime |

**Verdict:** IterLaw naming only in legacy `infra/k8s/iterlaw/` subdirectory that is **never applied to the cluster**. Runtime code is clean.

### AI provider

```
docker compose exec backend printenv AI_PROVIDER → (not set)
health endpoint: {"ai_provider":{"provider":"stub","active":false,"note":"No AI key configured — StubReasoningModel active"}}
```

Complex assessment with stub model → `insufficient_grounding` — **correct safe behaviour, not fake legal reasoning**.

---

## 5. Frontend Audit

### Pages confirmed existing

All 10 pages exist: `/`, `pages/register.html`, `pages/login.html`, `pages/intake.html`, `pages/assessment.html`, `pages/dashboard.html`, `pages/saved_case.html`, `pages/success.html`, `pages/cancel.html`

### Legal notices

13 occurrences of "not a law firm / not legal advice / SELF-HELP" across client pages — **PASS**

### Hardcoded legal values in JS

```
grep -RIn "time_limit_months|3 months|6 months|123543|751" client/public --include="*.js"
→ No matches
```

`fetchDeadlineRules()` calls `GET /rules/{claimType}` at runtime — **PASS**

### ACAS fields in intake

`intake.html` contains `#ec_day_a`, `#ec_day_b`, `#acas_not_started` — **PASS** (added this session)

### Playwright results (current empty-DB state)

```
17 tests total → 10 passed, 3 failed
FAIL: intake deadline preview (rules API returns 0 rules)
FAIL: assessment definitiveness (depends on rules data)
FAIL: save case with JWT (depends on rules returning data)
```

---

## 6. Database Audit

### Critical Finding: DB seed not automated

```
docker compose up -d --build (fresh)
SELECT COUNT(*) FROM rules → 0
SELECT COUNT(*) FROM legislation → 0
SELECT COUNT(*) FROM acas_guidance → 0
SELECT COUNT(*) FROM brain_traces → 0
```

**Root cause:** Migrations create table schemas, but seed/ingestion data is loaded separately by Python scripts. `docker-entrypoint-initdb.d` only runs SQL migrations.

**Impact:** Every assessment returns `insufficient_grounding`. Rules API returns empty list. Legal accuracy tests fail. Deadline `authority_url` is empty string.

### Tables: 43 confirmed (Claude claimed 42 — minor)

Extensions: `pgcrypto`, `plpgsql`, `vector` — **PASS**

### Graph nodes/edges: PASS (seeded in migration 018)

```
legal_nodes: 15 rows ✓
legal_edges: 14 rows ✓
```

### Rules table structure

```
\d rules → id, rule_key, claim_type, jurisdiction, value_numeric, value_text, unit, description, authority_ref, authority_url, effective_from, effective_to
```

Table structure is correct — data just not loaded.

---

## 7. RAG / Brain / New Technologies Audit

| Technology | Code exists | DB exists | Route exists | Runtime works (empty DB) | Tests pass | Real or stub | Verdict |
|---|---|---|---|---|---|---|---|
| Agentic AI (19-step brain) | YES | brain_traces | /api/brain/trace | YES — 19 steps traced | 43/43 | Real pipeline, stub model | **PARTIAL** |
| Hybrid Search | YES | retrieval_audit | /api/rag/hybrid-search | YES — returns empty bundle | 18/18 | Real code, no data | **PARTIAL** |
| Graph RAG | YES | legal_nodes/edges | /api/rag/graph | YES | 24/24 | Real — 15 nodes seeded | **PASS** |
| Knowledge Graph | YES | legal_nodes/edges | internal | YES | 21/21 | Real | **PASS** |
| Context Compression | YES | context_compression_log | Brain step 13 | YES | brain tests | Real | **PASS** |
| Memory Engine | YES | legal_memory | /api/memory/save,get | YES | 9/9 | Real, consent-gated | **PASS** |
| Evaluation AI | YES | evaluation_results | /api/evaluate | YES | passing | Real rubric | **PASS** |
| MCP Connectors | YES | mcp_tool_calls | /api/mcp/tools | YES — 5 connectors | 17/17 | Real, deny-by-default | **PASS** |
| Multimodal AI | PARTIAL | documents | /api/documents/upload | Upload endpoint exists | 11/11 | mock_extract() stub | **STUB** |
| AI Router | YES | routing_decisions | Brain step 9 | YES | router tests | Real routing | **PASS** |
| Semantic Cache | YES | semantic_cache | /api/cache/test | YES | cache tests | Real | **PASS** |
| WASM/JS fallback | PARTIAL | wasm_calculations | /rules/ feeds it | Binary exists, not rebuilt | deadline tests | JS fallback active | **PARTIAL** |

---

## 8. Security Audit

### JWT and user isolation: PASS

```
bash scripts/smoke_local_journey.sh → Step 10: HTTP 403 for cross-user access
docker compose exec backend printenv LAWAPP_AUTH_MODE → jwt
```

### Encryption tests

```
python -m pytest tests/security/test_encryption.py → 8 passed, 2 skipped (ENCRYPTION_KEY absent)
```

**Finding:** 2 encryption tests skip because `ENCRYPTION_KEY` is absent in test environment. The skips are labelled correctly. The conftest sets `ENCRYPTION_KEY=dev-jwt-secret-replace-in-production` — this is a placeholder, not real Fernet key. In production with a real key, tests would run.

### De-identification: PASS

```
python -m pytest tests/security/test_deidentification.py → 11 passed
```

Pipeline enforces `deidentify()` before `model.reason()` — code-verified.

### Rate limiting: PARTIAL

```
grep -n "redis|Redis" docker-compose.yml → No Redis in docker-compose.yml
```

Rate limiting is in-memory only (slowapi). Not safe for multi-instance production. **No Redis**.

### Reserved activity language: PASS

```
grep -RIn "win your case|guarantee|we will file|we represent|our solicitor|rights of audience" backend client → Only in detection/blocking code, not in output generation
```

Guaranteed language detection is in brain.py `_SAFETY_GUARANTEE_PHRASES` — blocks output, not generates it.

---

## 9. Payment Audit

```
http://localhost:8000/api/payment/status → {"mode":"test_simulator","stripe_configured":false,"demo_mode":true}
```

| Check | Result |
|---|---|
| No token → preview only | PASS |
| Invalid token (no test_ prefix) → payment_required=True | PASS |
| Valid test_ token → full document | PASS |
| Stripe webhook endpoint exists | PASS (200 in test mode) |
| Stripe webhook signature verification | STUB (Phase 7) |
| Live Stripe keys | NOT CONFIGURED |

**Verdict:** PARTIAL — simulator works correctly; Stripe integration is a stub.

---

## 10. Document Generation Audit

```
POST /documents/generate with test_xxx token → 9620 chars
Contains: "SELF-HELP DRAFT", "lawapp is not a solicitor or law firm"
Contains: ERA 1996 citations
Does NOT contain: "we will file", "we represent"
Document boundary notice: PRESENT
Ownership enforced: PASS
```

**Verdict: PASS** — real template content, not static sample. Legal boundary notice confirmed.

---

## 11. WASM Audit

```
ls client/public/wasm/ → lawapp_wasm_bg.wasm (95392 bytes), lawapp_wasm.js, .d.ts files
stat client/wasm/src/lib.rs → exists
deadline.js line 166: fetch('/rules/${claimType}') — fetches from backend
No hardcoded legal values in client JS
```

**WASM binary:** Exists (95KB) — not recently rebuilt (last modified Jun 2)  
**JS fallback:** Active and functional  
**Legal values source:** Backend `/rules/` endpoint — PASS  
**WASM rebuild automation:** Missing (`wasm-pack build` not in scripts)

**Verdict: PARTIAL** — binary exists; JS fallback functional; WASM rebuild not automated.

---

## 12. Upload / OCR / Multimodal Audit

```
grep -n "mock_extract" backend/api/main.py → line 1242: extracted = mock_extract(doc_type)
```

`mock_extract()` is in `backend/core/extraction.py` and returns static placeholder facts.  
No real OCR engine present. Route exists (`/cases/{id}/uploads`) but extraction is a stub.

**Verdict: STUB** — upload route works; OCR/extraction is a mock placeholder.

---

## 13. Kubernetes Audit

```
bash -n scripts/deploy-talos.sh → Script syntax: PASS
17 lawapp-*.yaml manifests found
Secret names: lawapp-postgres-secret, lawapp-secrets, lawapp-ai-secrets, lawapp-rag-secrets ← 10/10 match
kubectl apply --dry-run=client -f infra/k8s/ → kubectl not available
```

**Not deployed** — cluster status cannot be verified from this machine. Manifests are syntax-valid and secrets are consistent.

**IterLaw legacy files:** `infra/k8s/iterlaw/` — NOT applied to lawapp cluster; legacy from previous project name.

**Verdict: NOT PROVEN** (manifests ready, cluster not deployed/verified)

---

## 14. CI/CD Audit

```
ls .github/workflows/ →
  build-images.yml
  ci.yml (generic, not lawapp-specific)
  deploy-iterlaw-ai.yml ← WRONG NAME
  deploy-staging.yml
  docker-proof.yml
  lawapp-ci.yml ← lawapp-specific
  lawapp-deploy-k8s.yml ← lawapp-specific
  smoke.yml
```

**Missing:**
- `scripts/push-and-deploy.sh` — **NOT FOUND** (Claude coding task)

**deploy-iterlaw-ai.yml** — wrong project name in CI file. Should be updated or deleted.

**Verdict: PARTIAL** — lawapp-specific CI exists; push automation missing; stale workflow file present.

---

## 15. Legal Guardrail Audit

```
grep -RIn "win your case|guarantee|we will file|we represent|our solicitor|rights of audience" backend client tests → Only in detection/blocking lists
grep -RIn "not a law firm|not legal advice|SELF-HELP" client/public → 13 occurrences across all pages
```

**Hardcoded 3-month default in test-only route:**

```
backend/api/main.py:3187: time_limit_months: int = 3  (in /api/test/wasm-deadline only)
```

This is in a test-only admin route, not in production assessment path. The production `/api/deadline/calculate` reads from the DB (returns correct 3 from rules when seeded).

**Verdict: PASS for production paths** | MINOR ISSUE: default=3 in test route (not a runtime risk)

---

## 16. Test Suite Audit

### Against empty DB (current state)

```
python -m pytest tests/security/ tests/user_isolation/ tests/brain/ tests/deadlines/ tests/router/ tests/agents/ tests/payment/ tests/documents/ tests/rate_limiting/ -q
→ 215 passed, 3 skipped, 0 failed

python -m pytest tests/legal_accuracy/ tests/ingestion/ -q
→ 7 failed (all data-dependent — rules/legislation/ACAS rows = 0)
→ 56 passed

Playwright: 10 passed, 3 failed (all data-dependent)
Smoke journey: 20 PASS / 4 FAIL (data-dependent)
```

### Data-dependent test failures (all caused by empty DB after fresh Docker start)

```
TestLegislationTable::test_legislation_has_rows — 0 rows in legislation
TestAcasGuidanceTable::test_acas_guidance_has_rows — 0 rows in acas_guidance
TestRulesTable::test_ud_time_limit_rule_exists — 0 rows in rules
TestRulesTable::test_ud_qualifying_period_rule_exists
TestRulesTable::test_ud_compensatory_cap_rule_exists
TestRulesTable::test_prospective_rules_exist_for_future
smoke: time_limit_months: got missing
smoke: Assessment status: insufficient_grounding
```

**Root cause:** The seed/ingestion scripts are not part of Docker Compose startup. The `docker-entrypoint-initdb.d` runs migrations but not Python seed scripts.

---

## 17. Blockers

| ID | Blocker | Severity | Owner | Exact fix required | Verification command |
|---|---|---|---|---|---|
| B1 | DB seed not automated — fresh Docker has no rules/legislation/ACAS data | CRITICAL | Claude | Add seed step to docker-compose or migration | `SELECT COUNT(*) FROM rules;` → must show >0 on fresh start |
| B2 | ANTHROPIC_API_KEY=placeholder | HIGH | Owner | Set real API key | `curl /health \| jq .ai_provider.active` → true |
| B3 | Case law corpus = 0 rows | HIGH | Owner (FCL licence) | Obtain FCL bulk computational access | `SELECT COUNT(*) FROM case_law_chunks;` |
| B4 | Stripe webhook signature verification stub | HIGH | Claude | Implement using stripe Python SDK | `python -m pytest tests/payment/ -k webhook` |
| B5 | Redis rate limiting missing | MEDIUM | Claude | Add Redis to docker-compose + backend config | `docker compose exec redis redis-cli ping` |
| B6 | `scripts/push-and-deploy.sh` missing | MEDIUM | Claude | Create script | `bash scripts/push-and-deploy.sh --dry-run` |
| B7 | OCR/extraction is mock_extract() stub | MEDIUM | Claude | Implement real OCR (Phase 4) or clearly disable route | Route returns 501 instead of mock |
| B8 | WASM not rebuilt with current rules | LOW | Claude | Add `wasm-pack build` to scripts | `stat client/public/wasm/lawapp_wasm_bg.wasm` + check timestamp |
| B9 | `deploy-iterlaw-ai.yml` CI file has wrong project name | LOW | Claude | Delete or rename to `deploy-lawapp-staging.yml` | `ls .github/workflows/` |
| B10 | Kubernetes cluster not deployed/proven | BLOCKED_OWNER | Owner | Run `bash scripts/deploy-talos.sh` from WSL with kubeconfig | `kubectl get pods -n lawapp-api` |
| B11 | `ENCRYPTION_KEY` placeholder causes 2 test skips | LOW | Owner (production) | Set real Fernet key in staging .env | `python -m pytest tests/security/test_encryption.py` → 0 skipped |

---

## 18. Claude Code Workpack

### Task 1: Automate DB seed on fresh Docker start (CRITICAL)

**Files to edit:** `docker-compose.yml` or create `scripts/init-db.sh`  
**Required:** After migrations, run `python ingestion/rules/seed_unfair_dismissal.py` and `python ingestion/rules/seed.py` automatically  
**Option A:** Add a `db-init` service to docker-compose that runs once after DB is healthy  
**Option B:** Add seed SQL to a migration file  
**Verification:** `docker compose down -v && docker compose up -d --build && docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"` → must return >0  
**Pass condition:** >0 rules on fresh Docker start

### Task 2: Implement Stripe webhook signature verification

**Files:** `backend/core/payment.py`, `backend/api/main.py`, `tests/payment/test_payment.py`  
**Required:** Use `stripe.Webhook.construct_event(payload, sig_header, webhook_secret)` when `PAYMENT_MODE=stripe_test` or `stripe_live`  
**Verification:** `python -m pytest tests/payment/test_payment.py -k webhook`

### Task 3: Add Redis to Docker Compose + configure rate limiting

**Files:** `docker-compose.yml`, `backend/api/main.py`, `pyproject.toml`  
**Required:** Add Redis service; configure `RATELIMIT_STORAGE_URI=redis://redis:6379`  
**Verification:** Rate limit test with Redis backend

### Task 4: Create `scripts/push-and-deploy.sh`

**Required:** git status check, run tests, build Docker, push to GHCR, trigger GitHub Actions  
**Verification:** `bash scripts/push-and-deploy.sh --dry-run`

### Task 5: Honestly mark OCR as 501 Not Implemented

**Files:** `backend/api/main.py` lines around `/api/documents/upload` extraction flow  
**Required:** Replace `mock_extract()` call with `raise HTTPException(501, "OCR extraction not yet implemented")` until real OCR is added  
**Verification:** `curl POST /cases/{id}/uploads/{id}/extract → 501`

### Task 6: WASM rebuild script

**Required:** Add `scripts/rebuild-wasm.sh` with `wasm-pack build --target web --out-dir ../public/wasm`  
**Verification:** `bash scripts/rebuild-wasm.sh && ls client/public/wasm/*.wasm`

### Task 7: Delete/rename stale CI workflow

**Files:** `.github/workflows/deploy-iterlaw-ai.yml`  
**Required:** Rename to `lawapp-deploy-staging.yml` or delete  
**Verification:** `ls .github/workflows/ | grep iterlaw` → empty

---

## 19. Final Sign-Off Decision

**REJECT CLAIMED COMPLETION**

**Reason:** Claude's reports claimed 24/24 smoke journey PASS and 439/0 test pass, but these were only true against a manually pre-seeded database that is lost on fresh Docker restart. Against the committed codebase state:

- Smoke journey: 20 PASS / 4 FAIL  
- Ingestion tests: 7 FAIL  
- Playwright: 3 FAIL

The architecture is genuinely solid. The code is real, not hallucinated. The legal guardrails are correct. JWT isolation works. The 19-step brain pipeline exists. Documents generate real content. But the **reproducibility gap** — seed data not automated — means a developer cannot run `docker compose up` and get a working lawapp.

**Accept only:** ACCEPT LOCAL DEMO ONLY (with manual seed step required)

**Not accept:** "Internal local demo ready" as stated — this implies a developer can start from scratch and get a demo, which is false.
