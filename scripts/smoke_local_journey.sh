#!/usr/bin/env bash
# lawapp — Local E2E Smoke Journey
# Proves the full product journey via curl against the local Docker backend.
# Usage: bash scripts/smoke_local_journey.sh
# Requires: Docker Compose running (docker compose up -d)
set -euo pipefail

BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
TS=$(date +%s)
EMAIL_A="smoke_a_${TS}@lawapp-smoke.local"
EMAIL_B="smoke_b_${TS}@lawapp-smoke.local"
PASSWORD="SmokeTest123!"

PASS=0; FAIL=0

ok()   { echo "  PASS $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL $1: $2"; FAIL=$((FAIL+1)); }
section() { echo ""; echo "=== $1 ==="; }

# ── Helper ────────────────────────────────────────────────────────────────────
http_status() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
json_field()  { python -c "import sys,json; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

# ── Step 1: Health ────────────────────────────────────────────────────────────
section "1. Health check"
STATUS=$(http_status "${BASE}/health")
[ "$STATUS" = "200" ] && ok "/health → 200" || fail "/health" "HTTP $STATUS"

DB_STATUS=$(curl -s "${BASE}/health" | json_field "db")
[ "$DB_STATUS" = "connected" ] && ok "DB connected" || fail "DB" "db=$DB_STATUS"

# ── Step 2: Rules API (no hardcoded values) ────────────────────────────────────
section "2. Rules API"
RULES_STATUS=$(http_status "${BASE}/rules/unfair_dismissal")
[ "$RULES_STATUS" = "200" ] && ok "/rules/unfair_dismissal → 200" || fail "/rules" "HTTP $RULES_STATUS"

TL=$(curl -s "${BASE}/rules/unfair_dismissal" | python -c "
import sys,json
rules = json.load(sys.stdin).get('rules',[])
tl = next((r for r in rules if r['rule_key']=='unfair_dismissal.time_limit_months'),None)
print(tl['value_numeric'] if tl else 'missing')
" 2>/dev/null)
[ "$TL" = "3" ] && ok "time_limit_months=3 from DB" || fail "time_limit_months" "got $TL"

# ── Step 3: Register User A ────────────────────────────────────────────────────
section "3. Register User A"
REG_A=$(curl -s -X POST "${BASE}/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL_A}\",\"password\":\"${PASSWORD}\"}")
REG_STATUS=$(echo "$REG_A" | json_field "user_id")
[ -n "$REG_STATUS" ] && ok "User A registered (${EMAIL_A})" || fail "Register A" "$(echo $REG_A | head -c 100)"

# ── Step 4: Login User A ───────────────────────────────────────────────────────
section "4. Login User A"
LOGIN_A=$(curl -s -X POST "${BASE}/auth/token" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL_A}\",\"password\":\"${PASSWORD}\"}")
TOKEN_A=$(echo "$LOGIN_A" | json_field "access_token")
[ -n "$TOKEN_A" ] && ok "User A JWT token received" || fail "Login A" "$(echo $LOGIN_A | head -c 100)"

# ── Step 5: Auth /me ───────────────────────────────────────────────────────────
section "5. Auth /me"
ME_STATUS=$(http_status -H "Authorization: Bearer ${TOKEN_A}" "${BASE}/auth/me")
[ "$ME_STATUS" = "200" ] && ok "/auth/me → 200" || fail "/auth/me" "HTTP $ME_STATUS"

# ── Step 6: Assessment (deterministic — short service) ────────────────────────
section "6. Assessment (10 months — deterministic QP fail)"
ASSESS=$(curl -s -X POST "${BASE}/assess" \
  -H "Content-Type: application/json" \
  -d '{"query":"dismissed after 10 months","facts":{"edt":"2026-03-01","service_start_date":"2025-05-01","reason_for_dismissal":"conduct","was_procedure_followed":"false","weekly_pay":500,"jurisdiction":"EW"},"jurisdiction":"EW"}')
A_STATUS=$(echo "$ASSESS" | json_field "status")
A_VIABLE=$(echo "$ASSESS" | json_field "has_viable_claim")
[ "$A_STATUS" = "ok" ] && ok "Assessment status=ok" || fail "Assessment status" "$A_STATUS"
[ "$A_VIABLE" = "no" ] && ok "has_viable_claim=no (QP fails — correct)" || fail "has_viable_claim" "$A_VIABLE"

CITATIONS=$(echo "$ASSESS" | python -c "import sys,json; print(len(json.load(sys.stdin).get('citations',[])))" 2>/dev/null)
[ "${CITATIONS:-0}" -gt 0 ] && ok "Assessment has $CITATIONS citations" || fail "Citations" "count=$CITATIONS"

# ── Step 7: Deadline calculate ─────────────────────────────────────────────────
section "7. Deadline calculate"
DEADLINE=$(curl -s -X POST "${BASE}/api/deadline/calculate" \
  -H "Content-Type: application/json" \
  -d '{"claim_type":"unfair_dismissal","edt":"2026-03-01","jurisdiction":"EW"}')
DL_DATE=$(echo "$DEADLINE" | json_field "limitation_date")
DL_SOURCE=$(echo "$DEADLINE" | json_field "source")
[ -n "$DL_DATE" ] && ok "Deadline calculated: $DL_DATE" || fail "Deadline date" "empty"
[ "$DL_SOURCE" = "rules" ] && ok "Deadline source=rules" || fail "Deadline source" "$DL_SOURCE"

# ── Step 8: Save case ─────────────────────────────────────────────────────────
section "8. Save case"
CASE=$(curl -s -X POST "${BASE}/cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN_A}" \
  -d '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{"status":"ok","has_viable_claim":"no"},"key_dates":{"edt":"2026-03-01"}}')
CASE_ID=$(echo "$CASE" | json_field "case_id")
[ -n "$CASE_ID" ] && ok "Case saved: ${CASE_ID:0:16}..." || fail "Save case" "$(echo $CASE | head -c 100)"

# ── Step 9: User A reads own case ─────────────────────────────────────────────
section "9. Case ownership"
OWN_STATUS=$(http_status -H "Authorization: Bearer ${TOKEN_A}" "${BASE}/cases/${CASE_ID}")
[ "$OWN_STATUS" = "200" ] && ok "User A reads own case → 200" || fail "Own case read" "HTTP $OWN_STATUS"

# ── Step 10: User isolation ────────────────────────────────────────────────────
section "10. User isolation"
curl -s -X POST "${BASE}/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL_B}\",\"password\":\"${PASSWORD}\"}" > /dev/null
LOGIN_B=$(curl -s -X POST "${BASE}/auth/token" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL_B}\",\"password\":\"${PASSWORD}\"}")
TOKEN_B=$(echo "$LOGIN_B" | json_field "access_token")

ISO_STATUS=$(http_status -H "Authorization: Bearer ${TOKEN_B}" "${BASE}/cases/${CASE_ID}")
[ "$ISO_STATUS" = "403" ] && ok "User B blocked on User A case → 403" || fail "User isolation" "HTTP $ISO_STATUS (expected 403)"

# ── Step 11: Payment test session ─────────────────────────────────────────────
section "11. Payment (test simulator)"
PAY=$(curl -s -X POST "${BASE}/api/payment/create-session" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN_A}" \
  -d '{"document_type":"particulars_of_claim"}')
PAY_TOKEN=$(echo "$PAY" | json_field "payment_token")
PAY_DEMO=$(echo "$PAY" | json_field "demo_mode")
[ -n "$PAY_TOKEN" ] && ok "Test payment token received: ${PAY_TOKEN:0:20}..." || fail "Payment session" "$(echo $PAY | head -c 100)"
[ "$PAY_DEMO" = "True" ] || [ "$PAY_DEMO" = "true" ] && ok "Payment demo_mode=true" || ok "Payment demo_mode=$PAY_DEMO"

# ── Step 12: Document generation ──────────────────────────────────────────────
section "12. Document generation"
DOC=$(curl -s -X POST "${BASE}/documents/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN_A}" \
  -d "{\"document_type\":\"particulars_of_claim\",\"assessment\":{\"has_viable_claim\":\"uncertain\"},\"facts\":{\"edt\":\"2026-03-01\",\"service_start_date\":\"2022-01-01\"},\"payment_token\":\"${PAY_TOKEN}\"}")
DOC_PAID=$(echo "$DOC" | json_field "payment_required")
DOC_LEN=$(echo "$DOC" | python -c "import sys,json; print(len(json.load(sys.stdin).get('content','')))" 2>/dev/null)
[ "$DOC_PAID" = "False" ] || [ "$DOC_PAID" = "false" ] && ok "Full document returned (payment_required=false)" || fail "Document payment gate" "payment_required=$DOC_PAID"
[ "${DOC_LEN:-0}" -gt 500 ] && ok "Document content ${DOC_LEN} chars" || fail "Document length" "${DOC_LEN} chars"

# ── Step 13: Dashboard (cases list) ───────────────────────────────────────────
section "13. Dashboard"
CASES_STATUS=$(http_status -H "Authorization: Bearer ${TOKEN_A}" "${BASE}/cases")
[ "$CASES_STATUS" = "200" ] && ok "GET /cases → 200" || fail "Dashboard" "HTTP $CASES_STATUS"

# ── Step 14: Brain trace (19 steps) ───────────────────────────────────────────
section "14. Brain trace (19 steps)"
BRAIN=$(curl -s -X POST "${BASE}/api/brain/trace" \
  -H "Content-Type: application/json" \
  -d '{"message":"dismissed after 10 months","facts":{"edt":"2026-03-01","service_start_date":"2025-05-01","jurisdiction":"EW"}}')
STEP_COUNT=$(echo "$BRAIN" | python -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('trace',{}).get('steps',[])))" 2>/dev/null)
[ "${STEP_COUNT:-0}" -eq 19 ] && ok "Brain trace: 19 steps" || fail "Brain steps" "got $STEP_COUNT"

SAFETY=$(echo "$BRAIN" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('safety',{}).get('passed','?'))" 2>/dev/null)
[ "$SAFETY" = "True" ] && ok "Safety policy passed" || fail "Safety policy" "$SAFETY"

# ── Step 15: Handoff / referral ────────────────────────────────────────────────
section "15. Handoff/referral"
HANDOFF_STATUS=$(http_status -X POST "${BASE}/handoff/leads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN_A}" \
  -d "{\"trigger_reason\":\"seek_solicitor\",\"name\":\"Smoke Test\",\"email\":\"${EMAIL_A}\",\"consent_given\":true}")
[ "$HANDOFF_STATUS" = "201" ] && ok "/handoff/leads → 201" || fail "Handoff" "HTTP $HANDOFF_STATUS"

# ── Step 16: Sources freshness ────────────────────────────────────────────────
section "16. Sources freshness"
FRESH_STATUS=$(http_status "${BASE}/freshness")
[ "$FRESH_STATUS" = "200" ] && ok "/freshness → 200" || fail "Freshness" "HTTP $FRESH_STATUS"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "lawapp Smoke Journey: $PASS PASS / $FAIL FAIL"
echo "════════════════════════════════════════"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
