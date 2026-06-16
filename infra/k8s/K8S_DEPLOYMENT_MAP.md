# Kubernetes Deployment Map

**Canonical tree:** `infra/k8s/` only (Owner Q8)  
**Track C:** Prep and document only. Do not apply to production from this work order.

---

## Namespace diagram

```
lawapp-api          lawapp-ai           lawapp-rag
-----------         -----------         -----------
lawapp-backend      lawapp-brain        (rag deployments in
lawapp-postgres     lawapp-rules         legacy + compose mirror)
lawapp-ingress      llm-inference       lawapp-ingestion-jobs
(case/admin via     ollama fabric       lawapp-embedding-job
 compose/K8s TBD)                       crawler/worker TBD

lawapp-security     lawapp-monitoring
---------------     -----------------
network policies    lawapp-monitoring
security policies   prometheus rules
redaction (compose)   freshness cronjobs
citation-guard      audit service
```

---

## Manifest to workload map

| File | Kind | Namespace | Workload |
|------|------|-----------|----------|
| `lawapp-namespaces.yaml` | Namespace x5 | cluster | api, ai, rag, security, monitoring |
| `lawapp-backend.yaml` | Deployment+Service | lawapp-api | Monolith API :8000 |
| `lawapp-postgres-sts.yaml` | StatefulSet | lawapp-api | Postgres pgvector |
| `lawapp-ingress.yaml` | Ingress | lawapp-api | staging.lawapp.ai to backend |
| `lawapp-ai-brain.yaml` | Deployment | lawapp-ai | Brain on :8001 (split deploy option) |
| `lawapp-brain-deployment.yaml` | Deployment | lawapp-ai | Alternate brain manifest |
| `lawapp-reasoning-worker.yaml` | Deployment | lawapp-ai | Async reasoning worker |
| `llm-inference-fabric.yaml` | Deployment | lawapp-ai | Ollama internal |
| `inference/ollama-inference-daemonset.yaml` | DaemonSet | lawapp-ai | Optional per-node Ollama |
| `lawapp-configmaps.yaml` | ConfigMap | multi | Shared env (1024 embeddings) |
| `lawapp-secrets-template.yaml` | Secret template | multi | JWT, DB, admin keys |
| `lawapp-security-policies.yaml` | Policy | lawapp-security | Pod security |
| `lawapp-network-policies.yaml` | NetworkPolicy | multi | Egress restrictions |
| `lawapp-monitoring.yaml` | ServiceMonitor etc | lawapp-monitoring | Observability |
| `lawapp-monitoring-cronjobs.yaml` | CronJob | lawapp-monitoring | Freshness checks |
| `lawapp-prometheus-rules.yaml` | PrometheusRule | lawapp-monitoring | Alerts |
| `lawapp-ingestion-jobs.yaml` | Job | lawapp-rag | Legislation/ACAS ingest |
| `lawapp-embedding-job.yaml` | Job | lawapp-rag | Re-embed corpus |
| `lawapp-backup-job.yaml` | CronJob | lawapp-api | DB backup |
| `cert-manager-clusterissuer.yaml` | ClusterIssuer | cluster | TLS |

**Docker Compose only (add K8s manifests when scaling):**

| Service | Port | Suggested namespace |
|---------|------|---------------------|
| lawapp-rag-service | 8017 | lawapp-rag |
| lawapp-graph-rag-service | 8018 | lawapp-rag |
| lawapp-redaction-service | 8019 | lawapp-security |
| lawapp-audit-service | 8020 | lawapp-monitoring |
| lawapp-admin-service | 8007 | lawapp-api |
| lawapp-case-service | 8008 | lawapp-api |
| lawapp-notification-service | 8009 | lawapp-api |
| frontend-next | 3000 | lawapp-api |

---

## Apply order (staging smoke, not executed here)

1. `kubectl apply -f infra/k8s/lawapp-namespaces.yaml`
2. Secrets from `lawapp-secrets-template.yaml` (owner-filled)
3. `lawapp-configmaps.yaml`, Postgres STS
4. Tier-1 AI/RAG services, backend, brain
5. Ingress + cert-manager
6. Monitoring CronJobs

---

## Owner constraints reflected

- Postgres graph (`legal_nodes`/`legal_edges`), not Neo4j
- Admin reviewers on `lawapp-admin-service` :8007 with SSO/MFA
- Shared DB with `knowledge.*` schema
- Separate staging cluster (not namespace-only isolation)
- Track C independent of knowledge layer completion
