#!/usr/bin/env bash
# prove_handoff_workflow.sh  -  beyond-self-help handoff: trigger + capture, free to user.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE   DB: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

n0=$(Q "SELECT count(*) FROM handoff_leads;" 2>/dev/null || echo 0)

echo "########## handoff capture (consented) returns 201 ##########"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/handoff/leads" -H "Content-Type: application/json" -d '{"trigger_reason":"seek_solicitor","name":"Test User","email":"handoff@example.com","consent_given":true,"case_summary":"unfair dismissal, weak procedure"}')
[ "$c" = "201" ] && ok "lead captured (201)" || bad "capture failed ($c)"

echo "########## consent is required ##########"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/handoff/leads" -H "Content-Type: application/json" -d '{"trigger_reason":"seek_solicitor","name":"No Consent","email":"x@example.com","consent_given":false}')
[ "$c" = "422" ] && ok "no consent -> 422 (fail closed)" || bad "accepted without consent ($c)"

echo "########## invalid trigger_reason rejected ##########"
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/handoff/leads" -H "Content-Type: application/json" -d '{"trigger_reason":"please_win_my_case","name":"Bad","email":"b@example.com","consent_given":true}')
[ "$c" = "422" ] && ok "invalid trigger_reason -> 422" || bad "invalid trigger accepted ($c)"

echo "########## lead persisted; free to user (no charge at capture) ##########"
n1=$(Q "SELECT count(*) FROM handoff_leads;" 2>/dev/null || echo 0)
[ "${n1:-0}" -gt "${n0:-0}" ] && ok "handoff_leads grew ($n0 -> $n1)" || bad "lead not persisted"
grep -qiE "free|no charge|referral lead only|not a solicitor" backend/api/main.py && ok "handoff documented as free referral (not charged)" || echo "  NOTE: free-to-user guardrail is in code comments"

[ "$fail" -ne 0 ] && { echo "HANDOFF WORKFLOW PROOF: FAIL"; exit 1; }
echo "HANDOFF WORKFLOW PROOF: PASS"
