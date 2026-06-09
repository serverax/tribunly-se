# LAWAPP AGGRESSIVE NEW TECHNOLOGY + END-TO-END ACCEPTANCE ORDER

**Project:** lawapp  
**Target project root:** `F:\lawapp` / `/mnt/f/lawapp`  
**Order type:** mandatory implementation, wiring, verification, and acceptance-gate order  
**Status rule:** no local demo-only claims, no fake PASS, no hidden stubs, no unsupported sign-off  

---

## 0. COMMAND TO CLAUDE CODE

Claude Code, you must now apply this order to the entire lawapp system end to end.

This is not a request for another short test report. This is a mandatory completion and verification order covering all new technologies, backend/frontend wiring, database wiring, route wiring, security, CI/CD, Kubernetes readiness, and end-to-end user journeys.

From now on, every feature and every new technology must be treated as **not accepted** until it is:

1. implemented in code,
2. wired to the backend,
3. wired to the frontend where user-facing,
4. wired to the correct database table or persistent store where applicable,
5. protected by security and ownership checks,
6. covered by unit/integration/e2e tests,
7. proven from a clean Docker rebuild,
8. proven with exact commands and raw outputs,
9. documented honestly in the final report.

Do not negotiate the acceptance criteria. Do not reduce scope silently. Do not mark anything as complete because the architecture exists. Architecture is not completion. A route without database state is not completion. A frontend button without backend proof is not completion. A database table with no code path is not completion. A passing mocked test without real route/database proof is not completion.

If something external is genuinely unavailable, you must still implement the code path, fail closed safely, provide a local deterministic test harness or simulator, and prove the production path refuses to run without real configuration. You may label only the external dependency as blocked. You may not label your coding work as blocked if you can build the interface, validation, audit logging, database state, and fail-closed behaviour.

---

## 1. FINAL ACCEPTANCE CLASSIFICATION RULES

You must use only these classifications:

| Classification | Meaning | Allowed only when |
|---|---|---|
| `NOT READY` | Broken, unwired, failing, or unproven | Any required gate fails |
| `LOCAL DEMO READY` | Works locally from clean Docker with demo/test/simulator configuration | All local gates pass, but real AI/Stripe/ingestion/Kubernetes may still be absent |
| `STAGING READY` | Deployed and verified in the lawapp Kubernetes namespaces with staging secrets/config | Kubernetes rollout, health, logs, ingress, DB, Redis, AI config, and smoke tests pass |
| `PRODUCTION CANDIDATE` | Staging ready plus production-like security, monitoring, legal-data freshness, Stripe, OCR decision, and compliance evidence | All production candidate gates pass |
| `PRODUCTION READY` | Real production deployment with live secrets, live monitoring, live backup/restore, DPIA/compliance, and legal review complete | No critical blocker remains |

Forbidden phrases unless all required proof exists:

- “complete”
- “done”
- “production ready”
- “staging ready”
- “fully wired”
- “final sign-off”
- “all implemented”

If you use any of those words, the same section must include exact proof commands and raw output.

---

## 2. GLOBAL NON-NEGOTIABLE ACCEPTANCE CRITERIA

These criteria apply to every feature, route, table, page, technology, and workflow.

### 2.1 Code acceptance

A feature is accepted only if:

- source code exists in the correct service/module,
- route/function/service is reachable,
- no placeholder implementation remains unless intentionally disabled and hidden from user claims,
- no fake success response exists,
- no hardcoded demo-only legal or payment values exist outside controlled test fixtures,
- errors are explicit and safe,
- logging does not expose raw personal facts or secrets.

### 2.2 Backend acceptance

A backend feature is accepted only if:

- API route exists,
- request schema validation exists,
- response schema is stable,
- authentication/authorization is enforced where needed,
- ownership isolation is enforced on user resources,
- database write/read path is proven,
- failure path is tested,
- route appears in OpenAPI or route list,
- curl/httpx test proves real behaviour.

### 2.3 Frontend acceptance

A frontend feature is accepted only if:

- page/component exists,
- button/form is wired to the real backend endpoint,
- loading/error/success states are shown,
- auth token handling works,
- user-owned data is shown only to the owner,
- legal notice appears where relevant,
- no hidden fake/demo values are displayed as real,
- Playwright proves the journey.

### 2.4 Database acceptance

A database feature is accepted only if:

- migration exists,
- schema is applied from clean DB,
- indexes/constraints exist where needed,
- seed data is automatic if required,
- code writes to the table,
- code reads from the table,
- row count and sample rows are proven after workflow execution,
- rollback/idempotency is considered,
- no manual-only database step is required for local demo readiness.

### 2.5 Security acceptance

A feature is accepted only if:

- JWT/auth is enforced where needed,
- cross-user access returns 403,
- secrets are never committed,
- CORS is restricted outside local dev,
- rate limiting is active with Redis when configured,
- uploads validate file size/type,
- raw PII is not sent to third-party models,
- payment routes fail closed in Stripe mode,
- logs do not expose raw facts, documents, tokens, keys, or webhook secrets.

### 2.6 Evidence acceptance

No feature is accepted without:

- exact command,
- exact output,
- file path changed,
- line number or grep proof where applicable,
- database proof where applicable,
- test proof,
- classification: accepted / rejected / disabled honestly.

---

## 3. NEW TECHNOLOGIES NOW UNDER STRICT ACCEPTANCE

The following technologies/features have been added or introduced. Every one must be inspected, wired, tested, and reported.

---

## 4. AGENTIC AI / 19-STEP BRAIN

### Required state

The agentic brain must not be a fake trace generator. It must coordinate the real workflow:

`classify -> retrieve -> reason -> score -> govern -> respond -> generate where paid path applies`

### Mandatory checks

- Confirm the brain route exists.
- Confirm the 19 steps are not hardcoded-only theatre.
- Confirm it calls actual retrieval/rules/scoring/governance modules.
- Confirm it records trace/audit data in the database.
- Confirm insufficient grounding stops unsafe reasoning.
- Confirm no reserved legal activity wording passes governance.

### Acceptance commands

```bash
cd /mnt/f/lawapp
python -m pytest tests -q
curl -s http://localhost:8000/api/brain/trace -H 'Content-Type: application/json' -d '{"claim_type":"unfair_dismissal","facts":{"dismissal_date":"2026-05-10","service_months":36}}' | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM brain_traces;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT id, created_at FROM brain_traces ORDER BY created_at DESC LIMIT 3;"
```

### Rejection triggers

Reject if:

- the trace is static,
- the trace does not touch retrieval/rules/governance,
- no DB row is written,
- unsafe or unsupported advice is generated,
- empty legal sources still produce confident legal assessment.

---

## 5. HYBRID RAG

### Required state

Hybrid RAG must combine:

- structured SQL from `rules`,
- semantic retrieval from `legislation`,
- semantic retrieval from `acas_guidance`,
- case law retrieval only where licence permits,
- retrieval audit logging.

### Mandatory checks

- Empty legal corpus must return `insufficient_grounding`.
- Populated legal corpus must return real citations.
- Exact legal facts must come from `rules`, not the model.
- Retrieval must write audit rows.
- Similarity/search failure must not fall back to model memory.

### Acceptance commands

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS rules FROM rules;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS legislation FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS acas_guidance FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS case_law_chunks FROM case_law_chunks;" || true
curl -s http://localhost:8000/api/rag/hybrid-search -H 'Content-Type: application/json' -d '{"query":"unfair dismissal time limit and ACAS early conciliation","claim_type":"unfair_dismissal"}' | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM retrieval_audit;" || true
```

### Rejection triggers

Reject if:

- semantic legal tables are empty but the system claims full RAG complete,
- no citations are returned after ingestion,
- exact deadline/cap is generated by AI,
- retrieval audit is absent,
- route returns fake success with zero sources.

---

## 6. GRAPH RAG / KNOWLEDGE GRAPH

### Required state

Graph RAG must use real `legal_nodes` and `legal_edges` data, not hardcoded JSON only.

### Mandatory checks

- Nodes and edges exist after clean DB migration.
- Graph traversal route/function reads from DB.
- Brain can use graph context.
- Graph data does not replace primary legal citations.
- Graph traversal is logged or test-proven.

### Acceptance commands

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS legal_nodes FROM legal_nodes;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) AS legal_edges FROM legal_edges;"
curl -s http://localhost:8000/api/rag/graph -H 'Content-Type: application/json' -d '{"concept":"unfair_dismissal"}' | jq .
python -m pytest -q -k "graph or knowledge"
```

### Rejection triggers

Reject if:

- graph route ignores DB,
- graph has no link to brain/retrieval,
- graph is used as legal authority without citation,
- graph fails after clean DB rebuild.

---

## 7. CONTEXT COMPRESSION

### Required state

Context compression must reduce retrieved context safely without deleting required citations or deterministic rules.

### Mandatory checks

- Compression module exists.
- Compression logs metrics.
- Citations survive compression.
- Rules survive compression.
- No PII is introduced or leaked.

### Acceptance commands

```bash
python -m pytest -q -k "compression or context"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM context_compression_log;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM context_compression_log ORDER BY created_at DESC LIMIT 3;" || true
```

### Rejection triggers

Reject if:

- compression removes citations,
- compression removes `rules` facts,
- no metrics are recorded,
- compressed context is not used anywhere.

---

## 8. MEMORY ENGINE

### Required state

Memory must be consent-gated, user-owned, encrypted/minimised, and never silently used across users.

### Mandatory checks

- Save memory requires user identity and consent.
- Get memory returns only current user's records.
- Cross-user access is impossible.
- Raw PII is not stored unnecessarily.
- Delete/retention path exists or is clearly documented.

### Acceptance commands

```bash
python -m pytest -q -k "memory or consent or isolation"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legal_memory;"
curl -s http://localhost:8000/api/memory/save -H 'Content-Type: application/json' -d '{"consent":true,"case_id":"test","memory":"test memory"}' | jq . || true
```

### Rejection triggers

Reject if:

- memory works without consent,
- memory leaks across users,
- memory stores raw documents without reason,
- memory exists only as a table with no route/function.

---

## 9. EVALUATION AI / QUALITY RUBRIC

### Required state

Evaluation AI must test legal quality and system honesty, not just return a decorative score.

### Mandatory checks

- Evaluation endpoint exists.
- Evaluation results are written to DB.
- Rubric includes grounding, citations, legal-boundary safety, weaknesses, deterministic deadline, and confidence.
- Low-quality output fails.
- CI or regression script can run evaluations.

### Acceptance commands

```bash
python -m pytest -q -k "evaluation or eval"
curl -s http://localhost:8000/api/evaluate -H 'Content-Type: application/json' -d '{"assessment":{"claim_type":"unfair_dismissal","citations":[],"reasoning_summary":"You will win."}}' | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM evaluation_results;"
```

### Rejection triggers

Reject if:

- bad legal output passes,
- no DB result is stored,
- rubric ignores citations/grounding,
- evaluation route is not wired to real assessment output.

---

## 10. MCP CONNECTORS / TOOL CONNECTORS

### Required state

MCP/tool connectors must be deny-by-default, audited, and unable to access unsafe tools without explicit allow rules.

### Mandatory checks

- Connector registry exists.
- Allowed tools are explicit.
- Denied tools fail closed.
- Every tool call is audited.
- No connector can exfiltrate raw case documents by default.

### Acceptance commands

```bash
python -m pytest -q -k "mcp or connector or tool"
curl -s http://localhost:8000/api/mcp/tools | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM mcp_tool_calls;"
```

### Rejection triggers

Reject if:

- all tools are allowed by default,
- no audit row is written,
- connector errors return fake success,
- raw facts can be sent to an external tool without de-identification.

---

## 11. MULTIMODAL AI / OCR

### Required state

OCR must be either fully implemented and wired, or fully disabled from user promises. A 501 route is acceptable only if the frontend does not advertise OCR as available.

### Mandatory checks if OCR implemented

- Upload route exists.
- Ownership enforced.
- File type/size validation exists.
- OCR extracts text/facts.
- Extracted facts are marked unconfirmed.
- User confirmation required before use.
- Raw upload is not sent to LLM.
- Documents are encrypted or stored safely.

### Mandatory checks if OCR not implemented

- Route returns 501.
- Frontend clearly says upload extraction is not enabled.
- No marketing/user journey claims OCR is ready.
- Tests expect disabled state.

### Acceptance commands

```bash
python -m pytest -q -k "upload or ocr or extraction or document"
curl -s -i http://localhost:8000/cases/test/uploads/test/extract || true
grep -R "OCR\|upload\|extract\|document photo\|dismissal letter" client backend -n | head -100
```

### Rejection triggers

Reject if:

- frontend advertises OCR but backend returns 501 without explanation,
- raw uploaded document is sent to AI,
- cross-user upload access is possible,
- extracted facts are silently trusted.

---

## 12. AI ROUTER

### Required state

The AI router must choose between stub/local/test/real provider based on configuration and must fail closed where real mode is required but keys are missing.

### Mandatory checks

- `/health` reports active AI status honestly.
- Test mode cannot be confused with production mode.
- Missing key in real mode fails closed.
- De-identification happens before third-party call.
- Provider choice is audited.

### Acceptance commands

```bash
curl -s http://localhost:8000/health | jq .
python -m pytest -q -k "ai_router or provider or deidentify or pii"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM routing_decisions;" || true
```

### Rejection triggers

Reject if:

- stub model is reported as real AI,
- real mode works without key,
- raw PII reaches provider boundary,
- AI route returns confident legal advice with empty retrieval.

---

## 13. SEMANTIC CACHE

### Required state

Semantic cache must improve performance without storing PII or stale legal conclusions incorrectly.

### Mandatory checks

- Cache stores non-PII key only.
- Cache excludes raw facts/names/documents.
- Cache invalidates or namespaces by source freshness/version.
- Cache hit/miss is testable.
- Cache does not bypass governance.

### Acceptance commands

```bash
python -m pytest -q -k "cache or semantic"
curl -s http://localhost:8000/api/cache/test | jq . || true
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM semantic_cache;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM semantic_cache LIMIT 3;" || true
```

### Rejection triggers

Reject if:

- cache stores raw PII,
- cache bypasses retrieval/governance,
- stale legal data is reused without versioning,
- cache table exists but no code path uses it.

---

## 14. WASM + JS FALLBACK

### Required state

WASM must do only client-side deterministic/privacy-sensitive computation: deadline arithmetic, document preview/assembly, validation. It must not run legal reasoning or RAG.

### Mandatory checks

- Rust/WASM source exists.
- Generated WASM exists.
- JS fallback exists.
- Deadline values come from backend `rules`, not hardcoded in WASM/JS.
- CI rebuilds or verifies WASM.
- Frontend uses WASM/fallback in actual page flow.

### Acceptance commands

```bash
bash scripts/rebuild-wasm.sh || true
python -m pytest -q -k "deadline or wasm"
cd client && npm test -- --runInBand || true
cd /mnt/f/lawapp && grep -R "3 months\|three months\|123543\|751\|118223" client -n || true
```

### Rejection triggers

Reject if:

- legal values are hardcoded in client,
- WASM binary is stale with no rebuild proof,
- frontend deadline calculator does not call backend rules,
- JS fallback disagrees with WASM/server result.

---

## 15. REDIS RATE LIMITING

### Required state

Rate limiting must use Redis when configured and fail safely to in-memory only in local/dev mode with clear logging.

### Mandatory checks

- Redis service runs in Docker.
- Backend config uses Redis URI.
- Redis responds to ping.
- Rate limit test exists.
- Production/staging must not silently use in-memory fallback.

### Acceptance commands

```bash
docker compose ps
docker compose exec -T redis redis-cli ping
docker compose exec -T backend printenv | grep RATELIMIT
python -m pytest -q -k "rate or limit or redis"
```

### Rejection triggers

Reject if:

- Redis is running but backend ignores it,
- production mode falls back silently,
- no test proves rate limiting,
- rate limit can be bypassed on sensitive routes.

---

## 16. STRIPE PAYMENTS

### Required state

Stripe must be implemented as real production-capable code with test/simulator mode clearly separated. Webhook must verify signature and update DB idempotently.

### Mandatory checks

- Stripe SDK installed in Docker.
- Payment session route works in simulator/test mode.
- Stripe mode fails closed without secrets.
- Webhook verifies signature in Stripe mode.
- `checkout.session.completed` updates DB payment/case status.
- Duplicate webhook event is idempotent.
- Frontend payment path reflects payment state.

### Acceptance commands

```bash
docker compose exec -T backend python -c "import stripe; print(stripe.__version__)"
python -m pytest -q -k "stripe or payment or webhook"
curl -s http://localhost:8000/api/payment/status | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM payment_events;" || true
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT id, payment_status FROM cases LIMIT 5;" || true
```

### Rejection triggers

Reject if:

- Stripe import fails in Docker,
- webhook accepts unsigned events in Stripe mode,
- payment state is not persisted,
- frontend can download paid documents without valid payment state,
- duplicate event corrupts state.

---

## 17. LEGAL DATA INGESTION

### Required state

The legal data spine must be real, not just schema. At minimum, legislation and ACAS ingestion must populate rows. Case law bulk ingestion remains licence-gated but must have safe sample/manual logic and explicit licence gating.

### Mandatory checks

- `legislation` rows after ingestion.
- `acas_guidance` rows after ingestion.
- `rules` rows after clean migration.
- freshness report works.
- ingestion is repeatable/idempotent.
- empty source state causes honest insufficient-grounding.
- populated source state returns citations.

### Acceptance commands

```bash
docker compose run --rm ingestion python -m ingestion.legislation.ingest
docker compose run --rm ingestion python -m ingestion.acas.ingest
docker compose run --rm ingestion python -m ingestion.freshness
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;"
```

### Rejection triggers

Reject if:

- ingestion commands do not exist,
- ingestion only prints success but inserts zero rows,
- source freshness is fake,
- rules are manually seeded only,
- case law bulk crawl ignores licence gate.

---

## 18. DATABASES + FUNCTIONS END-TO-END WIRING

### Required state

Every table must be connected to a real function or route, or documented as future-only and not counted as complete.

### Mandatory DB wiring audit

For each table, produce:

| Table | Migration | Seed/insert path | Read path | Route/function | Test | Status |
|---|---|---|---|---|---|---|

Minimum tables to audit:

- users
- cases
- documents
- rules
- legislation
- acas_guidance
- case_law / case_law_chunks
- legal_nodes
- legal_edges
- brain_traces
- retrieval_audit
- safety_boundary_checks
- context_compression_log
- evaluation_results
- mcp_tool_calls
- semantic_cache
- legal_memory
- payment_events
- referrals/handoff leads
- wasm_calculations if present
- routing_decisions if present

### Acceptance commands

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
python -m pytest -q
bash scripts/smoke_local_journey.sh
```

### Rejection triggers

Reject if:

- table exists only for show,
- route exists but does not write/read DB,
- tests mock DB when real DB proof is required,
- clean DB startup loses required seed data.

---

## 19. BACKEND TO FRONTEND WIRING

### Required state

Every user-facing page must be connected to backend endpoints and real state.

### Mandatory page audit

For each page, produce:

| Page | Route | Buttons/forms | Backend endpoint | Auth | DB state touched | Error state | Playwright proof | Status |
|---|---|---|---|---|---|---|---|---|

Minimum pages:

- landing
- register
- login
- intake
- assessment
- dashboard
- saved case
- document generation
- document download
- payment success
- payment cancel
- handoff/referral
- deadline tracker
- upload/OCR state
- admin/debug pages if any

### Required user journeys

1. Register -> login -> auth/me.
2. Intake -> assessment -> citations/weaknesses/deadline displayed.
3. Assessment -> save case -> dashboard shows case.
4. Saved case -> deadline displayed from rules.
5. Payment simulator/test -> case payment status updated -> document download allowed.
6. Invalid/no payment -> paid document blocked.
7. Handoff trigger -> lead stored.
8. Cross-user case/document access -> 403.
9. OCR/upload either fully works or clearly disabled.
10. Logout/session expiry handled.

### Acceptance commands

```bash
cd /mnt/f/lawapp/client
node_modules/.bin/playwright test --reporter=list
cd /mnt/f/lawapp
bash scripts/smoke_local_journey.sh
python -m pytest -q -k "frontend or journey or auth or document or payment"
```

### Rejection triggers

Reject if:

- button has no backend call,
- frontend uses hardcoded legal output,
- frontend shows paid content without payment state,
- frontend shows OCR as ready while backend returns 501,
- Playwright covers pages but not real user flows.

---

## 20. DOCUMENT GENERATION

### Required state

Document generation must use structured assessment, user facts, templates, and payment checks. It must not be generic filler.

### Mandatory checks

- Particulars of Claim generated.
- Schedule of Loss generated.
- User facts appear correctly.
- Legal notice appears.
- Payment required where configured.
- Document stored in DB.
- Download route checks ownership.
- Cross-user download is 403.

### Acceptance commands

```bash
python -m pytest -q -k "document or generate or download"
bash scripts/smoke_local_journey.sh
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM documents;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT doc_type, is_user_upload, created_at FROM documents ORDER BY created_at DESC LIMIT 5;"
```

### Rejection triggers

Reject if:

- documents are generated without payment when payment required,
- document is generic and ignores user facts,
- no DB record exists,
- cross-user download works,
- document implies legal advice or solicitor representation.

---

## 21. LEGAL SAFETY + RESERVED ACTIVITY GUARDRAILS

### Required state

The system must remain a self-help information/assessment/drafting product. It must never conduct litigation, represent users, file claims, guarantee outcomes, or imply solicitor/law-firm status.

### Mandatory checks

Search all source and UI content for forbidden language.

Forbidden or suspicious wording includes:

- “we will file your claim”
- “we represent you”
- “our lawyers will act for you”
- “guaranteed win”
- “you will win”
- “legal advice” without clear boundary
- “solicitor service” unless referring to external handoff

### Acceptance commands

```bash
grep -R "we will file\|represent you\|guaranteed win\|you will win\|rights of audience\|conduct litigation\|solicitor service" backend client docs -n || true
python -m pytest -q -k "governance or safety or reserved or boundary"
```

### Rejection triggers

Reject if:

- any user-facing content crosses reserved activity boundary,
- governance allows guarantee language,
- documents omit self-help/not-legal-advice notice,
- handoff suggests lawapp itself is acting as solicitor.

---

## 22. SECURITY END-TO-END

### Required state

Security must be proven, not claimed.

### Mandatory checks

- JWT auth active.
- Password handling safe.
- Cross-user isolation on cases/documents/uploads/memory.
- CORS restricted outside local dev.
- Secrets not committed.
- Rate limiting active.
- Payment fail-closed.
- Upload validation.
- PII stripped before AI.
- Logs safe.

### Acceptance commands

```bash
python -m pytest -q -k "security or auth or isolation or cors or pii or upload"
grep -R "sk_live\|sk_test\|ANTHROPIC_API_KEY\|STRIPE_SECRET_KEY\|JWT_SECRET" . --exclude-dir=.git --exclude='*.md' || true
bash scripts/security-regression.sh || true
docker compose logs backend --tail=200 | grep -Ei "password|token|secret|raw_document|address|dob" || true
```

### Rejection triggers

Reject if:

- secrets are committed,
- cross-user access succeeds,
- raw facts appear in logs,
- production CORS is wildcard,
- Stripe mode accepts unsigned webhook,
- third-party AI receives raw PII.

---

## 23. CI/CD

### Required state

CI/CD must run tests, build client/backend, verify WASM, and deploy only with explicit environment controls.

### Mandatory checks

- CI workflow exists.
- Deploy workflow exists.
- Stale/wrong project names removed from active workflows.
- Local push-and-deploy script exists.
- Dry-run passes.
- No deployment to wrong namespace.
- Branch/environment gates exist.

### Acceptance commands

```bash
ls -la .github/workflows
bash scripts/push-and-deploy.sh --dry-run
grep -R "IterLaw\|RightsNow\|hermes\|sakina" .github scripts infra -n || true
bash -n scripts/push-and-deploy.sh
```

### Rejection triggers

Reject if:

- workflow points to wrong namespace/name,
- deployment happens without tests,
- dry-run is fake,
- stale workflow remains active,
- secrets are printed in CI.

---

## 24. KUBERNETES / LAWAPP NAMESPACES

### Required state

Kubernetes is not accepted until live cluster proof exists. Manifests alone are not deployment proof.

Canonical active namespaces:

- `lawapp-ai`
- `lawapp-rag`
- `lawapp-api`
- `lawapp-monitoring`
- `lawapp-security`

### Mandatory checks

- Correct kube context.
- Namespaces exist.
- Secrets/configmaps exist.
- Backend pod running.
- RAG/AI services running or explicitly disabled with honest health.
- Ingress/service reachable where configured.
- Rollout status passes.
- Logs have no crash loop.

### Acceptance commands

```bash
kubectl config current-context
kubectl get ns | grep lawapp
kubectl -n lawapp-api get deploy,po,svc,ingress,cm,secret
kubectl -n lawapp-rag get deploy,po,svc,cm,secret
kubectl -n lawapp-ai get deploy,po,svc,cm,secret
kubectl -n lawapp-monitoring get deploy,po,svc,cm,secret
kubectl -n lawapp-security get deploy,po,svc,cm,secret
kubectl -n lawapp-api rollout status deploy/lawapp-backend --timeout=180s
kubectl -n lawapp-api exec deploy/lawapp-backend -- curl -s http://localhost:8000/health
kubectl -n lawapp-api logs deploy/lawapp-backend --tail=100
```

### Rejection triggers

Reject if:

- kubeconfig missing and report says Kubernetes done,
- pods are CrashLoopBackOff,
- wrong namespace is used,
- secrets mismatch manifests,
- health not proven from inside pod,
- deployment report uses local Docker proof as Kubernetes proof.

---

## 25. OBSERVABILITY / MONITORING

### Required state

Monitoring must not be a YAML-only claim. It must show live health, logs, metrics, and failure visibility.

### Mandatory checks

- Health endpoint returns DB, Redis, AI mode, payment mode.
- Backend logs available.
- Kubernetes logs available.
- Monitoring namespace has resources.
- Error paths are visible.
- No sensitive data in logs.

### Acceptance commands

```bash
curl -s http://localhost:8000/health | jq .
docker compose logs backend --tail=100
kubectl -n lawapp-monitoring get all || true
kubectl -n lawapp-api logs deploy/lawapp-backend --tail=100 || true
```

### Rejection triggers

Reject if:

- health says ok while DB unavailable,
- logs leak secrets/PII,
- monitoring namespace empty but claimed complete,
- AI/payment modes are hidden.

---

## 26. CLEAN BUILD GATE

Every final claim must start from a clean build.

### Mandatory commands

```bash
cd /mnt/f/lawapp
docker compose down -v
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"
```

### Rejection triggers

Reject if:

- test depends on dirty DB,
- manual seed required but not documented,
- containers are unhealthy,
- backend health lies about dependencies.

---

## 27. FULL REQUIRED FINAL TEST GATE

You must run this full gate before writing the final report.

```bash
cd /mnt/f/lawapp
docker compose down -v && docker compose up -d --build
curl -s http://localhost:8000/health | jq .
python -m pytest -q
bash scripts/smoke_local_journey.sh
cd client && node_modules/.bin/playwright test --reporter=list
cd /mnt/f/lawapp
bash scripts/push-and-deploy.sh --dry-run
bash scripts/security-regression.sh || true
bash scripts/rebuild-wasm.sh || true
```

If any command fails, do not hide it. Fix it, rerun it, and include both the failure and the final passing output in the report.

---

## 28. REQUIRED FINAL REPORT

Create this report:

`reports/claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md`

The report must include these sections:

1. Executive classification.
2. Commit hash and branch.
3. Clean Docker proof.
4. Backend route matrix.
5. Frontend wiring matrix.
6. Database/table/function wiring matrix.
7. New technology matrix.
8. AI/RAG/brain evidence.
9. Graph RAG evidence.
10. Memory/evaluation/MCP/cache evidence.
11. OCR/multimodal evidence.
12. WASM evidence.
13. Stripe/payment evidence.
14. Redis/rate limit evidence.
15. Legal data ingestion evidence.
16. Document generation evidence.
17. Security evidence.
18. CI/CD evidence.
19. Kubernetes namespace evidence.
20. Monitoring evidence.
21. Full command-output appendix.
22. Remaining gaps, if any, with classification:
    - coding gap,
    - owner secret/config gap,
    - external licence gap,
    - compliance/legal-review gap.

If any remaining gap exists, do not call the system complete. Say exactly what is still not accepted.

---

## 29. STRICT FINAL RULE

You must work until every coding, wiring, database, frontend, backend, and test issue that is inside the repository is solved.

Do not stop at “blocked” when you can still:

- write the code,
- create the interface,
- add the migration,
- wire the route,
- wire the frontend,
- add tests,
- add a simulator,
- fail closed safely,
- add evidence commands,
- document the exact external dependency.

Only external items may remain blocked:

- real Anthropic/OpenAI key,
- real Stripe live keys,
- Find Case Law computational-analysis licence grant,
- production DNS/TLS/cluster access if not available,
- formal legal/DPIA/compliance review.

Even for those, the code must be complete, fail closed, and have a local/staging-safe proof path.

No negotiation. No fake PASS. No local-only sign-off pretending to be staging or production.
