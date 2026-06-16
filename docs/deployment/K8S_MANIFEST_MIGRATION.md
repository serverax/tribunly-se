# Kubernetes manifest migration

**Owner decision:** `infra/k8s/` is canonical ([`OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md) Deployment Q8).

## Current state

| Tree | Role | Status |
|------|------|--------|
| `infra/k8s/` | Full namespaces, monitoring CronJobs, secrets templates | **Canonical** |
| `k8s/` | Partial brain/rag/citation-guard snippets | **Deprecated** |

## Namespaces (canonical)

- `lawapp-api` - monolith backend, Postgres STS
- `lawapp-ai` - brain, rules, Ollama inference
- `lawapp-rag` - retrieval, ingestion, crawler, worker
- `lawapp-security` - citation-guard
- `lawapp-monitoring` - freshness and health CronJobs

## Migration steps

1. Inventory unique files under `k8s/lawapp-ai/`, `k8s/lawapp-rag/`, `k8s/lawapp-security/`.
2. Merge into `infra/k8s/` equivalents or delete if duplicate.
3. Point `infra/k8s/lawapp-k8s-deploy.sh` at single tree.
4. Staging apply uses `infra/k8s/` only (separate staging cluster per Q12).
5. Remove `k8s/` after owner staging smoke.

## Embedding env (Q5)

ConfigMaps under `infra/k8s/` must use:

- `EMBEDDING_MODEL=bge-large-en-v1.5` (or `mxbai-embed-large`)
- `EMBEDDING_DIM=1024`

No `text-embedding-3-small` / 1536 references in active manifests.
