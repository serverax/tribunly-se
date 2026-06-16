# lawapp  -  Claude Code Order: Add Advanced Technologies into the Brain-Controlled Workflow

**Project:** lawapp  
**Root:** `F:\lawapp` / `/mnt/f/lawapp`  
**Output report:** `F:\lawapp\reports\lawapp-advanced-technologies-end-to-end-signoff.md`

This order is for **lawapp only**. Do not work on Sakina, OrdinoxAI, Hermes, RightsNow, IterLaw, or any unrelated project unless the owner explicitly says so.

---

## 0. Non-Negotiable Instruction

Claude Code must create, wire, test, and prove all technologies inside the real lawapp workflow.

The owner is **not accepting**:

```text
FAILED
BLOCKED
PARTIAL
LOCAL ONLY
SAFE DISABLED AS COMPLETION
MOCKED
PLACEHOLDER
DOCUMENTED ONLY
IMPLEMENTED BUT NOT WIRED
```

If something fails, fix it.  
If something needs external owner credentials, implement the real path, make it fail closed, and report the exact owner action. But do not call it complete.

---

## 1. Meaning of Acceptance

Acceptance does not mean:

- file exists
- route exists
- table exists
- code compiles
- mocked script passes
- report says implemented
- screenshot exists
- technology is mentioned in docs

Acceptance means the full lawapp workflow works end to end:

```text
User UI
→ frontend state/service
→ backend API
→ auth/session/security guard
→ Brain Algorithm
→ legal intent classifier
→ risk classifier
→ policy-as-code
→ prompt injection guard
→ RAG / Graph RAG / Hybrid Search
→ legal source trust ranking
→ context compression
→ AI router/model router
→ LLM/provider call where required
→ citation and hallucination validator
→ legal safety guard
→ remedy/compensation logic
→ DB/vector DB/cache/queue/WASM where required
→ audit log
→ trace/metrics
→ response back to frontend
→ frontend renders real backend result
→ CI/CD proof
→ Docker/Kubernetes proof
```

No isolated component is accepted.

---

## 2. Brain Algorithm Must Control Everything

Create or upgrade the central lawapp Brain Algorithm.

### Workflow position

```text
Frontend request → Backend route → Brain Algorithm → All AI/RAG/DB/Tool decisions → Final response
```

### Required Brain stages

```text
Request Intake
→ Auth/User Context
→ Case Context
→ Jurisdiction Check
→ Legal Domain Router
→ Risk/Urgency Classifier
→ Entitlement/Feature Flag Check
→ Memory/Case History Permission Check
→ Retrieval Planner
→ Hybrid Search
→ Graph RAG
→ Legal Source Trust Ranking
→ Context Compression
→ AI Router
→ Draft Legal Response
→ Citation Validator
→ Hallucination Validator
→ Legal Safety Guard
→ Remedy/Compensation Model
→ Final Response
→ Audit Log
→ Observability Trace
```

### Implementation

- central brain service/module
- trace object for every stage
- DB table for brain traces
- audit table for legal actions
- fail-closed behaviour
- direct LLM bypass prevention
- direct RAG bypass prevention
- route coverage matrix

### Acceptance criteria

Accepted only if:

- every user-facing legal answer goes through Brain
- every Brain stage appears in trace
- trace is persisted in DB
- no route can call LLM directly
- no route can answer legal advice without citation validation
- frontend legal actions map to Brain-controlled routes
- negative bypass tests fail correctly
- CI proves no direct LLM/RAG bypass exists

Reject if Brain exists but only one route uses it, trace is static JSON, handlers call LLM directly, or safety/citation validation can be skipped.

---

## 3. Agentic AI Workflow Engine

### Workflow position

```text
Brain → Agent Workflow → Retrieval / Reasoning / Validation → Brain Final Response
```

### Required agents

- intake agent
- legal issue classifier
- jurisdiction checker
- RAG retrieval agent
- Graph RAG relationship agent
- citation verifier
- hallucination reviewer
- legal safety reviewer
- remedy/compensation estimator
- document drafting agent
- evidence reviewer
- escalation/human-review agent
- entitlement/billing agent if paid features exist

### Implementation

Each agent must have:

- agent ID
- input schema
- output schema
- allowed tools
- denied tools
- timeout
- retry limit
- audit log
- trace log
- failure state
- safe fallback

### Acceptance criteria

Accepted only if agents are code-defined, Brain invokes them, schemas are enforced, forbidden tools are blocked, failed steps are persisted, retry/timeout are tested, and agent output affects the final response.

Reject if agents are only prompts, can call any tool, or have no persisted workflow state.

---

## 4. RAG for Legal Sources

### Workflow position

```text
Brain → Retrieval Planner → RAG → Hybrid Search → Citation Validator → Final Answer
```

### Implementation

Add:

- legal source ingestion pipeline
- source metadata
- chunking
- embeddings
- vector DB storage
- citation IDs
- version/date of law or guidance
- jurisdiction/domain tags
- legal source trust ranking
- reindex job
- stale source detection

Initial source types:

- legislation
- ACAS guidance
- GOV.UK guidance
- tribunal/case-law sources where available
- internal templates
- policy rules

### Acceptance criteria

Accepted only if documents are ingested, chunks have metadata, embeddings exist, vector search works, answer cites retrieved legal sources, unsupported answers fail closed, stale law is flagged, frontend displays citations, and CI proves retrieval/citation validation.

Reject if collection exists but no vectors, citations are fabricated, or RAG is mocked.

---

## 5. Graph RAG / Legal Knowledge Graph

### Workflow position

```text
Brain → Legal Issue Classifier → Graph RAG → Legal Relationship Context → RAG/LLM → Citation Validator
```

### Implementation

Create graph data for:

- legal concepts
- claims
- remedies
- limitation periods
- tribunal steps
- evidence types
- employer duties
- employee rights
- protected-characteristic relationships where legally relevant
- case-law relationships
- legislation-to-guidance links
- remedy-to-evidence links

Must include:

- entity extraction
- relationship extraction
- graph traversal
- graph context builder
- graph trace
- fallback if no entity is found

### Acceptance criteria

Accepted only if graph traversal runs during a real legal question, graph context appears in Brain trace, graph result affects retrieval/reasoning, at least 5 legal issue types are tested, and missing-entity tests fail cleanly.

Reject if graph is only tables or SQL counts.

---

## 6. Hybrid Search

### Workflow position

```text
Brain → Retrieval Planner → Vector Search + Lexical Search → Hybrid Ranking → RAG Context
```

### Implementation

Hybrid search must include:

- vector search
- full-text/lexical search
- score normalisation
- weighted ranking
- duplicate removal
- source trust weighting
- recency weighting
- jurisdiction weighting
- ranking trace
- vector failure fallback
- lexical failure fallback

### Acceptance criteria

Accepted only if vector and lexical results are both shown, ranking is explainable, source trust affects results, wrong jurisdiction is downgraded/rejected, and fallback paths are tested.

Reject if it is only vector search or only SQL LIKE.

---

## 7. Legal Source Trust Ranking

### Workflow position

```text
RAG/Hybrid Search → Source Trust Ranking → Context Selection → Citation Validator
```

### Implementation

Trust levels:

- primary legislation: highest
- official government guidance: high
- ACAS guidance: high for employment context
- tribunal/court decisions: high with date/context
- internal templates: medium
- unknown source: low or rejected

Trust score must consider:

- source type
- jurisdiction
- publication date
- update date
- legal domain
- authority level
- conflict with higher authority

### Acceptance criteria

Accepted only if every source has trust metadata, trust affects ranking, low-trust source cannot override legislation, conflicts are flagged, and trace shows ranking decision.

Reject if all sources get the same score.

---

## 8. Citation and Hallucination Validator

### Workflow position

```text
Draft Answer → Citation Validator → Hallucination Validator → Legal Safety Guard → Final Answer
```

### Implementation

Validator must check:

- cited source IDs exist
- cited source supports claim
- unsupported claims are removed or blocked
- fabricated citations are rejected
- minimum evidence threshold
- legal date and jurisdiction match
- uncertainty caveats
- no legal conclusion beyond evidence

### Acceptance criteria

Accepted only if every legal answer with legal claims has citations, fabricated source IDs are rejected, unsupported claims are detected, no-source answers are blocked/caveated, hallucination traps fail closed, validator result is persisted, and frontend shows citation/support status.

Reject if citations are only text.

---

## 9. Legal Safety Guard / Policy-as-Code

### Workflow position

```text
Brain → Risk Classifier → Policy-as-Code → Draft Answer → Legal Safety Guard → Final Response
```

### Implementation

Policies must cover:

- not pretending to be a regulated solicitor if not applicable
- urgent deadlines
- limitation periods
- tribunal deadlines
- settlement risk
- evidence risk
- vulnerability signals
- harassment/discrimination claims
- dismissal/probation risk
- when to advise human legal help
- when to refuse or caveat

Policies must be versioned, testable, traceable, configurable by legal domain, and enforced at runtime.

### Acceptance criteria

Accepted only if policies exist outside prompts, each policy has tests, urgent/high-risk cases trigger stricter safety, unsafe overconfident answers are blocked, policy decisions appear in trace, and frontend shows warnings/escalation.

Reject if policies are prompt-only.

---

## 10. Context Compression

### Workflow position

```text
Case Context + Retrieved Sources → Context Compression → AI Router / LLM
```

### Implementation

Compression must preserve:

- source IDs
- legal issues
- dates
- deadlines
- risk flags
- user facts
- evidence list
- jurisdiction
- source hierarchy
- caveats

### Acceptance criteria

Accepted only if before/after size is shown, context is reduced, source IDs and legal risk flags are preserved, answer still cites correct sources, compression failure falls back safely, and trace shows compression.

Reject if legal dates, source IDs, or risk flags are lost.

---

## 11. AI Router / Model Router

### Workflow position

```text
Brain → Task/Risk/Cost/Language Classification → AI Router → Provider/Model → Validator
```

### Implementation

Route by:

- legal domain
- complexity
- risk
- cost
- language
- evidence requirement
- latency requirement
- provider availability
- fallback provider

### Acceptance criteria

Accepted only if Brain calls the router, routing is logged, different tasks route differently, high-risk legal questions use stricter routes, disabled providers are not selected, provider failure safely falls back/fails closed, and no route calls provider directly.

Reject if one hardcoded provider is always used.

---

## 12. Evaluation AI / Legal Quality Gate

### Workflow position

```text
Generated Answer → Evaluation AI → Threshold Decision → Pass / Rewrite / Escalate / Fail
```

### Implementation

Dataset must include at least 50 cases:

- urgent deadline cases
- discrimination cases
- dismissal/probation cases
- grievance cases
- settlement cases
- weak evidence cases
- hallucination traps
- citation-required cases
- refusal/caveat cases

Score:

- legal accuracy
- citation support
- jurisdiction match
- hallucination risk
- deadline/risk detection
- clarity
- safety
- remedy logic

### Acceptance criteria

Accepted only if dataset exists, scoring output is produced, threshold is enforced, failed cases are listed, CI fails if score drops, and answer pipeline uses evaluation where required.

Reject if evaluation is manual only.

---

## 13. Semantic Cache

### Workflow position

```text
Brain → Cache Lookup → Safety Check → Return Cached / Continue Retrieval
```

### Implementation

Cache must include:

- semantic similarity
- user isolation
- case isolation
- source version hash
- TTL
- source-update invalidation
- safety re-check
- hit/miss metrics
- no PII in keys

### Acceptance criteria

Accepted only if first similar question is miss, second is hit, different user cannot get cached private answer, source update invalidates cache, cached answer still passes safety/citation validation, TTL works, and metrics show hit/miss.

Reject if cache is global across users or serves stale law.

---

## 14. Redis / Valkey Performance Cache

### Workflow position

```text
API Request → Rate Limit / Session / Feature Flag / Cache → Brain
```

### Implementation

Use Redis/Valkey for:

- rate-limit counters
- refresh/session revocation cache where suitable
- feature flag cache
- semantic cache metadata where suitable
- short-lived retrieval cache
- expensive provider call guard

### Acceptance criteria

Accepted only if Redis/Valkey runs locally and in deployment, backend connects to it, readiness checks it where required, hit/miss is proven, failure path is safe, no sensitive raw data is stored, and Docker/Kubernetes include it.

Reject if dependency exists but is unused.

---

## 15. WASM Module

### Workflow position

```text
Brain → Deterministic Scoring/Validation → WASM → Result → Brain Trace
```

Suggested uses:

- risk scoring
- evidence completeness scoring
- deadline calculation
- compensation helper
- citation support scoring
- retrieval reranking helper

### Implementation

WASM must:

- build from source
- be loaded by backend
- be invoked by real request
- have input/output schema
- handle bad input
- fallback if unavailable
- be built in Docker and CI

### Acceptance criteria

Accepted only if real legal workflow invokes WASM, output affects Brain decision, bad input fails safely, Docker/CI build it, and trace shows WASM stage.

Reject if WASM merely exists.

---

## 16. MCP / Connector Layer

### Workflow position

```text
Brain → Tool Permission Check → Connector Call → Audit → Result → Validator
```

Possible connectors:

- legal source updater
- email/export if allowed
- document storage if allowed
- calendar deadline reminder if allowed
- payment provider if enabled
- monitoring alerts

### Implementation

Each connector must have:

- registry
- allowlist
- denylist
- user permission
- timeout
- rate limit
- audit log
- secret isolation
- failure handling

### Acceptance criteria

Accepted only if Brain controls connector calls, forbidden connectors are blocked, user permission is checked, timeout works, failures are handled, secrets are masked, and audit logs record calls.

Reject if connectors can be called directly.

---

## 17. Event Bus / Queue / Outbox

### Workflow position

```text
User Action → DB Transaction → Outbox Event → Worker → Status/Audit
```

Use for:

- source ingestion
- reindexing
- report generation
- notifications
- audit processing
- evaluation jobs
- payment webhook processing
- account deletion jobs

### Implementation

Outbox must include:

- event type
- payload schema
- status
- retry count
- dead-letter state
- idempotency key
- trace ID
- worker

### Acceptance criteria

Accepted only if event is written, worker processes it, status changes pending to processed, failures retry, max retry moves to dead-letter, duplicate events are idempotent, and trace ID is preserved.

Reject if async is only a log.

---

## 18. OpenTelemetry Observability

### Workflow position

```text
Frontend Request → Backend Trace → Brain Trace → DB/Vector/LLM Spans → Response
```

### Implementation

Include:

- request ID
- trace ID
- structured logs
- metrics
- traces
- error logs
- DB spans
- vector DB spans
- LLM/provider spans
- no secret leakage
- Kubernetes logs

### Acceptance criteria

Accepted only if same trace ID appears in response, logs, DB, and Brain trace; metrics show real counters; errors are logged safely; readiness fails if critical dependency fails; Kubernetes logs show runtime behaviour; secrets are masked.

Reject if only logs exist.

---

## 19. OWASP API Security Gate

### Workflow position

```text
CI/CD + Runtime Security Tests → API Guard → Deployment Gate
```

### Implementation

Test for:

- broken object-level authorization
- broken authentication
- broken function-level authorization
- excessive data exposure
- unrestricted resource consumption
- mass assignment
- injection
- SSRF where relevant
- unsafe CORS
- missing rate limits

### Acceptance criteria

Accepted only if protected endpoints reject unauthenticated access, user A cannot access user B case, admin routes are protected, invalid payloads are blocked, rate limit works, CORS is restricted, and CI blocks release on findings.

Reject if only happy paths are tested.

---

## 20. OWASP MASVS Mobile Security Gate

Use only if lawapp has a mobile app.

### Workflow position

```text
Mobile Build → MASVS Gate → Release APK/AAB Gate
```

### Implementation

Check:

- secure token storage
- no hardcoded secrets
- no localhost in release
- TLS enforced
- debug disabled in release
- no sensitive logs
- permissions justified
- account deletion/privacy links

### Acceptance criteria

Accepted only if release APK/AAB build, no static secrets/tokens exist, secure storage is used, release config uses real API, permissions match enabled features, sensitive logs are absent, and CI runs mobile gate.

Reject if debug APK only.

---

## 21. SAST / SCA / Secret / Container Scanning

### Workflow position

```text
Code Commit → Static Scan → Dependency Scan → Secret Scan → Container Scan → CI Gate
```

### Implementation

Add scans for:

- backend code
- frontend code
- dependencies
- committed secrets
- Docker images
- Kubernetes manifests
- GitHub Actions workflow safety

### Acceptance criteria

Accepted only if scans run in CI, high/critical findings block release, secrets fail the build, container scan runs, results are saved, and false positives are reviewed.

Reject if scans are optional.

---

## 22. Kubernetes Restricted / Admission Policy Gate

### Workflow position

```text
Kubernetes Manifest → Policy Check → Apply → Runtime Verification
```

### Implementation

Enforce:

- non-root containers
- no privileged pods
- read-only root filesystem where possible
- resource requests/limits
- no hostPath unless justified
- secrets from Kubernetes secrets
- network policy where suitable
- liveness/readiness probes
- namespace isolation

### Acceptance criteria

Accepted only if manifests pass restricted policy, pods run non-root, no privileged containers exist, limits/probes exist, secrets are not hardcoded, policy check runs in CI, and live cluster proof exists.

Reject if cluster proof is missing.

---

## 23. Prompt Injection / Jailbreak Guard

### Workflow position

```text
User Input + Retrieved Sources → Injection Guard → Brain → LLM
```

### Implementation

Detect:

- ignore previous instructions
- override system prompt
- malicious source text
- data exfiltration request
- tool abuse
- legal source manipulation
- citation manipulation

### Acceptance criteria

Accepted only if malicious user prompts are blocked, malicious retrieved chunks are neutralised, tool exfiltration is blocked, guard decision appears in trace, and CI runs injection tests.

Reject if guard is prompt-only.

---

## 24. PII Detection and Redaction

### Workflow position

```text
User Input / Case Facts / Logs → PII Detector → Redaction/Protection → Storage/Logs/AI
```

### Implementation

Detect and protect:

- names
- addresses
- emails
- phone numbers
- employer names where needed
- medical information
- protected characteristics
- financial data
- case identifiers

### Acceptance criteria

Accepted only if PII is detected, logs redact sensitive data, AI prompt minimises unnecessary PII, audit stores only required data, deletion works, and cross-user leakage tests fail closed.

Reject if PII appears in logs.

---

## 25. Data Retention and Account Deletion Engine

### Workflow position

```text
User Deletion Request → Auth Check → Outbox Job → Data Deletion → Audit → Confirmation
```

### Implementation

Include:

- account deletion endpoint
- case deletion or anonymisation
- memory deletion
- vector deletion/reindex
- audit-safe deletion record
- retention policy
- frontend deletion UI
- job retry/dead-letter

### Acceptance criteria

Accepted only if authenticated user can request deletion, user A cannot delete user B data, DB/vector data is deleted or anonymised, frontend shows deletion state, audit records deletion, and negative tests pass.

Reject if deletion is frontend-only.

---

## 26. Backup and Disaster Recovery

### Workflow position

```text
Scheduled Backup → Restore Test → Verification Gate
```

### Implementation

Back up:

- PostgreSQL
- vector DB
- legal source index
- key configuration
- uploaded documents if used

### Acceptance criteria

Accepted only if backup command exists, restore command exists, restore is tested into temporary environment, restored DB passes core checks, restored vector DB returns results, and evidence is saved.

Reject if restore is not tested.

---

## 27. Load Testing / Performance Budget

### Workflow position

```text
CI / Pre-release → Load Test → Performance Budget → Pass/Fail
```

### Example budgets

- health endpoint under 300 ms
- authenticated profile under 500 ms
- search/retrieval under 2 seconds
- Brain answer budget defined by provider/model
- p95 latency recorded
- error rate recorded

### Acceptance criteria

Accepted only if load test script exists, p50/p95 latency is recorded, error rate is recorded, DB/vector latency is measured, performance budget is enforced, and CI/release gate fails on regression.

Reject if no p95 or no budget exists.

---

## 28. Canary / Feature Rollout

### Workflow position

```text
Feature Flag → Small User Group → Metrics → Expand / Roll Back
```

### Implementation

Include:

- feature flag
- rollout percentage
- beta group
- kill switch
- metrics
- rollback plan

### Acceptance criteria

Accepted only if feature can be enabled for beta users only, disabled users cannot access direct API, kill switch works, rollout status is logged, frontend respects flag, and backend enforces it.

Reject if feature flag is frontend-only.

---

## 29. Crash Reporting

### Workflow position

```text
Runtime Error → Crash/Error Reporter → Trace ID → Triage
```

### Implementation

Include:

- frontend crash capture
- backend error capture
- trace ID association
- no secret/PII leakage
- release mode enabled
- dashboard/export proof

### Acceptance criteria

Accepted only if frontend crash and backend error are captured, trace ID links to request, PII/secrets are masked, release mode works, and test crash proof exists.

Reject if debug-only crash reporting exists.

---

## 30. Cost Governor

### Workflow position

```text
Brain → Cost Governor → AI Router → Provider Call / Block / Cheaper Route
```

### Implementation

Include:

- per-user quota
- per-feature budget
- per-provider cost estimate
- token counting
- expensive request approval/denial
- abuse detection
- cost metrics

### Acceptance criteria

Accepted only if cost is estimated before provider call, over-quota request is blocked or downgraded, cheaper route is selected for simple task, cost metrics are logged, user isolation applies, and abuse tests pass.

Reject if provider call happens before cost check.

---

## 31. Human Review Queue

### Workflow position

```text
Brain Risk Classifier → High-Risk Flag → Human Review Queue / Caveated Response
```

### Queue high-risk items

- urgent tribunal deadline
- high-value compensation
- discrimination claim
- dismissal risk
- disability/medical-sensitive claim
- weak evidence but serious allegation
- contradictory source result
- low-confidence answer

### Acceptance criteria

Accepted only if high-risk case creates review item, user gets safe caveated response, review queue stores case summary with minimised PII, status updates, frontend shows review state where required, and direct bypass is blocked.

Reject if high-risk answer goes straight to final with no caveat.

---

## 32. Final Master Workflow

After implementation, the final lawapp workflow must be:

```text
User opens lawapp
→ secure auth/session check
→ user starts or resumes case
→ frontend sends real request
→ backend validates auth and ownership
→ Brain Algorithm starts trace
→ legal intent/domain classified
→ risk and urgency classified
→ feature entitlement checked
→ policy-as-code applied
→ prompt injection guard runs
→ PII minimisation runs
→ case memory and user facts loaded safely
→ retrieval planner decides sources
→ hybrid search runs
→ Graph RAG runs
→ legal source trust ranking runs
→ context compression runs
→ cost governor checks spend
→ AI router chooses provider/model
→ LLM drafts answer if required
→ citation validator checks support
→ hallucination validator checks claims
→ legal safety guard checks risk
→ human review queue triggered if high-risk
→ final answer or safe caveat returned
→ DB/audit/outbox updated
→ frontend displays answer, citations, warnings, next steps
→ observability trace links every stage
→ CI/CD, Docker, Kubernetes, and security gates prove the workflow
```

---

## 33. Required Final Gates

Create or update:

```bash
cd /mnt/f/lawapp || exit 1

bash scripts/lawapp/final-advanced-technologies-gate.sh
bash scripts/lawapp/final-brain-workflow-gate.sh
bash scripts/lawapp/final-security-performance-gate.sh
bash scripts/lawapp/final-end-to-end-product-gate.sh
```

These gates must fail if any technology is not integrated into the full workflow.

The gates must not use:

```bash
|| true
echo PASS
continue-on-error
mock success
static proof
```

---

## 34. Required Final Report

Create:

```text
F:\lawapp\reports\lawapp-advanced-technologies-end-to-end-signoff.md
```

The report must include:

- final verdict
- files changed
- commands run
- evidence files
- workflow trace proof
- frontend/backend/DB proof
- Brain Algorithm proof
- RAG proof
- Graph RAG proof
- hybrid search proof
- source trust ranking proof
- citation/hallucination proof
- legal safety proof
- policy-as-code proof
- AI router proof
- WASM proof
- cache proof
- Redis/Valkey proof
- OpenTelemetry proof
- security scans
- Kubernetes proof
- CI/CD proof
- release proof if applicable
- remaining blockers, if any

Final verdict can only be:

```text
READY  -  FULL ADVANCED WORKFLOW END-TO-END PROVEN
```

if every gate passes.

If any gate fails, verdict must be:

```text
NOT READY  -  ADVANCED TECHNOLOGY WORKFLOW NOT FULLY PROVEN
```

But this is not an accepted final state. Fix the blocker and rerun.

---

## 35. Final Acceptance Rule

The owner is not accepting failed, partial, blocked, local-only, mocked, or isolated component success.

Final acceptance requires:

```text
frontend + backend + DB + Brain Algorithm + AI/RAG + Graph RAG + Hybrid Search + source trust + citation validation + hallucination guard + legal safety + WASM + cache + queues + observability + security + CI/CD + Kubernetes
```

working together as one system.

No isolated acceptance.

No fake proof.

No partial sign-off.

No blocked sign-off.

Only working end-to-end proof.
