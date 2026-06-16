# Control plane (Graph RAG)

NestJS `GraphRagService` proxies to Python `lawapp-graph-rag-service` (8018):

- `control-plane/src/modules/graph-rag/graph-rag.service.ts` - `buildLegalChain()`, `format()`, `scorePath()`
- `control-plane/src/modules/retrieval/retrieval.service.ts` - `retrieveHybrid()` merge

Neo4j schema: `control-plane/scripts/neo4j/schema.cypher`

Dev Neo4j credentials (compose only): `neo4j` / `lawapp_dev_only`
