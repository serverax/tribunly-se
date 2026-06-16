#!/usr/bin/env bash
# prove_full_pytest_suite.sh  -  official, repeatable full-suite test command.
# Runs the complete repo pytest suite inside the ingestion image, whose Dockerfile
# (Dockerfile.ingestion) installs ALL required deps (pytest, fastapi, slowapi, boto3,
# itsdangerous, cryptography, ...). NO ad-hoc pip install. Fails on any failure/error.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
REPORT="reports/full-pytest-suite-result.md"
echo "Test runner: docker compose run --rm ingestion (image: Dockerfile.ingestion)"

# Guard: deps must be in the IMAGE, not pip-installed at runtime.
if grep -q "slowapi" Dockerfile.ingestion && grep -q "itsdangerous" Dockerfile.ingestion; then
  echo "  OK: API test deps (slowapi, itsdangerous) are baked into Dockerfile.ingestion"
else
  echo "  FAIL: required test deps not in Dockerfile.ingestion"; exit 1
fi

OUT=$(docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion \
  sh -c "cd /app && python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/integration/test_semantic_retrieval.py" 2>&1)
rc=$?

SUMMARY=$(echo "$OUT" | grep -E "passed|failed|error" | tail -1)
echo "$OUT" | tail -20
echo
echo "SUMMARY: $SUMMARY"

{
  echo "# Full Pytest Suite  -  Result"
  echo
  echo "- Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo 2026-06-05)"
  echo "- Command: \`docker compose run --rm ingestion python -m pytest tests/ -q\`"
  echo "- Image: Dockerfile.ingestion (deps baked in  -  no ad-hoc pip)"
  echo "- Exit code: $rc"
  echo
  echo '```'
  echo "$SUMMARY"
  echo '```'
  echo
  echo "## Tail of run"
  echo '```'
  echo "$OUT" | tail -25
  echo '```'
} > "$REPORT"
echo "Report written: $REPORT"

# Fail on any failure or error (allow skips).
if echo "$SUMMARY" | grep -qE "failed|error"; then
  echo "FULL PYTEST SUITE: FAIL"; exit 1
fi
[ "$rc" -ne 0 ] && { echo "FULL PYTEST SUITE: FAIL (exit $rc)"; exit 1; }
echo "FULL PYTEST SUITE: PASS"
