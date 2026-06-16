#!/usr/bin/env bash
# Run all DB migrations against the cluster Postgres via kubectl exec.
# Usage: bash scripts/run-migrations.sh [--namespace NAMESPACE]
# Requires: KUBECONFIG set to target Hetzner/Talos cluster
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-hetzner}"

# PostgreSQL lives in lawapp-api namespace
NAMESPACE="${1:-lawapp-api}"

echo "=== lawapp migrations ==="
echo "Cluster: $(kubectl config current-context)"
echo "Namespace: $NAMESPACE"

PGPOD=$(kubectl get pod -n "$NAMESPACE" -l app=lawapp-postgres \
  -o jsonpath='{.items[0].metadata.name}')
echo "Postgres pod: $PGPOD"

echo "Installing pgvector and pgcrypto extensions..."
kubectl exec -i -n "$NAMESPACE" "$PGPOD" -- \
  psql -U lawapp -d lawapp -c "
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto');
  "

echo "Applying migrations..."
for f in db/migrations/*.sql; do
  echo "  $(basename $f)"
  kubectl exec -i -n "$NAMESPACE" "$PGPOD" -- \
    psql -U lawapp -d lawapp < "$f"
done

echo ""
echo "=== Migration complete  -  DB state ==="
kubectl exec -n "$NAMESPACE" "$PGPOD" -- \
  psql -U lawapp -d lawapp -c "
    SELECT schemaname, tablename
    FROM pg_tables WHERE schemaname='public'
    ORDER BY tablename;
  "
kubectl exec -n "$NAMESPACE" "$PGPOD" -- \
  psql -U lawapp -d lawapp -c "SELECT count(*) AS rules FROM rules;"
kubectl exec -n "$NAMESPACE" "$PGPOD" -- \
  psql -U lawapp -d lawapp -c "SELECT count(*) AS legal_nodes FROM legal_nodes;"
kubectl exec -n "$NAMESPACE" "$PGPOD" -- \
  psql -U lawapp -d lawapp -c "SELECT count(*) AS legal_edges FROM legal_edges;"
echo "=== Done ==="
