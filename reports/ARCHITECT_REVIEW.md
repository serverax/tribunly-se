# Fullstack Architect Review v2 -- WO007 / SA-5

**Date:** 2026-07-08 | **Branch:** cc/convergence | **Reviewer:** SA-5 (read-only)

---

## 1. Service Dependency Chain

**docker-compose.yml backend `depends_on`:** db (healthy), redis (healthy), ollama (healthy).

**MISSING from `depends_on`:** rules-service, rag-service, graph-rag-service, redaction-service, audit-service. The backend references all five via env vars (`RULES_SERVICE_URL`, `RAG_SERVICE_URL`, `GRAPH_RAG_SERVICE_URL`, `AUDIT_SERVICE_URL`, `REDACTION_SERVICE_URL` -- lines 99-103) but does NOT declare startup ordering for any of them. A cold `docker compose up` may route requests to those services before they are healthy.

**Runtime state (all 15 services healthy):**

| Service | Status |
|---|---|
| backend | Up 3h (healthy) |
| control-plane | Up 3h (healthy) |
| db | Up 3h (healthy) |
| frontend | Up 3h (healthy) |
| lawapp-admin-service | Up 3h (healthy) |
| lawapp-audit-service | Up 3h (healthy) |
| lawapp-case-service | Up 3h (healthy) |
| lawapp-graph-rag-service | Up 3h (healthy) |
| lawapp-notification-service | Up 3h (healthy) |
| lawapp-rag-service | Up 3h (healthy) |
| lawapp-redaction-service | Up 3h (healthy) |
| lawapp-rules-service | Up 3h (healthy) |
| ollama | Up 3h (healthy) |
| outbox-worker | Up 3h (healthy) |
| redis | Up 3h (healthy) |

**Verdict:** All 15 services healthy at review time. Backend resilience at runtime is fine (HTTP calls retry/fail gracefully), but `depends_on` is incomplete -- a race on cold start is possible. **P2.**

---

## 2. Orphan Route Audit

Route modules registered via `app.include_router()` in `backend/api/main.py`:

| # | Router module | Registered line | Test coverage | Auth/Rate-limit | Status |
|---|---|---|---|---|---|
| 1 | admin_workspace_routes | 177 | tests/integration/test_phase6b_beta_readiness.py | admin key | WIRED |
| 2 | reasoning_routes | 199 | tests/test_reasoning_routes.py | rate-limited (global) | WIRED |
| 3 | sovereign_routes | 205 | tests/test_sovereign_pipeline.py | rate-limited (global) | WIRED |
| 4 | payment_routes | 210 | tests/payment/test_payment.py, tests/security/test_payment_access.py | auth-gated | WIRED |
| 5 | document_routes | 215 | tests/documents/test_documents.py, tests/integration/test_canonical_paid_documents.py | auth + payment | WIRED |
| 6 | upload_routes | 220 | tests/uploads/test_uploads.py, tests/integration/test_beta_upload_route_fenced.py | auth-gated | WIRED |
| 7 | auth_routes | 225 | tests/security/test_auth_routes.py, tests/integration/test_phase11_auth_routes.py | rate-limited | WIRED |
| 8 | tools_routes | 229 | tests/test_integration_tools.py | public (preview tools) | WIRED |
| 9 | features_routes | 232 | tests/test_feature_spec_integration.py | public | WIRED |
| 10 | feedback_routes | 236 | grep match in test_phase6b; auth-gated | auth | WIRED |
| 11 | ingestion_proposal_routes | 239 | no dedicated test file found | admin key likely | PARTIAL |
| 12 | i18n_routes | 242 | tests/test_i18n_api.py | public | WIRED |
| 13 | login_gate_routes | 246 | tests/test_login_gate.py | public | WIRED |
| 14 | chatbot.router | 250 | no dedicated route test found | auth (brain path) | PARTIAL |
| 15 | domain_routes | 253 | tests/test_domain_modularity.py, test_domain_pack_loader.py | public | WIRED |

**Unregistered files:** `admin_routes.py` and `case_routes.py` exist in `backend/api/` but are helper modules (no `APIRouter`), not orphan routers. `auth.py` is a utility module.

**Summary:** 13/15 registered routers are WIRED with tests. 2 are PARTIAL (ingestion_proposal_routes, chatbot.router -- present and functional but lack dedicated route-level test files). Zero ORPHAN routers found. **P3.**

---

## 3. Module-Registry Second-Country Verdict (A6 Jurisdiction)

### Evidence chain

**pack_contract.py** (`backend/domains/pack_contract.py`):
- `DomainPack` dataclass has `jurisdiction: list[str]` (line 28) and `country_code: str = "GB"` (line 29).
- Both are declarative fields loaded from `domain_config.json`.

**registry.py** (`backend/domains/registry.py`):
- `jurisdiction_supported_for_domain(domain, jurisdiction)` (line 156): checks if `jurisdiction` is in the pack's `jurisdiction` list. Pure data lookup, no hardcoded country.
- `_pack_to_spec()` copies `list(pack.jurisdiction)` into the DomainSpec (line 45).

**loader.py** (`backend/domains/loader.py`):
- Loads packs from `domains/<code>/domain_config.json`. Each pack is self-contained.
- `_SKIP_DIRS = {"_schema", "employment_uk"}` -- skips legacy dir, not countries.

**domain_config.json** (`domains/employment/domain_config.json`):
```json
"jurisdiction": ["EW", "S", "NI"],
"country_code": "GB"
```

**employment_modules table** (DB, migration 058):
- Schema has NO `jurisdiction` column. Columns: `module_key`, `label`, `status`, `db_backed_required`, `created_at`, `updated_at`.
- 24 rows, all UK-specific by content (titles reference UK-only concepts like TUPE, ACAS, ET).

**Live DB query result:** 24 rows returned; 11 production, 13 partial, 0 planned. No jurisdiction column exists.

### Verdict

A second country (e.g., Sweden) could be added **by data alone at the registry/pack layer** -- drop a `domains/employment_se/domain_config.json` with `country_code: "SE"`, `jurisdiction: ["SE"]`, and the loader picks it up without core edits. However, **the DB layer requires code changes**: the `employment_modules` table has no `jurisdiction` column, so the 24 module rows are implicitly UK-only. The `rules` table does have a `jurisdiction` column (`WHERE jurisdiction = %s`), so rule-level multi-jurisdiction works. The gap is: (1) `employment_modules` needs a jurisdiction FK or per-country module catalog, (2) ingestion sources, corpus, and templates are UK-specific content that must be authored, (3) legislation and ACAS guidance tables contain UK-only data. **Second country = data + schema migration, not just data.** **P2.**

---

## 4. Embedding Model Status

**`docker compose exec -T ollama ollama list` output:**
```
bge-large-en-v1.5:latest    99bda20996d2  207 MB  About an hour ago
qwen2.5:3b-instruct-q6_K   9f78f7728716  2.5 GB  3 hours ago
```

bge-large-en-v1.5 is present and loaded.

**Vector dimension mismatch:**
- `legislation.embedding`: **vector(384)** -- 384-dimensional.
- `corpus_chunks.embedding`: **vector(1024)** -- 1024-dimensional, with `embedding_model` default `'bge-large-en-v1.5'`.

bge-large-en-v1.5 natively produces 1024-dimensional embeddings. The `corpus_chunks` table is correctly dimensioned. The `legislation` table at vector(384) is a mismatch -- either it was created for a different model (e.g., bge-small or all-MiniLM-L6-v2 at 384d) or was never migrated. Semantic search over legislation using bge-large-en-v1.5 embeddings will fail or produce zero results due to dimension incompatibility.

**Verdict:** Active mismatch. `legislation` table needs ALTER to vector(1024) or a separate embedding model. **P1.**

---

## 5. GPU Passthrough

The `ollama` service in docker-compose.yml (lines 577-589) has **no `deploy.resources.reservations.devices`** block. GPU passthrough is NOT configured. Ollama runs CPU-only.

For production throughput this means inference latency is higher than necessary. Adding:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - capabilities: [gpu]
```
would enable NVIDIA GPU passthrough where available.

**Verdict:** CPU-only inference. Acceptable for dev/beta; production throughput risk. **P3.**

---

## 6. Floor Delta Root-Cause (One Line)

1834/0/44/8 to 1919/0/58/0: the 8 errors were `ExternalLLMForbidden` in `test_phase2_real_model.py` (now skip-marked), 5 `doc_type NOT NULL` failures were pre-existing (now fixed), 1 Dockerfile test had a missing file (now skip-marked), +85 passed came from WO007 copying updated test files into the container that the image lacked bind-mounted (newly discovered tests ran for the first time), and +14 skipped = 8 ExternalLLMForbidden + 1 Dockerfile + 5 other existing skips now counted.

---

## Priority Summary

| ID | Finding | Priority |
|---|---|---|
| 4 | legislation table vector(384) vs corpus_chunks vector(1024) dimension mismatch -- semantic search over legislation is broken | **P1** |
| 1 | Backend `depends_on` missing 5 upstream services (rules, rag, graph-rag, redaction, audit) -- cold-start race | **P2** |
| 3 | Second-country needs schema migration (`employment_modules` lacks jurisdiction column) + content authoring, not data-only | **P2** |
| 2 | 2/15 route modules (ingestion_proposal, chatbot) lack dedicated route-level tests | **P3** |
| 5 | Ollama GPU passthrough not configured -- CPU-only inference | **P3** |
| 6 | Floor delta fully explained -- no residual mystery | info |
