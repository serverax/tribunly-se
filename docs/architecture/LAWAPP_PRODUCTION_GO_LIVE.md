# LawApp Production Go-Live Architecture

**Status:** Local Docker verified, K8s prep only (no Track C deploy)  
**Branch:** `release/lawapp-clean-snapshot`  
**Owner decisions:** [`OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md)  
**Last verified:** 2026-06-16

---

## ASCII architecture (user go-live spec)

```
                         +---------------------------+
                         |   Frontend (Next.js)    |
                         |   Port 3000 (Docker)    |
                         |   Static fallback :8000   |
                         +------------+--------------+
                                      | NEXT_PUBLIC_API_URL
                                      v
+---------------------------+  +------+----------------------+
| Admin Control Layer       |  | API Gateway (FastAPI)      |
| lawapp-admin-service      |  | backend monolith           |
| Port 8007                 |  | Port 8000                  |
| SSO/MFA reviewers (K8s)   |  | /api/* /cases/* /assess    |
+-------------+-------------+  +------+---------------------+
              |                         |
              |                         | Brain entry (no bypass)
              v                         v
       +------+-------------------------+----------------------+
       | Orchestration / Case Engine Controller               |
       | backend/core/orchestrator.py (classify route merge)  |
       | backend/core/brain.py Orchestrator facade (step 11b) |
       +------+-------------------------+----------------------+
              |                         |
     +--------v--------+       +--------v------------------------+
     | AI Brain        |       | Security layer                  |
     | 19-step pipeline|       | JWT auth, rate limit (Redis)    |
     | CitationGuard   |       | Redaction :8019, Audit :8020    |
     | local Ollama    |       | ADMIN_API_KEY monolith admin    |
     +--------+--------+       +---------------------------------+
              |
    +---------+---------+---------+
    |         |         |         |
    v         v         v         v
+-------+ +-------+ +-------+ +-----------+
| Rules | |  RAG  | | Graph | | Case/Notif|
| :8016 | | :8017 | | :8018 | | :8008/9   |
+---+---+ +---+---+ +---+---+ +-----------+
    |         |         |
    +----+----+---------+
         v
+---------------------------+       +------------------+
| Data layer                |       | Ingestion        |
| Postgres (pgvector)       |       | docker profiles  |
| public.* + knowledge.*    |       | legislation/ACAS |
| legal_nodes/legal_edges   |       | embedder scripts |
| corpus_chunks (1024 dim)  |       +------------------+
| Redis cache :6379         |
+---------------------------+
         |
         v
+---------------------------+
| Infrastructure (K8s prep) |
| infra/k8s/ canonical      |
| namespaces (see below)    |
| Talos/Hetzner (Track C)   |
+---------------------------+
```

---

## Box-to-repo mapping

| Diagram box | Repo path / service | Port (local Docker) | K8s namespace |
|-------------|---------------------|---------------------|---------------|
| Frontend Next.js | `client/next/` | 3000 | `lawapp-api` (ingress) |
| Static HTML fallback | `client/public/` via `backend/api/main.py` | 8000 | `lawapp-api` |
| API Gateway | `backend/api/main.py`, `Dockerfile` | 8000 | `lawapp-api` |
| Admin Control Layer | `backend/services/lawapp-admin-service/` | 8007 | `lawapp-api` |
| Case Engine Controller | `backend/core/orchestrator.py`, facade in `brain.py` | in-process | `lawapp-ai` |
| AI Brain (19-step) | `backend/core/brain.py`, `backend/core/pipeline.py` | in-process on 8000 | `lawapp-ai` |
| CitationGuard | `backend/core/agentic/corpus_citation_guard.py` | in-process | `lawapp-security` |
| Rules engine | `backend/services/lawapp-rules-service/` | 8016 | `lawapp-ai` |
| RAG retrieval | `backend/services/lawapp-rag-service/` | 8017 | `lawapp-rag` |
| Graph RAG (Postgres) | `backend/services/lawapp-graph-rag-service/`, `backend/core/rag/graphrag_traversal.py` | 8018 | `lawapp-rag` |
| Redaction | `backend/services/lawapp-redaction-service/` | 8019 | `lawapp-security` |
| Audit | `backend/services/lawapp-audit-service/` | 8020 | `lawapp-monitoring` |
| Case service | `backend/services/lawapp-case-service/` | 8008 | `lawapp-api` |
| Notifications | `backend/services/lawapp-notification-service/` | 8009 | `lawapp-api` |
| Outbox worker | `backend/core/outbox_worker.py` | internal | `lawapp-api` |
| Postgres + pgvector | `docker-compose.yml` service `db`, `infra/k8s/lawapp-postgres-sts.yaml` | 5432 / 5435 host | `lawapp-api` |
| Redis | `docker-compose.yml` service `redis` | 6379 | `lawapp-api` |
| Ollama (local LLM) | `docker-compose.yml` profile `ollama` | 11434 | `lawapp-ai` |
| Ingestion | `ingestion/`, profiles `bootstrap`/`ingestion` | one-shot | `lawapp-rag` |
| K8s manifests | `infra/k8s/` (canonical) | n/a | all |

**Deprecated:** `k8s/` partial tree (see `k8s/DEPRECATED.md`). **No Neo4j** (Owner Q2: Postgres graph only).

---

## Kubernetes namespaces

| Namespace | Workloads |
|-----------|-----------|
| `lawapp-api` | Backend monolith, Postgres STS, ingress, case/notification/admin edge |
| `lawapp-ai` | Brain deployment, rules service, Ollama inference fabric |
| `lawapp-rag` | RAG, graph-RAG, ingestion jobs, embedding jobs, crawler |
| `lawapp-security` | Redaction, citation-guard policies, network policies |
| `lawapp-monitoring` | Prometheus rules, freshness CronJobs, audit service |

Apply order: `lawapp-namespaces.yaml` then per-component manifests under `infra/k8s/`.

---

## Integration wiring

### Frontend to API

| Client | Env var | Target |
|--------|---------|--------|
| Next.js (`client/next/`) | `NEXT_PUBLIC_API_URL=http://localhost:8000` | FastAPI monolith |
| Static (`client/public/js/api-client.js`) | same-origin relative URLs | Served by backend :8000 |

### Admin

- Dedicated service: `http://localhost:8007/health`
- Monolith admin routes: `X-Admin-Key` on `/admin/*` (dev only; reviewers use 8007 in prod per Owner Q9)

### Brain microservice URLs (backend env)

```
RULES_SERVICE_URL=http://lawapp-rules-service:8016
RAG_SERVICE_URL=http://lawapp-rag-service:8017
GRAPH_RAG_SERVICE_URL=http://lawapp-graph-rag-service:8018
REDACTION_SERVICE_URL=http://lawapp-redaction-service:8019
AUDIT_SERVICE_URL=http://lawapp-audit-service:8020
```

### Case Engine Controller

`backend/core/orchestrator.py` implements classify, route, delegate, merge.  
`backend/core/brain.py` step 11b calls `orchestrator.run_stages()` as the **Case Engine Controller** inside the 19-step Brain pipeline. No legal answer bypasses Brain.

### Data

- **public schema:** cases/matters, users, brain_traces, rules, corpus_chunks, legal_nodes/edges
- **knowledge.*** schema: `provision`, `module`, `legal_source` (`db/migrations/078_knowledge_schema_stubs.sql`)
- **Embeddings:** 1024-dim local (`bge-large-en-v1.5`, Owner Q5)
- **Redis:** rate limits, rules cache, session-adjacent keys

---

## MUST HAVE vs SHOULD HAVE vs LATER

| Item | Tier | Status | Evidence |
|------|------|--------|----------|
| FastAPI gateway :8000 healthy | MUST | PASS | `curl http://localhost:8000/health` |
| Brain pipeline no bypass | MUST | PASS | `backend/core/brain.py` guardrails, tests |
| Rules :8016 | MUST | PASS | health 200 |
| RAG :8017 | MUST | PASS | health 200 |
| Graph :8018 Postgres traversal | MUST | PASS | health 200, no Neo4j |
| CitationGuard fail-closed | MUST | PASS | `corpus_citation_guard.py` in pipeline |
| Redis + Postgres up | MUST | PASS | compose healthy |
| JWT auth enforced | MUST | PARTIAL | jwt mode on; SSO/MFA admin pending |
| Admin reviewer UI :8007 | MUST | PARTIAL | service healthy; full gate UI incomplete |
| knowledge.* schema migrated | MUST | PARTIAL | migration 078 exists; cutover in progress |
| Next.js :3000 wired to API | MUST | PARTIAL | scaffold in `client/next/` |
| Local Ollama inference | MUST | PARTIAL | ollama profile healthy; model pull env-specific |
| Docker full stack `compose up` | MUST | PASS | all microservices healthy |
| K8s manifests canonical `infra/k8s/` | MUST | PASS | namespaces + deployments present |
| Track C prod deploy | MUST | FAIL | explicit owner gate, not executed |
| Stripe live / secrets rotation | MUST | FAIL | PAYMENT_MODE disabled/test |
| FCL bulk case law ingestion | MUST | FAIL | `FCL_BULK_LICENCE_GRANTED=false` |
| k6 10k readiness | SHOULD | PARTIAL | reports exist; not re-run this session |
| Static pages full Case OS | SHOULD | PARTIAL | `client/public/pages/*` expanding |
| Outbox worker delivery | SHOULD | PASS | compose healthy |
| Companies House verify | SHOULD | FAIL | API key owner action |
| ERA 2025 commencement job | SHOULD | PARTIAL | planned; human sign-off |
| Partner referral registry | LATER | PARTIAL | table stub migration 079 |
| Bilingual on-device translation | LATER | FAIL | Wave 4 |
| Neo4j graph | LATER | FAIL | rejected per Owner Q2 |
| Mastra second orchestrator | LATER | FAIL | rejected per agentic endorsement |

---

## Local test URLs

| URL | Purpose |
|-----|---------|
| http://localhost:3000 | Next.js landing (when `frontend-next` service up) |
| http://localhost:8000 | API + static HTML client |
| http://localhost:8000/pages/architecture.html | Architecture overview (static) |
| http://localhost:3000/about-architecture | Architecture overview (Next.js) |
| http://localhost:8000/docs | OpenAPI |
| http://localhost:8007/health | Admin service |
| http://localhost:8016/health | Rules |
| http://localhost:8017/health | RAG |
| http://localhost:8018/health | Graph RAG |
| http://localhost:8019/health | Redaction |
| http://localhost:8020/health | Audit |

---

## Related docs

- [`THREE_LAYER_SYSTEM.md`](THREE_LAYER_SYSTEM.md) (if present)
- [`../frontend/NEXTJS_DEPLOYMENT_PLAN.md`](../frontend/NEXTJS_DEPLOYMENT_PLAN.md)
- [`../deployment/K8S_MANIFEST_MIGRATION.md`](../deployment/K8S_MANIFEST_MIGRATION.md)
- [`../../infra/k8s/K8S_DEPLOYMENT_MAP.md`](../../infra/k8s/K8S_DEPLOYMENT_MAP.md)
