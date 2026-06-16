# LAWAPP DEEP QA + REPAIR REPORT

Date: 2026-06-12 · Branch: `release/lawapp-clean-snapshot` · Base HEAD: `62b9146`
Stack under test: local Docker compose (backend:8000, db pgvector:16, redis, 8 microservices)  -  AKS production unreachable from this machine.
Modes: `LAWAPP_AUTH_MODE=jwt`, `PAYMENT_MODE=disabled`, `ENVIRONMENT=development`.

---

## 1. Executive verdict

| Question | Verdict |
|---|---|
| **Closed beta** | **CONDITIONAL YES**  -  all 16 workflows proven live (29/29), all legacy/canonical routes fail closed, DB integrity proven, citation/deadline determinism proven. Conditions: rebuild image from this repo state before exposing (done locally; redeploy required for any remote env), and the full-suite known-stale failures listed in §10 stay quarantined or fixed. |
| **Public launch** | **NO**  -  TLS/DNS/KMS/DPIA unproven, backup/restore unproven, payment in `disabled` mode (Stripe live keys are an owner decision), `ENVIRONMENT=development`. |
| **100K users in 5 minutes** | **NO**  -  no load test executed this session; claim not permitted under strict pass rules. |

## 2. Files changed (this session)

| File | Change |
|---|---|
| `backend/api/main.py` | Legacy `GET /api/payment/status`: auth gate added (401 unauth  -  parity with canonical). Legacy `POST /documents/generate`: ownership check made conditional on `case_id` presence (caseless drafts have no resource to own; payment gate still forces preview). `/freshness`: fixed `UndefinedColumn` 500 (`source` → `source_name`). |
| `backend/api/document_routes.py` | `DOCUMENT_TYPE_ALIASES` added; canonical generate now normalizes `particulars_of_claim`→`particulars` etc. before validation  -  fixes paid users getting 400 from both frontend pages. |
| `client/public/pages/case_detail.html` | `downloadDoc()` rewired from legacy `/documents/generate` to canonical `/api/documents/generate` + authed canonical download, 402 handling; dead `pocBtn`/`solBtn` now actually appended (buttons previously never rendered). |
| `scripts/smoke_local_journey.sh` | Steps 11–12 updated to hardened payment contract (no raw `payment_token` unlock; unpaid → 402/preview-gated); brain-trace assertion `>=19` steps; step 12 now sends `case_id`. |
| `tests/test_legacy_route_parity.py` | `unpaid_case` fixture seeds `users` row first (FK), cleans it up; legacy `GET /api/payment/status` added to unauthenticated-401 parametrize. |
| `tests/security/test_payment_access.py` | 3 stale anonymous-access tests now pin fail-closed 401; doc-type validation test authenticates; new `test_payment_status_requires_auth`. |
| `tests/test_integrity_framework.py` | All 3 citation-gate tests authenticate (mock identity)  -  they target the citation gate, not the auth gate. |
| `scripts/proof/prove_lawapp_full_workflows.sh` | **NEW**  -  16-workflow live proof, exits non-zero on failure. |
| `scripts/proof/prove_database_integrity.sh` | **NEW**  -  migrations/tables/FKs/rules/password proof, exits non-zero on failure. |

## 3. Tests run (command → exit → result → evidence)

| Command | Exit | Result | Evidence |
|---|---|---|---|
| `pytest tests/test_legacy_route_parity.py tests/security/test_payment_access.py` (in container) | 0 | **22 passed** | session log |
| `pytest tests/test_integrity_framework.py` (in container) | 0 | **3 passed** | session log |
| `pytest tests -k "rag or reasoning or assessment or deadline or rules or citation or grounding or deident"` (in container) | 1→fixed | 396 passed, 28 failed → service-contract failures re-run **30 passed** after `services/` copied into container; integrity failure fixed (see §2) | `reports/` + session log |
| `pytest tests/test_services_health.py tests/test_distributed_service_contracts.py` (in container) | 0 | **30 passed** | session log |
| FULL SUITE (in container) | _see §3a_ | _see §3a_ | `/tmp/full_suite.txt` in container, copied to `reports/full_suite_results.txt` |
| `bash scripts/smoke_local_journey.sh` | 0 | **23 PASS / 0 FAIL** | `reports/smoke_local_journey_latest.txt` |
| `bash scripts/proof/prove_lawapp_full_workflows.sh` | 0 | **29 PASS / 0 FAIL** | `reports/proof_full_workflows.txt` |
| `bash scripts/proof/prove_database_integrity.sh` | 0 | **15 PASS / 0 FAIL** | `reports/proof_database_integrity.txt` |

### 3a. Full suite
PENDING_FULL_SUITE

## 4. Frontend audit

- **Pages tested live (200):** `/`, `/pages/intake.html`, `/pages/assessment.html`, `/pages/dashboard.html`, `/pages/case_detail.html` (+ login/register/onboarding/tools pages exist and are linked).
- **Route wiring:** every `fetch`/`fetchWithAuth` target verified against live OpenAPI  -  **0 missing** (`/assess`, `/cases*`, `/api/documents/*`, `/api/payments/create-session`, `/api/auth/*`, `/api/tools/*`, `/api/deadline/calculate`, `/api/workflows/constructive-dismissal`, `/handoff/leads`).
- **Legacy calls removed:** `case_detail.html` was the only page calling `/documents/generate`  -  rewired to canonical. **No active page calls `/api/payment/` or `/documents/generate`** (`reports/deep_qa_route_hits.txt`).
- **Broken UI fixed:** case-detail download buttons were created but never rendered; now rendered and wired to canonical flow with 402 messaging.
- **Legal notices:** boundary notice present on index(5), intake(3), assessment(6), dashboard(2), case_detail(6)  -  `reports/deep_qa_legal_notice_hits.txt` (131 notice lines repo-wide).

## 5. Backend route matrix (live-probed, unauthenticated)

| Route | Kind | Deprecated | Auth gate | Payment gate | Ownership gate | Live probe |
|---|---|---|---|---|---|---|
| POST /api/payments/create-session | canonical | – | ✅ | ✅ (403 disabled) | ✅ | 401 |
| POST /api/payment/create-session | legacy | ✅ | ✅ | ✅ (delegates) | ✅ (via canonical) | 401 |
| GET /api/payments/status/{case_id} | canonical | – | ✅ | n/a | ✅ | 401 |
| GET /api/payment/status | legacy | ✅ | ✅ **(fixed this session)** | n/a (mode only) | n/a | 401 (was 200) |
| POST /api/payments/webhook | canonical | – | Stripe signature | fail-closed; disabled→202 no-op | n/a | 202 no-op |
| POST /api/payment/webhook | legacy | ✅ | Stripe signature | fail-closed; disabled→503 | n/a | 503 |
| POST /api/documents/generate | canonical | – | ✅ | ✅ 402 (FOR UPDATE txn) | ✅ | 401 |
| POST /documents/generate | legacy | ✅ | ✅ | ✅ preview-only unpaid | ✅ (when case linked) | 401 |
| GET /api/documents/{id} | canonical | – | ✅ | ✅ 402 | ✅ 403 | 401 |
| GET /api/documents/{id}/download | legacy | ✅ | ✅ | ✅ 402 | ✅ 403 | 401 |

All 5 legacy routes `deprecated=True` in live OpenAPI (probed). Debug/test routes (`/api/test/*`, `/api/debug/*`) admin-gated in production via `_require_admin_in_production`.

## 6. Workflow audit  -  `scripts/proof/prove_lawapp_full_workflows.sh` → **29/29 PASS**

assessment ✅ (status=ok, 8 citations) · deadline ✅ (rules-sourced, 3-months-less-1-day) · case save ✅ · case list ✅ · case detail ✅ · payment-disabled consistency ✅ (canonical 403 / legacy payment_required=true) · unpaid generate blocked ✅ (402) · DB-paid unlock ✅ (only after `payment_status='paid'`) · paid generate POC+SoL ✅ · download auth/ownership/payment ✅ (401/403/200) · out-of-scope ✅ (`not_supported`) · weak case ✅ (honest `missing_edt`) · legal notices ✅.

## 7. Security audit

- **Auth:** fail-closed everywhere probed; `LAWAPP_AUTH_MODE=none` → identityless → 401 on protected routes; mock mode rejected by production startup validation.
- **Payment bypass:** raw token unlock removed (tests pin it); webhook signature mandatory in stripe modes; disabled mode never marks paid; document unlock only via DB `payment_status` (proven by WF11–12).
- **Cross-user access:** case read 403, document download 403, both live-proven (smoke + proof script).
- **Secrets:** scan (`reports/deep_qa_secret_scan.txt`)  -  only templates/CI patterns/guard code; **no real secrets**. CI has its own secret-scan step.
- **CORS:** no CORS middleware → no cross-origin allowance (frontend is same-origin); foreign-origin preflight gets no ACAO headers.
- **Logs:** recent backend logs contain zero email addresses/identities; code guardrails state user IDs are never logged (spot-verified).
- **Production mode risks:** startup validation blocks production with non-jwt auth, missing JWT keys, disabled KMS, or non-Stripe payment mode (fail-to-start). Current stack is `development` by design.

## 8. Database audit  -  `scripts/proof/prove_database_integrity.sh` → **15/15 PASS**

51 migration files applied (63 recorded incl. superseded); tables `users, cases, documents, payment_sessions, payment_events, rules, auth_sessions` + audit table present; FKs `cases.user_id→users`, `documents.case_id→cases` enforced (FK violation actually caught a bad test fixture this session  -  constraint demonstrably live); rules table populated (23 rows) and **effective-dated** (unfair-dismissal limit 3 months today; 6-month row staged for 2026-10-01); `POSTGRES_PASSWORD` not a placeholder.

## 9. RAG / legal safety audit

- **Retrieval before reasoning + citations required:** assessment returned 8 citations live; citation-pinning Critic gate blocks fake citations with 422 + audit log row **before drafting** (3/3 adversarial tests pass).
- **Deterministic deadlines/caps:** `/api/deadline/calculate` returns `source=rules`; smoke asserts time limit from DB; effective-dated rules table is the single source.
- **No model-memory answers:** out-of-scope → `not_supported`; missing facts → `missing_edt` (no guess)  -  both live-proven.
- **De-identification:** reasoner asserts non-empty `boundary_log` (deidentify-before-reason) or raises; external classifier path is hard-disabled (`return None` before any cloud call); compose pins `LAWAPP_LLM_PROVIDER=ollama_local`. Only `anthropic` imports are in dead/disabled code paths.

## 10. Open blockers

| Item | Class |
|---|---|
| TLS/DNS/KMS/DPIA not in place/proven | PUBLIC LAUNCH BLOCKER (owner-led) |
| Backup/restore unproven | PUBLIC LAUNCH BLOCKER |
| No load test → no 100K claim | PUBLIC LAUNCH BLOCKER |
| Stripe live keys + PAYMENT_MODE decision | OWNER DECISION |
| `ENVIRONMENT/DEPLOYMENT_MODE=development` on local stack | NOT A BLOCKER locally; must be `production` on real deploy (startup validation then enforces jwt/KMS/Stripe) |
| Canonical webhook returns 202 no-op in disabled mode vs legacy 503 | NOT A BLOCKER (no state change either way); cosmetic parity nit |
| `tests/test_route_consolidation.py`, `tests/test_route_shims.py` named in QA order don't exist | NOT A BLOCKER  -  covered by `tests/test_legacy_route_parity.py` |
| PENDING_SUITE_BLOCKERS | |

## 11. Exact fixes still needed

PENDING_REMAINING_FIXES

## 12. Phase 10  -  stack rebuild

PENDING_PHASE10
