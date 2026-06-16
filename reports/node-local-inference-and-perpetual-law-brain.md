# lawapp Node-Local Inference Fabric and Perpetual Law Brain Report

Statuses: **PASS** (proven by command/test/DB/output) · **FAIL** (tested, failed) ·
**UNPROVEN** (requires cluster/operator) · **NOT IMPLEMENTED** (missing).
No fake PASS. Cluster rows are UNPROVEN because this environment has no kubeconfig
for the Talos cluster (`kubectl` resolves only a dead AKS endpoint).

## 1. Verdict

| Area | Status |
| ---- | ------ |
| Inference fabric manifest (offline) | PASS  -  file exists, valid YAML |
| Ollama DaemonSet running per node | UNPROVEN  -  no kubeconfig / no cluster access |
| Local traffic policy (runtime) | UNPROVEN  -  no kubeconfig / no cluster access |
| Mother Algorithm wired to Ollama Service DNS | PASS  -  config + code proven |
| Perpetual Law Brain (crawler/critic/linker/embedder/orchestrator) | PASS  -  14/14 tests |
| Whitelist crawler | PASS  -  tests |
| Critic gate | PASS  -  tests |
| Graph linker (node+edge) | PASS  -  DB test |
| Embedder (gated, provenance) | PASS  -  DB test |
| RAG searchable (chunk stored + embedded + current) | PASS  -  DB test |
| Local Ollama single inference (qwen2.5:3b) | PASS  -  returned exact JSON `{"edt":"2024-05-01","reason":"conduct"}` |
| Benchmark latency vs 400ms gate (CPU, concurrency 4) | FAIL  -  P50 79.0s / P95 103.8s, 10/20 timed out @120s |
| CPU pinning / Guaranteed QoS (runtime) | UNPROVEN  -  no kubeconfig / no cluster access |
| Payment expanded | NO |

## 2. Files Changed / Created

| File | Change | Reason |
| ---- | ------ | ------ |
| infra/k8s/llm-inference-fabric.yaml | created | Ollama DaemonSet + ClusterIP Service (lawapp-ai, 11434, internalTrafficPolicy: Local) |
| infra/k8s/lawapp-llm-inference.yaml | deleted | superseded llama.cpp manifest |
| scripts/verify_llm_fabric_cluster.sh | created (renamed) | operator cluster-verification (PART 9 + node-IP checks) |
| scripts/bench_local_inference.py | created (earlier) | real concurrency benchmark, P95 gate |
| ingestion/config.py | edited | local_inference_url → Ollama Service DNS:11434, model qwen2.5:3b |
| backend/core/models.py | edited | LocalInferenceReasoningModel + select_model reads OLLAMA_BASE_URL |
| backend/core/ingestion/__init__.py | created | Perpetual Law Brain package |
| backend/core/ingestion/crawler.py | created | whitelist crawler (refuses non-official domains + redirects) |
| backend/core/agentic/ingestion_critic.py | created | structural/provenance critic gate |
| backend/core/ingestion/graph_linker.py | created | legal_nodes/legal_edges linkage (provenance-bound) |
| backend/core/ingestion/embedder.py | created | gated corpus_chunks embedder + staleness |
| backend/core/ingestion/perpetual_law_brain.py | created | ingestion orchestrator (audited, idempotent) |
| db/migrations/039_corpus_chunks_ingestion_run_id.sql | created | add ingestion_run_id to corpus_chunks |
| tests/test_autonomous_ingestion.py | created | 14 real tests |

## 3. Kubernetes Proof

| Command | Result | Evidence |
| ------- | ------ | -------- |
| kubectl get nodes -o wide | UNPROVEN | `dial tcp: lookup aks-iterla-...azmk8s.io: no such host` (only AKS kubeconfig present, unreachable; not the Talos cluster) |
| DaemonSet / pod placement / node-IP map / ollama list / svc routing / no-exposure / CPU pinning | UNPROVEN | operator must run `scripts/verify_llm_fabric_cluster.sh` on the Talos cluster |

## 4. Ollama Pod Status

UNPROVEN  -  no cluster access. Operator verification required per node
(148.251.247.56, 138.201.253.245, 138.201.202.174) via the verify script.

## 5. Service Routing

* Service DNS: `http://llm-inference-service.lawapp-ai.svc.cluster.local:11434` (set in manifest + config)  -  PASS (config/manifest), runtime UNPROVEN
* internalTrafficPolicy: `Local` (set in manifest)  -  PASS (manifest text), runtime behaviour UNPROVEN
* Public exposure: ClusterIP only, no Ingress/LoadBalancer in manifest  -  PASS (manifest), runtime UNPROVEN
* Local routing proof / failover: UNPROVEN  -  no cluster access

## 6. CPU and Memory Tuning

* Guaranteed QoS: manifest sets requests==limits (cpu "4", memory "8Gi")  -  PASS (manifest); runtime UNPROVEN
* CPU Manager static policy / true core pinning: UNPROVEN  -  requires kubelet configz on the Talos nodes (verify script step 9)
* Model: qwen2.5:3b · Quantization: Ollama default Q4_K_M tag (nearest standard small Qwen2.5-3B)  -  to be confirmed by `ollama list`
* Notes: do not claim true pinning unless kubelet `cpuManagerPolicy=static` is proven

## 7. Perpetual Law Brain Pipeline

| Stage | File | Status | Proof |
| ----- | ---- | ------ | ----- |
| whitelist crawler | backend/core/ingestion/crawler.py | PASS | test_whitelist_allows/blocks, redirect block |
| critic | backend/core/agentic/ingestion_critic.py | PASS | test_clml_passes, news/missing/jurisdiction fail |
| graph linker | backend/core/ingestion/graph_linker.py | PASS | test_ingest_creates_node_and_citation_edge |
| chunker+embedder | backend/core/ingestion/embedder.py | PASS | test_approved_content_is_embedded_and_searchable |
| orchestrator/audit | backend/core/ingestion/perpetual_law_brain.py | PASS | test_ingestion_run_logs_success / error_logs_failure |
| content-hash staleness | embedder.mark_stale | PASS | test_content_hash_change_marks_old_chunks_stale |

## 8. Database Changes

| Table/Migration | Change | Proof |
| --------------- | ------ | ----- |
| corpus_chunks (032, exists) | mapped as `legal_chunks` equivalent; added `ingestion_run_id` | `ALTER TABLE` + `CREATE INDEX` succeeded |
| legal_sources (028, exists) | mapped  -  NOT recreated (pasted duplicate rejected) | conflicting `CREATE TABLE` would error |
| corpus_ingestion_runs (028) / corpus_ingestion_errors (037) | reused | run/error tests pass |
| legal_nodes / legal_edges (018) | reused | node/edge test passes |
| 039_corpus_chunks_ingestion_run_id.sql | added column + index | applied to live db |

## 9. Test Results

| Test Command | Passed | Failed | Notes |
| ------------ | -----: | -----: | ----- |
| pytest tests/test_autonomous_ingestion.py -v | 14 | 0 | `14 passed in 23.64s` |
| pytest tests/test_local_inference.py -q | 4 | 0 | `4 passed` (provider wiring/fallback/de-id) |

## 10. Benchmark Results

| Node | Pod | Model | p50 | p95 | Notes |
| ---- | --- | ----- | --: | --: | ----- |
| local-docker (host CPU) | lawapp-ollama | qwen2.5:3b | 79,020 ms | 103,796 ms | **FAIL vs 400ms gate.** 20 requests, concurrency 4, max_tokens 128; 10 ok / 10 timed out @120s. Single-request inference PASS (correct JSON). CPU only  -  no GPU. This is local docker, NOT the Talos cluster. The pasted "P50 14.82ms" was REJECTED (it timed `x**2`, not inference). |

**Latency verdict:** the 400ms P95 target is unreachable for a 3B generative model on CPU. Honest options: (a) GPU nodes, (b) a much smaller model for extraction, (c) cap output tokens + treat as classification, or (d) accept multi-second reasoning latency with UI streaming and keep the <400ms gate only for the deterministic rules/DB path.

## 11. Security and Safety

* External exposure: none in manifest (ClusterIP only)  -  PASS (manifest), runtime UNPROVEN
* Domain whitelist: hardcoded `DOMAIN_WHITELIST`, non-official refused  -  PASS (tests)
* Redirect protection: each hop validated  -  PASS (test)
* Non-legal source rejection: news/opinion discarded  -  PASS (test)
* No AI-generated authority: only crawler-fetched, critic-approved content embedded  -  PASS (rejected doc → 0 chunks test)
* No raw personal data to model: de-identification asserted in reasoning providers  -  PASS (test_local_inference de-id test)

## 12. Remaining Blockers

| Blocker | Impact | Required Fix |
| ------- | ------ | ------------ |
| No Talos kubeconfig in this env | all cluster runtime checks UNPROVEN | operator runs `scripts/verify_llm_fabric_cluster.sh` with Talos kubeconfig |
| qwen2.5:3b not yet measured | benchmark UNPROVEN | run `scripts/bench_local_inference.py` against a reachable Ollama |
| case_law table absent (licence-blocked) | precedent ingestion limited | grant Find Case Law licence; ingest via crawler |

## 13. Final Decision

* Can lawapp use node-local Ollama now? UNPROVEN on the cluster (no access). The manifest + provider + config are PASS offline.
* Can the Mother Algorithm call the local fabric safely? PASS at code level (fail-soft to stub proven); cluster routing UNPROVEN.
* Can the Perpetual Law Brain ingest official law safely? PASS  -  14/14 tests prove whitelist-only, critic-gated, provenance-bound, no-AI-authority ingestion.
* Can approved documents become searchable in RAG? PASS  -  chunk stored, embedded, is_current (DB test).
* Unproven claims: every Talos cluster runtime check, and the real Qwen2.5-3B latency.
