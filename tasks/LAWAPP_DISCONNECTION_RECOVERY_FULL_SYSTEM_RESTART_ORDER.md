# LAWAPP  -  DISCONNECTION RECOVERY FULL-SYSTEM RESTART ORDER
## Ultimate Restricted Aggressive Acceptance Criteria for All Functions, Features, Technologies, DBs, Wiring, Frontend, Backend, RAG, AIA, WASM, CI/CD and Kubernetes

**File name:** `LAWAPP_DISCONNECTION_RECOVERY_FULL_SYSTEM_RESTART_ORDER.md`  
**Project root:** `F:\lawapp`  
**Required location:** `F:\lawapp\tasks\LAWAPP_DISCONNECTION_RECOVERY_FULL_SYSTEM_RESTART_ORDER.md`  
**Must read first:** `F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md`  
**Must also read:** `F:\lawapp\tasks\LAWAPP_FINAL_GAP_CLOSURE_NO_STAGING_UNTIL_E2E_PROOF.md`  
**Latest report to continue from:** `F:\lawapp\reports\claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md`  
**Applies to:** Claude Code or any replacement agent after disconnection  
**Priority:** Absolute highest. No weaker report, test result, or local success can override this file.

---

# 0. FIRST ACTION AFTER DISCONNECTION

You were disconnected. Do not continue from memory.

Start again from source of truth.

Run:

```bash
cd /mnt/f/lawapp
pwd
git status --short
git rev-parse HEAD
```

Then read these files in this exact order:

```text
F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md
F:\lawapp\tasks\LAWAPP_FINAL_GAP_CLOSURE_NO_STAGING_UNTIL_E2E_PROOF.md
F:\lawapp\tasks\LAWAPP_DISCONNECTION_RECOVERY_FULL_SYSTEM_RESTART_ORDER.md
F:\lawapp\reports\claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md
```

If any task file is missing, recreate it from the user-provided content or ask the owner to copy it, but do not downgrade the acceptance criteria.

---

# 1. OWNER POSITION  -  NO FAILED, BLOCKED, PARTIAL OR ISOLATED PASS

The owner does **not** accept:

```text
failed
blocked
partial
mock-only
stub-only
simulator-only
unit-test-only
backend-only
frontend-only
DB-only
route-only
script-only
YAML-only
CI-only
local-only presented as full
technology-added-but-not-wired
feature-working-alone-but-not-end-to-end
```

## Meaning of PASS

PASS means the model/system works with **all other models, services, functions, DBs, APIs, frontend screens, backend routes, RAG, AIA, WASM, security, CI/CD, and deployment layers end to end without issues**.

A PASS must prove this chain:

```text
User journey / frontend UI
→ backend route
→ authentication / ownership / security
→ DB migration, table, index, function
→ deterministic rules engine
→ official legal data ingestion
→ hybrid RAG
→ graph RAG where applicable
→ algorithm brain
→ responsible AIA governance
→ WASM/JS where applicable
→ payment/document/upload/memory/cache where applicable
→ audit rows and trace IDs
→ frontend displays real result
→ tests pass
→ CI/CD gate passes
→ Kubernetes proof if staging is claimed
```

If one link is missing, the status is:

```text
NOT ACCEPTED
```

---

# 2. LOOP RULE  -  APPLY BEFORE, DURING, AND AFTER EVERY TASK

For every task, repeat this loop.

## 2.1 Before coding

Read:

```text
F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md
```

Then state internally:

```text
I will not accept partial work.
I will not accept isolated technology work.
I will not accept mock-only work.
I will not accept blocked work as completion.
I will wire every change through the full lawapp system.
```

## 2.2 During coding

For every change, ask:

```text
Is it wired to frontend?
Is it wired to backend?
Is it wired to DB?
Is it wired to rules?
Is it wired to official RAG?
Is it wired to algorithm brain?
Is it wired to responsible AIA?
Is it wired to WASM/JS if applicable?
Is it secured?
Is it audited?
Is it tested?
Does it survive clean Docker rebuild?
```

If any answer is no, continue fixing.

## 2.3 After coding

Run the relevant proof commands.

If any command fails:

```text
Do not report completion.
Find root cause.
Fix it.
Rerun failed command.
Rerun dependent commands.
Rerun full gate.
```

A failed command is work-in-progress, not a report.

---

# 3. CURRENT KNOWN GAPS TO CLOSE FIRST

You must continue from the latest known gap list.

## 3.1 Automate/full-bootstrap ingestion

Problem:

```text
After clean Docker start, rules auto-seed but legislation and ACAS require manual ingestion.
```

Required outcome:

```text
One command brings local system to full legal-data-ready state.
```

Create/verify:

```bash
scripts/lawapp-full-local-bootstrap.sh
```

It must:

```text
docker compose down -v
docker compose up -d --build
wait for db/backend/redis health
run legislation ingestion
run ACAS ingestion
run embeddings
verify rules count > 0
verify legislation count > 0
verify ACAS count > 0
verify source freshness
verify /health
run smoke journey
```

Required proof:

```bash
bash scripts/lawapp-full-local-bootstrap.sh
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/api/sources/freshness | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;"
```

PASS requires legal data populated and health/freshness showing real legal-data state.

---

## 3.2 Prove retrieval_audit writes

Problem:

```text
retrieval_audit writes were not confirmed.
```

Required outcome:

```text
Every retrieval path writes audit rows.
```

Must cover:

```text
/api/rag/hybrid-search
/assess
/api/brain/trace
```

Required proof:

```bash
BEFORE=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM retrieval_audit;")

curl -s http://localhost:8000/api/rag/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal time limit","claim_type":"unfair_dismissal","jurisdiction":"EW"}' | jq .

AFTER=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM retrieval_audit;")
echo "retrieval_audit: $BEFORE -> $AFTER"

python -m pytest tests/rag tests/retrieval -q
```

PASS requires audit count increase.

---

## 3.3 Fix WASM rebuild automation in CI and local setup

Problem:

```text
WASM binary exists, JS fallback works, but rebuild fails if wasm-pack is missing.
```

Required outcome:

```text
Local and CI WASM rebuild path is deterministic and documented.
```

Must create/verify:

```text
scripts/setup-wasm-toolchain.sh
scripts/rebuild-wasm.sh
CI step that installs wasm-pack
CI stale-WASM detection
tests proving backend and frontend deadline match
```

Required proof:

```bash
bash scripts/setup-wasm-toolchain.sh || true
bash scripts/rebuild-wasm.sh
npm --prefix client test
python -m pytest tests/deadlines -q
node_modules/.bin/playwright test --trace=retain-on-failure
grep -R "123543\|118223\|751\|719\|9157\|3 months\|2 years\|52 weeks" client/wasm client/js client/public --exclude-dir=node_modules || true
```

PASS requires no hardcoded legal values and a working rebuild path or CI-safe install step.

---

## 3.4 Harden Stripe test/live readiness

Problem:

```text
test_simulator works, but real Stripe keys are absent.
```

Owner keys are external, but the code must be ready.

Must prove:

```text
stripe_test mode validates config
missing STRIPE_WEBHOOK_SECRET fails closed
invalid signature rejected
valid webhook fixture writes payment_events
valid webhook fixture updates cases.payment_status
duplicate webhook is idempotent
document generation checks DB payment_status
```

Required proof:

```bash
python -m pytest tests/payment -q
python -m pytest tests/payment/test_stripe_webhook_db_update.py -q
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT id, event_id, event_type, processed, created_at FROM payment_events ORDER BY created_at DESC LIMIT 10;"
```

PASS requires DB payment state change from verified webhook fixture.

---

## 3.5 OCR must be implemented or fully excluded

Problem:

```text
OCR currently returns 501 / Phase 4 disabled.
```

Choose one.

### Option A  -  Implement OCR

Must prove:

```text
PDF extraction
DOCX extraction
image OCR if advertised
file type validation
file size validation
cross-user blocking
raw upload not sent to LLM
user confirmation before extracted facts are used
frontend journey
audit row
```

### Option B  -  Exclude OCR from acceptance

Must prove:

```text
frontend clearly says Phase 4 not enabled
route returns 501
reports do not claim OCR complete
product does not advertise OCR as working
tests prove disabled state
```

Required proof for exclusion:

```bash
python -m pytest tests/uploads tests/document_intelligence -q
grep -R "OCR accepted\|OCR complete\|extraction accepted\|document extraction working" reports client backend --exclude-dir=node_modules --exclude-dir=.git || true
```

PASS means either OCR works end to end or is clearly excluded. Do not mark disabled OCR as accepted.

---

## 3.6 Quarantine legacy IterLaw

Problem:

```text
legacy IterLaw directory/naming may still exist.
```

Required outcome:

```text
No active lawapp deploy path references IterLaw, RightsNow, or old project names.
```

Required proof:

```bash
find infra .github scripts -type f -exec grep -Il "IterLaw\|iterlaw\|RightsNow\|rightsnow" {} \; || true
```

If old files remain, move them to:

```text
archive/legacy/
```

with a README saying they are not active and not applied.

PASS requires no active deploy/CI path using old names.

---

## 3.7 Create ready-to-run owner gates

Create these scripts:

```text
scripts/verify-real-ai.sh
scripts/verify-stripe-live-ready.sh
scripts/verify-lawapp-k8s-staging.sh
```

### Real AI gate

Must check:

```text
ANTHROPIC_API_KEY exists
backend can start in real AI mode
/health shows ai_provider.active=true
assessment is de-identified
citations still required
no uncited confident answer
```

### Real Stripe gate

Must check:

```text
STRIPE_SECRET_KEY exists
STRIPE_WEBHOOK_SECRET exists
stripe_test checkout works
webhook signature verifies
payment_events updated
case payment_status updated
document generation allowed only after paid state
duplicate webhook safe
```

### Kubernetes staging gate

Must run:

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

If kubeconfig is absent, the script must fail clearly and say:

```text
Kubernetes not proven. Do not claim staging ready.
```

---

# 4. FULL LAWAPP FEATURE AND TECHNOLOGY RECAP

You must audit and prove every major lawapp area, not only the seven gaps.

## 4.1 Backend

Must verify:

```text
/health
/auth/register
/auth/token
/auth/me
/assess
/cases
/cases/{id}
/documents/generate
/api/documents/{id}/download
/rules/{claim_type}
/api/rules/{claim_type}
/api/deadline/calculate
/freshness
/api/sources/freshness
/api/payment/create-session
/api/payment/webhook
/api/payment/status
/api/brain/trace
/api/rag/hybrid-search
/api/rag/graph
/api/evaluate
/api/mcp/tools
/api/memory/save
/api/cache/test
/handoff/leads
upload routes
extract route or disabled state
```

Each route must have:

```text
auth where required
ownership where required
DB read/write where required
audit where required
tests
```

## 4.2 Frontend

Must verify:

```text
landing
register
login
intake
assessment
dashboard
saved case
success
cancel
payment UI
document UI
handoff UI
deadline UI
citations UI
OCR disabled/active UI
legal notice on all relevant pages
```

No dead button. No hidden mock path.

## 4.3 Databases

Must verify:

```text
users
cases
documents
rules
legislation
acas_guidance
case_law_chunks
legal_nodes
legal_edges
brain_traces
retrieval_audit
rag_citation_bundles
aia_governance_checks
safety_boundary_checks
context_compression_log
evaluation_results
mcp_tool_calls
semantic_cache
legal_memory
payment_events
handoff_leads
routing_decisions
source_freshness
```

## 4.4 New technologies

Must verify:

```text
Agentic 19-step brain
Hybrid RAG
Graph RAG
Knowledge graph
Context compression
Memory engine
Evaluation AI
MCP connectors
AI router
Semantic cache
Redis rate limiting
Stripe payments
WASM/JS fallback
Legal ingestion
Source freshness
Security regression
CI/CD
Kubernetes manifests and staging gate
```

## 4.5 Responsible AIA

Must control answers, not just exist.

Must block/downgrade:

```text
no citation
unofficial-only source
reserved activity
outcome guarantee
low confidence
missing jurisdiction
stale source
PII exposure
model-generated deadline/cap
```

---

# 5. FULL COMMAND GATE

After fixes, run:

```bash
set -euo pipefail

bash scripts/lawapp-full-local-bootstrap.sh

python -m pytest -q
python -m pytest tests/security -q
python -m pytest tests/aia_governance -q
python -m pytest tests/rag -q
python -m pytest tests/retrieval -q
python -m pytest tests/ingestion -q
python -m pytest tests/payment tests/documents -q

bash scripts/rebuild-wasm.sh
npm --prefix client test
node_modules/.bin/playwright test --trace=retain-on-failure

bash scripts/smoke_local_journey.sh
bash scripts/security-regression.sh
bash scripts/push-and-deploy.sh --dry-run
```

Then:

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM retrieval_audit;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rag_citation_bundles;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM brain_traces;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM aia_governance_checks;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;"
```

If any command fails, do not claim completion.

---

# 6. FINAL REPORT REQUIRED

Create:

```text
F:\lawapp\reports\claude-lawapp-disconnection-recovery-full-system-proof.md
```

The report must include:

```text
1. Confirmation all three task files were read
2. Commit hash and branch
3. Disconnection recovery summary
4. All seven gap fixes
5. Full lawapp feature matrix
6. Backend route matrix
7. Frontend wiring matrix
8. DB/function matrix
9. New technology matrix
10. Responsible AIA matrix
11. WASM proof
12. Stripe proof
13. OCR decision proof
14. Ingestion/bootstrap proof
15. Retrieval audit proof
16. Legacy naming proof
17. Owner gate scripts proof
18. Full command output
19. DB/audit counts
20. Final classification
```

Allowed classifications:

```text
NOT ACCEPTED
LOCAL DEMO READY - FULL LOCAL BOOTSTRAP PROVEN
STAGING READY - ONLY IF KUBERNETES AND REAL CONFIG GATES PASS
PRODUCTION READY - ONLY IF LIVE AI, LIVE STRIPE, COMPLIANCE, MONITORING, BACKUP AND SECURITY GATES PASS
```

No other wording.

---

# 7. FINAL OWNER ORDER

You were disconnected. Restart properly.

Do not continue from memory.

Read the loop files.

Apply the full restrictive criteria.

Close all gaps.

Audit all lawapp features, functions, technologies, DBs, wiring, frontend, backend, security, CI/CD, and Kubernetes gates.

If anything is failed, blocked, partial, mock-only, or isolated, it is not accepted.

PASS means the model/system works with every other model/service/function end to end without issues.

Fix, rerun, and prove.
