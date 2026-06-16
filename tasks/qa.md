# LAWAPP FULL TAKEOVER ORDER  -  DEEP QA, REPAIR, GO-LIVE READINESS

Project root:

```bash
F:\lawapp
```

GitHub:

```text
https://github.com/serverax/lawapp
```

## Mission

Take over LawApp as release engineer. Goal: make LawApp production-ready and prepare it to go live.

Do not only test. Audit, repair, prove, and report.

LawApp must be checked across:

* frontend
* backend
* database
* security
* API wiring
* payment workflow
* user workflows
* legal reasoning algorithm
* RAG
* Graph RAG
* document generation
* authentication
* deployment readiness
* 100k-user scale readiness

## Non-negotiable rules

1. Do not fake PASS.
2. Do not hide failures.
3. Do not mark production-ready unless proven.
4. Every issue must have:

   * severity
   * file path
   * root cause
   * repair action
   * test evidence
   * status: fixed / partial / blocked
5. Legal answers must use retrieved cited sources, not model memory.
6. Deadlines, caps, thresholds must come from `rules` table, not LLM.
7. No raw personal data must be sent to third-party LLMs.
8. The app must clearly state it is not a law firm and not legal advice.
9. Do not push to GitHub until all tests and report are complete.

## Phase 1  -  Repo and environment audit

Run:

```bash
cd /mnt/f/lawapp || cd F:/lawapp

git status
git branch --show-current
git log --oneline -10

docker compose ps
docker compose config

find . -maxdepth 3 -type f | sort > reports/file_inventory.txt
```

Create:

```text
reports/LAWAPP_TAKEOVER_AUDIT.md
```

Include:

* current branch
* dirty files
* running services
* ports
* env files found
* missing services
* unsafe secrets
* broken config
* current blockers

## Phase 2  -  Backend deep QA

Check:

* FastAPI routes
* OpenAPI validity
* auth middleware
* payment gates
* document generation
* case ownership
* error handling
* CORS
* logging
* health endpoints
* legacy route shims
* canonical route parity

Run:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/openapi.json > reports/openapi.json

python -m pytest -q tests > reports/pytest_full.txt 2>&1
```

If tests fail, repair them properly.

Do not weaken tests to pass.

## Phase 3  -  Frontend deep QA

Audit all pages under:

```text
client/public
client/src
frontend
```

Check:

* broken links
* missing pages
* wrong API URLs
* old legacy routes
* broken JS
* auth token handling
* payment screen flow
* case dashboard flow
* document download flow
* mobile responsiveness
* legal notices
* SEO metadata
* accessibility basics

Create a route map:

```text
reports/frontend_route_map.md
```

Verify every frontend API call exists in backend OpenAPI.

## Phase 4  -  Workflow QA

Prove these workflows end-to-end:

1. Landing page opens.
2. User registers/logs in.
3. User starts diagnosis.
4. User enters unfair dismissal facts.
5. System returns structured assessment.
6. Deadline is calculated correctly.
7. Weak case shows honest warning.
8. Out-of-scope case returns not supported.
9. User saves case.
10. User returns to dashboard.
11. Unpaid user cannot generate full documents.
12. Paid user can generate:

    * Particulars of Claim
    * Schedule of Loss
13. Documents contain user facts.
14. Document says self-help draft, not legal advice.
15. Beyond self-help case triggers handoff.
16. User A cannot access User B case.
17. Anonymous user receives 401.
18. Invalid payment cannot unlock documents.
19. Admin/reporting pages are protected.

Create:

```text
scripts/proof/prove_lawapp_full_workflows.sh
reports/proof_full_workflows.txt
```

The script must exit non-zero on failure.

## Phase 5  -  Database QA

Check:

* migrations
* schema consistency
* foreign keys
* indexes
* pgvector extension
* rules table
* source freshness
* legal source tables
* users/cases/documents/payments
* encryption fields
* migration tracking

Run:

```bash
docker compose exec -T db psql -U lawapp -d lawapp -c "\dt"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT * FROM source_freshness;"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT rule_key, value_numeric, value_text, effective_from, effective_to FROM rules ORDER BY rule_key, effective_from;"
```

Create:

```text
scripts/proof/prove_database_integrity.sh
reports/proof_database_integrity.txt
```

## Phase 6  -  Algorithm, RAG, Graph RAG QA

Audit:

* classify
* retrieve
* reason
* score
* govern
* respond
* RAG citations
* Graph RAG relationships
* fallback behaviour
* insufficient grounding handling
* de-identification boundary
* deadline logic
* rules lookup
* legal citation quality

Test cases:

* ordinary unfair dismissal
* less than 2 years service
* redundancy
* misconduct dismissal
* no ACAS
* ACAS with stop-clock
* out-of-scope tenancy query
* weak facts
* unclear facts
* future 2027 rule transition

Create:

```text
reports/rag_algorithm_qa.md
reports/legal_accuracy_matrix.md
```

Every legal answer must show:

* retrieved source
* citation
* confidence
* grounding score
* decision reason
* weakness

## Phase 7  -  Security QA

Run security checks for:

* auth bypass
* payment bypass
* IDOR
* insecure direct object access
* exposed secrets
* unsafe CORS
* debug endpoints
* unauthenticated admin pages
* raw PII in logs
* third-party LLM payload leakage
* SQL injection risks
* XSS risks
* file upload risks
* rate limiting
* brute force protection

Create:

```text
reports/security_qa_report.md
```

Use severity:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

## Phase 8  -  Performance and 100k readiness

LawApp must support 100k users in the first 5 minutes.

Do not claim this is proven unless load tested.

Create:

```text
reports/performance_readiness.md
```

Include:

* current bottlenecks
* DB connection limits
* API worker count
* Redis/cache status
* queue status
* static file serving
* CDN readiness
* horizontal scaling plan
* k6 test plan
* realistic infra needed

Create k6 script:

```text
scripts/load/k6_100k_readiness.js
```

At minimum test:

* homepage
* health
* login
* assessment
* save case
* document-gated request

If the local machine cannot run 100k, state clearly:

```text
100k not locally proven. Requires distributed load test.
```

## Phase 9  -  Repair

For every issue found:

1. Fix code.
2. Add or update test.
3. Re-run targeted test.
4. Re-run full proof suite.
5. Record evidence.

Do not leave broken placeholders.

## Phase 10  -  Final go-live report

Create:

```text
reports/LAWAPP_GO_LIVE_READINESS_REPORT.md
```

Include:

```text
Executive summary
Current release status: GO / NO-GO
Critical blockers
High risks
Fixed issues
Remaining issues
Test evidence
Workflow evidence
Security evidence
Database evidence
RAG/legal accuracy evidence
Performance evidence
Git status
Recommended next steps
```

Final status must be one of:

```text
GO LIVE
GO LIVE WITH RISK
NO-GO
```

## Required final command output

At the end, print:

```text
LAWAPP TAKEOVER COMPLETE

Backend tests:
Frontend tests:
Workflow proof:
Database proof:
Security proof:
RAG proof:
Performance proof:
Go-live status:
Report path:
Commit hash:
```

Only after this, ask permission to push to GitHub.
