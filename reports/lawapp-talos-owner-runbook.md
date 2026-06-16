# lawapp  -  Talos Cluster Owner Runbook

**Project:** lawapp  -  UK Employment Law AI Assistant  
**Cluster:** Talos/Hetzner  
**Date:** 2026-06-04  

---

## Cluster Details

| Role | IP |
|---|---|
| master/control-plane | 148.251.247.56 |
| worker-llm | 138.201.253.245 |
| worker-secondary | 138.201.202.174 |

**Approved namespaces only:**
- `lawapp-api`
- `lawapp-ai`
- `lawapp-rag`
- `lawapp-security`
- `lawapp-monitoring`

---

## Prerequisites

```bash
# From WSL on your machine
export KUBECONFIG=$HOME/.kube/config-hetzner
kubectl config current-context
kubectl get nodes -o wide
# Confirm nodes show IPs: 148.251.247.56, 138.201.253.245, 138.201.202.174
```

---

## One-Command Deploy

```bash
cd /mnt/f/lawapp

# Set your real secrets (do NOT commit these)
export POSTGRES_PASSWORD='your-secure-db-password'
export JWT_SECRET="$(openssl rand -base64 32)"
export ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
# NOTE: inference is LOCAL OLLAMA ONLY  -  no external LLM API key is used.
# LAWAPP_LLM_PROVIDER/LAWAPP_OLLAMA_* are set in deployment manifests/config.
export STRIPE_SECRET_KEY='sk_test_your_stripe_key_or_placeholder'
export STRIPE_PUBLIC_KEY='pk_test_your_stripe_key_or_placeholder'
export ADMIN_API_KEY="$(openssl rand -base64 16)"

bash scripts/deploy-talos.sh
```

---

## Step-by-Step Manual Deploy

### Step 1: Create namespaces

```bash
kubectl apply -f infra/k8s/lawapp-namespaces.yaml
kubectl get ns | grep lawapp
```

Expected:
```
lawapp-api         Active
lawapp-ai          Active
lawapp-rag         Active
lawapp-security    Active
lawapp-monitoring  Active
```

### Step 2: Create secrets

**Secret names must exactly match `envFrom.secretRef.name` in each deployment YAML:**

| Namespace | Secret name | Used by |
|---|---|---|
| `lawapp-api` | `lawapp-postgres-secret` | PostgreSQL StatefulSet |
| `lawapp-api` | `lawapp-secrets` | `lawapp-backend.yaml` |
| `lawapp-ai` | `lawapp-ai-secrets` | `lawapp-ai-brain.yaml` |
| `lawapp-rag` | `lawapp-rag-secrets` | ingestion/embedding jobs |



**Do NOT print or commit values.**

```bash
# DB secret
kubectl -n lawapp-api create secret generic lawapp-postgres-secret \
  --from-literal=POSTGRES_DB=lawapp \
  --from-literal=POSTGRES_USER=lawapp \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

# App secrets (lawapp-api)
DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-api.svc.cluster.local:5432/lawapp"
kubectl -n lawapp-api create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  --from-literal=STRIPE_SECRET_KEY="$STRIPE_SECRET_KEY" \
  --from-literal=STRIPE_PUBLIC_KEY="$STRIPE_PUBLIC_KEY" \
  --from-literal=ADMIN_API_KEY="$ADMIN_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# AI secrets (lawapp-ai)
kubectl -n lawapp-ai create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# RAG secrets (lawapp-rag)
kubectl -n lawapp-rag create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify secret names only
kubectl get secrets -n lawapp-api
kubectl get secrets -n lawapp-ai
kubectl get secrets -n lawapp-rag
```

### Step 3: Apply ConfigMaps

```bash
kubectl apply -f infra/k8s/lawapp-configmaps.yaml
```

### Step 4: Deploy PostgreSQL

```bash
kubectl apply -f infra/k8s/lawapp-postgres-sts.yaml
kubectl wait --for=condition=ready pod -l app=lawapp-postgres -n lawapp-api --timeout=120s

kubectl get pods -n lawapp-api -o wide
kubectl get svc -n lawapp-api
kubectl get pvc -n lawapp-api
```

### Step 5: Enable extensions

```bash
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- \
  psql -U lawapp -d lawapp -c "
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto');
  "
```

Expected:
```
  extname
----------
 pgcrypto
 vector
(2 rows)
```

### Step 6: Run migrations

```bash
PGPOD=$(kubectl get pod -n lawapp-api -l app=lawapp-postgres -o jsonpath='{.items[0].metadata.name}')
for f in db/migrations/*.sql; do
  echo "  $(basename $f)"
  kubectl exec -i -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp < "$f"
done

# Verify
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "\dt" | wc -l
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM rules;"
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM legal_nodes;"
```

Expected: ~38 tables, rules=19, legal_nodes=15

### Step 7: Deploy backend

```bash
kubectl apply -f infra/k8s/lawapp-backend.yaml
kubectl wait --for=condition=available deploy/lawapp-backend -n lawapp-api --timeout=120s
kubectl get pods -n lawapp-api -o wide
kubectl logs -n lawapp-api deploy/lawapp-backend --tail=20
```

### Step 8: Smoke test backend

```bash
kubectl -n lawapp-api port-forward svc/lawapp-backend 8000:8000 &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status":"ok","db":"connected"}
```

### Step 9: Deploy Brain service

```bash
kubectl apply -f infra/k8s/lawapp-ai-brain.yaml
kubectl wait --for=condition=available deploy/lawapp-brain -n lawapp-ai --timeout=120s
kubectl get pods -n lawapp-ai -o wide
kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=20
```

### Step 10: Deploy RAG/Ingestion

```bash
kubectl apply -f infra/k8s/lawapp-ingestion-jobs.yaml || true
kubectl apply -f infra/k8s/lawapp-embedding-job.yaml || true
kubectl get pods -n lawapp-rag -o wide
kubectl get jobs -n lawapp-rag
```

### Step 11: Deploy security + monitoring

```bash
kubectl apply -f infra/k8s/lawapp-security-policies.yaml
kubectl apply -f infra/k8s/lawapp-monitoring.yaml
kubectl get networkpolicy -A | grep lawapp
kubectl get cronjob -n lawapp-monitoring
```

### Step 12: Configure ingress (when domain/DNS is ready)

```bash
# Check if ingress controller exists
kubectl get pods -A | grep -E "traefik|ingress-nginx"

# If ready, apply ingress
kubectl apply -f infra/k8s/lawapp-ingress.yaml
kubectl get ingress -A | grep lawapp
```

---

## Final Cluster Verification

```bash
kubectl get ns | grep lawapp
kubectl get pods -n lawapp-api -o wide
kubectl get pods -n lawapp-ai -o wide
kubectl get pods -n lawapp-rag -o wide
kubectl get pods -n lawapp-security -o wide
kubectl get pods -n lawapp-monitoring -o wide
kubectl get svc -A | grep lawapp
kubectl get pvc -A | grep lawapp
kubectl get secrets -n lawapp-api    # names only
kubectl get configmap -n lawapp-api
kubectl get ingress -A | grep lawapp

# DB tables
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- \
  psql -U lawapp -d lawapp -c "SELECT count(*) FROM rules;"

# Brain trace smoke test
kubectl -n lawapp-api port-forward svc/lawapp-backend 8000:8000 &
curl -s -X POST http://localhost:8000/api/brain/trace \
  -H "Content-Type: application/json" \
  -d '{"message":"I was dismissed after 10 months","facts":{"edt":"2026-03-01","service_start_date":"2025-05-01","jurisdiction":"EW"}}'
# Expected: status=ok, has_viable_claim=no (deterministic result without AI key)
```

---

## Post-Deploy Status Expected

After successful deploy:
```
READY FOR TALOS INTERNAL DEMO: YES (if all pods Running and smoke test passes)
READY FOR PUBLIC STAGING: NO until ingress/TLS + local Ollama inference healthy + payment decision
READY FOR PRODUCTION: NO
```

---

## Important Notes

1. **Inference is LOCAL OLLAMA ONLY**  -  do not set `ANTHROPIC_API_KEY` or any external LLM key. The brain routes to the in-cluster Ollama service (`LAWAPP_LLM_PROVIDER=ollama_local`, `LAWAPP_OLLAMA_BASE_URL`, `LAWAPP_OLLAMA_MODEL`). If Ollama is unreachable, assessments fail closed with `insufficient_grounding` (correct safety behaviour)  -  fix the Ollama deployment, do not add an external key.

2. **JWT_ISSUER and JWT_AUDIENCE must match**  -  both `_create_jwt` and `_verify_jwt_hs256` use these. They're set in lawapp-app-secrets and lawapp-ai-secrets above.

3. **PostgreSQL is in `lawapp-api` namespace**  -  internal DNS: `lawapp-postgres.lawapp-api.svc.cluster.local:5432`

4. **Never print secret values**  -  the secret creation commands above use env vars only. Do not add values to YAML files or commit to git.

5. **Backend image tag**  -  deploy by the immutable commit-SHA tag (or sha256 digest) published by the canonical CI workflow (`ci.yml` build-push job), never by `latest`. Update `infra/k8s/lawapp-backend.yaml` to `ghcr.io/serverax/lawapp/backend:<release-commit-sha>` so the deployed artifact maps to the exact commit that passed CI.
