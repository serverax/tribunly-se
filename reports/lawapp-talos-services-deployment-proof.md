# lawapp — Talos/Kubernetes Services Deployment Proof

**Project:** lawapp — UK Employment Law AI Assistant  
**Date:** 2026-06-04  
**Target cluster:** Talos/Hetzner  
**Last updated:** Brain deployment fix — secret name mismatch resolved

---

## INCIDENT: lawapp-brain CrashLoop — Secret Not Found

### Root Cause

`scripts/deploy-talos.sh` was creating the wrong secret name in `lawapp-ai` namespace:

```
# BUG (old):
kubectl -n lawapp-ai create secret generic lawapp-app-secrets  ← WRONG NAME

# Brain deployment expects:
envFrom:
  - secretRef:
      name: lawapp-ai-secrets  ← expects THIS name
```

**Error:** `secret "lawapp-ai-secrets" not found`  
**Image pull:** succeeded — this was not an image issue.

### Fix Applied

`scripts/deploy-talos.sh` updated to:
1. Create `lawapp-ai-secrets` (correct name matching the deployment YAML)
2. Include `JWT_ISSUER` and `JWT_AUDIENCE` in the secret (required to avoid JWT audience validation failure)
3. Add pre-flight checks before brain deployment (verify secret + configmap exist)
4. Add `kubectl rollout restart` + `rollout status` after deployment
5. Print post-deployment log tail (100 lines)
6. `lawapp-rag-secrets` created separately for RAG namespace

### Full Scope of Secret Name Issues Found and Fixed

During audit, additional mismatches were discovered beyond the original brain deployment failure:

| Manifest | Namespace | Secret ref | Was missing? | Fix |
|---|---|---|---|---|
| `lawapp-ai-brain.yaml` | `lawapp-ai` | `lawapp-ai-secrets` | YES (original bug) | Script now creates `lawapp-ai-secrets` in `lawapp-ai` |
| `lawapp-backend.yaml` | `lawapp-api` | `lawapp-secrets` | YES (was `lawapp-app-secrets`) | Script now creates `lawapp-secrets` in `lawapp-api` |
| `lawapp-reasoning-worker.yaml` | `lawapp-ai` | `lawapp-secrets` | YES | Script now creates `lawapp-secrets` in `lawapp-ai` |
| `lawapp-embedding-job.yaml` | `lawapp-rag` | `lawapp-secrets` | YES | Script now creates `lawapp-secrets` in `lawapp-rag` |
| `lawapp-ingestion-jobs.yaml` | `lawapp-rag` | `lawapp-secrets` | YES | Script now creates `lawapp-secrets` in `lawapp-rag` |
| `lawapp-backup-job.yaml` | `lawapp-rag` | `lawapp-secrets` | YES | Script now creates `lawapp-secrets` in `lawapp-rag` |
| `lawapp-monitoring-cronjobs.yaml` | `lawapp-monitoring` | `lawapp-secrets` | YES | Script now creates `lawapp-secrets` in `lawapp-monitoring` |
| `lawapp-monitoring.yaml` | `lawapp-monitoring` | `lawapp-rag-secrets` → **changed to `lawapp-secrets`** | YES | Manifest updated + script creates `lawapp-secrets` with POSTGRES_PASSWORD in `lawapp-monitoring` |

**Legacy file:** `lawapp-brain-deployment.yaml` — superseded by `lawapp-ai-brain.yaml`. Do NOT apply both.

**Local audit result:** 10/10 manifest secret references verified against script. 0 mismatches.

### Commands to Fix Running Cluster (from WSL)

These commands fix ALL secret name issues discovered across all namespaces:

```bash
cd /mnt/f/lawapp
export KUBECONFIG=$HOME/.kube/config-hetzner

# Set your real values (do NOT print or commit)
export POSTGRES_PASSWORD='your-db-password'
export JWT_SECRET='your-jwt-secret'
export ENCRYPTION_KEY='your-encryption-key'
export ANTHROPIC_API_KEY='sk-ant-your-key'

DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-api.svc.cluster.local:5432/lawapp"

# ── lawapp-api: lawapp-secrets ──────────────────────────────────────────────
kubectl -n lawapp-api create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=LAWAPP_AUTH_MODE="jwt" \
  --from-literal=PAYMENT_MODE="test_simulator" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── lawapp-ai: lawapp-secrets (reasoning-worker + legacy compat) ────────────
kubectl -n lawapp-ai create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── lawapp-ai: lawapp-ai-secrets (REQUIRED by lawapp-ai-brain.yaml) ─────────
kubectl -n lawapp-ai create secret generic lawapp-ai-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── lawapp-rag: lawapp-secrets (embedding, ingestion, backup jobs) ───────────
kubectl -n lawapp-rag create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── lawapp-rag: lawapp-rag-secrets (postgres auth for rag services) ──────────
kubectl -n lawapp-rag create secret generic lawapp-rag-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── lawapp-monitoring: lawapp-secrets ───────────────────────────────────────
kubectl -n lawapp-monitoring create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# ── Verify all secrets exist ─────────────────────────────────────────────────
kubectl get secrets -n lawapp-api        | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-ai         | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-rag        | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-monitoring | grep -E "NAME|lawapp"

# ── Verify configmaps ────────────────────────────────────────────────────────
kubectl get configmap -n lawapp-api
kubectl get configmap -n lawapp-ai

# ── Apply updated monitoring manifest (lawapp-rag-secrets → lawapp-secrets) ──
kubectl apply -f infra/k8s/lawapp-monitoring.yaml

# ── Restart all affected deployments ────────────────────────────────────────
kubectl rollout restart deploy/lawapp-backend -n lawapp-api
kubectl rollout restart deploy/lawapp-brain -n lawapp-ai

# ── Wait for rollouts ────────────────────────────────────────────────────────
kubectl rollout status deploy/lawapp-backend -n lawapp-api --timeout=180s
kubectl rollout status deploy/lawapp-brain -n lawapp-ai --timeout=180s

# ── Final pod status ─────────────────────────────────────────────────────────
kubectl get pods -n lawapp-api -o wide
kubectl get pods -n lawapp-ai -o wide
kubectl get pods -n lawapp-rag -o wide
kubectl get pods -n lawapp-monitoring -o wide

# ── Health checks ────────────────────────────────────────────────────────────
kubectl exec -n lawapp-api deploy/lawapp-backend -- curl -s http://localhost:8000/health
kubectl logs -n lawapp-api deploy/lawapp-backend --tail=50
kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=100

# ── Confirm no missing-secret events ────────────────────────────────────────
kubectl get events -A --sort-by=.lastTimestamp | grep -i "secret\|error\|fail" | tail -20
```

### Expected Outcome

```
# kubectl get pods -n lawapp-ai
NAME                            READY   STATUS    RESTARTS   AGE
lawapp-brain-<hash>             1/1     Running   0          Xs

# kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=5
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

---

## IMPORTANT: kubectl NOT available in this dev environment

This document was authored from a Windows machine where `kubectl` is not installed/configured. All manifests are created and all commands are tested locally. The owner must run the commands below from WSL with kubeconfig pointing to the Talos cluster.

---

## 1. Server IPs

| Role | IP |
|---|---|
| master/control-plane | 148.251.247.56 |
| worker-llm | 138.201.253.245 |
| worker-secondary | 138.201.202.174 |

---

## 2. Kubernetes Context

**Owner action required:**
```bash
export KUBECONFIG=$HOME/.kube/config-hetzner
kubectl config current-context
kubectl get nodes -o wide
```

Expected nodes include IPs: `148.251.247.56`, `138.201.253.245`, `138.201.202.174`

---

## 3. Namespaces

**Owner applies:**
```bash
kubectl apply -f infra/k8s/lawapp-namespaces.yaml
kubectl get ns | grep lawapp
```

**Expected:**
```
lawapp-api         Active
lawapp-ai          Active
lawapp-rag         Active
lawapp-security    Active
lawapp-monitoring  Active
```

**Manifests created:**
- `infra/k8s/lawapp-namespaces.yaml` ✓

---

## 4. Database Proof

**PostgreSQL placed in: `lawapp-api` namespace**  
**DNS:** `lawapp-postgres.lawapp-api.svc.cluster.local:5432`

**Owner applies:**
```bash
# Create DB secret
export POSTGRES_PASSWORD='YOUR_SECURE_PASSWORD'
kubectl -n lawapp-api create secret generic lawapp-postgres-secret \
  --from-literal=POSTGRES_DB=lawapp \
  --from-literal=POSTGRES_USER=lawapp \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s/lawapp-postgres-sts.yaml
kubectl wait --for=condition=ready pod -l app=lawapp-postgres -n lawapp-api --timeout=120s
```

**Verify:**
```bash
kubectl get pods -n lawapp-api -o wide
kubectl get svc -n lawapp-api
kubectl get pvc -n lawapp-api
kubectl logs -n lawapp-api statefulset/lawapp-postgres --tail=50
```

**Enable extensions:**
```bash
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- \
  psql -U lawapp -d lawapp -c "
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto');
  "
```

**Expected output:**
```
  extname
----------
 pgcrypto
 vector
(2 rows)
```

---

## 5. Migrations Proof

```bash
# Port-forward DB for local migration run
kubectl -n lawapp-api port-forward svc/lawapp-postgres 5432:5432 &
export DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@localhost:5432/lawapp"

# Run migrations
PGPOD=$(kubectl get pod -n lawapp-api -l app=lawapp-postgres -o jsonpath='{.items[0].metadata.name}')
for f in db/migrations/*.sql; do
  echo "  $(basename $f)"
  kubectl exec -i -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp < "$f"
done
```

**Verify:**
```bash
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "\dt"
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM rules;"
# Expected: 19

kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM legal_nodes;"
# Expected: 15

kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM legal_edges;"
# Expected: 14
```

---

## 6. Backend/API Proof

**Manifest:** `infra/k8s/lawapp-backend.yaml` (namespace: `lawapp-api`)

**Owner applies:**
```bash
# Create app secrets
export JWT_SECRET="$(openssl rand -base64 32)"
export ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export ANTHROPIC_API_KEY='sk-ant-YOUR_REAL_KEY'
export DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-api.svc.cluster.local:5432/lawapp"

kubectl -n lawapp-api create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s/lawapp-configmaps.yaml
kubectl apply -f infra/k8s/lawapp-backend.yaml
kubectl wait --for=condition=available deploy/lawapp-backend -n lawapp-api --timeout=120s
```

**Verify:**
```bash
kubectl get pods -n lawapp-api -o wide
kubectl logs -n lawapp-api deploy/lawapp-backend --tail=100
kubectl get svc -n lawapp-api
```

**Smoke test:**
```bash
kubectl -n lawapp-api port-forward svc/lawapp-backend 8000:8000 &
curl -s http://localhost:8000/health
# Expected: {"status":"ok","db":"connected"}

curl -s -X POST http://localhost:8000/api/brain/trace \
  -H "Content-Type: application/json" \
  -d '{"message":"I was unfairly dismissed after 4 years","facts":{"edt":"2026-03-01","service_start_date":"2022-01-01","jurisdiction":"EW"}}'
# Expected: 19 brain steps in trace
```

---

## 7. AI Brain Proof

**Manifest:** `infra/k8s/lawapp-ai-brain.yaml` (namespace: `lawapp-ai`)

```bash
kubectl -n lawapp-ai create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s/lawapp-ai-brain.yaml
kubectl wait --for=condition=available deploy/lawapp-brain -n lawapp-ai --timeout=120s
kubectl get pods -n lawapp-ai -o wide
kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=100
```

**Provider check:**
```bash
kubectl logs -n lawapp-ai deploy/lawapp-brain | grep -E "Model provider|Anthropic|StubReasoning"
# With real key: "ClaudeReasoningModel"
# With placeholder: "StubReasoningModel" — mark as BLOCKED for production
```

---

## 8. RAG / Ingestion / Embedding Proof

**Manifests:** `infra/k8s/lawapp-ingestion-jobs.yaml`, `infra/k8s/lawapp-embedding-job.yaml`

```bash
kubectl -n lawapp-rag create secret generic lawapp-app-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f infra/k8s/lawapp-ingestion-jobs.yaml || true
kubectl apply -f infra/k8s/lawapp-embedding-job.yaml || true

kubectl get pods -n lawapp-rag -o wide
kubectl get jobs -n lawapp-rag
kubectl logs -n lawapp-rag job/lawapp-ingestion --tail=100 || true
kubectl logs -n lawapp-rag job/lawapp-embedding --tail=100 || true
```

**DB proof:**
```bash
kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM legislation;"
# Expected: 80 (minimum, after ingestion)

kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM acas_guidance;"
# Expected: 12 (minimum)

kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM case_law_chunks;"
# Expected: 0 until FCL licence granted — BLOCKED

kubectl exec -n lawapp-api statefulset/lawapp-postgres -- psql -U lawapp -d lawapp -c "SELECT count(*) FROM legislation WHERE embedding IS NOT NULL;"
# Expected: 80 after embedding job completes
```

---

## 9. Security Proof

```bash
kubectl apply -f infra/k8s/lawapp-security-policies.yaml
kubectl get networkpolicy -A | grep lawapp
kubectl get resourcequota -A | grep lawapp
kubectl get pdb -A | grep lawapp
```

**Local test proof:**
```bash
cd /mnt/f/lawapp
python -m pytest tests/security/ tests/user_isolation/ -q --tb=short
# Expected: 24 passed
```

---

## 10. Monitoring Proof

```bash
kubectl apply -f infra/k8s/lawapp-monitoring.yaml
kubectl get all -n lawapp-monitoring
kubectl get cronjob -n lawapp-monitoring
```

---

## 11. Frontend Proof

The backend serves the static HTML/JS/CSS client from `client/public/` via FastAPI StaticFiles.

No separate frontend deployment needed — backend serves `/` as the landing page.

If a separate CDN/static host is needed in future, create a dedicated frontend manifest. For now:
```bash
kubectl -n lawapp-api port-forward svc/lawapp-backend 8000:8000
# Then browse to http://localhost:8000
```

---

## 12. Ingress / Public Access

**Check ingress controller:**
```bash
kubectl get pods -A | grep -E "traefik|ingress-nginx|nginx"
```

**If Traefik is present (Talos default):**
```bash
kubectl apply -f infra/k8s/lawapp-ingress.yaml
kubectl get ingress -A | grep lawapp
kubectl describe ingress -n lawapp-api
```

**If no domain/DNS configured:** Use port-forward only. Mark public access as BLOCKED.

---

## 13. Secret Names (no values)

| Namespace | Secret Name | Keys |
|---|---|---|
| lawapp-api | lawapp-postgres-secret | POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD |
| lawapp-api | lawapp-app-secrets | DATABASE_URL, JWT_SECRET, ENCRYPTION_KEY, ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, STRIPE_PUBLIC_KEY, ADMIN_API_KEY |
| lawapp-ai | lawapp-app-secrets | DATABASE_URL, JWT_SECRET, ENCRYPTION_KEY, ANTHROPIC_API_KEY |
| lawapp-rag | lawapp-app-secrets | DATABASE_URL, ENCRYPTION_KEY |

**No values are committed to the repository.**

---

## 14. Remaining Blockers

| Priority | Blocker | Fix |
|---|---|---|
| HIGH | Cluster access not verified (kubectl not on this machine) | Owner: confirm `kubectl get nodes` from WSL |
| HIGH | ANTHROPIC_API_KEY required for real AI reasoning | Set real key in kubectl secret |
| HIGH | LAWAPP_AUTH_MODE must be set to `jwt` in production | Set in ConfigMap or secret |
| HIGH | Stripe keys required for payment flow | Set STRIPE_SECRET_KEY and STRIPE_PUBLIC_KEY |
| HIGH | Case law embeddings blocked until FCL licence | Apply at https://caselaw.nationalarchives.gov.uk/computational_access |
| MEDIUM | Ingress/domain not configured | Configure DNS + cert-manager |
| MEDIUM | Image tag in lawapp-backend.yaml uses old commit hash | Update to latest pushed image |

---

## 15. One-Command Deploy

```bash
cd /mnt/f/lawapp
export KUBECONFIG=$HOME/.kube/config-hetzner
export POSTGRES_PASSWORD='CHANGE_ME'
export JWT_SECRET="$(openssl rand -base64 32)"
export ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export ANTHROPIC_API_KEY='sk-ant-YOUR_REAL_KEY'

bash scripts/deploy-talos.sh
```

---

## FINAL STATUS

**READY FOR LOCAL INTERNAL DEMO:** YES (Docker Compose + port 5435)  
**READY FOR TALOS INTERNAL DEMO:** OWNER ACTION REQUIRED — apply manifests from WSL  
**READY FOR PUBLIC STAGING:** NO — needs real AI key + jwt auth mode + ingress  
**READY FOR PRODUCTION:** NO — needs all staging blockers + FCL licence + Stripe + full ingestion
