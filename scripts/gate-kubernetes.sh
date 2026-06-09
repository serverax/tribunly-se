#!/usr/bin/env bash
# lawapp Kubernetes Deployment Gate
# Validates cluster access and lawapp namespace state before claiming staging ready.
# Usage: bash scripts/gate-kubernetes.sh
# Returns: 0 if cluster is healthy, 1 if not

set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "=== lawapp Kubernetes Gate ==="

FAIL=0

# Check kubectl is available
if ! command -v kubectl >/dev/null 2>&1; then
  echo "FAIL: kubectl not found. Install kubectl first."
  exit 1
fi
echo "PASS: kubectl found: $(kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1)"

# Check cluster access
echo ""
echo "--- Cluster access ---"
CONTEXT=$(kubectl config current-context 2>&1)
echo "Context: $CONTEXT"

if ! kubectl cluster-info 2>&1 | grep -q "running\|control plane\|Kubernetes"; then
  echo "FAIL: Cannot connect to cluster."
  FAIL=1
else
  echo "PASS: Cluster accessible."
fi

# Check lawapp namespaces
echo ""
echo "--- Lawapp namespaces ---"
REQUIRED_NS=("lawapp-api" "lawapp-ai" "lawapp-rag" "lawapp-security" "lawapp-monitoring")
for ns in "${REQUIRED_NS[@]}"; do
  if kubectl get ns "$ns" >/dev/null 2>&1; then
    echo "  PASS: namespace $ns exists"
  else
    echo "  FAIL: namespace $ns MISSING"
    FAIL=1
  fi
done

# Check key deployments
echo ""
echo "--- Deployments ---"
if kubectl -n lawapp-api get deploy/lawapp-backend >/dev/null 2>&1; then
  STATUS=$(kubectl -n lawapp-api get deploy/lawapp-backend -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  if [ "${STATUS:-0}" -gt 0 ]; then
    echo "  PASS: lawapp-backend: $STATUS replicas available"
  else
    echo "  FAIL: lawapp-backend: 0 replicas available"
    FAIL=1
  fi
else
  echo "  FAIL: lawapp-backend deployment not found in lawapp-api"
  FAIL=1
fi

# Check secrets exist
echo ""
echo "--- Secrets ---"
for secret in "lawapp-secrets" "lawapp-postgres-secret"; do
  if kubectl -n lawapp-api get secret "$secret" >/dev/null 2>&1; then
    echo "  PASS: $secret exists in lawapp-api"
  else
    echo "  FAIL: $secret MISSING from lawapp-api"
    FAIL=1
  fi
done

if kubectl -n lawapp-ai get secret "lawapp-ai-secrets" >/dev/null 2>&1; then
  echo "  PASS: lawapp-ai-secrets exists in lawapp-ai"
else
  echo "  FAIL: lawapp-ai-secrets MISSING from lawapp-ai"
  FAIL=1
fi

# Run backend health check from inside pod
echo ""
echo "--- Backend health check ---"
if kubectl -n lawapp-api get deploy/lawapp-backend >/dev/null 2>&1; then
  HEALTH=$(kubectl -n lawapp-api exec deploy/lawapp-backend -- curl -sf http://localhost:8000/health 2>&1 || echo "FAILED")
  if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "  PASS: Backend health check passed from inside pod."
    echo "  $HEALTH"
  else
    echo "  FAIL: Backend health check failed: $HEALTH"
    FAIL=1
  fi
fi

# Check logs for errors
echo ""
echo "--- Recent backend logs ---"
kubectl -n lawapp-api logs deploy/lawapp-backend --tail=20 2>&1 | grep -E "ERROR|CRITICAL|Exception|Traceback" | head -5 || echo "  No critical errors in recent logs."

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "KUBERNETES GATE: PASSED — cluster is healthy."
  exit 0
else
  echo "KUBERNETES GATE: FAILED — see failures above."
  echo "Run: bash scripts/deploy-talos.sh"
  exit 1
fi
