# Ingestion + LangGraph checkpoint

**Branch:** `release/lawapp-clean-snapshot`  
**Updated:** 2026-06-16  
**Status:** **STOP ENFORCED** — LangGraph rolled back; single Brain confirmed

## LangGraph gate (ADR-000)

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

## Single Brain runtime (confirmed)

- **Only** `backend/core/brain.py` (+ `orchestrator` submodule) authorises legal reasoning.
- `POST /assess` → `MotherController` → `backend.core.brain.orchestrator` (generative lane) or deterministic rules lane; **no graph bypass**.
- Pipeline aligns with `docs/04_RAG_REASONING_SPEC.md`: classify → retrieve → reason → score → govern → respond (Brain maps these across 19 trace steps).
- CitationGuard + Legal Truth Validator remain on the Brain path only.

## Ingestion (unchanged — not LangGraph)

- Dual-plane ingestion jobs: `db/migrations/084_ingestion_jobs_dual_plane.sql` (when applied).
- Retrieval: `backend.core.retrieve` (rules + BM25 + pgvector RRF).
- Graph enrich: Postgres `legal_nodes` / `legal_edges` via `backend.core.rag` (no Neo4j requirement).

## Proof

- `reports/single_brain_enforcement_cursor.txt` — grep before/after enforcement
- `pytest tests/test_single_brain_architecture.py`

## Remaining (NOT LangGraph)

- Phase A: live docker curl on `/assess` with DB migrations + corpus seed for full `approved: true` path.
- Phase B: `brain_traces` row persistence verification for assess trace_id.
- Phase C: ERA ingestion hook to refresh `legal_nodes` after scrape pipeline.
