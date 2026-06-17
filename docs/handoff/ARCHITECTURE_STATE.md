# Architecture State

Generated: 2026-06-17  
Branch snapshot: `release/lawapp-clean-snapshot` @ `804a232`

## ADR-000 (single Brain)

| Check | Result | Evidence |
|-------|--------|----------|
| Status | ACCEPTED | `docs/adr/ADR-000-langgraph-gate.md` |
| Single runtime | `backend/core/brain.py` | ADR + `tests/test_single_brain_architecture.py` |
| `backend/ai/` | **Absent** | `Test-Path backend/ai` → False; `git ls-tree` release HEAD → 0 files |
| LangGraph in backend runtime | **0 hits** | `rg langgraph backend/` → no matches |
| `/api/v1/legal/reason` | **Not registered** | grep only in test assertions + proof scripts |
| Enforcement tests | **16 passed** | release: `test_single_brain_architecture.py` + `test_build_order_gates.py` |

**Forbidden paths (must not reappear without ADR + owner approval):**

- `backend/ai/`
- `backend/core/langgraph/`
- `backend/api/legal_reason_routes.py`
- `POST /api/v1/legal/reason`
- `langgraph` / `langchain-core` in production deps

## Brain path (legal answers)

```
HTTP → FastAPI monolith (:8000)
  → MotherController / assess routes
  → backend.core.brain.orchestrator (19 steps)
  → retrieve_legal_evidence / run_rules_engine
  → generate_draft (local Ollama)
  → CitationGuard / governance
  → response + brain_traces audit
```

NestJS control-plane (if deployed) is sidecar-only per ADR-000 — no second reasoning runtime.

## RAG flow (current)

```
Source tables (legislation, acas_guidance, …)
  → ingestion/sync_corpus_chunks.py
  → corpus_chunks (vector 1024, embedding_dim column)
  → pgvector HNSW index

Retrieve paths:
  - retrieve_hybrid / corpus direct query → 1024-dim hits (proven in embed hardening)
  - retrieve_semantic on legislation.embedding → EMPTY (384 schema, 0 rows embedded)
  - RAG microservice _vector_search → 384-dim fastembed query vs 1024 index → 0 hits
```

**Blocker:** query-side and semantic-leg alignment with 1024-dim corpus (see `RELEASE_STATE.md`).

## Corpus state (live verified 2026-06-17)

```sql
-- localhost:5435/lawapp (POSTGRES_PASSWORD=lawapp)
SELECT COUNT(*), COUNT(embedding), MAX(embedding_dim) FROM corpus_chunks;
-- 978 | 978 | 1024
```

| Metric | Value | Verified |
|--------|-------|----------|
| corpus_chunks total | 978 | Yes (live psql) |
| embedded | 978/978 | Yes |
| dimension | 1024 only | Yes |
| model | bge-large-en-v1.5 | Yes (reports; not re-queried model column this session) |
| legislation source embeddings | 0 @ 384 schema | Yes (reports) |

## Database

- **Operational + corpus:** Postgres with pgvector (`corpus_chunks`, `rules`, `matter`, brain traces, etc.)
- **Migrations:** through 084 on release; 087 on feat/seo-command only
- **Graph layer:** Postgres `legal_nodes` / `legal_edges` (not Neo4j)
- **Rules table:** effective-dated; used by Brain and SEO G4 grounding bridge (feat branch)

## Frontend

- Static client served by monolith (`client/public/`)
- WASM deadline calculator (client path) — status unchanged; NOT re-tested this session
- Admin shell + SEO dashboard on feat branch only (`client/public/admin/seo/`)

## SEO position

- **Release branch:** no SEO module code
- **feat/seo-command:** Track A read-only module at `backend/seo/` (no `agents/`)
- **Track B/C:** not started; owner approval required
- Spec: `docs/SEO_COMMAND_SPEC.md` (feat); handoff: `docs/handoff/SEO_COMMAND_STATE.md`

## Security

- JWT auth + admin role for `/admin/*`
- Row-level security on tenant/matter (policy unchanged)
- Local `.env` password drift documented: volume `lawapp` vs `.env` `change_this_password`
- No secrets in this handoff

## Kubernetes (NOT VERIFIED this session)

Fixed namespaces only: `lawapp-api`, `lawapp-rag`, `lawapp-ai`, `lawapp-security`, `lawapp-monitoring`.

Prior reports indicate mixed pod health; live cluster state requires owner verification.

## Service mesh ports (design)

| Port | Service |
|------|---------|
| 8000 | Monolith + UI |
| 8016 | Rules |
| 8017 | RAG |
| 8018 | Graph-RAG |
| 8019 | Redaction |
| 8020 | Audit |
| 8007 | Admin |
| 8008 | Case |
| 8009 | Notify |
