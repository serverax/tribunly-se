#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ALLOW_PARTIAL_PROOF="${ALLOW_PARTIAL_PROOF:-false}"
REPORT="${REPORT:-reports/proof_full_workflows.txt}"
mkdir -p "$(dirname "$REPORT")"
: > "$REPORT"

log() {
  printf '%s\n' "$*" | tee -a "$REPORT"
}

fail() {
  log "FAIL: $*"
  exit 1
}

json_post() {
  local path="$1"
  local body="$2"
  local code
  code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "$BASE_URL$path" \
    --data "$body" || true)"
  cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
  printf '\n' >> "$REPORT"
  printf '%s' "$code"
}

json_field() {
  local file="$1"
  local field="$2"
  local py_bin=""
  for candidate in python3 python python.exe py; do
    if command -v "$candidate" >/dev/null 2>&1; then
      py_bin="$candidate"
      break
    fi
  done
  [[ -n "$py_bin" ]] || fail "No Python interpreter available for JSON response parsing"
  "$py_bin" - "$file" "$field" <<'PY'
import json
import sys

path, field = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)
value = data
for part in field.split("."):
    value = value.get(part, "") if isinstance(value, dict) else ""
print(value if value is not None else "")
PY
}

auth_header() {
  local token="$1"
  printf 'Authorization: Bearer %s' "$token"
}

log "LAWAPP FULL WORKFLOW PROOF"
log "Base URL: $BASE_URL"

code="$(curl -sS -o /tmp/lawapp-home.html -w '%{http_code}' "$BASE_URL/" || true)"
[[ "$code" == "200" ]] || fail "Landing page did not open; HTTP $code"
log "PASS: landing page opens"

code="$(curl -sS -o /tmp/lawapp-health.json -w '%{http_code}' "$BASE_URL/health" || true)"
[[ "$code" == "200" ]] || fail "Health endpoint failed; HTTP $code"
log "PASS: health endpoint reachable"

ASSESS_BODY='{
  "query": "I was dismissed for alleged misconduct after five years with no hearing",
  "jurisdiction": "EW",
  "use_model": false,
  "facts": {
    "claim_type": "unfair_dismissal",
    "edt": "2026-05-01",
    "service_start_date": "2020-01-01",
    "reason_for_dismissal": "conduct",
    "was_procedure_followed": false,
    "weekly_pay": 600,
    "acas_not_started": true
  }
}'
code="$(json_post "/assess" "$ASSESS_BODY")"
[[ "$code" == "200" ]] || fail "Assessment failed; HTTP $code"
grep -E '"status"[[:space:]]*:[[:space:]]*"ok"|"status"[[:space:]]*:[[:space:]]*"insufficient_grounding"' "$REPORT" >/dev/null \
  || fail "Assessment did not return a governed status"
grep -E '"deadline_info"|"deadline"' "$REPORT" >/dev/null \
  || fail "Assessment did not include deadline evidence"
log "PASS: assessment endpoint returns governed response with deadline field"

WRONGFUL_BODY='{
  "claim_type": "wrongful_dismissal",
  "jurisdiction": "EW",
  "facts": {
    "termination_date": "2026-05-01",
    "employment_start_date": "2020-01-01",
    "weekly_pay": 600,
    "notice_given_weeks": 1
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$WRONGFUL_BODY")"
[[ "$code" == "200" ]] || fail "Wrongful dismissal diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"wrongful_dismissal"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Wrongful dismissal diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Wrongful dismissal diagnosis did not include retrieval proof"
grep '"ERA 1996 s.86"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Wrongful dismissal diagnosis did not include statutory notice citation"
log "PASS: wrongful dismissal workflow diagnosis is DB-grounded"

REDUNDANCY_BODY='{
  "claim_type": "redundancy",
  "jurisdiction": "EW",
  "facts": {
    "dismissal_date": "2026-05-01",
    "employment_start_date": "2020-01-01",
    "age": 45,
    "weekly_pay": 900
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$REDUNDANCY_BODY")"
[[ "$code" == "200" ]] || fail "Redundancy diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"redundancy"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Redundancy diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Redundancy diagnosis did not include retrieval proof"
grep '"ERA 1996 s.162"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Redundancy diagnosis did not include statutory calculation citation"
log "PASS: redundancy workflow diagnosis is DB-grounded"

WORKING_TIME_BODY='{
  "claim_type": "working_time",
  "jurisdiction": "EW",
  "facts": {
    "average_weekly_hours": 55,
    "daily_rest_hours": 8,
    "weekly_rest_hours": 20,
    "shift_hours": 8,
    "rest_break_minutes": 10
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$WORKING_TIME_BODY")"
[[ "$code" == "200" ]] || fail "Working time diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"working_time"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Working time diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Working time diagnosis did not include retrieval proof"
grep '"Working Time Regulations 1998 reg.4"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Working time diagnosis did not include working-time citation"
log "PASS: working time workflow diagnosis is DB-grounded"

HOLIDAY_PAY_BODY='{
  "claim_type": "holiday_pay",
  "jurisdiction": "EW",
  "facts": {
    "annual_leave_taken_weeks": 3,
    "employment_ended": true,
    "weekly_pay": 500
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$HOLIDAY_PAY_BODY")"
[[ "$code" == "200" ]] || fail "Holiday pay diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"holiday_pay"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Holiday pay diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Holiday pay diagnosis did not include retrieval proof"
grep '"Working Time Regulations 1998 reg.13"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Holiday pay diagnosis did not include annual-leave citation"
log "PASS: holiday pay workflow diagnosis is DB-grounded"

FLEXIBLE_BODY='{
  "claim_type": "flexible_working",
  "jurisdiction": "EW",
  "facts": {
    "requests_last_12_months": 1,
    "request_date": "2026-01-10",
    "decision_date": "2026-04-20",
    "refused": true,
    "consulted_before_refusal": false
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$FLEXIBLE_BODY")"
[[ "$code" == "200" ]] || fail "Flexible working diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"flexible_working"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Flexible working diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Flexible working diagnosis did not include retrieval proof"
grep '"ERA 1996 s.80G"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Flexible working diagnosis did not include procedure citation"
log "PASS: flexible working workflow diagnosis is DB-grounded"

CONTRACT_BODY='{
  "claim_type": "employment_contracts",
  "jurisdiction": "EW",
  "facts": {
    "received_written_statement": false
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$CONTRACT_BODY")"
[[ "$code" == "200" ]] || fail "Employment contracts diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"employment_contracts"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Employment contracts diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Employment contracts diagnosis did not include retrieval proof"
grep '"ERA 1996 s.1"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Employment contracts diagnosis did not include written-particulars citation"
log "PASS: employment contracts workflow diagnosis is DB-grounded"

FIXED_TERM_BODY='{
  "claim_type": "fixed_term_workers",
  "jurisdiction": "EW",
  "facts": {
    "successive_fixed_term_contract_years": 4,
    "less_favourable_treatment": true,
    "objective_justification_given": false
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$FIXED_TERM_BODY")"
[[ "$code" == "200" ]] || fail "Fixed-term worker diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"fixed_term_workers"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Fixed-term worker diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Fixed-term worker diagnosis did not include retrieval proof"
grep '"Fixed-term Employees Regulations 2002 reg.8"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Fixed-term worker diagnosis did not include successive-contract citation"
log "PASS: fixed-term worker workflow diagnosis is DB-grounded"

PART_TIME_BODY='{
  "claim_type": "part_time_workers",
  "jurisdiction": "EW",
  "facts": {
    "less_favourable_treatment": true,
    "comparable_full_time_worker": true,
    "objective_justification_given": false
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$PART_TIME_BODY")"
[[ "$code" == "200" ]] || fail "Part-time worker diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"part_time_workers"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Part-time worker diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Part-time worker diagnosis did not include retrieval proof"
grep '"Part-time Workers Regulations 2000 reg.5"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Part-time worker diagnosis did not include less-favourable-treatment citation"
log "PASS: part-time worker workflow diagnosis is DB-grounded"

AGENCY_BODY='{
  "claim_type": "agency_workers",
  "jurisdiction": "EW",
  "facts": {
    "weeks_on_assignment": 13,
    "less_favourable_basic_conditions": true
  }
}'
code="$(json_post "/api/workflow/diagnosis" "$AGENCY_BODY")"
[[ "$code" == "200" ]] || fail "Agency worker diagnosis failed; HTTP $code"
grep '"claim_type"[[:space:]]*:[[:space:]]*"agency_workers"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Agency worker diagnosis did not return expected claim type"
grep '"retrieval_proof"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Agency worker diagnosis did not include retrieval proof"
grep '"Agency Workers Regulations 2010 reg.7"' /tmp/lawapp-proof-response.json >/dev/null \
  || fail "Agency worker diagnosis did not include qualifying-period citation"
log "PASS: agency worker workflow diagnosis is DB-grounded"

OOS_BODY='{"query":"Can my landlord evict me?","jurisdiction":"EW","use_model":false,"facts":{}}'
code="$(json_post "/assess" "$OOS_BODY")"
[[ "$code" == "200" ]] || fail "Out-of-scope assessment failed; HTTP $code"
grep '"not_supported"' "$REPORT" >/dev/null || fail "Out-of-scope query was not rejected"
log "PASS: out-of-scope query rejected"

anon_code="$(curl -sS -o /tmp/lawapp-anon-doc.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/documents/generate" \
  --data '{"case_id":"00000000-0000-0000-0000-000000000000","document_type":"particulars_of_claim","confirmed_facts":{}}' || true)"
[[ "$anon_code" == "401" || "$anon_code" == "403" ]] || fail "Anonymous document generation was not blocked; HTTP $anon_code"
log "PASS: anonymous document generation blocked"

anon_case_code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/cases" \
  --data '{"claim_type":"unfair_dismissal","jurisdiction":"EW","assessment":{},"key_dates":{},"facts":{}}' || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$anon_case_code" == "401" || "$anon_case_code" == "403" ]] || fail "Anonymous case creation was not blocked; HTTP $anon_case_code"
log "PASS: anonymous case creation blocked"

suffix="$(date +%s)-$RANDOM"
email_a="qa-a-$suffix@example.invalid"
email_b="qa-b-$suffix@example.invalid"
password="Str0ngPass!23"

code="$(json_post "/api/auth/register" "{\"email\":\"$email_a\",\"password\":\"$password\",\"display_name\":\"QA User A\"}")"
[[ "$code" == "201" ]] || fail "User A registration failed; HTTP $code"
token_a="$(json_field /tmp/lawapp-proof-response.json access_token)"
[[ -n "$token_a" ]] || fail "User A registration did not return access_token"
log "PASS: User A registers and receives access token"

code="$(json_post "/api/auth/login" "{\"email\":\"$email_a\",\"password\":\"$password\"}")"
[[ "$code" == "200" ]] || fail "User A login failed; HTTP $code"
token_a="$(json_field /tmp/lawapp-proof-response.json access_token)"
[[ -n "$token_a" ]] || fail "User A login did not return access_token"
log "PASS: User A logs in"

code="$(json_post "/api/auth/register" "{\"email\":\"$email_b\",\"password\":\"$password\",\"display_name\":\"QA User B\"}")"
[[ "$code" == "201" ]] || fail "User B registration failed; HTTP $code"
token_b="$(json_field /tmp/lawapp-proof-response.json access_token)"
[[ -n "$token_b" ]] || fail "User B registration did not return access_token"
log "PASS: User B registers"

SAVE_BODY='{
  "claim_type": "unfair_dismissal",
  "jurisdiction": "EW",
  "assessment": {
    "status": "ok",
    "has_viable_claim": "uncertain",
    "strength": "medium",
    "citations": [{"cite": "ERA 1996 s.111(2)", "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/111"}]
  },
  "key_dates": {"edt": "2026-05-01", "deadline_date": "2026-07-31"},
  "recommended_next_step": "prepare_documents",
  "facts": {"reason_for_dismissal": "conduct", "weekly_pay": 600}
}'
code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "$(auth_header "$token_a")" \
  -X POST "$BASE_URL/cases" \
  --data "$SAVE_BODY" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "201" ]] || fail "User A could not save case; HTTP $code"
case_a="$(json_field /tmp/lawapp-proof-response.json case_id)"
[[ -n "$case_a" ]] || fail "Save case response did not return case_id"
log "PASS: User A saves case"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H "$(auth_header "$token_a")" "$BASE_URL/cases" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "200" ]] || fail "User A dashboard case list failed; HTTP $code"
grep "$case_a" /tmp/lawapp-proof-response.json >/dev/null || fail "User A dashboard did not include saved case"
log "PASS: User A returns to dashboard and sees saved case"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H "$(auth_header "$token_b")" "$BASE_URL/cases/$case_a" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "403" ]] || fail "User B could access User A case; HTTP $code"
log "PASS: User B cannot access User A case"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' "$BASE_URL/cases/$case_a" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "401" ]] || fail "Anonymous user could access case; HTTP $code"
log "PASS: anonymous user receives 401 for case access"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "$(auth_header "$token_a")" \
  -X POST "$BASE_URL/api/documents/generate" \
  --data "{\"case_id\":\"$case_a\",\"document_type\":\"particulars\",\"confirmed_facts\":{}}" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "402" ]] || fail "Unpaid user was not blocked from full document generation; HTTP $code"
log "PASS: unpaid user cannot generate full documents"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "$(auth_header "$token_a")" \
  -X POST "$BASE_URL/api/payments/create-session" \
  --data "{\"case_id\":\"$case_a\",\"package_id\":\"full_documents\"}" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "200" ]] || fail "Payment checkout session could not be created; HTTP $code"
session_id="$(json_field /tmp/lawapp-proof-response.json session_id)"
[[ -n "$session_id" ]] || fail "Payment session response did not include session_id"
log "PASS: payment checkout session created"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/payment/webhook" \
  --data '{}' || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" != "200" ]] || fail "Unsigned/invalid payment webhook was accepted"
log "PASS: invalid payment cannot unlock documents"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' "$BASE_URL/admin/compliance-status" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "403" ]] || fail "Admin compliance page was not protected; HTTP $code"
log "PASS: admin/reporting pages are protected without admin key"

code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "$(auth_header "$token_a")" \
  -X POST "$BASE_URL/api/payments/confirm-test" \
  --data "{\"session_id\":\"$session_id\"}" || true)"
cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
printf '\n' >> "$REPORT"
[[ "$code" == "200" ]] || fail "Test payment confirmation failed; HTTP $code"
grep '"payment_status"[[:space:]]*:[[:space:]]*"paid"' "$REPORT" >/dev/null || fail "Payment confirmation did not mark case paid"
log "PASS: test payment confirmation marked case paid"

for doc_type in particulars schedule_of_loss; do
  code="$(curl -sS -o /tmp/lawapp-proof-response.json -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -H "$(auth_header "$token_a")" \
    -X POST "$BASE_URL/api/documents/generate" \
    --data "{\"case_id\":\"$case_a\",\"document_type\":\"$doc_type\",\"confirmed_facts\":{\"claimant_name\":\"QA Claimant\",\"employer_name\":\"QA Employer\",\"dismissal_date\":\"2026-05-01\"}}" || true)"
  cat /tmp/lawapp-proof-response.json >> "$REPORT" || true
  printf '\n' >> "$REPORT"
  [[ "$code" == "200" ]] || fail "Paid document generation failed for $doc_type; HTTP $code"
  grep '"status"[[:space:]]*:[[:space:]]*"generated"' /tmp/lawapp-proof-response.json >/dev/null || fail "Document $doc_type was not generated"
  document_id="$(json_field /tmp/lawapp-proof-response.json document_id)"
  [[ -n "$document_id" ]] || fail "Document $doc_type response did not include document_id"
  code="$(curl -sS -o "/tmp/lawapp-$doc_type.html" -w '%{http_code}' \
    -H "$(auth_header "$token_a")" \
    "$BASE_URL/api/documents/$document_id" || true)"
  cat "/tmp/lawapp-$doc_type.html" >> "$REPORT" || true
  printf '\n' >> "$REPORT"
  [[ "$code" == "200" ]] || fail "Paid document download failed for $doc_type; HTTP $code"
  grep -Ei 'self-help|not legal advice|not a law firm|not a substitute' "/tmp/lawapp-$doc_type.html" >/dev/null \
    || fail "Downloaded $doc_type document did not include legal boundary notice"
  log "PASS: paid user can generate $doc_type"
done

log "PASS: generated documents include legal boundary notice evidence"

if [[ "$ALLOW_PARTIAL_PROOF" == "true" ]]; then
  log "PARTIAL: early workflow smoke passed, but full workflow proof is incomplete."
  exit 0
fi

log "PASS: full workflow proof completed"
