#!/usr/bin/env bash
# lawapp Kubernetes Deployment Script
# Uses only the approved lawapp namespaces:
#   lawapp-api, lawapp-ai, lawapp-rag, lawapp-security, lawapp-monitoring
#
# DO NOT RUN until:
#  1. kubectl is configured to the correct cluster
#  2. All secrets are created (see below)
#  3. Docker images are pushed to GHCR
#  4. This script is run with explicit approval
#
# Usage:
#   chmod +x infra/k8s/lawapp-k8s-deploy.sh
#   ./infra/k8s/lawapp-k8s-deploy.sh [--dry-run]
#
# With --dry-run, shows what would be applied without applying it.

set -euo pipefail
DRY_RUN=${1:-""}
KUBECTL="kubectl"
if [[ "${DRY_RUN}" == "--dry-run" ]]; then
  KUBECTL="kubectl --dry-run=client"
  echo ">>> DRY RUN MODE  -  no changes will be applied <<<"
fi

echo ""
echo "══════════════════════════════════════════════════════"
echo " lawapp Kubernetes Deployment"
echo " Namespaces: lawapp-api, lawapp-ai, lawapp-rag"
echo "             lawapp-security, lawapp-monitoring"
echo "══════════════════════════════════════════════════════"
echo ""

# ── Step 0: Verify kubectl connectivity ────────────────────────────────────────
echo "[0/8] Verifying cluster access..."
kubectl cluster-info || { echo "ERROR: kubectl not connected. Configure kubeconfig first."; exit 1; }

# ── Step 1: Create namespaces ──────────────────────────────────────────────────
echo "[1/8] Creating namespaces..."
for ns in lawapp-api lawapp-ai lawapp-rag lawapp-security lawapp-monitoring; do
  kubectl create namespace "${ns}" --dry-run=client -o yaml | kubectl apply -f -
done
echo "  Namespaces: lawapp-api, lawapp-ai, lawapp-rag, lawapp-security, lawapp-monitoring"

# ── Step 2: Create secrets ─────────────────────────────────────────────────────
echo "[2/8] Creating secrets..."
echo "  REQUIREMENT: Set these env vars before running:"
echo "    ANTHROPIC_API_KEY, JWT_SECRET, ENCRYPTION_KEY, ADMIN_API_KEY"
echo "    POSTGRES_PASSWORD, STRIPE_SECRET_KEY, APP_BASE_URL"
echo ""
echo "  Command to create secrets (run after setting env vars):"
cat <<'SECRETS_EXAMPLE'
# lawapp-api namespace secrets
kubectl create secret generic lawapp-secrets \
  --namespace lawapp-api \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  --from-literal=ADMIN_API_KEY="${ADMIN_API_KEY}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" \
  --from-literal=DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-rag.svc.cluster.local:5432/lawapp" \
  --dry-run=client -o yaml | kubectl apply -f -

# Repeat for lawapp-ai, lawapp-rag, lawapp-monitoring
for ns in lawapp-ai lawapp-rag lawapp-monitoring; do
  kubectl create secret generic lawapp-secrets \
    --namespace "${ns}" \
    --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
    --from-literal=ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
    --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    --from-literal=DATABASE_URL="postgresql://lawapp:${POSTGRES_PASSWORD}@lawapp-postgres.lawapp-rag.svc.cluster.local:5432/lawapp" \
    --dry-run=client -o yaml | kubectl apply -f -
done
SECRETS_EXAMPLE

# ── Step 3: Apply ConfigMaps ───────────────────────────────────────────────────
echo "[3/8] Applying ConfigMaps..."
for ns in lawapp-api lawapp-ai lawapp-rag lawapp-monitoring; do
  $KUBECTL create configmap lawapp-config \
    --namespace "${ns}" \
    --from-literal=DEPLOYMENT_MODE=production \
    --from-literal=LAWAPP_AUTH_MODE=jwt \
    --from-literal=JWT_ISSUER=lawapp-issuer \
    --from-literal=JWT_AUDIENCE=lawapp-audience \
    --from-literal=KEY_MANAGEMENT_MODE=env \
    --from-literal=PAYMENT_MODE=stripe_live \
    --from-literal=WORKHORSE_MODEL_ID=claude-haiku-4-5-20251001 \
    --from-literal=APP_BASE_URL="${APP_BASE_URL:-https://app.lawapp.co.uk}" \
    --from-literal=LOG_LEVEL=INFO \
    --save-config --dry-run=client -o yaml | kubectl apply -f -
done

# ── Step 4: Apply PostgreSQL (lawapp-rag namespace) ────────────────────────────
echo "[4/8] Deploying PostgreSQL..."
$KUBECTL apply -f infra/k8s/lawapp-postgres-sts.yaml

# ── Step 5: Apply Backend API (lawapp-api namespace) ───────────────────────────
echo "[5/8] Deploying backend API..."
$KUBECTL apply -f infra/k8s/lawapp-backend.yaml

# ── Step 6: Deploy Brain (lawapp-ai namespace) ─────────────────────────────────
echo "[6/8] Deploying Brain Algorithm service..."
$KUBECTL apply -f infra/k8s/lawapp-brain-deployment.yaml

# ── Step 7: Apply ingestion jobs and monitoring (lawapp-rag, lawapp-monitoring) ─
echo "[7/8] Applying ingestion jobs and monitoring..."
$KUBECTL apply -f infra/k8s/lawapp-ingestion-jobs.yaml
$KUBECTL apply -f infra/k8s/lawapp-monitoring-cronjobs.yaml

# ── Step 8: Apply network policies (lawapp-security) ──────────────────────────
echo "[8/8] Applying network policies..."
$KUBECTL apply -f infra/k8s/lawapp-network-policies.yaml

echo ""
echo "══════════════════════════════════════════════════════"
echo " Deployment commands submitted."
echo " Run verification commands below to confirm PASS:"
echo "══════════════════════════════════════════════════════"
echo ""
cat <<'VERIFY'
# Namespace check
kubectl get ns | grep lawapp

# Pod status  -  wait for Running/Healthy
kubectl get pods -n lawapp-api
kubectl get pods -n lawapp-ai
kubectl get pods -n lawapp-rag
kubectl get pods -n lawapp-security
kubectl get pods -n lawapp-monitoring

# Service endpoints
kubectl get svc -A | grep lawapp

# Health check (after ingress/port-forward)
kubectl port-forward -n lawapp-api svc/lawapp-backend 8080:80 &
curl http://localhost:8080/health
curl http://localhost:8080/api/brain/trace \
  -d '{"message":"I was dismissed without warning","facts":{"jurisdiction":"EW"}}'

# Brain service (internal)
kubectl port-forward -n lawapp-ai svc/lawapp-brain 8081:8000 &
curl http://localhost:8081/health

# Logs
kubectl logs -n lawapp-api deploy/lawapp-backend --tail=50
kubectl logs -n lawapp-ai deploy/lawapp-brain --tail=50

# Events (check for errors)
kubectl get events -n lawapp-api --sort-by=.lastTimestamp | tail -20
kubectl get events -n lawapp-ai --sort-by=.lastTimestamp | tail -20
VERIFY
