
# Architecture state (snapshot)

## Frontend

- Next.js / UI: present in repo; WASM status not re-verified in this pass (UNKNOWN - requires verification).

## Backend

- FastAPI monolith + service mesh pattern; local `lawapp-backend-1` healthy on Docker Compose.

## RAG

- Dedicated rag service (8017) and graph-rag (8018) containers healthy locally.
- pgvector on Postgres: `lawapp-db-1` healthy; migration/embed state not re-checked here.

## Graph RAG

- Postgres `legal_nodes` / `legal_edges` model per project rules; graph-rag service up locally.

## Database

- Operational and corpus Postgres via compose; exact applied migration revision not queried (UNKNOWN - requires verification).
- `matter` entity invariant; legacy `cases` bridge per project rules.

## Security

- Redaction/audit services running locally; encryption/GDPR controls documented under `docs/compliance*`; not re-audited in this pass.

## Kubernetes / deployment

- Cluster API unreachable from this host (kubectl DNS failure). Namespace/pod status: UNKNOWN - requires verification from connected environment.
