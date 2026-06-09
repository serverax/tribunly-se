#!/usr/bin/env bash
# lawapp Security Regression Script
# Usage: bash scripts/security-regression.sh
# Returns exit code 1 if any FAIL.
cd "$(git rev-parse --show-toplevel)"
set -uo pipefail

PASS=0; FAIL=0; WARN=0
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"

ok()   { echo "  PASS $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL $1: $2"; FAIL=$((FAIL+1)); }
warn() { echo "  WARN $1: $2"; WARN=$((WARN+1)); }
section() { echo ""; echo "=== $1 ==="; }

# ── Section 1: Secret scan ────────────────────────────────────────────────────
section "1. Secret scan"
TMP=$(mktemp)
grep -R "sk-ant-[A-Za-z0-9]\{20,\}\|sk_live_[A-Za-z0-9]\{20,\}" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude="*.disabled" . 2>/dev/null | grep -v "reports/\|docs/" > "$TMP" || true
COUNT=$(wc -l < "$TMP"); rm -f "$TMP"
[ "$COUNT" -eq 0 ] && ok "No real API keys committed" || fail "Secret scan" "$COUNT matches found"

# ── Section 2: Reserved legal language ───────────────────────────────────────
section "2. Reserved legal language scan"
TMP=$(mktemp)
grep -RInE "we represent you|we will file the claim|rights of audience|conduct litigation for you|we file your ET1" \
  backend client --include="*.py" --include="*.js" --include="*.html" 2>/dev/null \
  | grep -v "prohibited_actions\|BLOCKED\|_PHRASES\|_PATTERNS\|govern\.\|documents\." > "$TMP" || true
COUNT=$(wc -l < "$TMP"); rm -f "$TMP"
[ "$COUNT" -eq 0 ] && ok "No reserved legal language in source" || fail "Reserved language" "$COUNT occurrences"

# ── Section 3: Hardcoded legal values ────────────────────────────────────────
section "3. Hardcoded legal values in frontend"
TMP=$(mktemp)
grep -RIn "time_limit_months.*=.*3\|qualifying.*=.*2 years\|= 123543\|= 751\|= 118223" \
  client/public --include="*.js" --include="*.html" 2>/dev/null > "$TMP" || true
COUNT=$(wc -l < "$TMP"); rm -f "$TMP"
[ "$COUNT" -eq 0 ] && ok "No hardcoded legal values in frontend" || fail "Hardcoded values" "$COUNT found"

# ── Section 4: PII stripping ─────────────────────────────────────────────────
section "4. PII de-identification"
python -c "
from backend.core.deidentify import deidentify
pii = ['name','email','employer','raw_document','date_of_birth']
facts = {f: 'test_value' for f in pii}; facts['edt'] = '2026-01-01'
safe, _ = deidentify(facts)
for f in pii:
    if f in safe and safe[f] is not None:
        print(f'FAIL: {f} not stripped'); exit(1)
print('PASS')
" 2>&1 | grep -E "PASS|FAIL" | head -1 | grep -q PASS && ok "All PII fields stripped" || fail "PII" "Field not stripped"

# ── Section 5: Pipeline order ─────────────────────────────────────────────────
section "5. deidentify runs before model.reason"
python -c "
import inspect
from backend.core import pipeline
src = inspect.getsource(pipeline.assess)
assert 'deidentify' in src
di, mr = src.index('deidentify('), src.index('model.reason')
assert di < mr
print('PASS')
" 2>&1 | grep -q PASS && ok "deidentify before model.reason confirmed" || fail "Pipeline order" "Wrong order"

# ── Section 6: Payment gating ─────────────────────────────────────────────────
section "6. Payment gating"
python -c "
import os; os.environ['PAYMENT_MODE'] = 'test_simulator'
from backend.core.payment import is_paid
assert not is_paid(None), 'None should not be paid'
assert not is_paid('real_token'), 'Non-test token rejected'
assert is_paid('test_abc'), 'test_ token accepted'
print('PASS')
" 2>&1 | grep -q PASS && ok "Payment gating logic correct" || fail "Payment gating" "Logic error"

# ── Section 7: API checks ─────────────────────────────────────────────────────
section "7. Live API security checks"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/health" 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then
  AUTH_MODE=$(curl -s "${BASE}/health" 2>/dev/null | python -c "import sys,json; print(json.load(sys.stdin).get('auth_mode','?'))" 2>/dev/null)
  [ "$AUTH_MODE" = "jwt" ] || [ "$AUTH_MODE" = "mock" ] && ok "Auth mode: $AUTH_MODE" || fail "Auth mode" "Got: $AUTH_MODE"

  # User isolation test
  TS=$(date +%s%3N)
  EMAIL_A="sec_a_${TS}@reg.test"; EMAIL_B="sec_b_${TS}@reg.test"; PWD="Sec123Test!"
  curl -sf -X POST "${BASE}/auth/register" -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL_A\",\"password\":\"$PWD\"}" > /dev/null 2>&1 || true
  TOKEN_A=$(curl -s -X POST "${BASE}/auth/token" -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL_A\",\"password\":\"$PWD\"}" 2>/dev/null \
    | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  if [ -n "$TOKEN_A" ]; then
    CASE_ID=$(curl -s -X POST "${BASE}/cases" -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN_A" \
      -d '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{},"key_dates":{}}' \
      2>/dev/null | python -c "import sys,json; print(json.load(sys.stdin).get('case_id',''))" 2>/dev/null)
    if [ -n "$CASE_ID" ]; then
      curl -sf -X POST "${BASE}/auth/register" -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL_B\",\"password\":\"$PWD\"}" > /dev/null 2>&1 || true
      TOKEN_B=$(curl -s -X POST "${BASE}/auth/token" -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL_B\",\"password\":\"$PWD\"}" 2>/dev/null \
        | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
      ISO=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN_B" "${BASE}/cases/${CASE_ID}" 2>/dev/null)
      [ "$ISO" = "403" ] && ok "User isolation: HTTP 403" || fail "User isolation" "Expected 403, got $ISO"
    else
      warn "User isolation" "Case creation failed"
    fi
  else
    warn "User isolation" "Login failed"
  fi
else
  warn "Live checks" "Backend not running at ${BASE}"
fi

# ── Section 8: Security test suite ───────────────────────────────────────────
section "8. Security test suite"
python -m pytest tests/security/ tests/user_isolation/ -q --tb=line 2>&1 | tail -2 | grep -q "passed" && ok "Security tests pass" || fail "Security tests" "Tests failed"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "lawapp Security Regression: $PASS PASS / $FAIL FAIL / $WARN WARN"
echo "════════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
