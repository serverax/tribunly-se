#!/usr/bin/env bash
# Full integration regression  -  uses Docker to avoid WSL/Windows venv issues.
# No local Python venv required.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "======================================================================"
echo "LAWAPP  -  FULL INTEGRATION REGRESSION"
echo "======================================================================"
echo "Running via Docker ingestion container (WSL-safe, no local venv)..."
echo

docker compose run --rm ingestion python -m pytest tests/integration -q

echo
echo "======================================================================"
