# Ingestion + LangGraph checkpoint

**Branch:** `release/lawapp-clean-snapshot`  
**Updated:** 2026-06-16  
**Status:** **RESOLVED** (LangGraph STOPPED/rolled back; owner decisions locked)

## LangGraph (STOPPED - rolled back)

| Item | Status |
|------|--------|
| `backend/ai/` | **REMOVED** |
| `backend/core/langgraph/` | **REMOVED** |
| `backend/api/legal_reason_routes.py` | **REMOVED** |
| POST `/api/v1/legal/reason` + `/api/legal/reason` | **REMOVED** |
| `langgraph` / `langchain-core` in `pyproject.toml` + `Dockerfile` | **REMOVED** |
| LangGraph-only tests | **REMOVED** |
| Enforcement: `tests/test_single_brain_architecture.py` | **ACTIVE** |
| ADR: `docs/adr/ADR-000-langgraph-gate.md` | **ACCEPTED** |
| Historical docs (SUPERSEDED banners) | `LANGGRAPH_ORCHESTRATION_V1.md`, `LEGAL_REASON_API_V1.md` |

**Do not re-ask.** Single Brain only per ADR-000.

## Owner decisions RESOLVED (do not re-ask)

| Topic | Decision |
|-------|----------|
| Knowledge schema | `provision` canonical; `corpus_chunks` embedding layer |
| Graph engine | Postgres `legal_nodes` / `legal_edges` (not Neo4j default) |
| Module map | 16 canonical modules + tag layer; map 24 `employment_modules` keys |
| Embeddings | 1024-dim local via Ollama (`bge-large-en-v1.5`); re-embed corpus |
| Find Case Law bulk | **Not granted** - sample/manual only |
| Mastra sidecar | **No** - extend Python Brain only |
| RLHF | **No** |
| Companies House | Env stub only until API key |
| EU AI Act logs | PII-free audit/brain traces only |
| Domain scope | `employment_uk` only enabled; others fail closed |
| Tools vs agents | `/api/tools/*` separate from agent registry |

## Single Brain runtime (confirmed)

- **Only** `backend/core/brain.py` (+ orchestrator submodule) authorises legal reasoning.
- `POST /assess` -> `MotherController` -> `backend.core.brain.orchestrator`; no graph bypass.
- CitationGuard + Legal Truth Validator on Brain path only.

## Ingestion dual-plane (084)

- Migration: `db/migrations/084_ingestion_jobs_dual_plane.sql`
- Workers: `ingestion/workers/` (legislation, case_law, acas, rules_compiler)
- Unified indexer: `ingestion/workers/unified_indexer.py` (Postgres always; Neo4j optional via `NEO4J_ENABLED=false`)
- Re-embed script: `scripts/reembed_corpus_1024.py` (after migration 080 + Ollama pull)
- Freshness: `python -m ingestion.freshness.report`

## Proof artifacts

- `reports/single_brain_enforcement_cursor.txt`
- `reports/ingestion_084_cursor.txt`
- `reports/case_os_beta_ship_cursor.txt`
- `reports/multi_language_verify_cursor.txt`
- `reports/domain_plugin_verify_cursor.txt`
- `pytest tests/test_single_brain_architecture.py`

## Open owner items (genuinely remaining)

| Item | Notes |
|------|-------|
| Live `/assess` curl proof | Requires DB migrations applied + corpus seed on target env |
| `brain_traces` persistence audit | Verify trace_id in HTTP response matches DB row after assess |
| ERA graph refresh hook | Post-scrape `legal_nodes` refresh after ingestion pipeline |
| Document pack purchase | Beta UI shows "not yet available" - payment gate when owner enables |
