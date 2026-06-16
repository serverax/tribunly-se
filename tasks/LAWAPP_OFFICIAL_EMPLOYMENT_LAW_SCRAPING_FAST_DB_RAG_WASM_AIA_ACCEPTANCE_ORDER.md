# LAWAPP  -  RESTRICTED OFFICIAL UK EMPLOYMENT LAW SCRAPING, FAST DATABASE, RAG, ALGORITHM, WASM AND RESPONSIBLE AIA ACCEPTANCE ORDER

**File name:** `LAWAPP_OFFICIAL_EMPLOYMENT_LAW_SCRAPING_FAST_DB_RAG_WASM_AIA_ACCEPTANCE_ORDER.md`  
**Project root:** `F:\lawapp`  
**Target location:** `F:\lawapp\tasks\LAWAPP_OFFICIAL_EMPLOYMENT_LAW_SCRAPING_FAST_DB_RAG_WASM_AIA_ACCEPTANCE_ORDER.md`  
**Applies from:** Now  
**Owner instruction:** No negotiation. No fake PASS. No incomplete wiring. No local-only claim unless clearly marked local-only.

---

## 0. ABSOLUTE ORDER

Claude Code must now implement and prove the full official UK employment-law data spine and wire it end to end into:

- official-source scraping/ingestion,
- fast PostgreSQL + pgvector databases,
- deterministic `rules`,
- algorithm brain,
- hybrid RAG,
- graph RAG,
- responsible AIA governance,
- WASM/JS deadline logic,
- backend APIs,
- frontend UI,
- CI/CD,
- Kubernetes namespaces,
- audit logs,
- security gates,
- end-to-end user journeys.

The system must not answer UK employment-law questions from model memory.

Every user answer must be controlled by:

1. classification,
2. official source retrieval,
3. deterministic rules lookup,
4. RAG citation bundle,
5. responsible AIA governance,
6. legal-boundary filter,
7. confidence and grounding scoring,
8. final cited response.

If the system cannot retrieve official authority, it must say it cannot answer confidently. It must not invent.

---

## 1. SCRAPE EVERYWHERE  -  BUT AUTHORITY MUST BE CONTROLLED

### 1.1 Meaning of “scrape everywhere”

The crawler may discover and inspect broadly across the web only for discovery, monitoring, and source discovery.

But the lawapp legal-answer engine may only treat the following as **authority**:

1. `legislation.gov.uk`
2. National Archives Find Case Law / official case law services
3. ACAS official pages
4. GOV.UK official employment tribunal and employment rights pages
5. Judiciary UK official employment tribunal guidance and practice directions
6. HMCTS official tribunal forms and guidance
7. Official statutory instruments and official PDF/HTML publications from UK government domains
8. Any other official UK government, tribunal, regulator, or public authority source explicitly added to the allowlist.

Non-official sources may be used only as discovery hints. They must never be used as legal authority for a user-facing answer.

### 1.2 Mandatory source classification

Every scraped/discovered page must be classified as one of:

```text
OFFICIAL_AUTHORITY
OFFICIAL_GUIDANCE
OFFICIAL_FORM
OFFICIAL_PROCESS_GUIDANCE
APPROVED_SECONDARY_REFERENCE
DISCOVERY_HINT_ONLY
BLOCKED_UNTRUSTED
BLOCKED_COPYRIGHT
BLOCKED_LICENCE
```

Only these categories may enter RAG authority:

```text
OFFICIAL_AUTHORITY
OFFICIAL_GUIDANCE
OFFICIAL_FORM
OFFICIAL_PROCESS_GUIDANCE
```

### 1.3 Mandatory source allowlist

Create or verify a source allowlist table:

```sql
CREATE TABLE IF NOT EXISTS official_source_allowlist (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain text NOT NULL UNIQUE,
  source_name text NOT NULL,
  source_category text NOT NULL,
  allowed_for_ingestion boolean NOT NULL DEFAULT false,
  allowed_for_rag_authority boolean NOT NULL DEFAULT false,
  allowed_for_rules boolean NOT NULL DEFAULT false,
  licence_status text NOT NULL DEFAULT 'unknown',
  computational_analysis_allowed boolean NOT NULL DEFAULT false,
  bulk_scrape_allowed boolean NOT NULL DEFAULT false,
  rate_limit_policy text,
  last_policy_checked_at timestamptz,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

Minimum required domains:

```text
legislation.gov.uk
caselaw.nationalarchives.gov.uk
nationalarchives.gov.uk
acas.org.uk
gov.uk
judiciary.uk
justice.gov.uk
employmenttribunals.service.gov.uk
assets.publishing.service.gov.uk
```

### 1.4 Proof command

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT domain, source_category, allowed_for_ingestion, allowed_for_rag_authority, allowed_for_rules, licence_status, computational_analysis_allowed, bulk_scrape_allowed, last_policy_checked_at FROM official_source_allowlist ORDER BY domain;"
```

Acceptance:

- Allowlist exists.
- Every domain has policy status.
- Only official domains are authority.
- Unknown domains cannot enter RAG authority.
- Unknown domains cannot enter `rules`.
- Crawler refuses non-allowlisted authority ingestion.

---

## 2. OFFICIAL UK EMPLOYMENT LAW SOURCE INGESTION

### 2.1 Required source groups

Claude must implement ingestion for all required official source groups below.

#### A. Legislation

Must ingest from `legislation.gov.uk` using XML/CLML `/data.xml`.

Minimum required Acts and provisions:

```text
Employment Rights Act 1996
- s.94
- s.95
- s.97
- s.98
- s.108
- s.111
- s.119
- s.120
- s.122
- s.123
- s.124
- s.207B
- s.227

Employment Tribunals Act 1996
- s.18A

Trade Union and Labour Relations (Consolidation) Act 1992
- s.207A

Relevant Employment Rights Increase of Limits Orders
- current year
- previous year
- future/prospective where available
```

#### B. Case law

Must integrate Find Case Law safely.

Rules:

- Bulk/computational analysis must be blocked until licence approval is recorded.
- Sample/manual ingestion can exist.
- System must not pretend case law corpus is complete if licence not approved.
- Case law citations must state source and coverage limitation.

#### C. ACAS

Must ingest official ACAS guidance:

```text
ACAS Code of Practice on disciplinary and grievance procedures
ACAS guide to discipline and grievances at work
ACAS disciplinary procedure guidance
ACAS grievance procedure guidance
ACAS dismissal guidance
ACAS Early Conciliation guidance
```

#### D. GOV.UK / HMCTS / Judiciary

Must ingest official process guidance relevant to:

```text
employment tribunal claim process
ET1 claim guidance
employment tribunal forms
T420
T421
T422 where relevant
T425 hearing guidance
employment tribunal rules
presidential guidance
practice directions
tribunal decisions guidance
```

### 2.2 Mandatory ingestion architecture

Create or verify:

```text
ingestion/
  legislation/
  case_law/
  acas/
  govuk/
  judiciary/
  hmcts/
  common/
```

Each source module must have:

```text
fetcher.py
parser.py
normalizer.py
deduplicator.py
indexer.py
tests/
```

### 2.3 Mandatory ingestion audit tables

Create or verify:

```sql
ingestion_runs
ingestion_items
ingestion_errors
source_freshness
source_content_hashes
official_source_allowlist
```

Minimum fields for `ingestion_runs`:

```sql
id uuid
source_key text
source_domain text
mode text
started_at timestamptz
finished_at timestamptz
status text
items_seen int
items_inserted int
items_updated int
items_skipped int
items_failed int
error_summary text
commit_sha text
created_by text
```

Minimum fields for `ingestion_items`:

```sql
id uuid
run_id uuid
source_url text
source_title text
source_type text
authority_category text
jurisdiction text
version_date date
effective_from date
effective_to date
content_hash text
parser_status text
rag_authority_allowed boolean
rules_allowed boolean
created_at timestamptz
```

### 2.4 Ingestion acceptance commands

```bash
docker compose run --rm ingestion python -m ingestion.legislation.ingest --strict --claim-type unfair_dismissal
docker compose run --rm ingestion python -m ingestion.acas.ingest --strict
docker compose run --rm ingestion python -m ingestion.govuk.ingest --strict --topic employment_tribunal
docker compose run --rm ingestion python -m ingestion.judiciary.ingest --strict --topic employment_tribunal
docker compose run --rm ingestion python -m ingestion.case_law.ingest --sample --limit 5
```

Acceptance:

- Commands must not silently succeed with 0 useful rows.
- Every run writes an ingestion audit row.
- Parser errors are visible.
- Missing official source = FAIL.
- Unofficial source stored as authority = FAIL.
- Bulk Find Case Law without licence = FAIL.

---

## 3. FAST DATABASE ACCEPTANCE CRITERIA

### 3.1 Mandatory database groups

The database must support:

1. Legal source storage
2. Legal chunk storage
3. Vector search
4. Keyword search
5. Citation bundles
6. Deterministic rules
7. Source freshness
8. RAG audit
9. Brain trace audit
10. Responsible AIA governance audit
11. User cases
12. Documents
13. Payments
14. Uploads/OCR where enabled
15. Memory with consent
16. Semantic cache without PII

### 3.2 Required tables or equivalent views

Claude must create or verify:

```text
official_source_allowlist
ingestion_runs
ingestion_items
ingestion_errors
legislation
legislation_chunks
case_law
case_law_chunks
acas_guidance
govuk_guidance
tribunal_guidance
rules
legal_nodes
legal_edges
retrieval_audit
rag_citation_bundles
brain_traces
aia_governance_checks
safety_boundary_checks
context_compression_log
evaluation_results
semantic_cache
legal_memory
cases
documents
payment_events
source_freshness
```

If table names differ, create views with these names so tests and reports can verify them.

### 3.3 Required indexes

Add or verify indexes on:

```text
source_url
content_hash
source_domain
source_type
authority_category
claim_type
jurisdiction
effective_from
effective_to
last_verified_at
section_ref
rule_key
case_id
user_id
embedding vector index
full text search index
```

### 3.4 DB functions/views

Create or verify:

```sql
get_current_rules(claim_type text, jurisdiction text, as_of_date date)
get_official_sources_for_claim(claim_type text)
get_source_freshness()
search_legal_chunks(query_text text, claim_type text, jurisdiction text, as_of_date date, k int)
get_citation_bundle(trace_id uuid)
record_retrieval_audit(...)
record_aia_governance_check(...)
```

### 3.5 Performance proof

Required commands:

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "\dx"
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt"
docker compose exec -T db psql -U lawapp -d lawapp -c "\di"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM get_source_freshness();"
docker compose exec -T db psql -U lawapp -d lawapp -c "EXPLAIN ANALYZE SELECT * FROM get_current_rules('unfair_dismissal','EW',CURRENT_DATE);"
docker compose exec -T db psql -U lawapp -d lawapp -c "EXPLAIN ANALYZE SELECT * FROM search_legal_chunks('unfair dismissal time limit','unfair_dismissal','EW',CURRENT_DATE,10);"
```

Acceptance:

- `pgvector` installed.
- `pgcrypto` installed.
- required indexes exist.
- current rules query works.
- legal search query works.
- source freshness works.
- duplicate source/hash rows are blocked or deduplicated.
- query plans are acceptable.
- no giant sequential scan on legal chunks without justification.

---

## 4. RULES TABLE  -  HARD DETERMINISTIC LEGAL FACTS

### 4.1 Mandatory rule categories

The `rules` table must include effective-dated, cited rows for:

```text
unfair_dismissal.time_limit_months
unfair_dismissal.ec_required
unfair_dismissal.ec_pause_logic
unfair_dismissal.ec_one_month_floor
unfair_dismissal.qualifying_period
unfair_dismissal.compensatory_cap_amount
unfair_dismissal.compensatory_cap_weeks_pay
unfair_dismissal.weeks_pay_cap_amount
unfair_dismissal.basic_award_formula
unfair_dismissal.basic_award_min_automatic
unfair_dismissal.acas_uplift_max_percent
unfair_dismissal.acas_reduction_max_percent
unfair_dismissal.not_reasonably_practicable_extension_is_judgement
```

### 4.2 Strict deterministic rule

The following must not be generated by the LLM:

```text
deadline
limitation date
ACAS EC stop-clock days
qualifying period
compensation cap
week's pay cap
basic award formula
uplift percentage
jurisdiction coverage
```

They must come from the `rules` table and deterministic code.

### 4.3 Proof

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT rule_key, value_numeric, value_text, unit, authority_ref, authority_url, effective_from, effective_to, last_verified_at FROM rules WHERE claim_type='unfair_dismissal' ORDER BY rule_key, effective_from;"
grep -R "123543\|118223\|751\|719\|9157\|3 months\|2 years\|52 weeks" backend client shared ingestion --exclude-dir=node_modules --exclude-dir=.next || true
```

Acceptance:

- all mandatory rule categories exist.
- every rule has `authority_ref`, `authority_url`, `effective_from`, `last_verified_at`.
- hardcoded legal values in production code = FAIL.
- legal values allowed only in tests/fixtures or seed data with citations.

---

## 5. ALGORITHM BRAIN + RAG + RESPONSIBLE AIA CONTROL

### 5.1 Mandatory answer pipeline

Every user legal answer must pass this pipeline:

```text
1. classify user request
2. detect claim type and jurisdiction
3. fetch deterministic rules
4. retrieve official sources
5. perform hybrid RAG
6. perform graph RAG where useful
7. create citation bundle
8. compress context without losing citations
9. de-identify user facts before any third-party AI
10. run reasoning model against retrieved authority only
11. score grounding
12. score confidence
13. run responsible AIA governance
14. block unsafe/unreserved/reserved-activity language
15. create structured assessment
16. render user answer with citations
17. log full audit trace
```

### 5.2 Responsible AIA must control the answer

Responsible AIA is not decoration. It must actively decide whether the answer can be shown.

It must check:

```text
source authority
citation coverage
grounding score
confidence score
legal boundary
reserved activity risk
PII exposure risk
data minimisation
outcome guarantee language
unsupported legal claim
missing key facts
weakness disclosure
human handoff requirement
```

### 5.3 Hard block rules

Responsible AIA must block or downgrade the answer if:

- no official source is retrieved,
- citations are missing,
- RAG result is weak,
- case law is empty but answer relies on case law,
- answer crosses legal advice/representation boundary,
- answer says or implies “we will file”, “we will represent”, “you will win”,
- personal raw facts would be sent to third-party AI,
- legal values are generated instead of read from rules,
- confidence below threshold,
- source freshness is stale,
- jurisdiction mismatch exists.

### 5.4 Required API routes

Create or verify:

```text
POST /assess
POST /api/brain/trace
POST /api/rag/hybrid-search
POST /api/rag/graph
GET  /api/rules/{claim_type}
POST /api/deadline/calculate
GET  /api/sources/freshness
POST /api/aia/governance/check
POST /api/citations/bundle
```

### 5.5 Required response shape

Every legal answer must include:

```json
{
  "claim_type": "unfair_dismissal",
  "jurisdiction": "EW",
  "answer_status": "answered | insufficient_grounding | blocked | human_review",
  "structured_assessment": {},
  "deterministic_rules_used": [],
  "citations": [],
  "source_freshness": [],
  "grounding_score": 0.0,
  "confidence_score": 0.0,
  "responsible_aia_decision": {
    "allowed": true,
    "decision": "allow | block | downgrade | human_review",
    "reasons": []
  },
  "legal_boundary_notice": "Information and self-help drafting only. Not legal advice. Not a law firm."
}
```

### 5.6 Proof commands

```bash
curl -s http://localhost:8000/api/rag/hybrid-search -H "Content-Type: application/json" -d '{"query":"What is the time limit for unfair dismissal?","claim_type":"unfair_dismissal","jurisdiction":"EW"}' | jq .
curl -s http://localhost:8000/assess -H "Content-Type: application/json" -d @tests/fixtures/unfair_dismissal_case.json | jq .
curl -s http://localhost:8000/api/aia/governance/check -H "Content-Type: application/json" -d @tests/fixtures/assessment_sample.json | jq .
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM retrieval_audit;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rag_citation_bundles;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM brain_traces;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM aia_governance_checks;"
```

Acceptance:

- answer contains citations.
- citations point to official source rows.
- deterministic rules list is populated.
- responsible AIA decision is present.
- trace is stored.
- retrieval audit is stored.
- no official source = no confident answer.
- no raw uncited legal answer.

---

## 6. WASM ACCEPTANCE CRITERIA

### 6.1 WASM scope

WASM may only handle:

```text
deadline arithmetic
ACAS EC clock arithmetic
client-side validation
document preview/assembly
local non-legal transformations
```

WASM must not:

```text
store legal values
invent deadlines
run RAG
run LLM
decide claim viability
contain compensation caps
contain fixed legal deadlines
```

### 6.2 Required flow

```text
frontend asks backend for rules
backend returns current effective-dated rules with citations
frontend passes rule values to WASM
WASM calculates deadline
backend validates same calculation
frontend displays deadline and citations
responsible AIA confirms deadline source
```

### 6.3 Proof

```bash
bash scripts/rebuild-wasm.sh
npm --prefix client test
node_modules/.bin/playwright test
curl -s http://localhost:8000/api/deadline/calculate -H "Content-Type: application/json" -d @tests/fixtures/deadline_case_ec_floor.json | jq .
grep -R "123543\|118223\|751\|719\|9157\|3 months\|2 years\|52 weeks" client/wasm client/public/wasm client/js --exclude-dir=node_modules || true
```

Acceptance:

- WASM rebuilds.
- JS fallback works.
- WASM and backend deadline match.
- no legal values embedded in WASM.
- no backend rules = frontend safe error.
- deadline shows citation.

---

## 7. BACKEND ↔ FRONTEND WIRING

### 7.1 Every frontend feature must be wired

Required user journeys:

```text
landing
register
login
intake
fetch rules
deadline calculate
assessment
citations display
source freshness display/admin route
case save
dashboard
saved case
document generation
payment/test token
document download
handoff lead
upload/OCR either implemented or clearly disabled
```

### 7.2 No dead UI

Every button must either:

- call an API,
- navigate intentionally,
- or clearly show disabled/not-enabled state.

Dead button = FAIL.

### 7.3 Frontend must show citations

Assessment page must display:

- rule citations,
- legislation citations,
- ACAS citations,
- case law citations if used,
- source freshness warning if stale,
- legal boundary notice.

### 7.4 Proof

```bash
node_modules/.bin/playwright test
bash scripts/smoke_local_journey.sh
grep -R "TODO\|mock\|placeholder\|fake\|stub" client backend --exclude-dir=node_modules --exclude-dir=.next || true
```

Acceptance:

- Playwright passes.
- Smoke journey passes.
- citations visible.
- legal notice visible.
- no dead buttons.
- no hidden mock routes.
- no unsupported production claims.

---

## 8. SECURITY + DATA PROTECTION

### 8.1 Required controls

Must prove:

```text
JWT auth active
cross-user 403
case ownership enforced
document ownership enforced
upload ownership enforced
PII de-identification before AI
raw facts not logged
third-party model receives de-identified facts only
special-category facts encrypted
Redis rate limiting active
CORS strict in staging/prod
scraper domain allowlist enforced
SSRF blocked
Stripe webhook signature verified
payment state cannot be forged
secrets not committed
audit trails exist
```

### 8.2 Proof

```bash
python -m pytest tests/security -q
bash scripts/security-regression.sh
grep -R "sk_live\|sk_test\|ANTHROPIC_API_KEY\|STRIPE_SECRET_KEY\|password=" . --exclude-dir=.git --exclude-dir=node_modules || true
```

Acceptance:

- no failed security tests.
- no committed real secrets.
- no raw PII in logs.
- scraper cannot fetch arbitrary untrusted domains as authority.
- user data cannot leak cross-user.
- model boundary is de-identified.

---

## 9. TESTING ACCEPTANCE CRITERIA

### 9.1 Required tests

Create or verify tests for:

```text
official source allowlist
legislation ingestion
ACAS ingestion
GOV.UK/HMCTS/Judiciary ingestion
Find Case Law licence gate
rules effective dating
deadline no EC
deadline EC no floor
deadline EC floor
hybrid RAG
graph RAG
citation bundle
responsible AIA allow/block/downgrade
de-identification
reserved activity blocking
frontend full journey
payment
document generation
source freshness
WASM/backend consistency
security
```

### 9.2 Required command gate

```bash
docker compose down -v
docker compose up -d --build
docker compose run --rm ingestion python -m ingestion.legislation.ingest --strict --claim-type unfair_dismissal
docker compose run --rm ingestion python -m ingestion.acas.ingest --strict
docker compose run --rm ingestion python -m ingestion.govuk.ingest --strict --topic employment_tribunal
python -m pytest -q
bash scripts/smoke_local_journey.sh
node_modules/.bin/playwright test
bash scripts/security-regression.sh
bash scripts/push-and-deploy.sh --dry-run
```

Acceptance:

- all commands pass.
- any failure must be fixed and rerun.
- no “accepted with failures”.
- no “blocked” unless legally/external and documented.

---

## 10. CI/CD ACCEPTANCE CRITERIA

CI must run:

```text
backend tests
frontend tests
Playwright
security regression
WASM rebuild
ingestion dry-run or mocked official-source fixture tests
Docker build
migration test from empty DB
source allowlist test
RAG/citation tests
```

Proof:

```bash
gh workflow list
gh run list --limit 10
bash scripts/push-and-deploy.sh --dry-run
```

Acceptance:

- active workflows have correct `lawapp` names.
- no stale IterLaw/RightsNow workflow names.
- CI fails if citations missing.
- CI fails if official data tables are empty after ingestion fixture.
- CI fails if WASM stale.
- CI fails if security regression fails.

---

## 11. KUBERNETES / NAMESPACE ACCEPTANCE CRITERIA

The system is not staging-ready until deployed and verified in Kubernetes.

Required namespaces:

```text
lawapp-ai
lawapp-rag
lawapp-api
lawapp-monitoring
lawapp-security
```

Required proof:

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
```

Acceptance:

- all namespaces exist.
- backend healthy.
- RAG service healthy if split.
- AI service healthy if split.
- DB/secrets/config wired.
- no CrashLoopBackOff.
- no pending pods.
- no fake Kubernetes sign-off.

---

## 12. FINAL REPORT REQUIRED

Claude must create:

```text
reports/claude-lawapp-official-data-fast-db-rag-wasm-aia-final-proof.md
```

The report must include:

1. Commit hash.
2. Docker clean start proof.
3. Official source allowlist proof.
4. Ingestion proof.
5. DB table counts.
6. DB index proof.
7. Rules proof.
8. Source freshness proof.
9. RAG proof.
10. Citation bundle proof.
11. Responsible AIA proof.
12. WASM proof.
13. Frontend wiring proof.
14. Security proof.
15. CI/CD proof.
16. Kubernetes proof if claiming staging-ready.
17. Remaining blockers, split into:
    - code blockers,
    - owner-secret blockers,
    - legal/licence blockers,
    - production compliance blockers.

Final classification must be one of:

```text
NOT READY
LOCAL DEMO READY ONLY
STAGING READY
PRODUCTION READY
```

Rules:

- If official legal data is empty: NOT READY or LOCAL DEMO ONLY.
- If RAG has no citations: NOT READY.
- If responsible AIA does not control answers: NOT READY.
- If frontend not wired: NOT READY.
- If Kubernetes not proven: not STAGING READY.
- If real AI/Stripe/security/compliance not live: not PRODUCTION READY.

---

## 13. FINAL NON-NEGOTIABLE ACCEPTANCE GATE

Claude is not finished until this full gate passes:

```bash
docker compose down -v
docker compose up -d --build
docker compose run --rm ingestion python -m ingestion.legislation.ingest --strict --claim-type unfair_dismissal
docker compose run --rm ingestion python -m ingestion.acas.ingest --strict
docker compose run --rm ingestion python -m ingestion.govuk.ingest --strict --topic employment_tribunal
python -m pytest -q
bash scripts/smoke_local_journey.sh
node_modules/.bin/playwright test
bash scripts/security-regression.sh
bash scripts/push-and-deploy.sh --dry-run
```

Then DB proof:

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
```

If any command fails, the work is not accepted.

No negotiation.
No fake PASS.
No unsupported sign-off.
No “blocked” unless legally impossible and proven.
Fix, rerun, and prove.
