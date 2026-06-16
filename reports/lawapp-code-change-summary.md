# lawapp  -  Code Change Summary

**Branch:** master  
**Base commit:** 095be01  
**Date:** 2026-06-04  

---

## Files Created

### Backend  -  New Modules
| File | Purpose |
|---|---|
| `backend/core/context_compressor.py` | Brain Step 13  -  deduplicate rules, truncate authorities, preserve citations |
| `backend/core/legal_graph.py` | Brain Step 9  -  Graph RAG query (legal_nodes/edges), RAG source selector |
| `backend/core/mcp_connectors.py` | MCP connector layer  -  5 connectors, deny-by-default, audit-logged |

### Database
| File | Purpose |
|---|---|
| `db/migrations/019_phase1_brain_safety.sql` | safety_boundary_checks + context_compression_log tables; brain_traces new columns |

### Kubernetes Manifests
| File | Purpose |
|---|---|
| `infra/k8s/lawapp-namespaces.yaml` | All 5 approved namespaces |
| `infra/k8s/lawapp-configmaps.yaml` | ConfigMaps for lawapp-api, lawapp-ai, lawapp-rag |
| `infra/k8s/lawapp-secrets-template.yaml` | Secret creation commands (no values) |
| `infra/k8s/lawapp-ai-brain.yaml` | Brain deployment in lawapp-ai namespace |
| `infra/k8s/lawapp-security-policies.yaml` | NetworkPolicies + PDB + ResourceQuota |
| `infra/k8s/lawapp-monitoring.yaml` | Freshness + health CronJobs |

### Tests  -  New Suites
| Directory | Tests | Focus |
|---|---|---|
| `tests/conftest.py` | Root conftest | DB redirect, auth mode, payment mode |
| `tests/brain/test_brain.py` | 43 | 19-step Brain Algorithm |
| `tests/graph_rag/test_graph_rag.py` | 24 | Legal graph traversal, source selection |
| `tests/knowledge_graph/test_knowledge_graph.py` | 21 | legal_nodes/edges schema + paths |
| `tests/memory/test_memory.py` | 9 | Consent-gated memory, user isolation |
| `tests/mcp/test_mcp.py` | 17 | MCP connectors, deny-by-default, audit |
| `tests/uploads/test_uploads.py` | 11 | Document schema, de-id boundary |
| `tests/retrieval/test_retrieval.py` | 18 | Hybrid retrieval, rules, ERA citations |
| `tests/payment/test_payment.py` | 20 | Payment modes, is_paid(), gating |
| `tests/rate_limiting/test_rate_limiting.py` | 7 | slowapi wiring, endpoint limits |
| `tests/documents/test_documents.py` | 10 | Document generation, boundary notice |
| `tests/e2e/lawapp-journey.spec.js` | 17 Playwright | Full product journey |

### Reports + Samples
| File | Purpose |
|---|---|
| `reports/lawapp-new-architecture-technology-status.md` | Technology matrix |
| `reports/lawapp-phase1-to-phase3-readiness-final-audit.md` | Phase 1 audit |
| `reports/lawapp-feature-function-completion-audit.md` | Feature completion audit |
| `reports/lawapp-end-to-end-product-completion-report.md` | Full product report |
| `reports/lawapp-talos-services-deployment-proof.md` | K8s deployment proof |
| `reports/samples/particulars_of_claim_sample.md` | PoC sample output |
| `reports/samples/schedule_of_loss_sample.md` | SoL sample output |
| `reports/samples/letter_before_action_sample.md` | LBA sample output |
| `reports/samples/et1_notes_sample.md` | ET1 notes sample output |

### Scripts
| File | Purpose |
|---|---|
| `scripts/deploy-talos.sh` | One-command Talos cluster deployment |
| `scripts/run-migrations.sh` | Updated  -  namespace iterlaw-ai → lawapp-rag |

### Config
| File | Purpose |
|---|---|
| `playwright.config.js` | Playwright E2E test configuration |
| `package.json` + `package-lock.json` | @playwright/test dependency |

---

## Files Modified

| File | Changes |
|---|---|
| `backend/core/brain.py` | 16→19 steps; lawapp naming (was OrdinoxAI); new fields: missing_facts, rag_sources, safety_passed, memory_saved; safety policy gate; consent-gated memory |
| `backend/core/agents/registry.py` | Added DocumentDraftingAgent (wired to documents.py) |
| `backend/core/deidentify.py` | Added raw_document + 7 more raw upload fields to PII strip list |
| `backend/core/payment.py` | Added test_simulator mode; updated mode list; clear mode descriptions |
| `backend/api/main.py` | Rate limiting (slowapi); POST /api/payment/create-session; GET /api/payment/status; lawapp naming; 19-step docstring; JWT X-User-ID param fix |
| `client/public/pages/intake.html` | ACAS Day A/Day B fields; "not started" checkbox; validation; live deadline preview; warnings/appeal fields; salary converter; outcome wanted; brief description |
| `infra/k8s/lawapp-postgres-sts.yaml` | Fixed: user=lawapp (was lawapp_user); fsGroup dedup removed; namespace → lawapp-api; secret-based credentials |
| `infra/k8s/lawapp-backend.yaml` | Updated envFrom to use lawapp-app-secrets |
| `pyproject.toml` | Added fastembed>=0.4, slowapi>=0.1.9 |
| `Dockerfile` | Already had slowapi; rebuild confirmed with new deps |
| `docker-compose.yml` | Added LAWAPP_AUTH_MODE, JWT_SECRET, JWT_ISSUER, JWT_AUDIENCE, PAYMENT_MODE to backend environment |
| `.env` | LAWAPP_AUTH_MODE=jwt; PAYMENT_MODE=test_simulator; POSTGRES_PORT=5435 (port conflict fix) |
| `db/migrations/018_brain_architecture.sql` | Renamed OrdinoxAI → lawapp in comment |
| `db/migrations/014_legal_corpus_expansion.sql` | Renamed IterLaw → lawapp in comment |
| `tests/brain/test_brain.py` | Updated to 19 steps; new step assertions |
| `tests/conftest.py` | Updated comment; added JWT_SECRET, PAYMENT_MODE defaults |

---

## API Routes Added

| Method | Route | Description |
|---|---|---|
| POST | `/api/payment/create-session` | Create payment session (test simulator or Stripe) |
| GET | `/api/payment/status` | Return current payment mode + Stripe configured flag |

---

## DB Schema Changes (Migration 019)

| Table | Type | Purpose |
|---|---|---|
| `safety_boundary_checks` | NEW | Immutable log of Brain Step 16 safety policy checks |
| `context_compression_log` | NEW | Metrics for Brain Step 13 context compression |
| `brain_traces.missing_facts` | NEW COLUMN | Evidence gaps from Step 7 |
| `brain_traces.rag_sources` | NEW COLUMN | RAG sources selected at Step 9 |
| `brain_traces.safety_passed` | NEW COLUMN | Safety gate result from Step 16 |
| `brain_traces.memory_saved` | NEW COLUMN | Memory consent gate result from Step 17 |

---

## Frontend Changes

| Page | Change |
|---|---|
| `client/public/pages/intake.html` | **Major rewrite**: ACAS Day A/B, validation, live deadline preview, 4 extra fields |

---

## Known Blockers

| Blocker | Fix Required |
|---|---|
| `ANTHROPIC_API_KEY=placeholder`  -  stub AI model | Set real key |
| Kubernetes not deployed | Owner: `bash scripts/deploy-talos.sh` from WSL |
| Stripe real mode not configured | Set STRIPE_SECRET_KEY |
| Find Case Law bulk licence pending | Apply at nationalarchives |
| OCR extraction (Phase 4) | Future sprint |
