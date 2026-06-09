#!/usr/bin/env bash
# Docker proof — brings up all services and curls key endpoints.
# WSL-safe: uses docker compose, no local venv.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "======================================================================"
echo "LAWAPP — DOCKER PROOF"
echo "======================================================================"

# Ensure services are up
docker compose up -d
sleep 3

BASE="http://localhost:8000"
FAIL=0

check() {
  local label="$1"
  local expected="$2"
  local actual
  actual=$(curl -s -o /dev/null -w "%{http_code}" "$3")
  if [ "$actual" = "$expected" ]; then
    echo "  OK  $label → HTTP $actual"
  else
    echo "  FAIL  $label → expected $expected, got $actual"
    FAIL=1
  fi
}

check "GET /"                    "200" "$BASE/"
check "GET /health"              "200" "$BASE/health"
check "GET /rules/unfair_dismissal" "200" "$BASE/rules/unfair_dismissal"
check "GET /rules/unpaid_wages"  "200" "$BASE/rules/unpaid_wages"
check "GET /admin (no key)"      "403" "$BASE/admin/dp-report"
check "GET /pages/intake.html"   "200" "$BASE/pages/intake.html"
check "GET /pages/assessment"    "200" "$BASE/pages/assessment.html"
check "GET /pages/saved_case"    "200" "$BASE/pages/saved_case.html"

echo
if [ $FAIL -eq 0 ]; then
  echo "✓ DOCKER PROOF: ALL CHECKS PASSED"
else
  echo "✗ DOCKER PROOF: SOME CHECKS FAILED"
fi
echo "======================================================================"
exit $FAIL
