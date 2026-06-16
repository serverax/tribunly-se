# Ingestion Dual Plane V1

**Status:** Implemented (workers A-D, Redis queues, migration 084)  
**Branch:** `release/lawapp-clean-snapshot`  
**Conflict resolution:** Owner Decision Q2 chose Postgres-only graph; this spec adds **optional Neo4j** behind `NEO4J_ENABLED`. Postgres+pgvector is **always** written. Neo4j is a secondary enrichment plane, never authoritative for citations or rules.

## Planes

| Plane | Technology | Authority | When written |
|-------|------------|-----------|--------------|
| Primary | Postgres `legislation`, `acas_guidance`, `corpus_chunks`, pgvector | Yes | Every worker job |
| Secondary | Neo4j `LegalEntity` nodes (optional) | No | Only if `NEO4J_ENABLED=true` |
| Proposals | `knowledge.ingestion_proposals` | Review gate | Worker D + graph extractor |

Postgres `legal_nodes` / `legal_edges` (existing) remain the in-DB graph for GraphRAG service 8018 when Neo4j is off.

## Workers

| Worker | File | Queue | Responsibility |
|--------|------|-------|----------------|
| A | `ingestion/workers/legislation_worker.py` | `ingestion-legislation` | CLML fetch, chunk, embed sync, optional Act/Section nodes |
| B | `ingestion/workers/case_law_worker.py` | `ingestion-case-law` | **Sample only** unless `FCL_BULK_LICENCE_GRANTED=true` |
| C | `ingestion/workers/acas_worker.py` | `ingestion-acas` | ACAS guidance ingest + corpus sync |
| D | `ingestion/workers/rules_compiler_worker.py` | `graph-build-jobs` | Deterministic rule **candidates** to proposals (never direct `rules` write) |

Shared coordinator: `ingestion/workers/unified_indexer.py`  
Runner: `ingestion/worker_runner.py` (Docker profile `ingestion`)

## Redis queues

| Queue | Producer | Consumer |
|-------|----------|----------|
| `ingestion-legislation` | control-plane / manual enqueue | Worker A |
| `ingestion-case-law` | control-plane / manual enqueue | Worker B |
| `ingestion-acas` | control-plane / manual enqueue | Worker C |
| `embedding-jobs` | post-chunk hooks | embedder (existing `ingestion.embeddings.embedder`) |
| `graph-build-jobs` | unified_indexer / relationship_extractor | Worker D + Neo4j batch (optional) |

Transport: Redis lists (`LPUSH` / `BRPOP`) via `ingestion/workers/base_worker.py`.

## Sync strategy

1. Source tables ingested idempotently (existing upsert writers in `ingestion/db.py`).
2. `ingestion/sync_corpus_chunks.py` mirrors into `corpus_chunks` (chunk_hash dedupe).
3. Embeddings applied on source rows then synced.
4. Graph extraction (Ollama) produces JSON proposals; Neo4j writes only after validation and optional reviewer approval.
5. Job state tracked in `ingestion_jobs` (migration 084): `postgres_status`, `neo4j_status`.

## LLM policy

- Extraction LLM: **local Ollama only** (`ingestion/graph/relationship_extractor.py`).
- External OpenRouter: blocked unless `ALLOW_EXTERNAL_LLM=true` (default false); even then extractor stays on Ollama.
- Rule candidates: `knowledge.ingestion_proposals`, not `rules` table.

## Docker

```bash
docker compose up -d db redis backend
docker compose --profile ingestion up -d ingestion-worker
docker compose --profile graph-neo4j up -d neo4j   # optional
```

## Gaps / follow-ups

- Control-plane UI enqueue buttons (admin service 8007) not wired in this slice.
- Full corpus backfill into `knowledge.provision` remains Phase 2 cutover work.
- Neo4j driver is optional; install `neo4j` package when enabling graph plane.
