# IterLaw K8s Manifests

Kubernetes manifests for the `lawapp` / IterLaw UK Employment Claim Co-Pilot.

## Cluster

Context: `aks-iterlaw-we-prod` (Azure AKS)
Namespaces: `iterlaw-ai`, `iterlaw-api`, `iterlaw-rag`, `iterlaw-monitoring`, `iterlaw-security`

## Current Server Status (2026-06-02)

| Resource                | Namespace   | Status    | Notes                                     |
|-------------------------|-------------|-----------|-------------------------------------------|
| Node                    | cluster     | NotReady  | Kubelet stopped posting status — fix via Azure |
| legal-orchestrator      | iterlaw-ai  | Pending   | Wrong image (rightsnow); node taint blocks scheduling |
| lawapp-backend          | iterlaw-ai  | MISSING   | Not yet deployed (manifests in this dir)  |

## Pre-Apply Checklist

Before running `kubectl apply -f`:

1. Node must be `Ready` (fix via Azure Portal / `az aks nodepool scale`)
2. Build and push image: `ghcr.io/serverax/lawapp/backend:${GIT_SHA}`
3. Create `lawapp-secrets` Secret with real values (see `secrets.example.yaml`)
4. Run database migrations against target Postgres
5. Run local regression: `docker compose run --rm ingestion python -m pytest`
6. Run legal accuracy gate: `python scripts/run_legal_accuracy.py`
7. Run rules verification gate: `python scripts/check_rules_verification.py`
8. Validate YAML: `kubectl apply --dry-run=server -f .`

## Apply Order

```bash
# 1. Namespaces (already exist — skip if present)
kubectl apply -f namespace.yaml

# 2. ConfigMap
kubectl apply -f configmap.yaml -n iterlaw-ai

# 3. Secrets (create manually with real values, NOT from this file)
# kubectl create secret generic lawapp-secrets --from-env-file=.env -n iterlaw-ai

# 4. Backend service
kubectl apply -f backend-service.yaml -n iterlaw-ai

# 5. Backend deployment
kubectl apply -f backend-deployment.yaml -n iterlaw-ai

# 6. Network policy
kubectl apply -f networkpolicy.yaml -n iterlaw-ai

# 7. RAG jobs (only when node Ready and image available)
kubectl apply -f ingestion-job-legislation.yaml -n iterlaw-rag
kubectl apply -f ingestion-job-acas.yaml -n iterlaw-rag
kubectl apply -f source-freshness-cronjob.yaml -n iterlaw-rag

# Verify
kubectl rollout status deployment/lawapp-backend -n iterlaw-ai
kubectl logs -l app=lawapp-backend -n iterlaw-ai --tail=50
```

## Hard Rules

- NEVER apply to any namespace outside the `iterlaw-*` list above
- NEVER create public ingress until internal `/health` passes
- NEVER commit real secrets (secrets.example.yaml is placeholder-only)
- NEVER set `controlled_beta_ready=true` or `production_ready=true`
