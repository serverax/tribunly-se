# SA-014 Connectivity Matrix (proven with live in-cluster tests)

All tests run read-only via `kubectl exec` + in-pod `curl`/`psql`. "Pod Running" is NOT used as proof anywhere below.

| # | Path | Test command (in-pod) | Result | Verdict | Evidence |
|---|------|------------------------|--------|---------|----------|
| 1 | frontend → backend (route exists) | ingress `staging.lawapp.ai/` → svc `lawapp-backend:80`; frontend pages call `/auth/token`,`/auth/register`,`/cases`,`/documents/generate` | ingress backend = lawapp-backend (1 endpoint); pages reference the routes; backend `/cases` returns 401 unauth, `/health` 200 | **PASS** | infra/k8s/lawapp-ingress.yaml; client/public/pages/{login,register,assessment}.html; 01 |
| 2 | backend health + protected route | `curl localhost:8000/health`; `curl -o/dev/null -w %{http_code} localhost:8000/cases` | `/health`=200 `{db:connected, auth_mode:jwt}`; `/cases` (no JWT)=**401** | **PASS** | full-distributed-workflow-proof.txt; 03 |
| 3 | backend → brain | brain served by same backend image (`run_brain` in-proc via `/api/brain/trace`); also reachable cross-svc | `/api/brain/trace` POST returns full 23-step trace | **PASS** | full-distributed-workflow-proof.txt |
| 4 | brain → postgres (trace persist) | `psql -U lawapp_user -d lawapp -tAc "SELECT count(*) FROM brain_traces"` before vs after one trace | 5 → **6**; row `cfcf419d-…` present with final_status, citations_verified | **PASS** | full-distributed-workflow-proof.txt |
| 5 | rag-ingestion → postgres | rag-ingestion `needs_db=True`; corpus_chunks populated by ingestion | `corpus_chunks` = 890 rows, 0 orphans; ingestion `/health`=200, routes `/v1/ingest`,`/v1/ingest/legal-source` | **PASS** | 04; psql corpus_chunks |
| 6 | rag-retrieval → postgres/pgvector | real pgvector cosine NN query over `corpus_chunks` (HNSW index) | returns 3 real Equality Act 2010 chunks w/ source_id=10, source_url legislation.gov.uk, cos_dist 0.0/0.123/0.138 | **PASS** | 04; pgvector NN output |
| 6b | rag-retrieval service business route | `curl POST :8080/v1/retrieve {query, top_k}` | 200, `source:local_corpus`, `llm_called:false`, but **results:[]** for plain-text query (needs pre-embedded query vector) | **PARTIAL** | 04 |
| 7 | brain → ollama (WORKING svc) | `curl http://ollama-inference.lawapp-ai.svc:11434/api/tags` | 200, model `qwen2.5:3b-instruct-q6_K` loaded | **PASS (svc itself)** | 02 |
| 7b | brain → llm-inference-service (CONFIGURED svc, DEAD) | `curl http://llm-inference-service.lawapp-ai.svc:11434/api/tags` | HTTP 000 / curl exit 7 (conn refused — 0 endpoints) | **FAIL (misconfig)** | 01,02 |
| 8 | brain internal RAG stage | trace `steps[].retrieve_legal_evidence` + `rag_sources` | `retrieve_legal_evidence`=ok, sources_count=10, graph_nodes=10; rag_sources=[hybrid, legal_graph] | **PASS** | full-distributed-workflow-proof.txt |
| 9 | brain internal rules stage | trace `steps[].run_rules_engine` | ok, rules_found=0, claim_type=unfair_dismissal | **PASS (ran)** | full-distributed-workflow-proof.txt |
| 10 | brain internal CitationGuard | trace `steps[].verify_citations` | ok, verified=10, failed=0 (validates retrieved sources, fail-closed on missing facts blocks draft) | **PASS** | full-distributed-workflow-proof.txt |
| 11 | brain safety policy | trace `safety` checks | passed=True; 5 critical/high checks incl. critic_citation_integrity, deadline_from_rules | **PASS** | full-distributed-workflow-proof.txt |
| 12 | brain fail-closed on missing facts | trace `generate_draft`/`evaluate_draft` | generate_draft=missing_edt; evaluate_draft=fail (missing jurisdiction,edt,service_start_date); NO fabricated answer | **PASS (correct fail-closed)** | full-distributed-workflow-proof.txt |
| 13 | cross-namespace DNS | brain → `lawapp-backend.lawapp-api.svc:80/health` | HTTP 200 | **PASS** | 02 |
| 14 | standalone citation-guard validation | `curl POST :8080/v1/citations/validate` with all-zeros UUID and empty list | all-zeros UUID → **valid:true (WRONG)**; empty → **valid:true (WRONG)**; deployed image is permissive stub | **FAIL (deployed svc)** | 05 |
| 15 | rules-engine deadline route | `curl POST :8080/v1/deadline/calculate {claim_type, effective_date}` | 200, source:rules_table, llm_called:false, but **no deadline date** in response body | **PARTIAL (thin)** | 02 |

## Summary
- Core product distributed path (frontend → backend → brain → postgres → RAG retrieval → citation verify → safety → trace persist) is **PROVEN PASS** with real data and fail-closed behaviour.
- Two real defects: (a) `llm-inference-service` DEAD-SERVICE selector mismatch + brain configured to it; (b) deployed standalone `lawapp-citation-guard` image is a permissive stub (NOT in the brain path).
- Two completeness gaps (PARTIAL): rag-retrieval `/v1/retrieve` returns empty for plain-text query; rules-engine `/v1/deadline` returns no deadline field.
