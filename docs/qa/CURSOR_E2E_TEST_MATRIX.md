# CURSOR E2E TEST MATRIX  -  lawapp

Maps product features to proof commands and expected evidence. **No fake PASS**  -  run commands and compare output.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Proven PASS this session (2026-06-14) |
| ⚠️ | PARTIAL  -  service up but functional gap |
| ❌ | FAIL or not run |
| 🔒 | Requires auth token |

---

## 1. Infrastructure & health

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| All compose services up | `docker compose ps` | All `(healthy)` | ✅ |
| Backend health | `curl -s http://localhost:8000/health` | `"db":"connected"` | ✅ |
| Rules service | `curl -s http://localhost:8016/health` | `"status":"ok"` | ✅ |
| RAG service | `curl -s http://localhost:8017/health` | `"status":"ok"` | ✅ |
| Graph RAG | `curl -s http://localhost:8018/health` | `"status":"ok"` | ✅ |
| Audit | `curl -s http://localhost:8020/health` | `"status":"ok"` | ✅ |
| Redaction | `curl -s http://localhost:8019/health` | `"status":"ok"` | ✅ |
| Redis | `docker compose exec redis redis-cli ping` | `PONG` | ✅ (implied healthy) |
| Postgres | `docker compose exec -T db pg_isready -U lawapp` | accepting connections | ✅ |

---

## 2. Database & rules

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Backend DB connect | `docker compose exec -T backend python -c "import os,psycopg2; ..."` | `('lawapp','lawapp')` | ✅ |
| Schema present | `docker compose exec -T db psql -U lawapp -d lawapp -c "\dt"` | 91 tables | ✅ |
| Rules loaded | `... -c "SELECT COUNT(*) FROM rules;"` | ≥100 (actual: 125) | ✅ |
| Rule provenance | `... -c "SELECT rule_key, authority_ref FROM rules LIMIT 5;"` | Non-null authority_ref | ✅ |
| Employment modules | `... -c "SELECT status, COUNT(*) FROM employment_modules GROUP BY status;"` | 24 total | ✅ 11 prod / 13 partial |
| Migrations idempotent | `bash db/init-migrations.sh` | exit 0, skips applied | ✅ (via backend startup) |
| DB integrity script | `bash scripts/proof/prove_database_integrity.sh` | all PASS | ❌ fails module gate |
| Corpus seeded | `... -c "SELECT COUNT(*) FROM corpus_chunks;"` | >>100 for RAG | ⚠️ 28 only |
| Legislation rows | `... -c "SELECT COUNT(*) FROM legislation;"` | >0 | ✅ 104 |

---

## 3. RAG & Graph RAG

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| RAG search API | `POST http://localhost:8017/api/rag/search` JSON body | results with citations | ❌ 0 results |
| RAG wired to brain | `bash scripts/proof/prove_lawapp_full_workflows.sh` (assess step) | citations in JSON | ✅ 8 citations (rules+graph) |
| Graph context | Same  -  inspect assess JSON | `graph_context_used.used:true` | ✅ |
| Ingestion pipeline | `docker compose --profile bootstrap run --rm db-bootstrap` | corpus_chunks increase | ❌ not run this session |
| Graph tables | `SELECT COUNT(*) FROM graph_nodes;` | >0 | ⚠️ verify separately |

---

## 4. Brain & legal assessment

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Unfair dismissal assess | `POST /assess` (via workflow script) | deadline from rules, citations | ✅ |
| Wrongful dismissal | workflow script | DB-grounded diagnosis | ✅ |
| Redundancy | workflow script | statutory payment calc | ✅ |
| Working time | workflow script | WTR violations cited | ✅ |
| Holiday pay | workflow script | reg.13 citations | ✅ |
| Flexible working | workflow script | ERA s.80F–H | ✅ |
| Out of scope | workflow script | `not_supported` | ✅ |
| Brain trace persisted | `SELECT COUNT(*) FROM brain_traces;` after assess | row inserted | ⚠️ not queried this session |
| Citation guard | `pytest tests/test_integrity_framework.py -q` | pass | ✅ (prior report) |

---

## 5. Auth & security

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Anonymous protected route | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/cases` | 401 or 403 | ✅ (workflow script) |
| Register + login | workflow script steps | JWT/session | ✅ |
| Cross-user case deny | workflow script User B | 403 | ✅ |
| Admin routes | workflow script without admin key | blocked | ✅ |
| JWT mode | `/health` | `"auth_mode":"jwt"` | ✅ |
| Secret scan | `reports/deep_qa_secret_scan.txt` | no real secrets | ✅ (prior) |
| Security test suite | `pytest tests/security/ -q` | all pass | ⚠️ partial drift |

---

## 6. Payment & documents

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Payment session create | workflow script | session id returned | ✅ |
| Unpaid doc block | workflow script | 402/preview | ✅ |
| Test payment confirm | workflow script `/api/payments/confirm-test` | case paid in DB | ✅ |
| Paid POC generate | workflow script | 200 + content | ✅ |
| Paid SoL generate | workflow script | 200 + content | ✅ |
| Legal boundary in doc | workflow script grep | notice text present | ✅ |
| Invalid webhook rejected | workflow script | no unlock | ✅ |
| Stripe live mode | `PAYMENT_MODE=stripe_live` without keys | fail closed | ⚠️ unit tests fail |

---

## 7. Frontend journeys

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Landing page | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/` | 200 | ✅ (workflow) |
| Intake page | curl `/pages/intake.html` | 200 | ✅ (prior report) |
| Assessment page | curl `/pages/assessment.html` | 200 | ✅ |
| Dashboard | curl `/pages/dashboard.html` | 200 | ✅ |
| Case detail | curl `/pages/case_detail.html` | 200 | ✅ |
| API wiring scan | `reports/frontend_api_call_scan.txt` | no orphan routes | ✅ (prior) |
| Browser E2E | Playwright suite | green | ❌ not run |

---

## 8. CI/CD & quality gates

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Full pytest | `python -m pytest -q` | exit 0 | ❌ 59 fail (cached) |
| Container pytest | `docker compose run --rm backend pytest -q` | exit 0 | ❌ 2 fail, incomplete collection |
| Workflow proof | `bash scripts/proof/prove_lawapp_full_workflows.sh` | exit 0 | ✅ |
| Schema readiness | `python scripts/proof/prove_schema_readiness.py` | PASS | ✅ (prior report) |
| Smoke journey | `bash scripts/smoke_local_journey.sh` | 23/23 | ✅ (prior report) |
| CI workflow | `.github/workflows/ci.yml` | migrations + pytest | ⚠️ red if full suite pushed |
| k6 load | `k6 run scripts/load/k6_100k_readiness.js` | thresholds green | ❌ |

---

## 9. Kubernetes & production

| Feature | Proof command | Expected | Status |
|---------|---------------|----------|--------|
| Namespace manifest | `kubectl apply -f infra/k8s/lawapp-namespaces.yaml --dry-run` | valid | ⚠️ syntax only |
| Pod health (prod) | `kubectl get pods -n lawapp-api` | All Running | ❌ no cluster |
| Ingress TLS | curl https://prod-url/health | 200 + valid cert | ❌ |
| Backup/restore | `infra/k8s/lawapp-backup-restore-proof.yaml` | job success | ❌ |
| OTEL export | trace in collector | spans for assess | ❌ |

---

## 10. Module coverage matrix (24 UK employment modules)

| module_key | status | Workflow proof | RAG corpus |
|------------|--------|----------------|------------|
| unfair_dismissal | production | ✅ | ⚠️ sparse |
| unpaid_wages | production | ✅ (prior) | ⚠️ |
| wrongful_dismissal | production | ✅ | ⚠️ |
| redundancy | production | ✅ | ⚠️ |
| working_time | production | ✅ | ⚠️ |
| holiday_pay | production | ✅ | ⚠️ |
| flexible_working | production | ✅ | ⚠️ |
| employment_contracts | production | ✅ | ⚠️ |
| fixed_term_workers | production | ✅ | ⚠️ |
| agency_workers | production | ✅ | ⚠️ |
| part_time_workers | production | ⚠️ partial proof | ⚠️ |
| constructive_dismissal | partial | ⚠️ page exists | ❌ |
| discrimination | partial | ❌ | ❌ |
| equal_pay | partial | ❌ | ❌ |
| health_and_safety | partial | ❌ | ❌ |
| maternity_rights | partial | ❌ | ❌ |
| national_minimum_wage | partial | ❌ | ❌ |
| parental_leave | partial | ❌ | ❌ |
| paternity_rights | partial | ❌ | ❌ |
| pregnancy_maternity_discrimination | partial | ❌ | ❌ |
| shared_parental_leave | partial | ❌ | ❌ |
| trade_union_rights | partial | ❌ | ❌ |
| tupe | partial | ❌ | ❌ |
| whistleblowing | partial | ❌ | ❌ |

---

## Quick smoke script (copy-paste)

```powershell
cd F:\lawapp
docker compose ps
curl -s http://localhost:8000/health
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT COUNT(*) FROM rules;"
bash scripts/proof/prove_lawapp_full_workflows.sh
```

Expected: all services healthy, rules ≥100, workflow script exit 0.
