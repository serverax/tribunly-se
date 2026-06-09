#!/usr/bin/env bash
# Pre-release gate: all quality checks must pass before image push.
# Usage: bash scripts/release-check.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

PASS=0; FAIL=0

ok()   { echo "  PASS: $1"; ((PASS++)); }
fail() { echo "  FAIL: $1"; ((FAIL++)); }

echo "=== lawapp release check — $(git rev-parse --short HEAD) ==="

# Legal accuracy gate
echo "--- Legal accuracy ---"
if docker compose run --rm ingestion python scripts/run_legal_accuracy.py 2>&1 | grep -q "LEGAL ACCURACY GATE: PASSED"; then
  ok "Legal accuracy gate (38 tests)"
else
  fail "Legal accuracy gate"
fi

# Rules verification gate
echo "--- Rules verification ---"
if docker compose run --rm ingestion python scripts/check_rules_verification.py 2>&1; then
  ok "Rules verification gate"
else
  fail "Rules verification gate"
fi

# Unit tests
echo "--- Unit tests ---"
if docker compose run --rm ingestion python -m pytest \
    tests/test_classify.py tests/test_govern.py \
    tests/test_deidentify.py tests/test_deadline.py -q \
    2>&1 | grep -qE "passed"; then
  ok "Core unit tests"
else
  fail "Core unit tests"
fi

# Secret scan
echo "--- Secret scan ---"
FOUND=$(grep -rn "sk-ant-api\|AKIA[A-Z0-9]{16}" \
  --include="*.py" --include="*.js" --include="*.ts" \
  backend/ ingestion/ shared/ client/ 2>/dev/null | grep -v "#" | wc -l)
if [ "$FOUND" -eq 0 ]; then
  ok "Secret scan clean"
else
  fail "Secret scan found $FOUND potential secrets in source"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
