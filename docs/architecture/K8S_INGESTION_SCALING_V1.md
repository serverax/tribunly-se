# K8s Ingestion Scaling V1 (prep only)

**Status:** Design prep; no production deploy in this slice  
**Canonical manifests:** `infra/k8s/` (Owner Decision Q8)

## Namespaces

| Namespace | Workloads |
|-----------|-----------|
| `lawapp-core` | Monolith backend, outbox-worker, case/admin/notification services |
| `lawapp-ingestion` | ingestion-worker Deployment(s), Redis-backed queue consumers |
| `lawapp-ai` | Ollama Deployment (internal ClusterIP), graph extraction sidecar optional |
| `lawapp-data` | Postgres (or external RDS endpoint), optional Neo4j StatefulSet |

## Ingestion worker scaling

```yaml
# Pattern (not applied in this PR)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingestion-worker
  namespace: lawapp-ingestion
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ingestion-worker
  template:
    spec:
      containers:
        - name: worker
          image: lawapp/ingestion:latest
          command: ["python", "-m", "ingestion.worker_runner"]
          env:
            - name: REDIS_URL
              value: redis://redis.lawapp-core.svc:6379
            - name: NEO4J_ENABLED
              value: "false"
            - name: FCL_BULK_LICENCE_GRANTED
              value: "false"
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
```

Horizontal scaling: increase replicas; each replica competes on Redis `BRPOP` (at-most-once per message). For heavy embed jobs, split `embedding-jobs` to a dedicated Deployment.

## Queue backpressure

| Signal | Action |
|--------|--------|
| Redis queue depth > 1000 | HPA scale ingestion-worker |
| `ingestion_jobs.postgres_status=failed` rate | Alert + pause enqueue |
| Neo4j write failures | Set `NEO4J_ENABLED=false`, continue Postgres-only |

## Conflict resolution

- Owner Q2: production default is **Postgres graph**, not Neo4j. Neo4j StatefulSet lives under `lawapp-data` as optional profile only.
- Staging: separate cluster (Owner Q12), not namespace-only isolation on prod.

## Local Docker parity

```bash
docker compose up -d db redis backend
docker compose --profile ingestion up -d ingestion-worker
```

## Gaps

- HPA manifests and KEDA ScaledObject for Redis queue depth not committed yet.
- PgBouncer sidecar for 10k-readiness remains platform-devops-scale-agent scope.
