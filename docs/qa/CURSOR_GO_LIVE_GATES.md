# CURSOR GO-LIVE GATES — lawapp

Production readiness gates with pass/fail evidence. Gate must have **command + output** — no checklist-only PASS.

**Overall gate status:** ❌ **NOT READY**

---

## Gate 0 — Product identity

| Check | Required | Evidence | Status |
|-------|----------|----------|--------|
| Product named lawapp | YES | Repo root, namespaces, service names | ✅ PASS |
| No RightsNow/IterLaw in active paths | YES | Legacy quarantined `_legacy_iterlaw_QUARANTINED` | ✅ PASS |
| Canonical namespaces | lawapp-api, lawapp-ai, lawapp-rag, lawapp-security, lawapp-monitoring | `infra/k8s/lawapp-namespaces.yaml` | ✅ PASS |

---

## Gate 1 — Runtime health (local Docker)

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| All services healthy | `docker compose ps` | 12/12 healthy | ✅ PASS 2026-06-14 |
| Backend DB connected | `curl localhost:8000/health` | `"db":"connected"` | ✅ PASS |
| No password FATAL in logs | `docker compose logs backend --tail=300` | no FATAL | ✅ PASS |
| Microservices reachable | curl :8016,:8017,:8018,:8019,:8020 | status ok | ✅ PASS |

---

## Gate 2 — Database & migrations

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Migrations applied | `SELECT COUNT(*) FROM _migrations;` | matches file count | ✅ PASS (backend starts) |
| Core tables | `\dt` | users, cases, rules, corpus_chunks, brain_traces | ✅ PASS |
| Rules populated | `SELECT COUNT(*) FROM rules;` | ≥100 | ✅ PASS (125) |
| FK enforcement | insert bad FK (integrity script) | rejected | ✅ PASS (prior script) |
| Alembic | N/A — SQL migrations | documented | ✅ N/A |
| Go-live module gate | `bash scripts/proof/prove_database_integrity.sh` | all PASS | ❌ FAIL — 13 partial modules |

---

## Gate 3 — Legal data & RAG

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Rules have authority_ref | SQL sample | non-null | ✅ PASS |
| Corpus ingested | `COUNT corpus_chunks` | >>100 | ❌ FAIL (28) |
| RAG retrieval | POST /api/rag/search | results > 0 | ❌ FAIL (0) |
| Assessment citations | workflow proof /assess | citations array | ✅ PASS |
| No uncited legal rows | integrity + CitationGuard tests | pass | ✅ PASS (prior) |
| 24 modules production-ready | employment_modules | 24 × production | ❌ FAIL (11 prod, 13 partial) |

---

## Gate 4 — Brain & governance

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Brain pipeline | code review `backend/core/brain.py` | 19 steps | ✅ PASS |
| No bypass route | route scan + tests | all legal via brain | ✅ PASS (prior) |
| trace_id in response | workflow assess JSON | trace_id present | ✅ PASS |
| trace_id in DB | `SELECT trace_id FROM brain_traces LIMIT 1` | matches | ⚠️ NOT PROVEN this session |
| Local LLM only | `/health` ai_provider | ollama_local, no openrouter | ✅ PASS |
| Fail-closed missing facts | workflow weak case | missing_edt | ✅ PASS |

---

## Gate 5 — Security

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Auth fail-closed | unauth /cases, /api/documents | 401/403 | ✅ PASS |
| Payment no bypass | workflow unpaid/paid | 402 until DB paid | ✅ PASS |
| Cross-tenant isolation | User B case access | 403 | ✅ PASS |
| Admin gated | no ADMIN_API_KEY | blocked | ✅ PASS |
| Secrets not in repo | secret scan | clean | ✅ PASS (prior) |
| Production auth mode | ENVIRONMENT=production startup | rejects mock/none | ⚠️ code exists; not live-proven |
| JWT secret rotation | prod deploy | vault-managed | ❌ NOT PROVEN |

---

## Gate 6 — Payment (production)

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Test mode (local) | PAYMENT_MODE=test workflow | confirm-test works | ✅ PASS |
| Stripe live keys | prod env | configured in vault | ❌ NOT PROVEN |
| Webhook signature | invalid webhook test | rejected | ✅ PASS |
| PCI — no card data stored | code review | Stripe-hosted checkout | ✅ PASS (architecture) |

---

## Gate 7 — Frontend

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Pages served | curl key pages | 200 | ✅ PASS |
| Buttons wired | frontend route map | real API | ✅ PASS (prior) |
| Legal disclaimers | notice scan | on intake/assess | ✅ PASS (prior) |
| Accessibility WCAG AA | a11y audit | no critical | ❌ NOT RUN |
| Mobile responsive | visual test | usable | ⚠️ NOT PROVEN |

---

## Gate 8 — CI/CD

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| CI workflow exists | `.github/workflows/ci.yml` | on push | ✅ PASS |
| Migrations in CI | ci.yml step | psql loop | ✅ PASS |
| Full pytest green | CI job / local | exit 0 | ❌ FAIL (59 failures) |
| Image build | build-images workflow | pushes to registry | ⚠️ not verified this session |
| Deploy workflow | lawapp-deploy-k8s.yml | manual/dispatch | ⚠️ exists |

---

## Gate 9 — Kubernetes & infra

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| Manifests valid | kubectl apply --dry-run | no errors | ⚠️ partial |
| Pods running | kubectl get pods | All Ready | ❌ no cluster access |
| Ingress + TLS | curl prod URL | valid HTTPS | ❌ |
| Network policies | lawapp-network-policies.yaml | applied | ❌ |
| Postgres STS | lawapp-postgres-sts.yaml | running | ❌ |
| Ollama inference | ollama-inference daemonset | model loaded | ❌ |

---

## Gate 10 — Observability & ops

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| OTEL instrumentation | deps in Dockerfile | present | ✅ PASS (deps) |
| Prometheus rules | lawapp-prometheus-rules.yaml | exists | ✅ PASS (file) |
| Logs no PII | log grep | no emails | ✅ PASS (prior) |
| Backup job | lawapp-backup-job.yaml | success | ❌ NOT PROVEN |
| Restore drill | backup-restore-proof | pass | ❌ NOT PROVEN |
| On-call runbook | docs | exists | ⚠️ partial |

---

## Gate 11 — Performance & scale

| Check | Command | Expected | Status |
|-------|---------|----------|--------|
| k6 50 VU smoke | k6_100k_readiness.js | thresholds green | ❌ FAIL p95 1.05s, 64% failed |
| 10k concurrent design | architecture review | pooler, cache, HPA | ❌ NOT PROVEN |
| 100k in 5 min | user requirement | load proof | ❌ FAIL |

---

## Gate 12 — Legal/compliance product gates

| Check | Expected | Status |
|-------|----------|--------|
| Not legal advice disclaimer | visible UX | ✅ PASS |
| ACAS/ET deadline accuracy | rules-backed tests | ✅ PASS (7 modules) |
| All 24 modules accurate | legal accuracy matrix | ❌ FAIL (13 partial) |
| DPIA / data retention | documented + enforced | ❌ NOT PROVEN |

---

## Go / no-go summary

| Environment | Verdict | Blockers |
|-------------|---------|----------|
| Local dev Docker | ✅ GO (with override password) | RAG corpus sparse |
| Controlled beta (invite-only) | ⚠️ CONDITIONAL | QA-001, QA-002, QA-004 |
| Public production | ❌ NO-GO | Gates 3, 6, 9, 11, 12 |

---

## Minimum path to beta GO

1. Bootstrap corpus → RAG returns results (Gate 3)
2. Full pytest green or quarantine list approved (Gate 8)
3. Document 13 partial modules as unsupported in UI (Gate 3)
4. k6 smoke thresholds green at 50 VU (Gate 11)

## Minimum path to production GO

All beta items plus: K8s deploy proof, TLS, secret rotation, Stripe live, backup/restore, OTEL trace proof, 24-module legal accuracy sign-off.
