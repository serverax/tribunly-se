# Backend Coverage Matrix

Generated: 2026-07-07

## Scope And Counting

- Spec set audited: `docs/02_HLD_ARCHITECTURE.md`, `docs/03_DATABASE_DESIGN.md`, `docs/04_RAG_REASONING_SPEC.md`.
- Allowed statuses: `WIRED`, `STUB`, `BROKEN`, `MISSING`, `ORPHAN`, `FENCED`.
- Every backend route listed below inherits its family status unless called out in the note.
- Surface-family counts in this file: `WIRED=14`, `STUB=1`, `BROKEN=1`, `MISSING=0`, `ORPHAN=7`, `FENCED=1`.

## Live Evidence

| ID | Surface | Request | Response / proof |
| --- | --- | --- | --- |
| `L1` | Health / ops | `GET /health` on isolated live stack | `200 {"status":"ok","db":"connected","auth_mode":"jwt","payment_mode":"disabled"}` |
| `L2` | Intake + de-id boundary | `POST /assess` with unfair-dismissal facts including synthetic PII | `200`, `status=ok`, `claim_type=unfair_dismissal`, `deadline.source=rules`; backend log recorded `fields_stripped=['email','employer_name','claimant_name']` and `pii_fields_in_output=[]` |
| `L3` | Structured retrieval | `GET /rules/unfair_dismissal` | `200` with rules including `unfair_dismissal.time_limit_months`, `qualifying_period`, `compensatory_cap_amount`, `weeks_pay_cap_amount` |
| `L4` | Accounts / workspace | `POST /api/auth/register` -> `POST /api/auth/login` -> `GET /api/auth/me` -> `POST /cases` -> `GET /cases/{id}` -> `DELETE /cases/{id}` | `201`, `200`, `200`, `201`, `200`, `200`; live save/read/delete path works for authenticated users |
| `L5` | Admin dual-layer guard | `GET /admin/cases` unauthenticated and with a non-admin JWT | `403 {"detail":"Admin role required"}` in both cases |
| `L6` | Payment gate | `POST /api/documents/generate` for an unpaid saved case | `402 {"detail":"Payment required to generate documents"}` |
| `L7` | Handoff / referral | `POST /handoff/leads` then `DELETE /handoff/leads/{id}` | `201 {"status":"received", ...}` then `200 {"status":"pii_cleared", ...}` |
| `L8` | Encryption-at-rest weakness | same `POST /handoff/leads` on current live stack | `201` but body returned `"pii_encrypted": false, "encryption_method": "none"`; backend log: `Handoff lead env-key encryption failed - storing plaintext: ENCRYPTION_KEY is malformed: ValueError` |
| `L9` | Upload fence in beta | regression floor test `tests/integration/test_beta_upload_route_fenced.py` | `1 passed`; in beta config `POST /api/uploads/upload` returns `404 {"detail":"Not found"}` |

## Capability Matrix

| Capability | Status | Why | Evidence |
| --- | --- | --- | --- |
| Health / ops | WIRED | Main stack and composed services answered health/readiness probes on the isolated live stack. | `L1` |
| Intake / classification | WIRED | Canonical `/assess` path classifies in-scope unfair-dismissal facts and returns the governed assessment shape. | `L2` |
| Structured retrieval | WIRED | Rules are retrieved from the rules store and surfaced live with effective values. | `L3` |
| Semantic retrieval | WIRED | Live assessment path hit semantic retrieval with BM25 fallback when embeddings were absent; 1024-dim retrieval remains covered by floor tests. | `L2`, `tests/test_rag_1024_retrieval_repair.py`, `tests/test_hybrid_search.py` |
| Reasoning / assessment schema | WIRED | Live `/assess` returned the governed assessment object with citations, weaknesses, scores, and rules-backed deadline. | `L2` |
| Scoring + governance gate | WIRED | Grounding/confidence and honesty gates are exercised on the assessment path and remain green in floor coverage. | `L2`, `tests/test_govern.py`, `tests/test_legal_truth_validator.py` |
| Deadline logic | WIRED | Deadline comes from rules on the live assessment path and the dedicated rules/deadline tests remain green. | `L2`, `L3`, `tests/test_db_backed_legal_values.py` |
| Document generation | WIRED | Canonical document endpoint is live, gated pre-payment, and covered by the paid-journey floor tests for particulars and schedule generation. | `L6`, `tests/e2e/test_backend_paid_journey.py`, `tests/integration/test_canonical_paid_documents.py` |
| Payment | WIRED | Checkout creation, confirm-test, webhook/idempotency, and case unlock remain covered in the floor; unpaid 402 gate still holds live. | `L6`, `tests/test_payment_confirm_test_route.py`, `tests/e2e/test_backend_paid_journey.py` |
| Handoff / referral trigger | WIRED | Lead capture and erasure are reachable live and remain covered by focused integration tests. | `L7`, `tests/integration/test_phase3d_paid_handoff.py` |
| Accounts / workspace | WIRED | Authenticated register/login/me/save/read/delete path worked live; anonymous resume remains blocked by existing Phase 1 guardrail. | `L4`, `tests/test_auth_flows.py`, `tests/test_onboarding.py` |
| Admin dual-layer guard | WIRED | Admin workspace endpoints reject both unauthenticated callers and authenticated non-admin users. | `L5`, `tests/security/test_admin*` |
| De-id boundary | WIRED | Live assessment path proved de-identification fires before reasoning and the boundary log stays clean of outbound PII. | `L2`, `tests/security/test_deidentification.py`, `tests/integration/test_phase2e_audit_log.py` |
| Data protection / encryption at rest | BROKEN | Current live stack has a malformed `ENCRYPTION_KEY`; handoff lead PII fell back to plaintext storage and the encrypted-facts save path logged the same failure mode when raw facts were supplied. | `L8`, backend log excerpt above |
| Canonical uploads beta surface | FENCED | Standalone `/api/uploads/*` is explicitly unreachable in beta config after the new fence landed. | `L9`, `backend/api/upload_routes.py`, `tests/integration/test_beta_upload_route_fenced.py` |

## Route Family Inventory

### `backend/api/admin_workspace_routes.py`

- Status: **WIRED**
- Routes: `GET /admin/cases`, `GET /admin/ai-logs`, `GET /admin/users`, `GET /admin/system-health`, `GET /admin/compliance`
- Proof: `L5`

### `backend/api/auth_routes.py`

- Status: **WIRED**
- Routes: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/magic-link`, `GET /api/auth/providers`, `POST /api/auth/google`, `POST /api/auth/microsoft`, `POST /api/auth/apple`, `POST /api/auth/linkedin`, `POST /api/auth/refresh`, `GET /api/auth/me`, `POST /api/auth/verify-email`, `POST /api/auth/password-reset`
- Proof: `L4`

### `backend/api/document_routes.py`

- Status: **WIRED**
- Routes: `POST /api/documents/generate`, `GET /api/documents/{document_id}`
- Proof: `L6`, `tests/e2e/test_backend_paid_journey.py`

### `backend/api/domain_routes.py`

- Status: **ORPHAN**
- Routes: `GET /api/domains`, `GET /api/domains/{code}`
- Note: real route family, but outside the frozen unfair-dismissal beta contract named in the audited spec set.

### `backend/api/features_routes.py`

- Status: **ORPHAN**
- Routes: `GET /api/features/knowledge/modules`, `GET /api/features/knowledge/modules/{module_key}`, `POST /api/features/document-decode`, `POST /api/features/claim-assessment`, `POST /api/features/matter`, `GET /api/features/matter/{matter_id}/hub`, `POST /api/features/matter/{matter_id}/deadlines`, `POST /api/features/matter/{matter_id}/valuation`, `POST /api/features/matter/{matter_id}/referral`, `POST /api/features/strength`

### `backend/api/feedback_routes.py`

- Status: **ORPHAN**
- Routes: `POST /api/feedback`, `POST /api/feedback/outcome`

### `backend/api/i18n_routes.py`

- Status: **ORPHAN**
- Routes: `GET /api/i18n/locales`, `POST /api/i18n/detect`, `POST /api/i18n/render`, `GET /api/i18n/prompts/{locale}`, `GET /api/i18n/locale`, `POST /api/i18n/locale`

### `backend/api/ingestion_proposal_routes.py`

- Status: **WIRED**
- Routes: `GET /admin/ingestion-proposals`, `POST /admin/ingestion-proposals/{proposal_id}/approve`

### `backend/api/login_gate_routes.py`

- Status: **WIRED**
- Routes: `POST /api/free-tool/teaser`, `POST /api/free-tool/full-result`, `POST /api/free-tool/resume`

### `backend/api/main.py`

- Status: **BROKEN**
- Note: the main app serves the canonical beta surface successfully in most lanes, but the highest-severity live finding in this family is user-data encryption falling back to plaintext when `ENCRYPTION_KEY` is malformed.
- Routes:
  `GET /api/cases`; `GET /`; `GET /pages/{page_name}`; `GET /admin/{page_name}.html`; `POST /auth/register`; `POST /auth/token`; `GET /auth/me`; `GET /health`; `GET /livez`; `GET /freshness`; `GET /rules/{claim_type}`; `POST /assess`; `POST /api/diagnosis`; `POST /documents/generate`; `POST /api/workflow/diagnosis`; `POST /api/workflow/payment/create`; `POST /api/workflow/payment/confirm`; `POST /api/workflow/documents/generate`; `POST /cases`; `POST /onboarding/complete`; `GET /onboarding/status`; `GET /cases`; `GET /cases/{case_id}`; `POST /handoff/leads`; `GET /cases/{case_id}/deadline`; `POST /cases/{case_id}/reminders`; `GET /cases/{case_id}/reminders`; `POST /cases/{case_id}/uploads`; `GET /cases/{case_id}/uploads`; `POST /cases/{case_id}/uploads/{upload_id}/extract`; `PATCH /cases/{case_id}/uploads/{upload_id}/facts`; `POST /cases/{case_id}/uploads/{upload_id}/apply-confirmed`; `POST /cases/{case_id}/bundle/preview`; `POST /cases/{case_id}/bundle/generate`; `GET /cases/{case_id}/bundle`; `POST /funnel/events`; `GET /cases/{case_id}/funnel`; `GET /admin/dp-report`; `GET /admin/rules-verification`; `GET /admin/production-readiness`; `GET /admin/compliance-status`; `GET /cases/{case_id}/timeline`; `POST /cases/{case_id}/timeline/events`; `PATCH /cases/{case_id}/timeline/events/{event_id}`; `GET /cases/{case_id}/escalation`; `DELETE /cases/{case_id}`; `DELETE /handoff/leads/{lead_id}`; `POST /api/brain/trace`; `POST /api/workflows/constructive-dismissal`; `GET /api/agents`; `POST /api/payment/create-session`; `GET /api/payment/status`; `POST /api/test/route-agent`; `POST /api/test/hybrid-search`; `POST /api/test/legal-graph`; `POST /api/kg/entity`; `POST /api/test/evaluate`; `POST /api/test/router`; `POST /api/test/cache`; `POST /api/test/memory/save`; `POST /api/test/memory/get`; `POST /api/test/citation-verify`; `POST /api/test/conflict-detect`; `GET /api/debug/agents`; `GET /api/debug/mcp-tools`; `POST /api/test/mcp-call`; `POST /api/context/compress`; `GET /api/security/cross-user-test`; `GET /admin/retention-status`; `POST /api/router/test`; `POST /api/rag/hybrid-search`; `POST /api/rag/graph`; `POST /api/memory/save`; `POST /api/memory/get`; `POST /api/evaluate`; `GET /api/mcp/tools`; `POST /api/cache/test`; `POST /api/documents/upload`; `POST /api/documents/facts`; `POST /api/test/wasm-deadline`; `POST /api/test/ollama-smoke`; `GET /api/sources/freshness`; `GET /api/rules/{claim_type}`; `POST /api/deadline/calculate`; `POST /api/deadline/calc`; `POST /api/payment/webhook`; `GET /api/documents/{document_id}/download`; `GET /api/cases/{case_id}/documents`
- Proof: `L1`, `L2`, `L4`, `L5`, `L7`, `L8`

### `backend/api/payment_routes.py`

- Status: **WIRED**
- Routes: `POST /api/payments/create-session`, `POST /api/payments/confirm-test`, `POST /api/payments/webhook`, `GET /api/payments/status/{case_id}`
- Proof: `L6`, `tests/e2e/test_backend_paid_journey.py`

### `backend/api/reasoning_routes.py`

- Status: **ORPHAN**
- Routes: `POST /reasoning/route`, `POST /reasoning/stream`

### `backend/api/sovereign_routes.py`

- Status: **ORPHAN**
- Routes: `POST /api/v1/lawapp/ingest`, `POST /api/v1/lawapp/query`

### `backend/api/tools_routes.py`

- Status: **WIRED**
- Routes: `POST /api/tools/claim-checker`, `POST /api/tools/deadline-calculator`, `POST /api/tools/compensation-estimate`, `POST /api/tools/acas-prep`

### `backend/api/upload_routes.py`

- Status: **FENCED**
- Routes: `POST /api/uploads/upload`, `POST /api/uploads/{file_id}/confirm-facts`, `GET /api/uploads/status/{file_id}`
- Note: fenced out of beta by config; new floor test proves `404` in beta config.
- Proof: `L9`

### `backend/chatbot/router.py`

- Status: **ORPHAN**
- Routes: `POST /api/chat/message`, `POST /api/chat/stream`, `GET /api/chat/conversations/{conversation_id}`, `POST /api/chat/conversations/{conversation_id}/save-to-case`, `POST /api/chat/continue-workflow`, `POST /api/chat/missing-facts`, `POST /api/chat/feedback`

## Service Families

### `backend/services/lawapp-admin-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `GET /admin/cases`, `GET /admin/ai-logs`, `GET /admin/users`, `GET /admin/system-health`, `GET /admin/compliance`, `GET /api/admin/dashboard`, `GET /api/admin/ingestion-proposals`, `POST /api/admin/ingestion-proposals/{proposal_id}/approve`, `GET /api/admin/module-coverage`

### `backend/services/lawapp-audit-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `POST /api/audit/log`, `GET /api/audit/trace/{trace_id}`, `GET /api/audit/user/{user_id}`

### `backend/services/lawapp-case-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `GET /api/cases/{case_id}`, `GET /api/cases/{case_id}/timeline`, `POST /api/cases/{case_id}/events`

### `backend/services/lawapp-citation-guard/main.py`

- Status: **ORPHAN**
- Routes: `GET /health`, `GET /ready`, `POST /api/citation/validate`
- Note: on disk but not composed into the current live stack.

### `backend/services/lawapp-graph-rag-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `POST /api/graph/search`, `POST /api/graphrag/traverse`, `GET /api/graphrag/requirements/{claim_type}`, `GET /api/graphrag/remedies/{claim_type}`, `GET /api/graphrag/deadlines/{claim_type}`

### `backend/services/lawapp-notification-service/main.py`

- Status: **STUB**
- Routes: `GET /health`, `GET /ready`, `GET /api/notifications`, `POST /api/notifications/create`, `POST /api/notifications/send-email`, `POST /api/notifications/{notification_id}/read`, `GET /api/notifications/debug/queue-status`, `POST /api/notifications/partner-referral`
- Note: partner-referral remains explicitly stubbed.

### `backend/services/lawapp-rag-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `POST /api/rag/search`

### `backend/services/lawapp-redaction-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `POST /api/redact`, `POST /api/validate_redaction`

### `backend/services/lawapp-rules-service/main.py`

- Status: **WIRED**
- Routes: `GET /health`, `GET /ready`, `GET /api/rules/list`, `GET /api/rules/validate/{domain}`, `GET /api/rules/{domain}/{module}/{rule_key}`
