# lawapp Real Staging Readiness Completion Report

**Date:** 2026-06-04  
**Commit:** eb31849 + uncommitted session changes  
**Branch:** master  

---

## 1. Final Classification

**LOCAL DEMO READY: YES**  
**STAGING READY: NO**  -  Real AI key, Kubernetes deployment, and production secrets not yet applied  
**PRODUCTION READY: NO**

---

## 2. Clean Docker Proof

```bash
docker compose down -v && docker compose up -d --build

# Containers after clean start:
lawapp-backend-1  Up (healthy)  0.0.0.0:8000->8000/tcp
lawapp-db-1       Up (healthy)  0.0.0.0:5435->5432/tcp
lawapp-redis-1    Up (healthy)  0.0.0.0:6379->6379/tcp

# DB after fresh start (migration 020_seed_rules.sql auto-runs):
SELECT COUNT(*) FROM rules → 19 ✓ (automatic, no manual seed needed)
SELECT COUNT(*) FROM legislation → 80 ✓ (after running ingestion)
SELECT COUNT(*) FROM acas_guidance → 12 ✓ (after running ingestion)
SELECT COUNT(*) FROM case_law_chunks → 0 (FCL licence required)
SELECT COUNT(*) FROM legal_nodes → 15 ✓
SELECT COUNT(*) FROM legal_edges → 14 ✓
SELECT COUNT(*) FROM payment_events → 0 (table exists, used for webhook idempotency)
SELECT extname FROM pg_extension → pgcrypto, plpgsql, vector ✓

# Stripe SDK installed:
docker compose exec backend python -c "import stripe; print(stripe._version.VERSION)" → 15.2.0 ✓

# Redis active:
docker compose exec redis redis-cli ping → PONG ✓
docker compose exec backend printenv RATELIMIT_STORAGE_URI → redis://redis:6379 ✓
```

---

## 3. Test Proof

### Python tests
```bash
python -m pytest -q
→ 446 passed, 3 skipped, 0 failed in 231.89s

Skipped tests (all expected):
  - test_bundle_has_authorities: skip when legislation=0 (skip message included)
  - test_legislation_has_rows: skip when legislation=0 (skip message included)
  - 1 encryption skip when ENCRYPTION_KEY=placeholder
```

### Smoke journey
```bash
bash scripts/smoke_local_journey.sh
→ 24 PASS / 0 FAIL
```

### Playwright
```bash
node_modules/.bin/playwright test
→ 17 passed
```

### Security regression
```bash
bash scripts/security-regression.sh
→ 9 PASS / 0 FAIL / 0 WARN
  - No real API keys committed ✓
  - No reserved legal language ✓
  - No hardcoded legal values in frontend ✓
  - PII stripping verified ✓
  - deidentify before model.reason ✓
  - Payment gating correct ✓
  - Auth mode: jwt ✓
  - User isolation: HTTP 403 ✓
  - Security tests pass ✓
```

### push-and-deploy dry run
```bash
bash scripts/push-and-deploy.sh --dry-run
→ Tests run + dry run complete
```

---

## 4. DB Proof

| Table | Row Count | Status |
|---|---|---|
| rules | 19 | DONE  -  auto-seeded via migration 020 |
| legislation | 80 | DONE  -  run: `docker compose run --rm ingestion python -m ingestion.legislation.ingest` |
| acas_guidance | 12 | DONE  -  run: `docker compose run --rm ingestion python -m ingestion.acas.ingest` |
| case_law_chunks | 0 | BLOCKED_EXTERNAL_LICENCE  -  FCL bulk licence required |
| legal_nodes | 15 | DONE  -  seeded in migration 018 |
| legal_edges | 14 | DONE  -  seeded in migration 018 |
| payment_events | 0 | DONE  -  table exists, webhook idempotency ready |
| cases | varies | DONE |
| users | varies | DONE |
| documents | varies | DONE |

**Embeddings (after ingestion + embedding run):**
```
legislation: 80 embedded ✓
acas_guidance: 12 embedded ✓
case_law_chunks: 0 (FCL blocked)
```

**Source freshness:**
```bash
curl http://localhost:8000/freshness
→ Returns verification dates for legislation, acas_guidance, rules
```

---

## 5. Backend Route Matrix

| Route | Status | Auth | Ownership | Notes |
|---|---|---|---|---|
| GET /health | DONE (200) | none | n/a | Reports auth_mode, payment_mode, ai_provider |
| POST /auth/register | DONE (201) | none | n/a | bcrypt hash |
| POST /auth/token | DONE (200) | none | n/a | JWT issued |
| GET /auth/me | DONE (200) | JWT | self | |
| POST /assess | DONE | none | n/a | Stub model → insufficient_grounding for complex; deterministic for QP-fail |
| POST /cases | DONE | JWT | creates own | |
| GET /cases | DONE | JWT | own only | |
| GET /cases/{id} | DONE | JWT | enforced (403) | |
| GET /api/cases/{id}/documents | DONE | JWT | enforced | |
| POST /documents/generate | DONE | JWT+payment | enforced | 9620 chars |
| GET /api/documents/{id}/download | DONE | JWT | enforced | |
| GET /rules/{claim_type} | DONE | none | n/a | 9 rules returned |
| GET /api/rules/{claim_type} | DONE | none | n/a | alias |
| POST /api/deadline/calculate | DONE | none | n/a | source=rules |
| GET /freshness | DONE | none | n/a | |
| GET /api/sources/freshness | DONE | none | n/a | alias |
| POST /api/payment/create-session | DONE | optional JWT | n/a | test_simulator |
| POST /api/payment/webhook | DONE | Stripe-Sig | n/a | sig verification + DB write |
| GET /api/payment/status | DONE | none | n/a | |
| POST /api/brain/trace | DONE | optional JWT | n/a | 19 steps |
| POST /api/rag/hybrid-search | DONE | none | n/a | rules_found=8, citations from ERA 1996 |
| POST /handoff/leads | DONE | optional JWT | n/a | |
| POST /cases/{id}/uploads/{id}/extract | DONE (501) | JWT | enforced | Not Implemented  -  Phase 4 |

---

## 6. Frontend Wiring Matrix

| Page | Backend endpoints | ACAS fields | OCR notice | Legal notice | Status |
|---|---|---|---|---|---|
| / (Landing) | none | n/a | n/a | ✓ | DONE |
| register.html | /auth/register, /auth/token | n/a | n/a | ✓ | DONE |
| login.html | /auth/token | n/a | n/a | ✓ | DONE |
| intake.html | /assess, /rules/ | ✓ Day A/B | n/a | ✓ | DONE |
| assessment.html | /cases, /documents/generate, /handoff/leads | n/a | n/a | ✓ | DONE |
| dashboard.html | /auth/me, /cases | n/a | n/a | ✓ | DONE |
| saved_case.html | /cases/{id}, /documents/generate | n/a | ✓ Phase 4 banner | ✓ | DONE |
| success.html | none | n/a | n/a | ✓ | DONE |
| cancel.html | none | n/a | n/a | ✓ | DONE |

---

## 7. Security Matrix

| Control | Status | Evidence |
|---|---|---|
| JWT auth (HS256 + iss + aud) | DONE | printenv LAWAPP_AUTH_MODE=jwt |
| Cross-user 403 | DONE | smoke step 10, security regression |
| PII stripping | DONE | deidentify() before model.reason() |
| Reserved activity blocked | DONE | brain.py safety policy gate |
| Rate limiting  -  Redis | DONE | RATELIMIT_STORAGE_URI=redis://redis:6379, Redis running |
| Stripe webhook sig verify | DONE | verify_webhook_signature() with stripe SDK |
| Stripe webhook fail-closed | DONE | 503 if STRIPE_WEBHOOK_SECRET not configured |
| OCR  -  raw doc not sent to AI | DONE | raw_document in _PII_FIELDS |
| Payment idempotency | DONE | payment_events UNIQUE on stripe_event_id |
| No secrets committed | DONE | security regression scan passes |

---

## 8. AI/RAG/New Technology Matrix

| Technology | Code | DB | Route | Runtime | Status |
|---|---|---|---|---|---|
| Agentic AI (19-step brain) | ✓ | brain_traces | /api/brain/trace | 19 steps proven | DONE |
| Hybrid Search | ✓ | retrieval_audit | /api/rag/hybrid-search | rules_found=8, citations=ERA 1996 s.94/s.98 | DONE |
| Graph RAG | ✓ | legal_nodes/edges | /api/rag/graph | 15 nodes traversed | DONE |
| Knowledge Graph | ✓ | legal_nodes/edges | internal | Proven | DONE |
| Context Compression | ✓ | context_compression_log | Brain step 13 | Proven | DONE |
| Memory Engine | ✓ | legal_memory | /api/memory/save | Consent-gated | DONE |
| Evaluation AI | ✓ | evaluation_results | /api/evaluate | 8-check rubric | DONE |
| MCP Connectors | ✓ | mcp_tool_calls | /api/mcp/tools | 5 connectors, deny-by-default | DONE |
| Multimodal AI/OCR | Route→501 | documents | /cases/.../extract→501 | Phase 4 not implemented; clear notice in UI | STUB→501 |
| AI Router | ✓ | routing_decisions | Brain step 9 | Proven | DONE |
| Semantic Cache | ✓ | semantic_cache | /api/cache/test | PII excluded | DONE |
| WASM/JS fallback | ✓ binary | wasm_calculations | /rules/ feeds JS | JS fallback active; rebuild script created | PARTIAL |
| Real AI (Anthropic) | BLOCKED | n/a | /health shows active=false | StubReasoningModel | BLOCKED_OWNER_ACTION |

---

## 9. Payment Matrix

| Aspect | Status |
|---|---|
| test_simulator mode | DONE  -  test_ prefix required |
| No token → preview | DONE |
| Webhook endpoint | DONE |
| Webhook sig verification | DONE  -  stripe.Webhook.construct_event() |
| Webhook fails without secret | DONE  -  503 if STRIPE_WEBHOOK_SECRET absent |
| Payment events DB write | DONE  -  migration 021, idempotent |
| Real Stripe keys | BLOCKED_OWNER_ACTION |

---

## 10. OCR/Multimodal Matrix

| Aspect | Status |
|---|---|
| Upload route | DONE |
| Ownership enforced | DONE |
| Raw upload not sent to AI | DONE  -  raw_document in _PII_FIELDS |
| OCR extraction | STUB → 501 Not Implemented |
| UI notice | DONE  -  "Phase 4 not enabled" banner |
| Real OCR engine | NOT IMPLEMENTED (Phase 4) |

---

## 11. WASM Matrix

| Aspect | Status |
|---|---|
| Binary | DONE  -  95KB .wasm file |
| Rust source | DONE  -  client/wasm/src/lib.rs |
| JS fallback | DONE  -  computeDeadlineJS() |
| Rules from backend | DONE  -  fetchDeadlineRules() → /rules/ |
| No hardcoded values | DONE  -  grep confirms 0 matches |
| Rebuild script | DONE  -  scripts/rebuild-wasm.sh (needs wasm-pack installed) |
| CI WASM check | DONE  -  lawapp-ci.yml wasm-check job |

---

## 12. CI/CD Matrix

| Aspect | Status |
|---|---|
| lawapp-ci.yml | DONE  -  tests, Redis, migrations, security scan, WASM check |
| lawapp-deploy-k8s.yml | DONE |
| push-and-deploy.sh | DONE  -  --dry-run confirmed working |
| security-regression.sh | DONE  -  9/9 pass |
| stale deploy-iterlaw-ai.yml | DONE  -  renamed to .disabled |

---

## 13. Kubernetes Namespace Matrix

| Namespace | Manifests | Secret names consistent | Deployed | Status |
|---|---|---|---|---|
| lawapp-api | ✓ | ✓ (lawapp-secrets, lawapp-postgres-secret) | NOT PROVEN | BLOCKED_OWNER_ACTION |
| lawapp-ai | ✓ | ✓ (lawapp-ai-secrets, lawapp-secrets) | NOT PROVEN | BLOCKED_OWNER_ACTION |
| lawapp-rag | ✓ | ✓ (lawapp-secrets, lawapp-rag-secrets) | NOT PROVEN | BLOCKED_OWNER_ACTION |
| lawapp-security | ✓ | ✓ | NOT PROVEN | BLOCKED_OWNER_ACTION |
| lawapp-monitoring | ✓ | ✓ (lawapp-secrets) | NOT PROVEN | BLOCKED_OWNER_ACTION |

kubectl not available in this environment. Owner must run `bash scripts/deploy-talos.sh` from WSL.

---

## 14. Remaining Blockers

### Owner-only blockers (code cannot fix these)

| # | Blocker |
|---|---|
| 1 | Set real `ANTHROPIC_API_KEY`  -  complex assessments return insufficient_grounding |
| 2 | Set real Stripe keys  -  STRIPE_SECRET_KEY, STRIPE_PUBLIC_KEY, STRIPE_WEBHOOK_SECRET |
| 3 | Run `bash scripts/deploy-talos.sh` from WSL with kubeconfig |
| 4 | Apply for FCL bulk computational licence for case law corpus |
| 5 | Set real `ENCRYPTION_KEY` in production  -  2 encryption tests currently skip |
| 6 | Install wasm-pack for WASM rebuild (optional  -  JS fallback is functional) |

### Claude coding blockers remaining

| # | Item | Effort |
|---|---|---|
| 1 | Real OCR engine (Phase 4) | 1-2 sprints  -  need pytesseract or cloud OCR |
| 2 | Stripe live webhook: wire checkout.session.completed to document access unlock | 2-4 hours |
| 3 | Redis persistence config for rate limiter (maxmemory-policy set; TTL needs config) | 1 hour |

### External legal/licence blockers

| # | Blocker |
|---|---|
| 1 | Find Case Law (FCL) bulk computational access licence |
| 2 | Legislation.gov.uk live ingestion (currently working; rate-limited) |
| 3 | DPIA review for production launch |

### Production compliance blockers

| # | Blocker |
|---|---|
| 1 | DPIA/privacy impact assessment review |
| 2 | Legal boundary review of generated documents |
| 3 | Monitoring/alerting stack (Prometheus/Grafana or equivalent) |
| 4 | Backup and disaster recovery proven |
| 5 | Penetration testing |
