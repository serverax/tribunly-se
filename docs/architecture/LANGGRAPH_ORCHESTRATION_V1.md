# LangGraph Orchestration V1

> **SUPERSEDED - not implemented per [ADR-000](../adr/ADR-000-langgraph-gate.md).**  
> Historical design only. LawApp uses `backend/core/brain.py` as the single reasoning runtime. Do not implement from this document.

## High-level design

LawApp legal reasoning uses an in-process LangGraph orchestrator at `backend/ai/graph/`.
It is not a standalone microservice. The FastAPI monolith (`lawapp-api`) invokes the graph
on `POST /api/v1/legal/reason` (alias `/api/legal/reason`).

```
Client
  |
  v
lawapp-api (FastAPI)
  |
  v
LangGraph Orchestrator (backend/ai/graph/)
  |
  +-- Retrieval (pgvector hybrid via backend/core/retrieve.py)
  +-- Graph enrich (Neo4j optional, Postgres legal_nodes fallback)
  +-- Rules engine (Postgres rules table + employment deadline logic)
  +-- Local Ollama LLM (backend/ai/services/llm.py)
  +-- Governance (CitationGuard + backend/core/govern.py)
  |
  v
structured JSON (assessment, approved, errors, trace_id)
```

## Package layout

```
backend/ai/
  graph/
    graph.py          # StateGraph build_graph(), run_legal_graph()
    state.py          # LawAppState TypedDict
    nodes/
      intake.py       # normalize ed_t, employer, dismissal_type
      classify.py     # payload claim_type or keyword heuristics
      retrieve.py     # hybrid pgvector + BM25 retrieval
      graph_enrich.py # connected cases / exceptions
      rules.py        # rules table + deadline
      reason.py       # bounded structured LLM assessment
      govern.py       # CitationGuard + governance gate
  services/
    pgvector.py       # retrieve.py adapter
    neo4j.py          # graph_engine.py adapter (NEO4J_ENABLED)
    rules_engine.py   # retrieve_rules + compute_limitation_date
    llm.py            # local Ollama / stub / test override
```

## StateGraph edges

```
START -> intake -> classify -> retrieve -> graph_enrich -> rules -> reason -> govern -> END
```

## LawAppState fields

| Field | Purpose |
|-------|---------|
| trace_id | Correlation id for audit |
| user_id | Optional caller id |
| query | Retrieval query text |
| facts / normalized_facts | User facts (ed_t, employer, dismissal_type) |
| jurisdiction | EW / SC / NI |
| claim_type | e.g. unfair_dismissal |
| classification | classify node output |
| retrieval_bundle | Hybrid retrieval snapshot |
| authorities | Retrieved authority rows |
| graph_context | Legal graph enrichment |
| rules | Postgres rules rows |
| deadline_info | Deterministic limitation from rules |
| assessment | Structured assessment dict |
| approved | Governance pass/fail |
| errors | Fail-closed messages |
| govern_result | Governance gate detail |

## API

**Request**

```json
{
  "user_id": "uuid",
  "facts": {
    "ed_t": "2026-05-10",
    "employment_length": 18,
    "dismissal_type": "conduct"
  },
  "claim_type": "unfair_dismissal"
}
```

**Response**

```json
{
  "trace_id": "...",
  "assessment": { },
  "approved": true,
  "errors": [],
  "governance": { },
  "deadline_info": { }
}
```

## Constraints

- Postgres `legal_nodes` / `legal_edges` is canonical; Neo4j is optional (`NEO4J_ENABLED`).
- CitationGuard is mandatory: model output must cite real `corpus_chunks` UUIDs or verified citations.
- Local Ollama is the default LLM; external providers require `ALLOW_EXTERNAL_LLM=true` (discouraged).
- Brain `backend/core/brain.py` remains the full 19-step entry for chat; LangGraph is the dedicated legal-reason path.

## Phase roadmap

### Phase A (current)

- LangGraph wired in-process with real retrieve/rules/graph adapters.
- API route and unit tests with mocked LLM.
- Docker dependency: `langgraph`, `langchain-core`.

### Phase B

- Real embeddings path fully exercised in retrieve node under load.
- Neo4j Cypher traversal when `NEO4J_ENABLED=true`.
- Brain trace persistence for LangGraph `trace_id` in `brain_traces`.

### Phase C

- ERA ingestion pipeline connection for incremental graph updates.
- E2E docker proof in CI with seeded corpus UUIDs.
- Unified observability spans per LangGraph node.
