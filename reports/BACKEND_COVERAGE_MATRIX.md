# Backend Coverage Matrix

Generated: 2026-07-07

## Method

- Specs used: `docs/02_HLD_ARCHITECTURE.md` (Layers 2-5), `docs/04_RAG_REASONING_SPEC.md`, `docs/03_DATABASE_DESIGN.md`.
- Status meanings: `WIRED` = implemented + tested/reachable, `STUB` = explicit scaffold/fake/placeholder behaviour, `BROKEN` = wrong shape or failing the named contract, `MISSING` = spec claims absent, `ORPHAN` = code exists without a current claim in the named spec set.
- Scope rule for this audit: deprecated aliases, `/api/test/*`, `/api/debug/*`, and side-channel preview surfaces are enumerated below, but they do not automatically count as spec-complete just because code exists.

## Stage 1A Audit Matrix

| Surface | Status | Why | Evidence |
| --- | --- | --- | --- |
| Intake / classification | WIRED | Layer 2 classify->retrieve orchestration is live through `/assess`, `/api/diagnosis`, the PathSplitter, and the classifier. Tests hit both in-scope and out-of-scope routing. | `backend/api/main.py:652`, `backend/core/path_splitter.py:75`, `backend/core/classify.py`, `tests/test_assess_orchestrator.py`, `tests/integration/test_phase3a_flows.py` |
| Structured retrieval | WIRED | Rules-table retrieval is deterministic, effective-dated, and exposed through `/rules/{claim_type}` plus the governed assessment path. | `backend/api/main.py:494`, `backend/core/retrieve.py`, `backend/domains/employment/deadline.py`, `tests/test_db_backed_legal_values.py`, `tests/integration/test_phase3e_mvp_close.py` |
| Semantic retrieval | WIRED | Canonical semantic retrieval uses 1024-dim `corpus_chunks` embeddings with jurisdiction/effective-date filters and keyword fallback when embeddings are unavailable. | `backend/core/retrieve.py:291`, `backend/services/lawapp-rag-service/main.py:120`, `tests/test_rag_1024_retrieval_repair.py`, `tests/test_hybrid_search.py` |
| Reasoning / assessment schema | WIRED | The governed assessment path exposes the canonical `deadline` object required by the RAG spec while retaining `deadline_info` for compatibility. Focused contract proof now locks both `/assess` and `/api/diagnosis` to the rules-backed `deadline` shape. | `docs/04_RAG_REASONING_SPEC.md` §4, `backend/core/pipeline.py`, `backend/api/main.py`, `tests/integration/test_assessment_contract_deadline.py` |
| Scoring + governance gate | WIRED | Grounding/confidence scoring and the honesty gate are implemented as separate layers and exercised by unit/integration tests. | `backend/core/score.py`, `backend/core/govern.py`, `tests/test_govern.py`, `tests/test_legal_truth_validator.py` |
| Deadline logic | WIRED | Deadline calculation is deterministic, rules-backed, and exposed both inside the assessment path and through dedicated endpoints. | `backend/domains/employment/deadline.py`, `backend/api/main.py:1884`, `backend/api/main.py:4414`, `tests/integration/test_phase3e_mvp_close.py`, `tests/test_phase3_outage_copy.py` |
| Document generation | WIRED | The canonical paid route now generates template-backed `particulars` and `schedule_of_loss`, enforces the 402 pre-payment gate, unlocks via the deterministic test-mode payment flow, and keeps a second case locked. Focused route proof and an end-to-end paid-journey regression now cover the surface. | `backend/api/document_routes.py`, `backend/core/documents.py`, `tests/integration/test_canonical_paid_documents.py`, `tests/e2e/test_backend_paid_journey.py` |
| Payment | WIRED | Checkout creation, deterministic test confirmation, webhook signature verification, 402 gating, idempotency, per-case unlock, and `£29.99` config are all present and covered by tests/proof. | `backend/api/payment_routes.py`, `backend/api/document_routes.py:289`, `tests/test_payment_confirm_test_route.py`, `tests/integration/test_phase3_paid_moment_proof.py`, `reports/phase3_paid_moment_proof.json` |
| Handoff / referral trigger | WIRED | Beyond-self-help signaling and lead capture are live on the main path via `recommended_next_step` + `/handoff/leads`. The separate partner-referral scaffold remains non-critical to the minimum spec surface. | `backend/api/main.py:1742`, `backend/core/govern.py`, `tests/integration/test_phase3d_paid_handoff.py`, `tests/integration/test_phase3_paid_moment_proof.py` |
| Accounts / workspace | WIRED | Registration/login, case save/resume, login-gated resume-token reclaim, and deletion endpoints are implemented and tested. Anonymous answer restore remains intentionally blocked outside the authenticated resume path. | `backend/api/main.py:342`, `backend/api/main.py:1329`, `backend/api/main.py:1664`, `backend/api/main.py:3210`, `backend/api/login_gate_routes.py`, `tests/integration/test_phase3e_mvp_close.py`, `tests/test_phase3_outage_copy.py` |
| Admin | WIRED | Admin routes are guarded by auth + admin-role checks in the workspace router, with legacy admin endpoints still protected via the main app's admin gate. | `backend/api/admin_workspace_routes.py`, `backend/api/main.py:115`, `tests/security/test_admin*`, `scripts/proof/prove_lawapp_full_workflows.sh` |
| Data protection | PARKED | HARD STOP: case facts encryption and de-identification boundaries exist, but the standalone uploads router still uses XOR proof-of-concept storage and a no-op malware scan on user documents. Per Work Order 004, this user-data security defect is parked for owner review rather than repaired silently in-lane. | `backend/api/main.py:1358`, `backend/core/encryption.py`, `backend/core/deidentify.py`, `backend/api/upload_routes.py:96`, `backend/api/upload_routes.py:119`, `backend/services/lawapp-redaction-service/main.py`, `tests/legal_accuracy/test_legal_accuracy.py` |
| Health / ops | WIRED | Health/readiness endpoints exist across the monolith and composed services, and bootstrap/migration/test runner paths are present and actively used in the repo's proof floor. | `backend/api/main.py:420`, `docker-compose.yml`, `scripts/docker-init-db.sh`, `docs/qa/LAWAPP_DOCKER_TEST_ENV.md`, `docs/handoff/LAWAPP_CURRENT_STATE.md` |

## Service Inventory

| Service | Status | Spec mapping | Notes | Evidence |
| --- | --- | --- | --- | --- |
| `lawapp-rules-service` | WIRED | Layer 4 structured retrieval / rules API | Composed service with `/health`, `/ready`, single-rule lookup, list, and validation endpoints. | `backend/services/lawapp-rules-service/main.py`, `docker-compose.yml` |
| `lawapp-rag-service` | WIRED | Layer 4 semantic retrieval | Composed service exposing `/api/rag/search` and health endpoints against `corpus_chunks`. | `backend/services/lawapp-rag-service/main.py`, `docker-compose.yml` |
| `lawapp-graph-rag-service` | WIRED | Graph retrieval augmentation | Composed service with traversal/search/remedies/deadlines endpoints and health checks. | `backend/services/lawapp-graph-rag-service/main.py`, `docker-compose.yml` |
| `lawapp-redaction-service` | WIRED | De-identification boundary | Composed service with redact/validate endpoints and health probes. | `backend/services/lawapp-redaction-service/main.py`, `docker-compose.yml` |
| `lawapp-audit-service` | WIRED | Audit / trace persistence | Composed service exposing log + trace + user audit endpoints. | `backend/services/lawapp-audit-service/main.py`, `docker-compose.yml` |
| `lawapp-case-service` | WIRED | Case timeline/detail surface | Composed service exposing case detail and timeline endpoints. | `backend/services/lawapp-case-service/main.py`, `docker-compose.yml` |
| `lawapp-admin-service` | WIRED | Admin dashboards and proposal review | Composed service with dashboard/module-coverage/proposal review and admin views. | `backend/services/lawapp-admin-service/main.py`, `docker-compose.yml` |
| `lawapp-notification-service` | STUB | Notifications / partner referral | Core notification CRUD is implemented, but the partner-referral path is explicitly marked `F12 stub`, so the service is not fully production-complete against the referral surface. | `backend/services/lawapp-notification-service/main.py:488`, `docker-compose.yml` |
| `lawapp-citation-guard` | ORPHAN | Extra service code with no active deployment wiring | HTTP service exists on disk but is not composed in `docker-compose.yml`; the monolith uses internal citation validation instead. | `backend/services/lawapp-citation-guard/main.py`, `docker-compose.yml` |
| `lawapp-ingestion-worker` | ORPHAN | Extra service directory with no HTTP entrypoint | Directory exists but has no `main.py`; the actual compose `ingestion-worker` is built from root and does not use this service directory as a deployable HTTP service. | `backend/services/lawapp-ingestion-worker`, `docker-compose.yml` |

## Route Inventory (every backend API route enumerated)

### `backend/api/admin_workspace_routes.py`

- Family status: **WIRED**
- Note: Primary admin JWT-role workspace surface.
- Route count: 5

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/admin/ai-logs` | `admin_ai_logs` | 0 |
| `GET` | `/admin/cases` | `admin_cases` | 0 |
| `GET` | `/admin/compliance` | `admin_compliance` | 0 |
| `GET` | `/admin/system-health` | `admin_system_health` | 0 |
| `GET` | `/admin/users` | `admin_users` | 0 |

### `backend/api/auth_routes.py`

- Family status: **WIRED**
- Note: Registration/login/session auth surface.
- Route count: 13

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/apple` | `apple` | 0 |
| `POST` | `/google` | `google` | 0 |
| `POST` | `/linkedin` | `linkedin` | 0 |
| `POST` | `/login` | `login` | 0 |
| `POST` | `/logout` | `logout` | 0 |
| `POST` | `/magic-link` | `magic_link` | 0 |
| `GET` | `/me` | `me` | 0 |
| `POST` | `/microsoft` | `microsoft` | 0 |
| `POST` | `/password-reset` | `password_reset` | 0 |
| `GET` | `/providers` | `providers` | 0 |
| `POST` | `/refresh` | `refresh` | 0 |
| `POST` | `/register` | `register` | 0 |
| `POST` | `/verify-email` | `verify_email` | 0 |

### `backend/api/document_routes.py`

- Family status: **BROKEN**
- Note: Canonical paid-doc surface exists but particulars/schedule fall back to generic HTML.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/generate` | `generate_document` | 0 |
| `GET` | `/{document_id}` | `download_document` | 0 |

### `backend/api/domain_routes.py`

- Family status: **ORPHAN**
- Note: Domain-pack discovery surface outside the frozen unfair-dismissal beta contract.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `` | `list_domain_packs_endpoint` | 0 |
| `GET` | `/{code}` | `get_domain_pack_endpoint` | 0 |

### `backend/api/features_routes.py`

- Family status: **ORPHAN**
- Note: Feature-spec layer outside the HLD/RAG/DB minimum contract.
- Route count: 10

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/claim-assessment` | `claim_assessment` | 0 |
| `POST` | `/document-decode` | `document_decode` | 0 |
| `GET` | `/knowledge/modules` | `knowledge_modules` | 0 |
| `GET` | `/knowledge/modules/{module_key}` | `knowledge_module_detail` | 0 |
| `POST` | `/matter` | `create_matter` | 0 |
| `POST` | `/matter/{matter_id}/deadlines` | `save_deadlines` | 0 |
| `GET` | `/matter/{matter_id}/hub` | `matter_hub` | 0 |
| `POST` | `/matter/{matter_id}/referral` | `create_referral` | 0 |
| `POST` | `/matter/{matter_id}/valuation` | `save_valuation` | 0 |
| `POST` | `/strength` | `strength_preview` | 0 |

### `backend/api/feedback_routes.py`

- Family status: **ORPHAN**
- Note: Feedback loop surface; useful, but not claimed in the minimum backend completion spec.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/feedback` | `submit_feedback` | 0 |
| `POST` | `/feedback/outcome` | `submit_outcome_feedback` | 0 |

### `backend/api/i18n_routes.py`

- Family status: **ORPHAN**
- Note: Language/config support surface outside the named minimum spec set.
- Route count: 6

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/detect` | `detect_locale` | 0 |
| `GET` | `/locale` | `get_locale` | 0 |
| `POST` | `/locale` | `set_locale` | 0 |
| `GET` | `/locales` | `list_locales` | 0 |
| `GET` | `/prompts/{locale}` | `get_native_prompts` | 0 |
| `POST` | `/render` | `render_assessment_route` | 0 |

### `backend/api/ingestion_proposal_routes.py`

- Family status: **WIRED**
- Note: Admin proposal review surface tied to ingestion governance.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/ingestion-proposals` | `get_ingestion_proposals` | 0 |
| `POST` | `/ingestion-proposals/{proposal_id}/approve` | `post_approve_ingestion_proposal` | 0 |

### `backend/api/login_gate_routes.py`

- Family status: **WIRED**
- Note: Authenticated resume/login-wall funnel.
- Route count: 3

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/full-result` | `full_result` | 0 |
| `POST` | `/resume` | `resume` | 0 |
| `POST` | `/teaser` | `teaser` | 0 |

### `backend/api/main.py`

- Family status: **MIXED**
- Note: Canonical backend surface plus legacy/deprecated/test/debug paths.
- Route count: 85

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/admin/compliance-status` | `get_compliance_status` | 9 |
| `GET` | `/admin/dp-report` | `get_dp_report` | 13 |
| `GET` | `/admin/production-readiness` | `get_production_readiness` | 55 |
| `GET` | `/admin/retention-status` | `get_retention_status` | 2 |
| `GET` | `/admin/rules-verification` | `get_rules_verification` | 6 |
| `GET` | `/api/agents` | `list_agents` | 0 |
| `POST` | `/api/brain/trace` | `brain_trace` | 1 |
| `POST` | `/api/cache/test` | `api_cache_test` | 0 |
| `GET` | `/api/cases` | `api_cases_auth_gate` | 0 |
| `GET` | `/api/cases/{case_id}/documents` | `api_list_case_documents` | 0 |
| `POST` | `/api/context/compress` | `context_compress` | 0 |
| `POST` | `/api/deadline/calc` | `api_deadline_calc_alias` | 0 |
| `POST` | `/api/deadline/calculate` | `api_deadline_calculate` | 3 |
| `GET` | `/api/debug/agents` | `debug_agents` | 0 |
| `GET` | `/api/debug/mcp-tools` | `debug_mcp_tools` | 0 |
| `POST` | `/api/diagnosis` | `diagnosis_endpoint` | 2 |
| `POST` | `/api/documents/facts` | `api_documents_facts` | 0 |
| `POST` | `/api/documents/upload` | `api_documents_upload` | 0 |
| `GET` | `/api/documents/{document_id}/download` | `api_document_download` | 2 |
| `POST` | `/api/evaluate` | `api_evaluate` | 0 |
| `POST` | `/api/kg/entity` | `kg_entity_lookup` | 0 |
| `GET` | `/api/mcp/tools` | `api_mcp_tools` | 0 |
| `POST` | `/api/memory/get` | `api_memory_get` | 0 |
| `POST` | `/api/memory/save` | `api_memory_save` | 0 |
| `POST` | `/api/payment/create-session` | `create_payment_session` | 6 |
| `GET` | `/api/payment/status` | `get_payment_status` | 4 |
| `POST` | `/api/payment/webhook` | `api_payment_webhook` | 7 |
| `POST` | `/api/rag/graph` | `api_rag_graph` | 0 |
| `POST` | `/api/rag/hybrid-search` | `api_rag_hybrid_search` | 0 |
| `POST` | `/api/router/test` | `api_router_test` | 0 |
| `GET` | `/api/rules/{claim_type}` | `api_get_rules` | 0 |
| `GET` | `/api/security/cross-user-test` | `security_cross_user_test` | 0 |
| `GET` | `/api/sources/freshness` | `api_sources_freshness` | 0 |
| `POST` | `/api/test/cache` | `test_cache` | 0 |
| `POST` | `/api/test/citation-verify` | `test_citation_verify` | 0 |
| `POST` | `/api/test/conflict-detect` | `test_conflict_detect` | 0 |
| `POST` | `/api/test/evaluate` | `test_evaluate` | 0 |
| `POST` | `/api/test/hybrid-search` | `test_hybrid_search` | 0 |
| `POST` | `/api/test/legal-graph` | `test_legal_graph` | 0 |
| `POST` | `/api/test/mcp-call` | `test_mcp_call` | 0 |
| `POST` | `/api/test/memory/get` | `memory_get` | 0 |
| `POST` | `/api/test/memory/save` | `memory_save` | 0 |
| `POST` | `/api/test/ollama-smoke` | `test_ollama_smoke` | 0 |
| `POST` | `/api/test/route-agent` | `test_route_agent` | 0 |
| `POST` | `/api/test/router` | `test_router` | 0 |
| `POST` | `/api/test/wasm-deadline` | `test_wasm_deadline` | 0 |
| `POST` | `/api/workflow/diagnosis` | `workflow_diagnosis` | 4 |
| `POST` | `/api/workflow/documents/generate` | `workflow_documents_generate` | 0 |
| `POST` | `/api/workflow/payment/confirm` | `workflow_payment_confirm` | 0 |
| `POST` | `/api/workflow/payment/create` | `workflow_payment_create` | 0 |
| `POST` | `/api/workflows/constructive-dismissal` | `api_constructive_dismissal` | 0 |
| `POST` | `/assess` | `assess_endpoint` | 29 |
| `GET` | `/auth/me` | `get_me` | 4 |
| `POST` | `/auth/register` | `register` | 10 |
| `POST` | `/auth/token` | `login_for_token` | 6 |
| `GET` | `/cases` | `list_cases` | 32 |
| `POST` | `/cases` | `save_case` | 32 |
| `DELETE` | `/cases/{case_id}` | `delete_case` | 23 |
| `GET` | `/cases/{case_id}` | `get_case` | 23 |
| `GET` | `/cases/{case_id}/bundle` | `get_bundle_status` | 3 |
| `POST` | `/cases/{case_id}/bundle/generate` | `generate_bundle` | 13 |
| `POST` | `/cases/{case_id}/bundle/preview` | `preview_bundle` | 3 |
| `GET` | `/cases/{case_id}/deadline` | `get_case_deadline` | 3 |
| `GET` | `/cases/{case_id}/escalation` | `get_escalation` | 6 |
| `GET` | `/cases/{case_id}/funnel` | `list_funnel_events` | 3 |
| `GET` | `/cases/{case_id}/reminders` | `list_reminders` | 6 |
| `POST` | `/cases/{case_id}/reminders` | `create_reminder` | 6 |
| `GET` | `/cases/{case_id}/timeline` | `get_timeline` | 13 |
| `POST` | `/cases/{case_id}/timeline/events` | `create_timeline_event` | 2 |
| `PATCH` | `/cases/{case_id}/timeline/events/{event_id}` | `update_timeline_event` | 1 |
| `GET` | `/cases/{case_id}/uploads` | `list_uploads` | 13 |
| `POST` | `/cases/{case_id}/uploads` | `upload_document` | 13 |
| `POST` | `/cases/{case_id}/uploads/{upload_id}/apply-confirmed` | `apply_confirmed_facts` | 2 |
| `POST` | `/cases/{case_id}/uploads/{upload_id}/extract` | `extract_document` | 17 |
| `PATCH` | `/cases/{case_id}/uploads/{upload_id}/facts` | `update_extracted_facts` | 8 |
| `POST` | `/documents/generate` | `generate_document` | 57 |
| `GET` | `/freshness` | `freshness` | 0 |
| `POST` | `/funnel/events` | `record_funnel_event` | 6 |
| `POST` | `/handoff/leads` | `capture_handoff_lead` | 17 |
| `DELETE` | `/handoff/leads/{lead_id}` | `delete_handoff_lead` | 1 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/livez` | `livez` | 0 |
| `POST` | `/onboarding/complete` | `complete_onboarding` | 13 |
| `GET` | `/onboarding/status` | `onboarding_status` | 4 |
| `GET` | `/rules/{claim_type}` | `get_rules` | 0 |

### `backend/api/payment_routes.py`

- Family status: **WIRED**
- Note: Canonical payment surface.
- Route count: 4

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/confirm-test` | `confirm_test_payment` | 0 |
| `POST` | `/create-session` | `create_payment_session` | 0 |
| `GET` | `/status/{case_id}` | `get_payment_status` | 0 |
| `POST` | `/webhook` | `stripe_webhook` | 0 |

### `backend/api/reasoning_routes.py`

- Family status: **ORPHAN**
- Note: Alternate reasoning preview surface; not part of the governed canonical assessment contract.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/reasoning/route` | `reasoning_route` | 2 |
| `POST` | `/reasoning/stream` | `reasoning_stream` | 4 |

### `backend/api/sovereign_routes.py`

- Family status: **ORPHAN**
- Note: Experimental sovereign pipeline not claimed by the current HLD/RAG release line.
- Route count: 2

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/v1/lawapp/ingest` | `ingest` | 1 |
| `POST` | `/api/v1/lawapp/query` | `query` | 2 |

### `backend/api/tools_routes.py`

- Family status: **WIRED**
- Note: Public deterministic preview tools.
- Route count: 4

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/acas-prep` | `acas_prep` | 0 |
| `POST` | `/claim-checker` | `claim_checker` | 0 |
| `POST` | `/compensation-estimate` | `compensation_estimate` | 0 |
| `POST` | `/deadline-calculator` | `deadline_calculator` | 0 |

### `backend/api/upload_routes.py`

- Family status: **BROKEN**
- Note: Standalone upload router uses XOR proof-of-concept encryption and TODO malware scan.
- Route count: 3

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/status/{file_id}` | `get_upload_status` | 0 |
| `POST` | `/upload` | `upload_document` | 0 |
| `POST` | `/{file_id}/confirm-facts` | `confirm_upload_facts` | 0 |

### `backend/services/lawapp-admin-service/main.py`

- Family status: **WIRED**
- Note: Admin service.
- Route count: 11

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/admin/ai-logs` | `admin_list_ai_logs` | 0 |
| `GET` | `/admin/cases` | `admin_list_cases` | 0 |
| `GET` | `/admin/compliance` | `admin_compliance` | 0 |
| `GET` | `/admin/system-health` | `admin_system_health` | 0 |
| `GET` | `/admin/users` | `admin_list_users` | 0 |
| `GET` | `/api/admin/dashboard` | `get_admin_dashboard` | 0 |
| `GET` | `/api/admin/ingestion-proposals` | `admin_list_ingestion_proposals` | 0 |
| `POST` | `/api/admin/ingestion-proposals/{proposal_id}/approve` | `admin_approve_ingestion_proposal` | 0 |
| `GET` | `/api/admin/module-coverage` | `get_module_coverage` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

### `backend/services/lawapp-audit-service/main.py`

- Family status: **WIRED**
- Note: Audit service.
- Route count: 5

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/audit/log` | `log_audit` | 0 |
| `GET` | `/api/audit/trace/{trace_id}` | `get_audit_trace` | 0 |
| `GET` | `/api/audit/user/{user_id}` | `get_user_audit` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `readiness` | 3 |

### `backend/services/lawapp-case-service/main.py`

- Family status: **WIRED**
- Note: Case service.
- Route count: 5

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/api/cases/{case_id}` | `get_case_detail` | 0 |
| `POST` | `/api/cases/{case_id}/events` | `create_case_event` | 0 |
| `GET` | `/api/cases/{case_id}/timeline` | `get_case_timeline` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

### `backend/services/lawapp-citation-guard/main.py`

- Family status: **ORPHAN**
- Note: Uncomposed auxiliary service.
- Route count: 3

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/citation/validate` | `validate_answer` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

### `backend/services/lawapp-graph-rag-service/main.py`

- Family status: **WIRED**
- Note: Graph retrieval service.
- Route count: 7

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/graph/search` | `graph_search` | 0 |
| `GET` | `/api/graphrag/deadlines/{claim_type}` | `get_deadlines` | 0 |
| `GET` | `/api/graphrag/remedies/{claim_type}` | `get_remedies` | 0 |
| `GET` | `/api/graphrag/requirements/{claim_type}` | `get_requirements` | 0 |
| `POST` | `/api/graphrag/traverse` | `graphrag_traverse` | 0 |
| `GET` | `/health` | `health_check` | 33 |
| `GET` | `/ready` | `readiness_check` | 3 |

### `backend/services/lawapp-notification-service/main.py`

- Family status: **STUB**
- Note: Notification service with explicit referral stub.
- Route count: 8

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/api/notifications` | `list_notifications` | 0 |
| `POST` | `/api/notifications/create` | `create_notification` | 0 |
| `GET` | `/api/notifications/debug/queue-status` | `check_queue_status` | 0 |
| `POST` | `/api/notifications/partner-referral` | `notify_partner_referral` | 0 |
| `POST` | `/api/notifications/send-email` | `send_email_notification` | 0 |
| `POST` | `/api/notifications/{notification_id}/read` | `mark_notification_read` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

### `backend/services/lawapp-rag-service/main.py`

- Family status: **WIRED**
- Note: Semantic retrieval service.
- Route count: 3

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/rag/search` | `hybrid_search` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

### `backend/services/lawapp-redaction-service/main.py`

- Family status: **WIRED**
- Note: Redaction service.
- Route count: 4

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `POST` | `/api/redact` | `redact` | 0 |
| `POST` | `/api/validate_redaction` | `validate_redaction` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `readiness` | 3 |

### `backend/services/lawapp-rules-service/main.py`

- Family status: **WIRED**
- Note: Structured retrieval service.
- Route count: 5

| Method | Path | Handler | Test refs |
| --- | --- | --- | ---: |
| `GET` | `/api/rules/list` | `list_rules` | 0 |
| `GET` | `/api/rules/validate/{domain}` | `validate_rules` | 0 |
| `GET` | `/api/rules/{domain}/{module}/{rule_key}` | `get_rule` | 0 |
| `GET` | `/health` | `health` | 33 |
| `GET` | `/ready` | `ready` | 3 |

## Immediate Stage 1B Candidates From This Audit

1. `BROKEN`: canonical `/api/documents/generate` does not produce the template-anchored unfair-dismissal drafts for `particulars` or `schedule_of_loss`; it falls through to `_generate_generic_document(...)`.
2. `BROKEN`: assessment response shape is not yet spec-clean against `04_RAG_REASONING_SPEC.md` because the live contract centers `deadline_info` rather than the canonical `deadline` object.
3. `PARKED`: standalone `/api/uploads/*` uses XOR proof-of-concept encryption and a TODO malware scan, below the database/HLD data-protection bar; this is a hard-stop user-data security item under Work Order 004.
4. `STUB`: notification partner-referral path is explicitly marked stub.
5. `ORPHAN`: citation-guard microservice and `backend/services/lawapp-ingestion-worker` should be kept or deleted by deliberate owner decision; they should not silently drift.

## ORPHAN Recommendations (list only, no action taken)

| Item | Recommendation | Reason |
| --- | --- | --- |
| `backend/services/lawapp-citation-guard` | Keep only if the team plans a standalone citation-validation deployment; otherwise delete after confirming internal validator remains the only path. | On-disk service, no compose/runtime wiring. |
| `backend/services/lawapp-ingestion-worker` | Delete or fold into the root `ingestion-worker` compose path after owner review. | Duplicate concept, no HTTP entrypoint, not the deployed worker path. |
| `/api/test/*` and `/api/debug/*` families in `backend/api/main.py` | Keep short-term for local diagnostics, then fence behind explicit non-beta config or remove. | Enumerated code surface with no direct HLD claim. |
| `backend/api/sovereign_routes.py` | Keep only if the sovereign pipeline is an intentional future track; otherwise archive. | Experimental surface outside the frozen unfair-dismissal beta contract. |
| `backend/api/features_routes.py` | Keep if the Feature Spec layer is still an active roadmap track; otherwise isolate from beta completion work. | Real code, but not part of the named HLD/RAG/DB minimum contract. |
