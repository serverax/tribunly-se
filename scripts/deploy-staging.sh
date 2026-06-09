#!/usr/bin/env bash
# Deploy lawapp backend to the staging cluster namespace.
# Usage: bash scripts/deploy-staging.sh [image_tag]
# Requires: KUBECONFIG set to target cluster
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-hetzner}"
NAMESPACE="iterlaw-ai"
TAG="${1:-latest}"
IMAGE="ghcr.io/serverax/lawapp/backend:$TAG"

# Safety: confirm correct cluster and namespace
CTX=$(kubectl config current-context)
echo "Context: $CTX  Namespace: $NAMESPACE  Image: $IMAGE"
kubectl get ns "$NAMESPACE" > /dev/null

# Confirm required secrets exist
kubectl get secret lawapp-secrets -n "$NAMESPACE" > /dev/null
kubectl get secret ghcr-pull-secret -n "$NAMESPACE" > /dev/null

# Apply configmap
kubectl apply -f infra/k8s/iterlaw/configmap.yaml -n "$NAMESPACE"

# Set image and rollout
kubectl set image deployment/lawapp-backend \
  backend="$IMAGE" -n "$NAMESPACE"
kubectl rollout status deployment/lawapp-backend \
  -n "$NAMESPACE" --timeout=180s

# Run migrations
bash scripts/run-migrations.sh

# Smoke test
bash scripts/smoke-iterlaw-ai.sh

echo "DEPLOY COMPLETE: $IMAGE"
