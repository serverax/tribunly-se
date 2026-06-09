#!/usr/bin/env bash
# lawapp Talos/Kubernetes Deployment Runbook
# Run from: /mnt/f/lawapp on WSL machine with kubeconfig
# Target: Talos/Hetzner cluster
#   master:   148.251.247.56
#   worker-llm: 138.201.253.245
#   worker-secondary: 138.201.202.174
#
# Usage:
#   export KUBECONFIG=$HOME/.kube/config-hetzner
#   export POSTGRES_PASSWORD='YOUR_SECURE_PASSWORD'
#   export JWT_SECRET='YOUR_JWT_SECRET'
#   export ENCRYPTION_KEY='YOUR_ENCRYPTION_KEY'
#   export ANTHROPIC_API_KEY='sk-ant-YOUR_REAL_KEY'
#   bash scripts/deploy-talos.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-hetzner}"

echo "=== lawapp Talos Deployment ==="
kubectl config current-context
echo ""
echo "=== Cluster nodes ==="
kubectl get nodes -o wide
echo ""

# ── Step 1: Namespaces ──────────────────────────────────────────────────────
echo "=== Creating namespaces ==="
kubectl apply -f infra/k8s/lawapp-namespaces.yaml
kubectl get ns | grep lawapp
echo ""

# ── Step 2: Secrets ─────────────────────────────────────────────────────────
echo "=== Creating secrets (values from env vars — not committed) ==="

: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${JWT_SECRET:?JWT_SECRET is required}"
: "${ENCRYPTION_KEY:?ENCRYPTION_KEY is required}"

ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-placeholder}"
STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-placeholder}"
STRIPE_PUBLIC_KEY="${STRIPE_PUBLIC_KEY:-placeholder}"
ADMIN_API_KEY="${ADMIN_API_KEY:-$(openssl rand -base64 16)}"

DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-api.svc.cluster.local:5432/lawapp"

# DB secret (lawapp-api)
kubectl -n lawapp-api create secret generic lawapp-postgres-secret \
  --from-literal=POSTGRES_DB=lawapp \
  --from-literal=POSTGRES_USER=lawapp \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

# App secrets (lawapp-api)
# Secret name MUST match envFrom.secretRef.name in lawapp-backend.yaml: lawapp-secrets
kubectl -n lawapp-api create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY}" \
  --from-literal=STRIPE_PUBLIC_KEY="${STRIPE_PUBLIC_KEY}" \
  --from-literal=ADMIN_API_KEY="${ADMIN_API_KEY}" \
  --from-literal=LAWAPP_AUTH_MODE="jwt" \
  --from-literal=PAYMENT_MODE="test_simulator" \
  --dry-run=client -o yaml | kubectl apply -f -

# lawapp-secrets must exist in EVERY namespace that references it.
# Manifests in lawapp-rag, lawapp-ai, lawapp-monitoring all use `secretRef: lawapp-secrets`.

# lawapp-ai: lawapp-secrets (for lawapp-reasoning-worker, lawapp-brain-deployment legacy)
kubectl -n lawapp-ai create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# lawapp-ai: lawapp-ai-secrets (REQUIRED by lawapp-ai-brain.yaml envFrom.secretRef)
kubectl -n lawapp-ai create secret generic lawapp-ai-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=JWT_ISSUER="lawapp-issuer" \
  --from-literal=JWT_AUDIENCE="lawapp-audience" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# lawapp-rag: lawapp-secrets (for embedding job, ingestion jobs, backup jobs)
kubectl -n lawapp-rag create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# lawapp-rag: lawapp-rag-secrets (for lawapp-monitoring.yaml POSTGRES_PASSWORD secretKeyRef)
kubectl -n lawapp-rag create secret generic lawapp-rag-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

# lawapp-monitoring: lawapp-secrets (for lawapp-monitoring-cronjobs.yaml + lawapp-monitoring.yaml POSTGRES_PASSWORD)
kubectl -n lawapp-monitoring create secret generic lawapp-secrets \
  --from-literal=DATABASE_URL="${DATABASE_URL}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created (names only — values not shown):"
kubectl get secrets -n lawapp-api        | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-ai         | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-rag        | grep -E "NAME|lawapp"
kubectl get secrets -n lawapp-monitoring | grep -E "NAME|lawapp"
echo ""

# ── Step 3: ConfigMaps ───────────────────────────────────────────────────────
echo "=== Applying ConfigMaps ==="
kubectl apply -f infra/k8s/lawapp-configmaps.yaml
echo ""

# ── Step 4: PostgreSQL ───────────────────────────────────────────────────────
echo "=== Deploying PostgreSQL ==="
kubectl apply -f infra/k8s/lawapp-postgres-sts.yaml
echo "Waiting for Postgres to be ready..."
kubectl wait --for=condition=ready pod -l app=lawapp-postgres -n lawapp-api --timeout=120s
kubectl get pods -n lawapp-api -o wide
echo ""

# ── Step 5: Enable extensions ────────────────────────────────────────────────
echo "=== Enabling pgvector + pgcrypto ==="
PGPOD=$(kubectl get pod -n lawapp-api -l app=lawapp-postgres -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto');
"
echo ""

# ── Step 6: Migrations ───────────────────────────────────────────────────────
echo "=== Running migrations ==="
for f in db/migrations/*.sql; do
  echo "  $(basename $f)"
  kubectl exec -i -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp < "$f"
done
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "SELECT count(*) as rules FROM rules;"
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "SELECT count(*) as legal_nodes FROM legal_nodes;"
kubectl exec -n lawapp-api "$PGPOD" -- psql -U lawapp -d lawapp -c "SELECT count(*) as legal_edges FROM legal_edges;"
echo ""

# ── Step 7: Backend API ──────────────────────────────────────────────────────
echo "=== Deploying lawapp backend ==="

# Pre-flight: confirm required secret and configmap exist in lawapp-api
echo "  Verifying lawapp-secrets exists in lawapp-api..."
kubectl get secret lawapp-secrets -n lawapp-api \
  || { echo "ERROR: lawapp-secrets not found in lawapp-api. Run Step 2 first."; exit 1; }
echo "  Verifying lawapp-config configmap exists in lawapp-api..."
kubectl get configmap lawapp-config -n lawapp-api \
  || { echo "ERROR: lawapp-config not found in lawapp-api. Apply lawapp-configmaps.yaml first."; exit 1; }

kubectl apply -f infra/k8s/lawapp-backend.yaml
echo "  Waiting for lawapp-backend rollout (up to 120s)..."
kubectl rollout status deploy/lawapp-backend -n lawapp-api --timeout=120s
kubectl get pods -n lawapp-api -o wide
echo ""

# ── Step 8: AI Brain service ─────────────────────────────────────────────────
echo "=== Deploying lawapp AI Brain ==="

# Pre-flight: confirm required secret and configmap exist in lawapp-ai
echo "  Verifying lawapp-ai-secrets exists in lawapp-ai..."
kubectl get secret lawapp-ai-secrets -n lawapp-ai \
  || { echo "ERROR: lawapp-ai-secrets not found in lawapp-ai. Run Step 2 first."; exit 1; }
echo "  Verifying lawapp-ai-config configmap exists in lawapp-ai..."
kubectl get configmap lawapp-ai-config -n lawapp-ai \
  || { echo "ERROR: lawapp-ai-config not found in lawapp-ai. Apply lawapp-configmaps.yaml first."; exit 1; }

kubectl apply -f infra/k8s/lawapp-ai-brain.yaml

# Trigger a rollout to pick up any secret/configmap updates
kubectl rollout restart deploy/lawapp-brain -n lawapp-ai

echo "  Waiting for lawapp-brain rollout (up to 180s)..."
kubectl rollout status deploy/lawapp-brain -n lawapp-ai --timeout=180s

kubectl get pods -n lawapp-ai -o wide
echo ""
echo "=== lawapp-brain logs (last 50 lines) ==="
kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=50 || true
echo ""

# ── Step 9: RAG / Ingestion / Embedding ─────────────────────────────────────
echo "=== Deploying lawapp RAG/Ingestion ==="
kubectl apply -f infra/k8s/lawapp-ingestion-jobs.yaml || true
kubectl apply -f infra/k8s/lawapp-embedding-job.yaml || true
kubectl get pods -n lawapp-rag -o wide
kubectl get jobs -n lawapp-rag || true
echo ""

# ── Step 10: Security policies ───────────────────────────────────────────────
echo "=== Applying security policies ==="
kubectl apply -f infra/k8s/lawapp-security-policies.yaml
kubectl get networkpolicy -A | grep lawapp
echo ""

# ── Step 11: Monitoring ──────────────────────────────────────────────────────
echo "=== Deploying monitoring ==="
kubectl apply -f infra/k8s/lawapp-monitoring.yaml
kubectl get cronjob -n lawapp-monitoring
echo ""

# ── Step 12: Ingress (only if ingress controller present) ────────────────────
echo "=== Checking ingress controller ==="
kubectl get pods -A | grep -E "traefik|ingress|nginx" || echo "No ingress controller found — apply manually when ready"
echo ""

# ── Step 13: Final smoke test ────────────────────────────────────────────────
echo "=== Smoke test (port-forward) ==="
echo "Run in a separate terminal:"
echo "  kubectl -n lawapp-api port-forward svc/lawapp-backend 8000:8000"
echo "  curl -s http://localhost:8000/health"
echo "  curl -s -X POST http://localhost:8000/api/brain/trace -H 'Content-Type: application/json' -d '{\"message\":\"I was unfairly dismissed\",\"facts\":{\"edt\":\"2026-03-01\",\"service_start_date\":\"2022-01-01\",\"jurisdiction\":\"EW\"}}'"
echo ""

# ── Step 14: Full status ─────────────────────────────────────────────────────
echo "=== Full cluster status ==="
echo "--- Namespaces ---"
kubectl get ns | grep lawapp
echo "--- Pods (all lawapp namespaces) ---"
kubectl get pods -n lawapp-api -o wide
kubectl get pods -n lawapp-ai -o wide
kubectl get pods -n lawapp-rag -o wide
kubectl get pods -n lawapp-security -o wide
kubectl get pods -n lawapp-monitoring -o wide
echo "--- Services ---"
kubectl get svc -A | grep lawapp
echo "--- PVCs ---"
kubectl get pvc -A | grep lawapp
echo "--- Secrets (names only) ---"
kubectl get secrets -n lawapp-api
echo ""
echo "=== Deployment complete ==="
echo ""
echo "Secret names deployed per namespace (no values):"
echo "  lawapp-api:         lawapp-postgres-secret, lawapp-secrets"
echo "  lawapp-ai:          lawapp-secrets, lawapp-ai-secrets"
echo "  lawapp-rag:         lawapp-secrets, lawapp-rag-secrets"
echo "  lawapp-monitoring:  lawapp-secrets"
echo ""
echo "NOTE: lawapp-brain-deployment.yaml is a legacy file."
echo "      Use lawapp-ai-brain.yaml (lawapp-ai-secrets) for the current brain deployment."
echo "      Do NOT apply lawapp-brain-deployment.yaml in the same cluster."
echo ""
echo "NOTE: Set ANTHROPIC_API_KEY to a real key for production AI reasoning"
echo "NOTE: Configure Stripe keys for real payment processing"
echo "NOTE: Apply infra/k8s/lawapp-ingress.yaml when DNS/TLS is ready"
echo ""
echo "=== To resume after a failed brain deployment (secret was missing) ==="
echo "  Run these commands from WSL:"
echo "  export POSTGRES_PASSWORD='...' JWT_SECRET='...' ENCRYPTION_KEY='...' ANTHROPIC_API_KEY='...'"
echo "  source scripts/deploy-talos.sh   (or run the secret + brain steps manually)"
echo "  kubectl rollout restart deploy/lawapp-brain -n lawapp-ai"
echo "  kubectl rollout status deploy/lawapp-brain -n lawapp-ai --timeout=180s"
echo "  kubectl get pods -n lawapp-ai -o wide"
echo "  kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=100"
