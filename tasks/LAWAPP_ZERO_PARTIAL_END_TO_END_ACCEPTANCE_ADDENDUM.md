# LAWAPP — ZERO-PARTIAL ACCEPTANCE ADDENDUM
## End-to-End Integration Only, No Mock-Only PASS, No Isolated Technology PASS

**File name:** `LAWAPP_ZERO_PARTIAL_END_TO_END_ACCEPTANCE_ADDENDUM.md`  
**Project root:** `F:\lawapp`  
**Target location:** `F:\lawapp\tasks\LAWAPP_ZERO_PARTIAL_END_TO_END_ACCEPTANCE_ADDENDUM.md`  
**Applies from:** Immediately  
**Priority:** This overrides any weaker acceptance wording in previous reports, tasks, or Claude replies.

---

# 0. ABSOLUTE NON-NEGOTIABLE POSITION

The owner does **not** accept:

- failed gates,
- blocked gates,
- partial completion,
- mocked-only completion,
- isolated feature completion,
- “technology exists but not wired” completion,
- “backend ready but frontend not wired” completion,
- “frontend ready but backend mocked” completion,
- “DB exists but not used by algorithm/RAG” completion,
- “RAG exists but not connected to official data” completion,
- “AIA governance exists but does not control the answer” completion,
- “WASM exists but not used in the live user flow” completion,
- “tests pass against fake fixtures only” completion,
- “local demo ready” presented as full readiness,
- “blocked by owner” where code can still be improved,
- “blocked by external system” without a working fallback, queue, retry, clear error, audit log, and proof.

Acceptance means the feature works **inside the full lawapp system**, with all dependent technologies wired together, using real DB state, real APIs where available, real backend endpoints, real frontend screens, real security checks, real audit rows, and real proof commands.

A feature is not accepted because its individual unit test passes.

A feature is accepted only when it works through the complete chain:

```text
Frontend UI
→ Backend API
→ Authentication / ownership
→ DB function / table / migration
→ Algorithm brain
→ Rules engine
→ Official-source RAG
→ Citation bundle
→ Responsible AIA governance
→ WASM/JS where applicable
→ Final user response
→ Audit logs
→ Security controls
→ End-to-end tests
→ CI/CD gate
→ Kubernetes proof if staging is claimed
```

No exception.

---

# 1. DEFINITION OF “DONE”

Claude must use this definition.

A task is **DONE** only when all of the following are true:

1. The code exists.
2. The database schema exists.
3. The database migration runs from a clean DB.
4. The backend route exists.
5. The backend route uses the real DB, not an in-memory fake.
6. The frontend calls the backend route.
7. The user can trigger it from the UI.
8. The algorithm/RAG/AIA layer uses it where required.
9. The feature writes audit evidence to the DB.
10. The feature is covered by unit tests.
11. The feature is covered by integration tests.
12. The feature is covered by at least one end-to-end journey.
13. The feature is covered by failure-path tests.
14. Security/ownership is enforced.
15. No mock/stub/demo path is used in the acceptance journey unless the feature is explicitly marked “not production feature”.
16. CI runs the relevant tests.
17. The final report includes raw command output.
18. The same proof works after:

```bash
docker compose down -v
docker compose up -d --build
```

If any item above is false, the feature is **NOT DONE**.

---

# 2. FORBIDDEN ACCEPTANCE LANGUAGE

Claude must not use these phrases unless the full gate passes:

```text
complete
finished
ready
fully wired
production ready
staging ready
accepted
done
all working
end-to-end working
final sign-off
```

Claude may only use:

```text
local demo only
partial implementation
not accepted
blocked by external licence
blocked by missing owner secret
code blocker remains
integration blocker remains
security blocker remains
frontend wiring blocker remains
DB wiring blocker remains
```

But if a blocker exists, Claude must also provide:

```text
exact file
exact failing command
exact error output
root cause
fix plan
whether Claude can fix it now
next command to rerun
```

---

# 3. MOCKS, STUBS, SIMULATORS AND FIXTURES

## 3.1 Mock-only pass is forbidden

A mock, stub, simulator, fixture, or fake response may be used only for development and unit tests.

It cannot be used as acceptance proof for a real feature.

## 3.2 Any mock must be labelled

All mock/stub/demo/simulator code must be clearly named and isolated:

```text
mock_*
stub_*
demo_*
simulator_*
fixture_*
```

## 3.3 Production/staging routes must fail closed

If real configuration is missing, production/staging routes must not silently use mocks.

They must return a controlled error and write an audit row.

Example:

```text
Real Stripe mode without webhook secret → 503 fail closed
Real AI mode without API key → controlled unavailable response
Official source ingestion unavailable → clear ingestion failure, no fake legal rows
RAG without sources → insufficient_grounding, not generated answer
```

## 3.4 Proof command

```bash
grep -R "mock\|stub\|fake\|placeholder\|simulator\|TODO\|NotImplemented" backend client ingestion shared tests .github scripts --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next || true
```

Acceptance:

- Every result must be explained.
- Any mock in production route = FAIL.
- Any placeholder in user-facing flow = FAIL unless visibly disabled and excluded from readiness.
- Any hidden fallback to fake data = FAIL.

---

# 4. END-TO-END FEATURE ACCEPTANCE MATRIX

Claude must create and complete this matrix in the final report.

Each row must show:

```text
Feature
Frontend page/component
Backend route
DB tables/functions
Algorithm/RAG/AIA involvement
WASM involvement if any
Audit table written
Security control
Test command
Raw proof result
Status
```

Minimum required rows:

```text
User registration
User login
User profile / auth me
Guided intake
Rules fetch
Deadline calculation
ACAS EC calculation
WASM deadline calculation
Backend deadline validation
Free assessment
Official-source RAG retrieval
Citation bundle creation
Responsible AIA governance check
Structured assessment rendering
Weakness/honesty display
Source freshness display
Case save
Dashboard case list
Saved case open
Document generation
Payment session
Payment webhook
Payment status update
Document download
Handoff lead capture
Upload route
OCR/extraction if enabled
OCR disabled UI if not enabled
Memory save with consent
Semantic cache without PII
Graph RAG
Evaluation AI
MCP connectors if present
Kubernetes health if staging claimed
```

A row cannot be marked PASS unless every column is real and proven.

---

# 5. OFFICIAL DATA + RAG + AIA ACCEPTANCE

## 5.1 Legal answer chain

Every UK employment-law answer must prove this chain:

```text
user question
→ classify claim/intention
→ select jurisdiction
→ fetch deterministic rules from DB
→ retrieve official sources from DB
→ run hybrid search
→ build citation bundle
→ run algorithm brain
→ run responsible AIA governance
→ return answer with citations
→ write brain trace
→ write retrieval audit
→ write governance audit
```

## 5.2 Required DB audit rows

After an assessment, these counts must increase:

```text
retrieval_audit
rag_citation_bundles
brain_traces
aia_governance_checks
safety_boundary_checks
```

Proof:

```bash
BEFORE_RETRIEVAL=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM retrieval_audit;")
BEFORE_BUNDLES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM rag_citation_bundles;")
BEFORE_TRACES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM brain_traces;")
BEFORE_AIA=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM aia_governance_checks;")

curl -s http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/unfair_dismissal_case.json | jq .

AFTER_RETRIEVAL=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM retrieval_audit;")
AFTER_BUNDLES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM rag_citation_bundles;")
AFTER_TRACES=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM brain_traces;")
AFTER_AIA=$(docker compose exec -T db psql -U lawapp -d lawapp -tAc "SELECT COUNT(*) FROM aia_governance_checks;")

echo "retrieval_audit: $BEFORE_RETRIEVAL -> $AFTER_RETRIEVAL"
echo "rag_citation_bundles: $BEFORE_BUNDLES -> $AFTER_BUNDLES"
echo "brain_traces: $BEFORE_TRACES -> $AFTER_TRACES"
echo "aia_governance_checks: $BEFORE_AIA -> $AFTER_AIA"
```

Acceptance:

- Counts must increase.
- Answer must include official citations.
- Answer must include deterministic rules used.
- AIA decision must be present.
- If citations are empty, answer must be blocked or downgraded.
- No source = no confident answer.

---

# 6. FAST DB ACCEPTANCE IS NOT TABLE EXISTENCE

The DB is not accepted because tables exist.

The DB is accepted only when:

1. Clean migrations create the schema.
2. Official ingestion populates legal data.
3. Rules table is effective-dated and cited.
4. DB functions return correct data.
5. RAG queries use the DB.
6. Algorithm uses the DB output.
7. Frontend displays output derived from DB.
8. Audit tables prove use.
9. Performance is acceptable.
10. CI verifies the above from clean DB.

## 6.1 Required proof

```bash
docker compose down -v
docker compose up -d --build

docker compose exec -T db psql -U lawapp -d lawapp -c "\dt"
docker compose exec -T db psql -U lawapp -d lawapp -c "\df"
docker compose exec -T db psql -U lawapp -d lawapp -c "\di"

docker compose run --rm ingestion python -m ingestion.legislation.ingest --strict --claim-type unfair_dismissal
docker compose run --rm ingestion python -m ingestion.acas.ingest --strict
docker compose run --rm ingestion python -m ingestion.govuk.ingest --strict --topic employment_tribunal

docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM get_source_freshness();"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM get_current_rules('unfair_dismissal','EW',CURRENT_DATE);"
docker compose exec -T db psql -U lawapp -d lawapp -c "EXPLAIN ANALYZE SELECT * FROM search_legal_chunks('unfair dismissal time limit','unfair_dismissal','EW',CURRENT_DATE,10);"
```

Acceptance:

- No migration failure.
- No empty official data after strict ingestion.
- No missing DB functions.
- No search function failure.
- No uncited rules.
- No unacceptable slow query.
- No feature can bypass the DB with hardcoded legal data.

---

# 7. FRONTEND ↔ BACKEND ACCEPTANCE

Frontend is not accepted because pages exist.

Backend is not accepted because routes exist.

Acceptance requires real user journey proof.

## 7.1 Required frontend journey

Playwright must prove:

```text
open landing page
register real test user
login
open intake
enter unfair-dismissal facts
frontend fetches rules
frontend calculates deadline using WASM/JS
backend validates deadline
submit assessment
backend retrieves official sources
RAG returns citation bundle
algorithm brain returns structured assessment
responsible AIA allows/downgrades/blocks
assessment page displays:
  - claim status
  - weaknesses
  - deadline
  - official citations
  - source freshness
  - legal boundary notice
save case
open dashboard
open saved case
generate document
payment gate behaves correctly
download document if payment accepted
submit handoff lead if beyond self-help
```

## 7.2 Required proof

```bash
node_modules/.bin/playwright test --trace=retain-on-failure
bash scripts/smoke_local_journey.sh
```

Acceptance:

- Every screen must use backend data.
- No screen can use hardcoded assessment data.
- No screen can hide missing citations.
- No dead buttons.
- No console errors.
- No failed network calls.
- No mocked API in acceptance run.

---

# 8. WASM ACCEPTANCE

WASM is not accepted because a `.wasm` file exists.

WASM is accepted only when:

1. Built from source.
2. Used by the live frontend.
3. Receives rule values from backend.
4. Contains no legal values.
5. Produces same deadline as backend.
6. JS fallback produces same result.
7. Playwright proves live use.

Proof:

```bash
bash scripts/rebuild-wasm.sh
npm --prefix client test
node_modules/.bin/playwright test tests/e2e/deadline-wasm.spec.ts --trace=retain-on-failure
curl -s http://localhost:8000/api/deadline/calculate -H "Content-Type: application/json" -d @tests/fixtures/deadline_case_ec_floor.json | jq .
grep -R "123543\|118223\|751\|719\|9157\|3 months\|2 years\|52 weeks" client/wasm client/js client/public --exclude-dir=node_modules || true
```

Acceptance:

- WASM and backend result match.
- No hardcoded legal values.
- Live UI uses it.
- Fallback works.
- Deadline citations are shown.

---

# 9. RESPONSIBLE AIA ACCEPTANCE

Responsible AIA is not accepted because a function exists.

It is accepted only when it controls the answer.

## 9.1 Required block tests

Responsible AIA must block or downgrade:

```text
no citations
unofficial source only
reserved activity language
outcome guarantee
missing jurisdiction
stale legal source
low confidence
personal data leaving boundary
deadline generated by model
case law claim when case law corpus empty
```

Proof:

```bash
python -m pytest tests/aia_governance -q
curl -s http://localhost:8000/api/aia/governance/check -H "Content-Type: application/json" -d @tests/fixtures/aia/no_citations.json | jq .
curl -s http://localhost:8000/api/aia/governance/check -H "Content-Type: application/json" -d @tests/fixtures/aia/reserved_activity.json | jq .
curl -s http://localhost:8000/api/aia/governance/check -H "Content-Type: application/json" -d @tests/fixtures/aia/unofficial_source_only.json | jq .
```

Acceptance:

- unsafe answers are blocked.
- weak answers are downgraded.
- safe answers are allowed.
- every decision writes an audit row.
- frontend displays downgraded/blocked status honestly.

---

# 10. PAYMENT + DOCUMENT ACCEPTANCE

Payment is not accepted because a test token exists.

Document generation is not accepted because a file downloads.

Acceptance requires:

```text
case exists
user owns case
assessment exists
payment required for paid document
payment session created
payment event recorded
webhook verified
payment status updated in DB
document generated from real case facts
document has legal boundary notice
download requires ownership
cross-user download blocked
frontend journey proves it
```

Proof:

```bash
python -m pytest tests/payment tests/documents -q
bash scripts/smoke_local_journey.sh
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM payment_events ORDER BY created_at DESC LIMIT 5;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT id, case_id, doc_type, is_user_upload, created_at FROM documents ORDER BY created_at DESC LIMIT 5;"
```

Acceptance:

- no forged payment.
- no cross-user document access.
- no document from fake facts.
- payment DB state changes correctly.

---

# 11. BLOCKERS ARE NOT ACCEPTANCE

If Claude says “blocked”, that is not acceptance.

A blocker is acceptable only if it is truly outside Claude’s control and all internal work is complete.

For every blocker, Claude must provide:

```text
Blocker name
Why it is outside Claude's control
What code was still completed
What fallback exists
What user sees
What audit log is written
What command proves the blocker
What command should be rerun after blocker removed
```

Examples:

```text
Find Case Law computational-analysis licence not granted
Real Stripe keys not provided
Real Anthropic key not provided
Cluster kubeconfig not available
```

But Claude must still implement:

```text
licence gate
config validation
fail-closed behaviour
audit logs
clear UI state
tests
```

A blocker without working fail-closed handling = FAIL.

---

# 12. FINAL SINGLE ACCEPTANCE GATE

Claude must run this exact gate before any completion claim:

```bash
set -euo pipefail

docker compose down -v
docker compose up -d --build

docker compose run --rm ingestion python -m ingestion.legislation.ingest --strict --claim-type unfair_dismissal
docker compose run --rm ingestion python -m ingestion.acas.ingest --strict
docker compose run --rm ingestion python -m ingestion.govuk.ingest --strict --topic employment_tribunal

python -m pytest -q
python -m pytest tests/security -q
python -m pytest tests/aia_governance -q
python -m pytest tests/rag -q
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
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM legislation_chunks;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM acas_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM govuk_guidance;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM retrieval_audit;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rag_citation_bundles;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM brain_traces;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM aia_governance_checks;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM get_source_freshness();"
```

Acceptance:

- any failed command = NOT ACCEPTED.
- any empty required official data table after strict ingestion = NOT ACCEPTED.
- any uncited legal answer = NOT ACCEPTED.
- any mock-only acceptance = NOT ACCEPTED.
- any feature not wired end to end = NOT ACCEPTED.
- any security failure = NOT ACCEPTED.
- any frontend/backend mismatch = NOT ACCEPTED.

---

# 13. FINAL REPORT REQUIRED

Claude must create:

```text
reports/claude-lawapp-zero-partial-end-to-end-integration-proof.md
```

The report must include:

1. Exact commit hash.
2. Exact branch.
3. Clean Docker proof.
4. Official ingestion proof.
5. DB counts and functions proof.
6. Rules proof.
7. RAG proof.
8. Algorithm brain proof.
9. Responsible AIA proof.
10. WASM proof.
11. Frontend/backend wiring proof.
12. Payment/document proof.
13. Security proof.
14. CI/CD proof.
15. Kubernetes proof if staging is claimed.
16. Full feature acceptance matrix.
17. Every blocker with required blocker format.
18. Final classification.

Allowed final classifications only:

```text
NOT ACCEPTED
LOCAL DEMO ONLY - NOT FULLY ACCEPTED
STAGING READY - FULL E2E PROVEN
PRODUCTION READY - FULL LIVE GATES PROVEN
```

Claude must not invent a softer classification.

---

# 14. FINAL COMMAND TO CLAUDE

Read this carefully:

The owner does not accept failed, blocked, partial, isolated, or mock-only completion.

The acceptance criteria mean the whole lawapp system works together end to end.

You must prove every feature through the real chain:

```text
frontend
backend
DB
rules
official RAG
algorithm brain
responsible AIA
WASM where applicable
security
audit logs
CI/CD
Kubernetes if staging claimed
```

If one part is missing, the feature is not accepted.

Fix it, rerun the gate, and report the raw proof.
