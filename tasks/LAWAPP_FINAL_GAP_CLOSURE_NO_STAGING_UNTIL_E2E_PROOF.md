# LAWAPP  -  FINAL GAP-CLOSURE ORDER AFTER CLAUDE LOCAL DEMO REPORT
## No Staging Claim Until Integrated Proof Passes

**File name:** `LAWAPP_FINAL_GAP_CLOSURE_NO_STAGING_UNTIL_E2E_PROOF.md`  
**Project root:** `F:\lawapp`  
**Required location:** `F:\lawapp\tasks\LAWAPP_FINAL_GAP_CLOSURE_NO_STAGING_UNTIL_E2E_PROOF.md`  
**Must read first:** `F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md`  
**Report being challenged:** `F:\lawapp\reports\claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md`

---

# 0. FIRST COMMAND

Claude must read this before doing any more work:

```text
F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md
```

Then read:

```text
F:\lawapp\reports\claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md
```

Then execute this order.

---

# 1. OWNER VERDICT ON CURRENT REPORT

The current report is accepted only as:

```text
LOCAL DEMO READY  -  LIMITED ACCEPTANCE
```

It is **not** accepted as:

```text
FULL END-TO-END ACCEPTED
STAGING READY
PRODUCTION CANDIDATE
PRODUCTION READY
```

The report itself admits:

```text
STAGING READY: NO
PRODUCTION CANDIDATE: NO
PRODUCTION READY: NO
```

The report also admits:

```text
WASM rebuild fails because wasm-pack is missing
legal ingestion is not automatic after clean Docker
retrieval_audit writes are not confirmed
Stripe live mode is not proven
OCR is honestly disabled
Kubernetes is not proven
real Anthropic key is missing
real Stripe keys are missing
FCL case law licence is missing
DPIA, legal review, pentest are missing
```

Therefore the next task is to close every code-side gap and prepare owner-only gates with fail-closed proof.

---

# 2. NO MORE “PARTIAL ACCEPTED” WORDING

Claude must stop marking anything as `ACCEPTED` if the same row says:

```text
PARTIAL
requires ingestion
needs manual step
not confirmed
not automatic
not deployed
not implemented
not proven
requires owner action
```

Allowed status values from now on:

```text
PASS - FULL E2E PROVEN
LOCAL DEMO PASS ONLY
PARTIAL - NOT ACCEPTED
EXTERNAL BLOCKER - NOT ACCEPTED
FAIL - NOT ACCEPTED
```

Example:

```text
Hybrid RAG with data, but not automatic after clean Docker = PARTIAL - NOT ACCEPTED
WASM binary exists, rebuild fails = PARTIAL - NOT ACCEPTED
Stripe test simulator works, live keys absent = LOCAL DEMO PASS ONLY
OCR 501 disabled = NOT IN ACTIVE SCOPE, not accepted as OCR
Kubernetes manifests exist, kubeconfig absent = EXTERNAL BLOCKER - NOT STAGING
```

---

# 3. IMMEDIATE CODING GAPS TO CLOSE

## 3.1 Automate or hard-gate legal ingestion

Current report says:

```text
After clean Docker start, legislation=0 and acas=0.
Manual ingestion is required.
```

This is not acceptable for an end-to-end acceptance gate.

Claude must implement one of these:

### Option A  -  Automatic dev/test ingestion

After clean Docker start, a documented script must bring the full local demo to ready state in one command:

```bash
bash scripts/lawapp-full-local-bootstrap.sh
```

This script must:

```text
docker compose down -v
docker compose up -d --build
wait for db/backend/redis health
run legislation ingestion
run ACAS ingestion
run embeddings
verify rules count
verify legislation count
verify ACAS count
verify source freshness
run smoke journey
```

### Option B  -  Application refuses RAG-ready claim until ingestion done

If ingestion is not automatic, `/health` and `/api/sources/freshness` must expose:

```json
{
  "legal_data_ready": false,
  "required_action": "run ingestion",
  "legislation_rows": 0,
  "acas_rows": 0
}
```

And `/assess` must return:

```text
insufficient_grounding
```

with a clear audit row.

### Required proof

```bash
bash scripts/lawapp-full-local-bootstrap.sh
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/api/sources/freshness | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;"
```

Acceptance:

```text
No manual hidden step.
No RAG-ready claim with empty data.
No confident answer when legal data empty.
```

---

## 3.2 Confirm retrieval_audit writes

Current report says:

```text
retrieval_audit writes not confirmed in hybrid search path
```

This is a code-side gap.

Claude must:

```text
ensure /api/rag/hybrid-search writes retrieval_audit
ensure /assess writes retrieval_audit
ensure /api/brain/trace writes retrieval_audit
store query, claim_type, jurisdiction, source counts, citations count, insufficient_grounding, created_at
add tests proving audit count increases
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

Acceptance:

```text
audit count must increase.
empty/no audit = FAIL.
```

---

## 3.3 Fix WASM rebuild automation

Current report says:

```text
bash scripts/rebuild-wasm.sh fails because wasm-pack not installed
```

That is not full acceptance.

Claude must implement CI-safe WASM build.

Required work:

```text
Add wasm-pack install step to CI
Add local setup script or bootstrap install check
Add stale-WASM detection
Ensure JS fallback remains
Ensure backend and WASM deadline results match
```

Required proof:

```bash
bash scripts/setup-wasm-toolchain.sh || true
bash scripts/rebuild-wasm.sh
npm --prefix client test
python -m pytest tests/deadlines -q
node_modules/.bin/playwright test --trace=retain-on-failure
```

Acceptance:

```text
WASM rebuild passes locally or CI script proves install step.
No legal values hardcoded in WASM/client.
Backend and frontend deadline match.
```

---

## 3.4 Stripe live-mode readiness without real live keys

Current report says:

```text
Stripe live keys absent; live mode untestable.
```

Owner keys are external, but code can still be hardened.

Claude must prove:

```text
stripe_test mode can run with test key environment variables
missing STRIPE_WEBHOOK_SECRET fails closed
invalid signature rejected
valid test webhook updates payment_events
valid test webhook updates cases.payment_status
duplicate webhook is idempotent
document generation checks DB status
```

Required proof:

```bash
python -m pytest tests/payment -q
python -m pytest tests/payment/test_stripe_webhook_db_update.py -q
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT id, event_id, event_type, processed, created_at FROM payment_events ORDER BY created_at DESC LIMIT 10;"
```

Acceptance:

```text
test_simulator is local-demo only.
stripe_test path must be code-proven with test fixtures.
live keys missing = external blocker, not code blocker.
```

---

## 3.5 OCR must be either implemented or excluded everywhere

Current report says:

```text
OCR is honestly disabled  -  501 Not Implemented
```

That is acceptable only if OCR is not claimed as completed.

Claude must choose one:

### Option A  -  Implement Phase 4 OCR

Prove PDF/DOCX/image extraction with tests and frontend journey.

### Option B  -  Exclude OCR from all readiness claims

Keep route 501 and ensure:

```text
frontend says not enabled
reports do not list OCR as accepted
product does not advertise OCR
tests confirm disabled state
```

Required proof for Option B:

```bash
python -m pytest tests/uploads tests/document_intelligence -q
grep -R "OCR accepted\|OCR complete\|extraction accepted\|document extraction working" reports client backend --exclude-dir=node_modules --exclude-dir=.git || true
```

Acceptance:

```text
disabled is acceptable only as NOT IN ACTIVE SCOPE.
Do not mark OCR accepted.
```

---

## 3.6 Remove or quarantine legacy IterLaw directory

Current report says:

```text
IterLaw naming found in infra/k8s/iterlaw/
```

Claude must either:

```text
delete legacy directory if not used
or move to archive/legacy with README stating not active
or update CI/security scan to ignore archived legacy only
```

Required proof:

```bash
find infra -iname "*iterlaw*" -o -type f -exec grep -Il "IterLaw\|iterlaw\|RightsNow\|rightsnow" {} \;
```

Acceptance:

```text
No active manifests use old names.
No deploy script applies old namespace.
No CI workflow references old names.
```

---

# 4. OWNER-SUPPLIED BLOCKERS MUST HAVE READY GATES

Claude cannot supply:

```text
real Anthropic key
real Stripe keys
Talos kubeconfig
FCL licence
DPIA approval
pentest approval
```

But Claude must provide ready-to-run gates for each.

## 4.1 Real AI gate

Create:

```bash
bash scripts/verify-real-ai.sh
```

It must:

```text
check ANTHROPIC_API_KEY exists
start backend in real-ai mode
call /health
confirm ai_provider.active=true
run one de-identified assessment
confirm no raw PII sent
confirm citations still required
confirm no uncited confident answer
```

## 4.2 Real Stripe gate

Create:

```bash
bash scripts/verify-stripe-live-ready.sh
```

It must:

```text
check STRIPE_SECRET_KEY
check STRIPE_WEBHOOK_SECRET
create test checkout session in stripe_test mode
verify webhook signature with fixture
update payment_events
update case payment_status
generate document after paid status
reject duplicate event
```

## 4.3 Kubernetes staging gate

Create:

```bash
bash scripts/verify-lawapp-k8s-staging.sh
```

It must run:

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

Acceptance:

```text
If kubeconfig absent, script fails with clear message.
If wrong cluster context, script fails.
If pods unhealthy, script fails.
No staging claim without this script passing.
```

---

# 5. NEW FINAL GATE AFTER FIXES

Claude must run:

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

Then prove DB and audit state:

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

---

# 6. NEW REPORT REQUIRED

Create:

```text
F:\lawapp\reports\claude-lawapp-final-gap-closure-after-local-demo.md
```

Report must include:

```text
1. Confirmation loop rulebook was read
2. Confirmation current local-demo report was read
3. Exact commit hash
4. Fixed coding gaps
5. Full local bootstrap proof
6. Ingestion readiness proof
7. RAG audit write proof
8. WASM rebuild proof
9. Stripe test/live-readiness proof
10. OCR scope decision proof
11. Legacy naming proof
12. Owner-blocker gates created
13. Full command gate output
14. DB/audit counts
15. Final classification
```

Allowed classifications:

```text
LOCAL DEMO READY - FULL LOCAL BOOTSTRAP PROVEN
STAGING READY - ONLY IF KUBERNETES + REAL CONFIG GATES PASS
PRODUCTION READY - ONLY IF LIVE AI + LIVE STRIPE + COMPLIANCE + MONITORING + BACKUP PASS
NOT ACCEPTED
```

---

# 7. SHORT ORDER TO CLAUDE

Use this message:

```text
Claude, read the permanent loop rulebook first:

F:\lawapp\tasks\LAWAPP_PERMANENT_LOOP_ACCEPTANCE_RULEBOOK.md

Then read your latest report:

F:\lawapp\reports\claude-lawapp-aggressive-new-tech-end-to-end-acceptance-report.md

Then execute:

F:\lawapp\tasks\LAWAPP_FINAL_GAP_CLOSURE_NO_STAGING_UNTIL_E2E_PROOF.md

Your report is accepted only as LOCAL DEMO READY. It is not staging ready. Close every code-side gap: automate/full-bootstrap ingestion, prove retrieval_audit writes, fix WASM rebuild automation, harden Stripe test/live readiness, explicitly exclude or implement OCR, quarantine legacy IterLaw, and create ready-to-run gates for real AI, real Stripe, and Kubernetes.

No partial accepted. No staging claim until Kubernetes and real config gates pass.
```

---

# 8. FINAL OWNER RULE

Do not argue.

Do not downgrade the acceptance criteria.

Do not call manual ingestion a full local acceptance unless the bootstrap script runs it.

Do not call WASM accepted while rebuild fails.

Do not call RAG accepted while retrieval_audit writes are unconfirmed.

Do not call OCR accepted while it returns 501.

Do not call Stripe accepted while only test_simulator is proven.

Do not call staging ready without Kubernetes proof.

Fix the code-side gaps, prepare the owner-gates, rerun the full proof, and report honestly.
