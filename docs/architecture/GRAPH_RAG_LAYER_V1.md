# Graph RAG Layer Production v1

**Status:** Production v1 (hybrid)  
**Branch:** `release/lawapp-clean-snapshot`  
**Port:** 8018 (`lawapp-graph-rag-service`)

## Purpose

Graph RAG adds structured legal path finding on top of semantic retrieval (pgvector) and deterministic rules (SQL). It answers: which legal tests, statutes, cases, and remedies connect a claim type to an authority chain?

**Owner override (Q2):** Owner decision 16 June 2026 originally chose Postgres-only graph (`legal_nodes` / `legal_edges`). This v1 layer implements a **hybrid** model: Neo4j is primary when `NEO4J_ENABLED=true`; Postgres remains the fallback when Neo4j is off or unreachable. No silent sync between engines; ingestion writes through validated pipelines only.

## Node and relationship model

### Node labels (Neo4j primary; Postgres `node_type` maps 1:1)

| Label | Postgres `node_type` | Description |
|-------|----------------------|-------------|
| `Statute` | `legislation_section` (parent act) | Act or SI (e.g. Employment Rights Act 1996) |
| `Section` | `legislation_section` | Numbered provision with `source_ref` / URL |
| `Case` | `case_law` | Sample EAT/UKSC nodes only until FCL grant |
| `LegalTest` | `legal_test` | Burchell, band of reasonable responses, qualifying service |
| `Rule` | `rule` | Deterministic rule spine linked to SQL `rules` |
| `Outcome` | `remedy` | Compensation, reinstatement, declaration |
| `Concept` | `procedure` / `defence` | ACAS, grievance, mitigation concepts |

### Relationship types (both engines)

| Type | Meaning |
|------|---------|
| `requires` | Prerequisite test or procedure |
| `applies_to` | Scope link (test to claim or section) |
| `leads_to` | Sequential test or procedural step |
| `interprets` | Case interprets test or section |
| `extends` | Broadens or clarifies scope |
| `reduces` | Limits remedy or scope |
| `excludes` | Bars claim or remedy |

Postgres stores these in `legal_edges.relationship_type`. Neo4j uses uppercase relationship types in Cypher (`REQUIRES`, etc.) with application-layer normalisation to lowercase.

## Hybrid merge architecture

```
User query + claim_type
        |
        v
+------------------ Mother Algorithm (brain.py Step 11) ------------------+
|  retrieve_hybrid_context()                                             |
|    semantic  <- pgvector + BM25 RRF (retrieve_semantic / retrieve_keyword) |
|    rules     <- SQL rules table (retrieve_rules)                       |
|    graph     <- 8018 GraphRAG (Neo4j or Postgres via graph_cache Redis)  |
+------------------------------------------------------------------------+
        |
        v
final_context = { semantic, graph, rules }
        |
        v
Reasoning + CitationGuard (no graph-only answers without authorities)
```

### Engine selection (8018)

| `NEO4J_ENABLED` | Engine | Health `mode` |
|-----------------|--------|---------------|
| `false` (default) | Postgres `legal_nodes` / `legal_edges` | `postgres` |
| `true` + Neo4j reachable | Neo4j 5 | `neo4j` |
| `true` + Neo4j down | Postgres fallback | `postgres_fallback` |

Redis caches traversal results: `graph:chain:{sha256(query|claim_type|jurisdiction|mode)}` TTL 3600s.

## Service map

| Component | Path | Role |
|-----------|------|------|
| Graph RAG API | `backend/services/lawapp-graph-rag-service/main.py` | HTTP :8018 |
| Traversal core | `backend/core/rag/graphrag_traversal.py` | Postgres paths |
| Neo4j adapter | `backend/core/rag/neo4j_traversal.py` | Optional Neo4j driver |
| Graph cache | `backend/core/rag/graph_cache.py` | Redis `graph:chain:*` |
| Hybrid retrieval | `backend/core/retrieve.py` | `retrieve_hybrid_context()` |
| Mother Algorithm | `backend/core/brain.py` | Step 11 wiring |
| Neo4j schema | `control-plane/scripts/neo4j/schema.cypher` | Constraints and indexes |
| Ingestion | `ingestion/graph/` | Validated MERGE + proposals |

## API endpoints (8018)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/ready` | DB or Neo4j readiness |
| POST | `/api/graphrag/traverse` | Claim-type legal path |
| POST | `/api/graph/search` | Natural-language graph search |
| GET | `/api/graphrag/requirements/{claim_type}` | Legal tests |
| GET | `/api/graphrag/remedies/{claim_type}` | Remedies |
| GET | `/api/graphrag/deadlines/{claim_type}` | Deadlines |

## Mother Algorithm integration flow

1. **Step 9** (`select_rag_source`): `legal_graph` selected for employment claims with material risk.
2. **Step 11** (`retrieve_legal_evidence`): `retrieve_hybrid_context()` runs semantic + rules + graph in one call.
3. **Step 12** (`orchestrate_agents`): `graph_context` passed to reasoning with `bundle.authorities`.
4. **Trace**: `graph_nodes`, `graph_mode`, `graph_engine` recorded on brain trace.

Graph paths never bypass CitationGuard: every graph node must carry `source_ref` and `source_url` where applicable.

## Docker (dev only)

```bash
# Postgres-only (default)
docker compose up -d lawapp-graph-rag-service backend

# Neo4j profile (dev credentials only, not production secrets)
docker compose --profile graph-neo4j up -d neo4j lawapp-graph-rag-service backend
```

Neo4j Browser: http://localhost:7474  
Bolt: `bolt://localhost:7687`  
Dev auth: `neo4j` / `lawapp_dev_only` (set via `NEO4J_AUTH` in compose; rotate for any shared environment)

## Ingestion and governance

- **Direct Neo4j write from LLM:** forbidden.
- **relationship_extractor.py:** writes proposals to `knowledge.ingestion_proposals` with `status=pending`.
- **neo4j_ingest.py:** validated MERGE for statutes and sample case law only (FCL licence gate).
- Human or admin-service approval required before proposal promotion to Neo4j or Postgres graph tables.

## FCL and case law boundary

Bulk case-law embedding remains blocked (`FCL_BULK_LICENCE_GRANTED=false`). Graph ingestion may MERGE a **small sample** of openly licensed EAT/UKSC nodes for integration tests; no bulk FCL pipeline.

## Verification commands

```bash
curl http://localhost:8018/health
curl -X POST http://localhost:8018/api/graph/search \
  -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal band of reasonable responses"}'
pytest tests/test_graph_rag_hybrid.py -q
```

Evidence report: `reports/graph_rag_layer_v1_cursor.txt`
