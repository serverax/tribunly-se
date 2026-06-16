# Ingestion + LangGraph Integration Checkpoint

**Updated:** 2026-06-16  
**Branch:** `release/lawapp-clean-snapshot`  
**HEAD (at write):** `1fc6b9f` feat(legal-truth): wire DB-first validator and proposal queue into Brain.  
**Session:** dual-plane ingestion workers, LangGraph (rolled back), legal/reason API (removed), Brain legal-truth path  
**ADR:** [`docs/adr/ADR-000-langgraph-gate.md`](../adr/ADR-000-langgraph-gate.md)

---

## Executive summary

Dual-plane ingestion (Postgres always, Neo4j optional) is largely **committed** (`afa0331`): four Redis queue workers, graph LLM extractor prompts, migration 084, and proposal queue plumbing. **LangGraph and `POST /api/v1/legal/reason` were rolled back** per ADR-000 and owner decision Agentic Q1. Legal reasoning must enter through `backend/core/brain.py` and existing routes (`/assess`, `/api/diagnosis`). Remaining work is ingestion Docker proof, commit of compose `ingestion-worker`, corpus re-embed, and reconciling optional Neo4j with owner Q2.

---

## Completed (evidence-backed)

- **Ingestion workers A-D** (`afa0331`): `ingestion/workers/legislation_worker.py`, `case_law_worker.py`, `acas_worker.py`, `rules_compiler_worker.py`, `base_worker.py`
- **Redis queues** (`ingestion/workers/base_worker.py`): `ingestion-legislation`, `ingestion-case-law`, `ingestion-acas`, `embedding-jobs`, `graph-build-jobs`
- **Unified dual-write coordinator**: `ingestion/workers/unified_indexer.py` (Postgres always; `NEO4J_ENABLED` optional)
- **Worker runner**: `ingestion/worker_runner.py`
- **Graph LLM extraction**: `ingestion/graph/relationship_extractor.py`, `ingestion/prompts/graph_builder_system.txt`, `graph_builder_user.txt`
- **Neo4j optional plane**: `ingestion/graph/neo4j_batch_writer.py`, `neo4j_ingest.py`
- **Migration 084**: `db/migrations/084_ingestion_jobs_dual_plane.sql` (`ingestion_jobs`, `knowledge.ingestion_proposals`)
- **Proposal queue (no direct rules write)**: `backend/core/knowledge_proposer.py`, `backend/api/ingestion_proposal_routes.py`, migrations `082_*`
- **FCL sample-only guard**: `ingestion/workers/case_law_worker.py` checks `FCL_BULK_LICENCE_GRANTED`
- **Brain legal-truth validator** (`1fc6b9f`): `backend/core/legal_truth_validator.py` wired in `backend/core/brain.py`
- **Control plane MotherController**: `backend/core/control_plane/mother_controller.py`
- **Postgres GraphRAG (8018)**: `backend/core/rag/graphrag_traversal.py`, `lawapp-graph-rag-service`
- **Ingestion unit tests**: `pytest tests/test_relationship_extractor_schema.py tests/test_unified_indexer_dual_write.py` -> **5 passed** (2026-06-16)
- **Single Brain enforcement**: `tests/test_single_brain_architecture.py`, `docs/adr/ADR-000-langgraph-gate.md`
- **Owner decisions**: `docs/decisions/OWNER_DECISIONS_2026-06-16.md`
- **Bootstrap ingestion proof (legacy)**: `reports/bootstrap_ingestion_cursor.txt` (2026-06-14 CLML run)

**Recent commits:**

```
1fc6b9f feat(legal-truth): wire DB-first validator and proposal queue into Brain.
d094d1c docs: ingestion/langgraph integration checkpoint
afa0331 feat(snapshot): control plane, graph RAG, Case OS, checkpoint docs
```

**LangGraph rollback (removed, do not reintroduce without ADR):**

- `backend/ai/graph/`, `backend/core/langgraph/`, `backend/api/legal_reason_routes.py`
- `langgraph` removed from `pyproject.toml` / `Dockerfile`
- `tests/test_legal_reason_api.py`, `tests/test_langgraph_legal_reason.py`

---

## In progress / partial

- **Docker `ingestion-worker`**: in modified `docker-compose.yml` (`profiles: ingestion`); not in committed `HEAD` compose
- **Docker optional `neo4j`**: in modified compose; owner Q2 prefers Postgres graph by default
- **Architecture docs (draft, untracked)**: `docs/architecture/INGESTION_DUAL_PLANE_V1.md`, `K8S_INGESTION_SCALING_V1.md`; LangGraph/LEGAL_REASON docs superseded by ADR-000
- **`/assess` -> MotherController**: uncommitted `backend/api/main.py` changes
- **`unified_indexer.py` / `rules_compiler_worker.py`**: uncommitted local edits
- **Ingestion tests**: `tests/test_relationship_extractor_schema.py`, `tests/test_unified_indexer_dual_write.py` not committed
- **Deploy proof**: `reports/ingestion_langgraph_v1_cursor.txt` not created
- **Duplicate 082 migrations**: three `082_*ingestion_proposals*.sql` variants need consolidation

---

## Not started

- **`POST /api/v1/legal/reason`**: explicitly removed per ADR-000
- **LangGraph orchestrator**: blocked by Agentic Q1
- **Wire `analysis.html` to `/api/v1/legal/reason`**: Case OS uses `POST /assess` via `client/public/js/case-engine.js`
- **K8s `lawapp-ingestion` worker Deployment**: design only; existing `infra/k8s/lawapp-ingestion-jobs.yaml` is one-shot Jobs
- **Live Docker ingestion proof**: enqueue job + verify `ingestion_jobs` row end-to-end
- **`reports/ingestion_langgraph_v1_cursor.txt`**: specified deploy proof artifact

---

## Blockers / owner decisions

| Blocker | Status |
|---------|--------|
| LangGraph second runtime | **BLOCKED** by ADR-000 and Agentic Q1 |
| Neo4j optional vs Postgres canonical | Owner Q2: Postgres `legal_nodes`/`legal_edges`; Neo4j only if `NEO4J_ENABLED=true` |
| FCL bulk case law | Sample-only; `FCL_BULK_LICENCE_GRANTED=false` in Worker B |
| Ollama / load gates | k6 p95 ~37s at 50 VU (`reports/SESSION_GATES_C295E3C.md`) |
| External OpenRouter | Disabled unless `ALLOW_EXTERNAL_LLM=true`; legal routes local Ollama only |
| Subagent `89552fa1` | Transcript: user query only, no assistant output |

---

## Next actions (ordered)

1. Commit ingestion test files and `unified_indexer.py` / `rules_compiler_worker.py` fixes.
2. Commit `docker-compose.yml` `ingestion-worker` profile; run local queue proof.
3. Apply migration 084 in Docker test env; dedupe 082 proposal migrations.
4. Track `INGESTION_DUAL_PLANE_V1.md` and `K8S_INGESTION_SCALING_V1.md`; mark LangGraph docs historical.
5. Run bootstrap + 1024 re-embed (`scripts/reembed_corpus_1024.py`).
6. Write `reports/ingestion_langgraph_v1_cursor.txt` (compose ps, queue job, Brain `/assess` trace).
7. Do not re-add LangGraph without owner-approved ADR.

---

## Commands to resume

```bash
docker compose up -d db redis backend

docker compose run --rm ingestion python scripts/run_migrations.py

docker compose --profile ingestion up -d ingestion-worker

docker compose --profile graph-neo4j up -d neo4j   # dev only; conflicts with owner Q2 default

docker compose exec redis redis-cli LPUSH ingestion-legislation '{"job_id":"manual-1","section":"98","act_meta":{"leg_type":"ukpga","year":1996,"chapter":"18","act_title":"Employment Rights Act 1996"}}'

python -m pytest tests/test_relationship_extractor_schema.py tests/test_unified_indexer_dual_write.py -q
python -m pytest tests/test_single_brain_architecture.py -q

curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal conduct","facts":{"edt":"2026-05-10","employment_length":18,"dismissal_type":"conduct"},"jurisdiction":"EW","use_model":false}'
```

---

## Related docs

- [INGESTION_DUAL_PLANE_V1.md](../architecture/INGESTION_DUAL_PLANE_V1.md) (draft)
- [K8S_INGESTION_SCALING_V1.md](../architecture/K8S_INGESTION_SCALING_V1.md) (draft)
- [LANGGRAPH_ORCHESTRATION_V1.md](../architecture/LANGGRAPH_ORCHESTRATION_V1.md) (superseded)
- [LEGAL_REASON_API_V1.md](../architecture/LEGAL_REASON_API_V1.md) (superseded)
- [ADR-000-langgraph-gate.md](../adr/ADR-000-langgraph-gate.md)
- [OWNER_DECISIONS_2026-06-16.md](../decisions/OWNER_DECISIONS_2026-06-16.md)
- [THREE_LAYER_SYSTEM.md](../architecture/THREE_LAYER_SYSTEM.md)
- [CURSOR_CHECKPOINT_REPORT.md](../qa/CURSOR_CHECKPOINT_REPORT.md)

---

## Counts (at write)

| Category | Count |
|----------|------:|
| Completed (major items) | 16 |
| In progress / partial | 8 |
| Not started / removed | 6 |
