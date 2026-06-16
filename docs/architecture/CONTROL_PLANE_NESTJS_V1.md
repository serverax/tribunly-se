# NestJS Control Plane v1

**Status:** Sidecar orchestration service (port 3001)  
**Branch:** `release/lawapp-clean-snapshot`  
**Owner alignment:** `docs/decisions/OWNER_DECISIONS_2026-06-16.md`

---

## Purpose

The control plane is a **NestJS sidecar** that coordinates retrieval, queues, and request validation. It does **not** replace the Python Brain or bypass CitationGuard. Legal answers are always obtained via `POST {LAWAPP_API_URL}/assess` on the FastAPI monolith (:8000).

```
Client / Next.js
    |
    +-- :3001 POST /api/process  (optional orchestration entry)
    |         |
    |         +-- Retrieval (Postgres rules + legal_nodes graph)
    |         +-- Reasoning proxy -> backend:8000/assess
    |         +-- Governance (Zod + grounding checks)
    |
    +-- :8000 /assess, /api/*  (canonical Brain + CitationGuard)
```

---

## Conflict resolution (user spec vs owner decisions)

| Topic | User spec | Owner decision | v1 implementation |
|-------|-----------|----------------|---------------------|
| Graph DB | Neo4j | Postgres `legal_nodes` / `legal_edges` only | **Default:** `GraphService` uses Postgres CTE traversals. `NEO4J_ENABLED=false` by default. Setting `NEO4J_ENABLED=true` logs a warning and still uses Postgres until a Neo4j driver is explicitly added (no Neo4j container). |
| LLM | OpenRouter / OpenAI gateway | Local Ollama only for legal routes | **Default:** `LlmRouter.routeForLegalAnswer()` always proxies to Python `/assess`. `ALLOW_EXTERNAL_LLM=false` by default; auxiliary Ollama ping only. |
| Orchestration | NestJS replaces Brain | Extend Python Brain; no second legal runtime | **Sidecar mode:** NestJS enriches with retrieval metadata and validates the Brain response; never calls external LLMs for legal text. |
| CitationGuard | Risk of bypass | Single governed path | Governance rejects `status=ok` + `invokes_llm=true` without rules/citations. |

---

## Service map

| URL | Service | Role |
|-----|---------|------|
| http://localhost:3001 | `control-plane` | NestJS orchestration, BullMQ enqueue, Zod boundary |
| http://localhost:8000 | `backend` | FastAPI monolith, Brain, `/assess`, CitationGuard |
| http://localhost:3000 | `frontend-next` | Next.js UI (optional) |
| http://localhost:8018 | `lawapp-graph-rag-service` | HTTP fallback for graph subgraph |
| PostgreSQL :5432 | `db` | Shared `lawapp` DB (rules, legal_nodes, corpus) |
| Redis :6379 | `redis` | Cache + BullMQ queues |

---

## Environment

| Variable | Default (compose) | Notes |
|----------|-------------------|-------|
| `DATABASE_URL` | `postgresql://lawapp:***@db:5432/lawapp` | Shared Postgres + pgvector |
| `REDIS_URL` | `redis://redis:6379` | BullMQ + memory cache |
| `LAWAPP_API_URL` | `http://backend:8000` | Brain proxy target |
| `GRAPH_RAG_SERVICE_URL` | `http://lawapp-graph-rag-service:8018` | Graph HTTP fallback |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Health ping only in v1 |
| `ALLOW_EXTERNAL_LLM` | `false` | Must stay false for legal routes |
| `NEO4J_ENABLED` | `false` | Postgres graph is canonical |

---

## API

### `GET /api/health`

Returns postgres/redis/ollama check flags and adapter mode.

### `POST /api/process`

```json
{
  "claim_type": "unfair_dismissal",
  "facts": "dismissed after 2 years",
  "jurisdiction": "EW"
}
```

Flow:

1. `RetrievalService` loads matching `rules` rows and Postgres graph subgraph.
2. `ReasoningService` calls `POST /assess` on the Python backend with equivalent payload.
3. `GovernanceService` validates response schema and grounding policy.
4. `MemoryService` stores a trace snapshot in Redis (1h TTL).

---

## Next.js integration

`client/next/lib/api.ts` supports:

- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) for direct Brain/API calls.
- `NEXT_PUBLIC_CONTROL_PLANE_URL` (optional `http://localhost:3001`) for `POST /api/process`.

Use the control plane when you want orchestration metadata (retrieval counts, governance checks) without duplicating Brain logic in the browser.

---

## Queues (BullMQ)

| Queue | Name | Purpose |
|-------|------|---------|
| Learning | `lawapp:learning:proposals` | RLHF-safe ingestion proposals (queue only) |
| Ingestion | `lawapp:ingestion:jobs` | UK gov source fetch jobs (legislation.gov.uk, gov.uk, acas.org.uk) |

Workers are not part of v1; jobs are enqueued for the existing Python ingestion pipeline to consume.

---

## Deploy

```bash
docker compose build control-plane
docker compose up -d control-plane backend db redis
curl http://localhost:3001/api/health
curl -X POST http://localhost:3001/api/process \
  -H "Content-Type: application/json" \
  -d '{"claim_type":"unfair_dismissal","facts":"dismissed after 2 years"}'
```

Proof report: `reports/control_plane_nestjs_v1_cursor.txt`

---

## Tests

```bash
cd control-plane && npm test
```

Unit tests cover `GovernanceService` Zod and grounding policy.

---

## What uses Postgres vs optional Neo4j

| Data | Store | v1 |
|------|-------|-----|
| Rules | Postgres `rules` | Direct SQL in `RetrievalService` |
| Knowledge graph | Postgres `legal_nodes`, `legal_edges` | `GraphService` recursive CTE |
| Vector RAG | Postgres `corpus_chunks` + pgvector | Via Python RAG service (not duplicated in NestJS v1) |
| Neo4j | N/A | **Disabled** (`NEO4J_ENABLED=false`); owner decision: no Neo4j container |
