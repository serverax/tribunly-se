# Ingestion + LangGraph Integration Checkpoint

**Generated:** 2026-06-16  
**Repo:** serverax/lawapp  
**Branch:** `release/lawapp-clean-snapshot`  
**HEAD (at write):** `afa0331` feat(snapshot): control plane, graph RAG, Case OS, checkpoint docs  
**Case OS milestone:** `15c2638`  
**Session scope:** dual-plane ingestion workers, LangGraph orchestrator, `POST /api/v1/legal/reason`  
**Baseline inspection:** 2026-06-14 repo audit (evidence below)

---

## Executive summary

Case OS UX is **complete and committed** (static Case Operating System shell, wired to existing `/assess` and case APIs). The ingestion + LangGraph + legal/reason stack is **not integrated**. Background subagents dispatched for this work **did not finish** (transcript contains user query only). Partial **uncommitted** scaffolds exist on disk (`ingestion/workers/`, graph RAG, control plane) but are not proven, not wired to the API, and lack the architecture docs and tests specified in the HLD.

---

## Completed (evidence-backed)

### Case OS UX (COMPLETE)

| Item | Evidence |
|------|----------|
| Case OS pages | `client/public/pages/` (29 pages incl. `dashboard.html`, `my-case.html`, `advisor.html`, `analysis.html`, `workspace.html`, etc.) |
| Design tokens | `client/public/css/case-os.css` |
| Case state + API wiring | `client/public/js/case-engine.js` (`loadCase`, `runClaimAssessment`, debounced `liveAssess` via `POST /assess`) |
| Shared shell | `client/public/js/app-shell.js`, `client/public/js/case-components.js` |
| Commit | `15c2638` (Case OS UX integration) |
| Proof report | `reports/case_os_ux_integration_cursor.txt`, `reports/case_os_responsive_cursor.txt` |
| Architecture note | `docs/frontend/CASE_OS_ARCHITECTURE.md` |

`analysis.html` renders three reasoning layers (rules, corpus, citation guard) but calls **`POST /assess`** via `CaseEngine.runClaimAssessment`, **not** `/api/v1/legal/reason`.

### Prior platform work (related, not LangGraph)

| Item | Evidence |
|------|----------|
| Owner decisions recorded | `docs/decisions/OWNER_DECISIONS_2026-06-16.md` (Q2: Postgres graph canonical, no Neo4j container by default) |
| Brain governance pipeline | `backend/core/brain.py`, CitationGuard path |
| Graph RAG stub / hybrid prep | `backend/core/rag/graphrag_traversal.py`, `lawapp-graph-rag-service` on :8018 |
| Corpus + RAG | `lawapp-rag-service` :8017, ~323 corpus chunks (per `docs/qa/CURSOR_CHECKPOINT_REPORT.md`) |

---

## In progress / partial (uncommitted or unproven)

| Item | Status | Notes |
|------|--------|-------|
| `ingestion/workers/` | **Untracked files on disk** | `base_worker.py`, `legislation_worker.py`, `case_law_worker.py`, `acas_worker.py`, `rules_compiler_worker.py`, `unified_indexer.py` present; **not in git**, no `worker_runner.py`, no Docker profile proof |
| `ingestion/graph/` | **Untracked scaffold** | `neo4j_ingest.py`, `relationship_extractor.py` (per git status); no deploy proof |
| `ingestion/prompts/` | **Untracked** | graph builder prompts not verified against HLD |
| `control-plane/` | **Untracked NestJS tree** | Not wired as gateway for `/legal/reason` |
| `db/migrations/084_*.sql` | **Multiple untracked variants** | `084_ingestion_jobs_dual_plane.sql` and duplicates; not applied / not proven |
| Graph RAG hybrid layer | **Partial** | `docs/architecture/GRAPH_RAG_LAYER_V1.md` exists (untracked); Neo4j optional via profile |
| Subagent `89552fa1` | **Never finished** | Transcript: user query only, no assistant output |
| Subagent `cf6f3371` | **Never finished** | Checkpoint creation task; user query only |
| Subagent `6e5e6e51` | **Never finished** | LangGraph `backend/ai/graph/` task; user query only |

---

## Not started (per HLD and 2026-06-14 inspection)

| Item | Expected path |
|------|---------------|
| LangGraph orchestrator (`backend/ai/graph/`) | `graph.py`, `state.py`, `nodes/intake.py` through `govern.py` |
| Alternate LangGraph adapter | `backend/core/langgraph/` (earlier spec) |
| `POST /api/v1/legal/reason` | `backend/api/main.py` or `legal_reason_routes.py` |
| `POST /api/legal/reason` alias | Same |
| Architecture docs | `docs/architecture/INGESTION_DUAL_PLANE_V1.md`, `LANGGRAPH_ORCHESTRATION_V1.md`, `LEGAL_REASON_API_V1.md`, `K8S_INGESTION_SCALING_V1.md` |
| `ingestion/worker_runner.py` | Redis queue consumer |
| Docker `ingestion` profile service | `docker-compose.yml` profile not proven |
| Tests | `tests/test_legal_reason_api.py`, `tests/test_langgraph_legal_reason.py`, `tests/test_relationship_extractor_schema.py`, `tests/test_unified_indexer_dual_write.py` |
| Deploy proof | `reports/ingestion_langgraph_v1_cursor.txt` |
| `analysis.html` wired to `/api/v1/legal/reason` | Still uses `/assess` |

---

## Owner questions pending

Parent chat asked **11 architecture decisions** (2026-06-16). **No owner replies recorded** in repo. Implementation should not assume answers beyond `docs/decisions/OWNER_DECISIONS_2026-06-16.md` where they conflict.

| # | Topic | Question (short) |
|---|-------|------------------|
| 1 | **Neo4j default** | Postgres-only by default with `NEO4J_ENABLED` opt-in, or Neo4j required for beta? (Owner doc Q2 says Postgres; HLD says dual Neo4j plane.) |
| 2 | **Gateway** | `/api/legal/reason` on Python monolith `:8000`, NestJS control plane `:3001`, or both (NestJS proxy)? |
| 3 | **LangGraph vs Brain** | Replace `brain.py` / MotherController, parallel path for `/legal/reason` only, or wrap existing pipeline? |
| 4 | **Govern fail mode** | Fail closed (4xx + errors) or partial assessment with explicit caveats? |
| 5 | **Latency target** | Allow lighter cached `/legal/reason` (500ms to 2s) while `/assess` stays ~37s p95 at load? |
| 6 | **Classification** | Deterministic/heuristic classify for Wave 1 (payload `claim_type` + keywords)? |
| 7 | **Queue tech** | Celery + Redis, Redis Streams (plain Python), or BullMQ via NestJS? |
| 8 | **Case law scope** | Sample-only until FCL: how many judgments for beta (5, 20, 50)? |
| 9 | **Rules compiler** | Proposals queue only, or auto-promote high-confidence deterministic rules (e.g. ERA s.111)? |
| 10 | **Deploy target** | Docker Compose local only this wave, or also K8s manifests in `infra/k8s/` without prod apply? |
| 11 | **Reasoning LLM** | Local Ollama only (`qwen2.5:3b` or other), or external when `ALLOW_EXTERNAL_LLM=true`? |

**Default if owner says "defaults OK":** follow `OWNER_DECISIONS_2026-06-16.md` (Postgres-first graph, local Ollama, proposals gate, FCL sample-only).

---

## Blockers

- **11 owner answers** not recorded for LangGraph/ingestion-specific choices (table above).
- **Subagent runs incomplete:** `89552fa1`, `cf6f3371`, `6e5e6e51` produced no implementation output.
- **No `/api/v1/legal/reason` route** in `backend/api/main.py` (grep: no match).
- **No `backend/ai/`** directory (HLD target layout).
- **Ingestion workers uncommitted** and not run under Docker profile.
- **Assess latency:** p95 ~37s at 50 VU (per `reports/SESSION_GATES_C295E3C.md`); conflicts with 500ms to 2s `/legal/reason` target unless lighter path approved (Q5).
- **FCL licence:** not granted; bulk case-law embedding blocked (`OWNER_DECISIONS` Q4).

---

## Next actions

1. **Owner answers 11 questions** (table in Owner questions pending).
2. **Implement `backend/ai/graph/` per HLD** (or consolidated `backend/core/langgraph/` adapter): `LawAppState`, seven nodes, real service adapters to `retrieve.py`, rules table, Ollama, CitationGuard govern.
3. **Dual-plane ingestion workers:** commit `ingestion/workers/`, add `worker_runner.py`, Redis queues, Docker `ingestion` profile, migration 084, dual-write proof Postgres + optional Neo4j.
4. **Wire `analysis.html` to `/api/v1/legal/reason`** when route is live (replace or supplement `/assess` on analysis page).

### Secondary (after 1 to 4)

5. Write four architecture docs (`INGESTION_DUAL_PLANE_V1.md`, `LANGGRAPH_ORCHESTRATION_V1.md`, `LEGAL_REASON_API_V1.md`, `K8S_INGESTION_SCALING_V1.md`).
6. Add pytest suite + `reports/ingestion_langgraph_v1_cursor.txt` curl proof.
7. Reconcile NestJS `control-plane/` with Python monolith gateway decision (Q2).

---

## Commands to resume

```bash
# Verify branch and Case OS commit
git checkout release/lawapp-clean-snapshot
git log -1 --oneline 15c2638

# Confirm gaps
test ! -d backend/ai && echo "backend/ai missing"
grep -r "legal/reason" backend/api/ || echo "no legal/reason route"

# When implemented: local stack
docker compose up -d db redis backend
docker compose --profile ingestion up -d ingestion-worker

# API proof (expected after step 2)
curl -s -X POST http://localhost:8000/api/v1/legal/reason \
  -H "Content-Type: application/json" \
  -d '{"claim_type":"unfair_dismissal","facts":{"ed_t":"2026-05-10","employment_length":18,"dismissal_type":"conduct"}}'

# Tests
pytest tests/test_legal_reason_api.py tests/test_langgraph_legal_reason.py -q
```

---

## Related docs

- `docs/decisions/OWNER_DECISIONS_2026-06-16.md`
- `docs/frontend/CASE_OS_ARCHITECTURE.md`
- `docs/architecture/GRAPH_RAG_LAYER_V1.md` (partial, untracked)
- `docs/architecture/CONTROL_PLANE_NESTJS_V1.md` (untracked)
- `docs/qa/CURSOR_CHECKPOINT_REPORT.md`
- `reports/case_os_ux_integration_cursor.txt`
- `reports/SESSION_GATES_C295E3C.md` (Ollama gate, assess latency)

---

## Counts

| Category | Count |
|----------|-------|
| Completed (Case OS) | 1 major deliverable |
| In progress / partial | 8 items |
| Not started (HLD) | 12+ items |
| Owner questions open | 11 |
| Subagents unfinished | 3 |
