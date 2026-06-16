# Ingestion + Brain checkpoint

**Status:** PRE-BETA ENGINEERING (not production ready)  
**Branch:** `release/lawapp-clean-snapshot`  
**Updated:** 2026-06-16  
**Rollback commit:** `33abd9c` (Enforce single-brain architecture: roll back LangGraph bypass paths)  
**ADR:** [`docs/adr/ADR-000-langgraph-gate.md`](../adr/ADR-000-langgraph-gate.md)  
**Owner decisions:** [`docs/decisions/OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md) (RESOLVED - do not re-ask)

---

## LangGraph: STOPPED / rolled back

| Item | Status |
|------|--------|
| `backend/ai/graph/` StateGraph | **REMOVED** (33abd9c) |
| `backend/core/langgraph/` | **REMOVED** |
| `POST /api/v1/legal/reason` / `/api/legal/reason` | **REMOVED** |
| `langgraph` / `langchain-core` production deps | **REMOVED** |
| `tests/test_langgraph_legal_reason.py` | **REMOVED** |
| `docs/architecture/LANGGRAPH_ORCHESTRATION_V1.md` | **SUPERSEDED** (historical only) |
| `docs/architecture/LEGAL_REASON_API_V1.md` | **SUPERSEDED** (historical only) |

**Enforcement:** `tests/test_single_brain_architecture.py` (12 passed). Proof: `reports/single_brain_enforcement_cursor.txt`.

Coexistence with Brain is **not** a supported mode. Any reintroduction requires ADR + owner approval.

---

## Single reasoning runtime

| Path | Role |
|------|------|
| `backend/core/brain.py` | Sole authorised legal reasoning entry (19-step pipeline) |
| `backend/core/pipeline.py` | Stage implementations (retrieve, reason, govern) |
| `backend/core/orchestrator.py` | Case Engine Controller inside Brain (step 11b) |
| `POST /assess` | Brain / MotherController entry - no bypass |
| CitationGuard | `backend/core/agentic/corpus_citation_guard.py` in pipeline |

No second orchestration runtime (LangGraph, Mastra, NestJS reasoning) may serve legal answers.

---

## Graph RAG: retrieval only

Graph enrichment is **retrieval**, not a second reasoning runtime.

| Component | Behaviour |
|-----------|-----------|
| `backend/core/retrieve.py` | `retrieve_hybrid()` / `retrieve_hybrid_context()` - semantic + rules + graph in one call |
| Brain step 11 | `retrieve_legal_evidence` calls hybrid retrieval |
| Postgres graph | `legal_nodes` / `legal_edges` - canonical in-DB graph (Owner Q2) |
| Service 8018 | Postgres traversal via `graphrag_traversal.py`; fail closed when empty |
| Neo4j | **Optional read-only enrichment** only when `NEO4J_ENABLED=true` (default **`false`**) |
| Ingestion dual-write | `ingestion/workers/unified_indexer.py` - Postgres+pgvector always; Neo4j never authoritative |

Neo4j is not required for beta. No Neo4j container in default compose. Citations and rules always resolve to Postgres sources.

---

## Owner decisions RESOLVED (build order - do not re-ask)

All 31 items recorded 16 June 2026. Source: `docs/decisions/OWNER_DECISIONS_2026-06-16.md`.

### Deployment Plan §6 (Q1-Q15)

| # | Decision |
|---|----------|
| Q1 | `provision` / `module` / `legal_source` canonical; `corpus_chunks` = embedding layer; time-boxed dual-write then `provision` authoritative |
| Q2 | Postgres `legal_nodes` / `legal_edges`; refactor 8018; **no Neo4j container** |
| Q3 | 16 canonical modules + mapping from 24 `employment_modules` keys; subtopic/tag layer; honest coverage (11 production now) |
| Q4 | FCL sample-only until written grant; no bulk case-law embed without Computational Analysis Licence |
| Q5 | 1024-dim local embeddings (`bge-large-en-v1.5` or `mxbai-embed-large`); re-embed corpus; remove OpenAI 1536 refs |
| Q6 | Phase 0 parallel with k6/Ollama fixes; risky phases gated behind Track A+B re-ACCEPT |
| Q7 | Shared `lawapp` DB with `knowledge.*` schema namespace; not separate physical DB |
| Q8 | `infra/k8s/` canonical; deprecate partial `k8s/` subtree |
| Q9 | Reviewer gate UI on `lawapp-admin-service` (8007); SSO + MFA; not monolith admin routes |
| Q10 | ERA 2025 commencement: scheduled detection + human sign-off before `prospective` to `in_force` |
| Q11 | Per-source licence sign-off on each `legal_source` row before Phase 2 go-live |
| Q12 | Separate staging cluster (not namespace-only isolation on prod) |
| Q13 | API returns true per-module status + real coverage count; never claim 16 while 11 live |
| Q14 | In-cluster Ollama Deployment (AI namespace, internal-only); dev uses local host |
| Q15 | Track C entry independent of knowledge-layer completion |

### Feature Spec §5 (#1-#10)

| # | Decision |
|---|----------|
| 1 | `matter` canonical; optional `case_id` FK bridge; `/cases/*` aliases during transition |
| 2 | Same as Q1/Q5: `provision` + `corpus_chunks` embedding layer |
| 3 | Map 24 to 16 + tags; advertise 11 production topics |
| 4 | ET outcome dataset deferred until FCL; F6 on rules + corpus only |
| 5 | Partner registry table + notification routing; no hardcoded partners |
| 6 | Payments after Wave 2 hub; Stripe SKUs Wave 3; test mode until payments work order |
| 7 | `evidence_item` only; no dual-write to legacy `documents` |
| 8 | No anonymous special-category persistence; funnel metadata only |
| 9 | Law-change detection: checksum job + human sign-off (same as Q10) |
| 10 | UI strings: pre-translated bundles OK; case facts: on-device/self-hosted only (Wave 4) |

### Agentic Foundation (6 endorsements)

| # | Decision |
|---|----------|
| Mastra vs Python Brain | **Python Brain only**; no second orchestration runtime without ADR |
| RLHF | Feedback queue only; DSPy read-only queue consumer; never RLHF the generator |
| Companies House | Owner registers API key; Redis cache; public data |
| EU AI Act retention | Metadata/decisions/hashes in immutable traces; no raw special-category content |
| Domain expansion | `employment_uk` only enabled; fail closed elsewhere |
| Tool calling | Separate surfaces; shared deterministic implementations; auth + audit on registry tools |

### Owner-action items (not agent decisions)

FCL grant status, partner signing, Companies House key, ACAS/EHRC/HSE licence sign-off, staging cluster provisioning, Track C production entry - owner org actions only.

---

## Completed (evidence-backed)

| Area | Evidence |
|------|----------|
| Single-brain rollback | Commit `33abd9c`; ADR-000; `tests/test_single_brain_architecture.py` green |
| Dual-plane ingestion workers (A-D) | `ingestion/workers/*`, `unified_indexer.py`, `INGESTION_DUAL_PLANE_V1.md` |
| Migration 084 SQL | `db/migrations/084_ingestion_jobs_dual_plane.sql` (committed; Docker apply proof pending) |
| Hybrid graph retrieval | `retrieve_hybrid()` in `backend/core/retrieve.py`; `tests/test_graph_rag_hybrid.py` |
| Docker stack (12 services) | Gate 1 PASS (`reports/pytest_docker_full_c295e3c.txt`) |
| Corpus bootstrap | 941+ chunks post migration 075 (`reports/bootstrap_gate4_c295e3c.txt`) |
| Multi-language scaffold | See [`MULTI_LANGUAGE_CHECKPOINT.md`](./MULTI_LANGUAGE_CHECKPOINT.md) |
| Mother control plane v1 | Commit `9bcb5a5` |

---

## Remaining (C-F critical path - pre-beta)

Ordered engineering priorities. **Not LangGraph.**

| Priority | Item | Status | Proof target |
|----------|------|--------|--------------|
| **C** | Ingestion migration **084** Docker proof | **PENDING** | Apply 084; run `docker compose --profile ingestion`; worker job completes; `reports/ingestion_084_cursor.txt` |
| **D** | Case OS audit (static + Next.js wiring, honest module coverage, auth on mutating routes) | **PENDING** | `reports/case_os_audit_cursor.txt` |
| **E** | Grounding suite (live Ollama + `--live` legal accuracy + insufficient_grounding fail-closed) | **PENDING** | `reports/legal_accuracy_live.txt` without fallback; Gate 2 PASS |
| **F** | i18n verify (language engine + Brain `language_render` + API tests) | **PENDING** | `pytest tests/test_i18n_api.py tests/test_language_engine_router.py -q` |
| - | Domain verify (`employment_uk` fail-closed) | **PENDING** | Unsupported jurisdiction returns fail-closed |
| - | k6 assess latency (Gate 3) | **FAIL** | p95 < 3s @ 50 VU |
| - | Gatekeeper re-ACCEPT | **REJECT** | `docs/qa/GATEKEEPER_TRACK_AB_VERDICT.md` |

---

## Commands to resume (no LangGraph routes)

```bash
# Single-brain enforcement
python -m pytest tests/test_single_brain_architecture.py -q

# Ingestion 084 proof (critical path C)
docker compose up -d db redis backend
docker compose run --rm db-bootstrap
docker compose --profile ingestion up -d ingestion-worker

# Hybrid retrieval (graph = retrieval only)
python -m pytest tests/test_graph_rag_hybrid.py tests/test_unified_indexer_dual_write.py -q

# Grounding suite (critical path E)
docker compose --profile ollama up -d
python scripts/run_legal_accuracy.py --live
```

---

## References

- [`docs/adr/ADR-000-langgraph-gate.md`](../adr/ADR-000-langgraph-gate.md)
- [`docs/architecture/INGESTION_DUAL_PLANE_V1.md`](../architecture/INGESTION_DUAL_PLANE_V1.md)
- [`docs/architecture/GRAPH_RAG_LAYER_V1.md`](../architecture/GRAPH_RAG_LAYER_V1.md)
- [`docs/decisions/OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md)
- `.cursor/rules/40-ai-gate.mdc`
