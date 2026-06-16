#!/usr/bin/env bash
# lawapp local CI  -  runs the full test suite in docker compose.
# Usage: bash scripts/ci-local.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "=== lawapp local CI ==="
echo "Commit: $(git rev-parse --short HEAD)"
echo ""

echo "--- Unit tests ---"
docker compose run --rm ingestion python -m pytest \
  tests/test_classify.py tests/test_govern.py \
  tests/test_deidentify.py tests/test_deadline.py -q

echo ""
echo "--- Legal accuracy gate (38 tests) ---"
docker compose run --rm ingestion python scripts/run_legal_accuracy.py

echo ""
echo "--- Rules verification gate ---"
docker compose run --rm ingestion python scripts/check_rules_verification.py

echo ""
echo "--- Full regression ---"
docker compose run --rm ingestion python -m pytest tests/integration -q \
  --ignore=tests/integration/test_semantic_retrieval.py \
  --tb=short

echo ""
echo "=== CI LOCAL: PASS ==="
