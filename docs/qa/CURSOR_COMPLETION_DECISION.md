# CURSOR COMPLETION DECISION — lawapp

**Date:** 2026-06-14  
**Decision authority:** QA / delivery assessor audit  
**Repository:** `F:\lawapp`

---

## Executive decision

### Can lawapp be finished without a core rebuild?

**YES — AFTER P0/P1 REPAIRS**

The codebase is a coherent FastAPI monolith with real Postgres schema, deterministic rules engine, Brain governance pipeline, JWT auth, payment gating, static frontend wired to live APIs, and eight healthy Docker microservices. This is **not** a greenfield rewrite situation.

The product **cannot** honestly ship as "complete UK employment law coverage" or "production-ready at scale" until legal-data ingestion, module promotion, test debt, and deploy/observability proof close.

### Verdict matrix

| Question | Answer |
|----------|--------|
| Is the architecture salvageable? | **YES** |
| Is local Docker demonstrably real? | **YES** (2026-06-14) |
| Are core user workflows proven? | **YES** (`prove_lawapp_full_workflows.sh` PASS) |
| Is RAG proven with seeded legal data? | **NO** (28 chunks, 0 search hits) |
| Are all 24 modules production-ready? | **NO** (11 production, 13 partial) |
| Is full test suite green? | **NO** (59 failures / 1619 pass) |
| Is production/K8s proven? | **NO** |
| Should we rebuild core? | **NO** — repair data, tests, deploy proof |

---

## Finishability score

| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Core platform (API, DB, auth) | 25% | 85% | 21.3% |
| Legal rules & modules | 25% | 60% | 15.0% |
| RAG / corpus | 15% | 30% | 4.5% |
| Frontend & UX | 10% | 70% | 7.0% |
| Tests & CI | 10% | 55% | 5.5% |
| Deploy & ops | 15% | 40% | 6.0% |
| **Total** | 100% | — | **~59%** |

**Interpretation:** ~59% toward "feature-complete beta"; ~40% toward "public go-live with 24 modules + scale."

---

## Continue vs rebuild

| Option | Recommendation |
|--------|----------------|
| **Continue incremental repair** | ✅ **RECOMMENDED** — highest ROI; core is real |
| **Fork/rebrand rebuild** | ❌ Rejected — would discard working brain, rules, payment, workflow proof |
| **Scope cut to 7–11 modules** | ⚠️ Viable interim — ship only `production` modules with honest UX |
| **Pause until legal-data pipeline completes** | ⚠️ Required for full 24-module claim |

---

## What is genuinely done (evidence-backed)

1. **Monolith serves UI + API** — bind-mount frontend, `/health` db connected  
2. **125 DB rules** with `authority_ref` — SQL proof  
3. **11 employment modules at `production` status** — including unfair dismissal through agency workers  
4. **Live workflow proof** — registration, case save, assess, payment test confirm, paid documents, cross-user deny  
5. **Microservices tier-1** — rules, RAG, graph-rag, audit, redaction healthy on compose  
6. **Security posture (dev)** — JWT fail-closed, payment gated, no raw token unlock (workflow proof)  
7. **Brain pipeline implemented** — 19 steps documented and traced in assess responses  
8. **SQL migration system** — idempotent, no Alembic dependency  

---

## What is not done (honest gaps)

1. **RAG corpus** — 28 chunks; search returns empty  
2. **13 partial modules** — discrimination, TUPE, whistleblowing, etc.  
3. **59 pytest failures** — mostly integration auth drift  
4. **Container test parity** — Docker image doesn't run full `tests/` tree  
5. **k6 load gate** — thresholds crossed  
6. **K8s production** — manifests only  
7. **Ollama in local compose** — points to cluster DNS; assess uses stub/fallback in proof  
8. **OTEL end-to-end** — not proven HTTP → DB trace match  

---

## Recommended delivery phases

### Phase A — Beta unblock (2–4 weeks estimated)

- Run full ingestion bootstrap  
- Fix or quarantine 59 tests  
- Mount/copy `tests/` in Docker  
- UI: hide partial modules  
- Re-run workflow + integrity + targeted pytest  

**Exit criteria:** Gates 1–2 PASS, Gate 3 corpus PASS, Gate 8 pytest PASS or signed waiver list

### Phase B — Controlled beta (4–8 weeks)

- Promote next 5–8 modules with legal review  
- k6 50 VU green  
- Staging K8s deploy + ingress  
- OTEL trace proof  

**Exit criteria:** Gates 9–10 partial PASS, Gate 11 smoke PASS

### Phase C — Public go-live

- Remaining modules to production  
- Stripe live + secret rotation  
- Backup/restore drill  
- Legal accuracy matrix signed  
- 10k load architecture (not yet 100k)  

---

## Risk register (top 5)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sparse RAG misleads stakeholders | High | Block "RAG works" claims until QA-001 closed |
| Partial modules exposed in UI | High | Fail-closed module catalog enforcement |
| Test drift hides regressions | Medium | CI must run full suite |
| Password mismatch on fresh clone | Medium | Document override; single .env template |
| Cluster-only Ollama URL breaks local LLM | Medium | Local ollama compose service or dev stub |

---

## Sign-off checklist (for product owner)

- [ ] Accept **YES AFTER P0/P1** finishability decision  
- [ ] Accept scope cut (11 modules) OR fund full 24-module legal-data pipeline  
- [ ] Accept beta without K8s until Phase B  
- [ ] Assign owners from `CURSOR_REPAIR_BACKLOG.md`  
- [ ] Schedule re-audit after QA-001 + QA-004 closed  

---

## Hard exit (if audit could not complete)

**Not applicable** — audit completed with local Docker access. Partial evidence only for K8s cluster and full pytest (used cached `reports/full_suite_results.txt` + incomplete container run).

---

## Next 10 actions (ordered)

1. Run `docker compose --profile bootstrap run --rm db-bootstrap` — populate corpus  
2. Re-test RAG: POST `/api/rag/search` must return ≥1 result  
3. Fix Dockerfile to include root `tests/` for container parity  
4. Triage 59 failures — start with `tests/integration/test_phase3c_documents.py` auth fixtures  
5. Re-run full pytest; save output to `reports/pytest_full_cursor_20260614.txt`  
6. Update frontend to hide `partial` modules from intake claim-type picker  
7. Run k6 smoke after backend warm-up; document expected 401 rate  
8. Deploy to staging K8s; capture pod health screenshot/log  
9. Prove trace_id in `brain_traces` matches API response (one SQL + one curl)  
10. Schedule qa-release-gatekeeper re-review on closed P0/P1 items  

---

**Final recommendation:** **CONTINUE** incremental repair — do **not** rebuild core. Prioritize **QA-001 (RAG corpus)** and **QA-002 (module completeness)** before any public marketing of "full UK employment law AI."
