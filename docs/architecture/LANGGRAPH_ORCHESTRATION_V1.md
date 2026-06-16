# LangGraph Orchestration V1

## High-level design

```
Client -> lawapp-api (FastAPI) -> LangGraph Orchestrator -> Retrieval + Rules + LLM + Governance -> structured JSON
```

LangGraph lives at `backend/ai/graph/` (in-process, not a standalone microservice).

## Package layout

```
backend/ai/
  graph/
    graph.py
    state.py
    nodes/
      intake.py
      classify.py
      retrieve.py
      graph_enrich.py
      rules.py
      reason.py
      govern.py
  services/
    pgvector.py
    neo4j.py
    rules_engine.py
    llm.py
```

## StateGraph edges

```
START -> intake -> classify -> retrieve -> graph_enrich -> rules -> reason -> govern -> END
```

## API

- `POST /api/v1/legal/reason`
- `POST /api/legal/reason` (alias)

## Constraints

- Postgres `legal_nodes` canonical; Neo4j optional via `NEO4J_ENABLED`.
- CitationGuard mandatory in `reason` and `govern` nodes (no Brain bypass).
- Local Ollama default; `ALLOW_EXTERNAL_LLM=true` required for cloud paths.
- `POST /assess` remains Brain/MotherController entry.

## Phase roadmap

### Phase A (current)

- In-process LangGraph with real retrieve/rules/graph adapters.
- API route + unit tests with mocked LLM.
- Docker deps: `langgraph`, `langchain-core`.

### Phase B

- Full docker curl with seeded corpus UUIDs for `approved: true`.
- Neo4j Cypher when `NEO4J_ENABLED=true`.
- Persist `trace_id` in `brain_traces`.

### Phase C

- ERA ingestion hook for `legal_nodes` refresh.
- CI e2e proof and per-node OpenTelemetry spans.
