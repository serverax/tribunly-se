# SA-014 — lawapp Distributed Services: Real, Reachable, WIRED?

Agent: microservices-integration-agent · Context: `admin@ordinox-talos` · Date: 2026-06-07
Method: read-only kubectl + in-pod curl/psql, additive evidence only. No deployments/secrets/DB schema mutated.
Evidence root: `/mnt/f/lawapp/reports/hard-exit/evidence/microservices/`
Scripts: `/mnt/f/lawapp/scripts/lawapp/prove-microservices-wiring.sh`, `/mnt/f/lawapp/scripts/lawapp/scan-microservice-placeholders.sh`

## HARD EXIT RESULT: PARTIAL

The **core product distributed path is PROVEN REAL and WIRED** with live data and correct fail-closed behaviour. Two real defects and two completeness gaps prevent a clean PASS. None of them break the primary user assessment path, but two are correctness/security relevant and require owner-authorized fixes.

---

## What is PROVEN (PASS)

1. **Backend** (`lawapp-api/lawapp-backend`): `/health`=200 `db:connected auth_mode:jwt`; protected `/cases` unauth = **401**. Frontend (login/register/assessment pages) + ingress `staging.lawapp.ai/` → `lawapp-backend:80` (has endpoint). REAL+WIRED.
2. **Brain** (`lawapp-ai/lawapp-brain`): full **23-step pipeline** executes on a real authenticated request (register→token→`/api/brain/trace`). Steps include `retrieve_legal_evidence` (10 sources, 10 graph nodes), `run_rules_engine`, `verify_citations` (10 verified / 0 failed), `apply_safety_policy` (5 checks incl. critic_citation_integrity, deadline_from_rules), `store_audit_log`.
3. **Trace persistence**: `brain_traces` in `lawapp-rag/lawapp-postgres-0` incremented on a live request (verified twice: 5→6 manual, 9→10 by script) with the exact `trace_id`, `user_id`, `citations_verified`, `final_status`.
4. **RAG corpus**: `corpus_chunks` = **890 rows, 0 orphans**, real UK legislation (Equality Act 2010, legislation.gov.uk source_urls). A real **pgvector HNSW cosine** nearest-neighbour query returns real chunks with `source_id`.
5. **Fail-closed correctness**: with missing EDT/jurisdiction the brain set `generate_draft=missing_edt`, `evaluate_draft=fail`, and produced **NO fabricated legal answer or deadline** — exactly the required legal-AI safety behaviour.
6. **Service health**: backend, brain, rules-engine, llm-gateway, document-service, rag-retrieval, rag-ingestion, crawler, citation-guard all `/health`=200 with **real business routes** (not bare stubs); all use the shared `services._common.create_service` factory.
7. **Endpoints**: every `lawapp-*` k8s Service has non-empty endpoints EXCEPT the two documented exceptions.
8. **No CrashLoop / unexpected Pending** among critical (lawapp-ai/api/rag/security) pods.
9. **Working LLM**: `ollama-inference` (3 endpoints) serves `qwen2.5:3b-instruct-q6_K` (`/api/tags`=200).
10. **Cross-namespace DNS** works (brain → `lawapp-backend.lawapp-api`=200).
11. **prove-microservices-wiring.sh** runs **fail-closed** (set -Eeuo pipefail, no `|| true`/`echo PASS`), passes all assertions, exits 0; negative self-test confirms exit 1 on failure.

---

## Defects (block clean PASS)

### D1 — DEAD-SERVICE: `llm-inference-service` (FAIL)
`infra/k8s/llm-inference-fabric.yaml` Service selector = `{app: ollama-inference}`, but the ollama DaemonSet pods carry label `{app.kubernetes.io/name: ollama-inference}`. **Selector mismatch → 0 endpoints.** Live curl from brain → `http://llm-inference-service...:11434/api/tags` = HTTP 000 / exit 7 (connection refused). The brain AND backend `LOCAL_INFERENCE_URL`/`ai_provider.base_url` point at this dead service; they fail soft. Fix: repoint to `ollama-inference` (or fix the dead Service selector). Owner-authorization pending.

### D2 — STUB deployed citation-guard (FAIL, security-relevant but NOT in brain path)
The deployed `lawapp-security/lawapp-citation-guard` image (`b13c59d…`) returns `{"valid":true}` for the **all-zeros fake UUID** and for **empty citations** — it should return `valid:false`/`no_citation_present`. The SOURCE (`services/lawapp_citation_guard/app.py`) is CORRECT (DB-backed `valid_corpus_uuids`, fail-closed) and returns `claimed`/`valid_uuids`/`reason` fields the live image omits. **Deployed image is stale/divergent from source** — effectively a permissive stub. Mitigant: the **brain does NOT call this microservice**; the in-brain `verify_citations` (the one in the real product path) is real (10/10 verified). Fix: redeploy citation-guard from current source.

---

## Completeness gaps (PARTIAL)

- **G1** `lawapp-rag-retrieval /v1/retrieve` returns `results:[]` for a plain-text query (`source:local_corpus, llm_called:false`). It appears to expect a pre-embedded query vector. The underlying pgvector path is proven working via direct DB query, but the service route's text-query path returns empty. Needs query-embedding wiring or doc.
- **G2** `lawapp-rules-engine /v1/deadline/calculate` returns `{trace_id, service, source:rules_table, llm_called:false}` with **no actual deadline date** in the body. Route runs but response is thin.
- **G3** `lawapp-worker` deployed body is a `while True: time.sleep()` **NO-OP** — no real task processing.
- **G4** `lawapp-monitoring` CronJobs: **89 Pending** smoke-test pods (FailedScheduling: "Too many pods" + node taints) + `lawapp-health-probe` **CrashLoopBackOff**. Non-product observability jobs, but a real cluster-hygiene backlog.
- **G5** `lawapp-llm-gateway` is REAL + reachable but **not wired** into the live brain path (brain calls ollama directly). Dead-code candidate or future wiring.
- **G6** Deployed `lawapp-brain` runs the full backend image on :8000, not the slim `services.lawapp_brain.app` on :8080 from its Dockerfile (deploy/code divergence; functionally fine).

## Documented / allowed (not failures)
- `lawapp-reasoning-worker` SCALED-0 (0/0, no entrypoint) — intentional.
- `needs_db=False` on llm-gateway/document-service/crawler — by design (non-DB-owning).
- `iterlaw-*` namespaces (parallel/older lawapp-backend InvalidImageName) — out of `lawapp-*` scope.

---

## Service count by classification (16 tracked)
REAL+WIRED: 10 · REAL-not-WIRED: 1 (llm-gateway) · STUB (deployed): 1 (citation-guard) · NO-OP-BODY: 1 (worker) · SCALED-0: 1 (reasoning-worker) · DEAD-SERVICE: 1 (llm-inference-service) · REAL low-use: 1 (postgres-api).

## Paths: PASS / FAIL
PASS: frontend→backend, backend health+auth, backend→brain, brain→postgres trace persist, rag-ingestion→postgres (corpus 890), pgvector retrieval w/ source_id, brain internal RAG+rules+CitationGuard+safety, brain fail-closed, brain→ollama(working svc), cross-ns DNS.
FAIL: brain→llm-inference-service (dead), standalone citation-guard validation (stub deployed image).
PARTIAL: rag-retrieval /v1/retrieve (empty), rules-engine /v1/deadline (no date).

## Next required actions (for PASS)
1. Repoint brain/backend `LOCAL_INFERENCE_URL` to `ollama-inference` OR fix `llm-inference-service` selector (D1).
2. Redeploy `lawapp-citation-guard` from current source; re-run negative test (all-zeros UUID → valid:false) (D2).
3. Wire query-embedding into rag-retrieval `/v1/retrieve`; return deadline date from rules-engine (G1/G2).
4. Clean the lawapp-monitoring Pending/CrashLoop CronJob backlog (G4).

## Verdict
**HARD EXIT RESULT: PARTIAL** — core distributed legal path real, grounded, and fail-closed (PASS); two infra/deploy defects (dead inference Service the brain targets; stale permissive citation-guard image) and minor completeness gaps prevent a clean PASS. No mutations made; evidence + scripts produced.
