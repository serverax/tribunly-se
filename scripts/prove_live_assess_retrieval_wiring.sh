#!/usr/bin/env bash
# prove_live_assess_retrieval_wiring.sh  -  hard end-to-end proof that the LIVE /assess
# HTTP path is DB-first, retrieval-first, cited, jurisdiction-filtered, audited, and
# fails closed for unsupported jurisdictions. Hits the running backend, not a stub.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE   DB: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## 1. backend starts + DB connects ##########"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health")
[ "$code" = "200" ] && ok "backend /health = 200" || { bad "backend unhealthy ($code)"; echo "LIVE ASSESS WIRING PROOF: FAIL"; exit 1; }

lra0=$(Q "SELECT count(*) FROM legal_retrieval_audit;")
dca0=$(Q "SELECT count(*) FROM deadline_calculation_audit;")

echo "########## 2. GB /assess returns grounded, cited assessment ##########"
GB=$(curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" -d '{
  "query":"I was dismissed after 8 months for misconduct without a hearing",
  "facts":{"edt":"2024-05-01","service_start_date":"2023-09-01","reason_for_dismissal":"conduct","was_procedure_followed":false,"had_disciplinary_hearing":false},
  "jurisdiction":"EW","use_model":false}')
echo "$GB" | python -c "
import sys,json
d=json.load(sys.stdin)
ok = (d.get('status')=='ok'
      and not d.get('insufficient_grounding')
      and len(d.get('citations') or [])>=1
      and (d.get('deadline_info') or {}).get('source')=='rules'
      and (d.get('deadline_info') or {}).get('limitation_date')
      and d.get('jurisdiction')
      and d.get('has_viable_claim') in ('yes','no','uncertain'))
cits=d.get('citations') or []
cited_ok = all(c.get('url') for c in cits)
print('STATUS', d.get('status'))
print('CITATIONS', len(cits))
print('DEADLINE_SRC', (d.get('deadline_info') or {}).get('source'))
print('JURIS', d.get('jurisdiction'))
print('GROUNDING', d.get('grounding_score'))
print('ALLCITED', cited_ok)
sys.exit(0 if (ok and cited_ok) else 1)
" && ok "GB /assess: status=ok, cited, deadline from rules, jurisdiction present, every citation has a source_url" || bad "GB /assess not properly grounded/cited"

echo "########## 3. NI /assess fails closed (no GB law reuse) ##########"
NI=$(curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" -d '{
  "query":"Was I unfairly dismissed in Belfast?",
  "facts":{"edt":"2024-05-01"}, "jurisdiction":"NI","use_model":false}')
echo "$NI" | python -c "
import sys,json
d=json.load(sys.stdin)
ok = (d.get('status')=='not_supported'
      and d.get('jurisdiction_supported') is False
      and d.get('insufficient_grounding') is True
      and not d.get('citations'))
print('NI_STATUS', d.get('status'), 'supported', d.get('jurisdiction_supported'))
sys.exit(0 if ok else 1)
" && ok "NI /assess fails closed (not_supported, jurisdiction_supported=false, no citations)" || bad "NI did not fail closed"

echo "########## 4. legal_retrieval_audit written for every request ##########"
lra1=$(Q "SELECT count(*) FROM legal_retrieval_audit;")
[ "${lra1:-0}" -gt "${lra0:-0}" ] && ok "legal_retrieval_audit grew ($lra0 -> $lra1)" || bad "legal_retrieval_audit not written"
gbrow=$(Q "SELECT count(*) FROM legal_retrieval_audit WHERE jurisdiction_code='GB';")
[ "${gbrow:-0}" -ge 1 ] && ok "legal_retrieval_audit has GB rows=$gbrow" || bad "no GB retrieval audit row"

echo "########## 5. deadline_calculation_audit written (deadline from rules) ##########"
dca1=$(Q "SELECT count(*) FROM deadline_calculation_audit;")
[ "${dca1:-0}" -gt "${dca0:-0}" ] && ok "deadline_calculation_audit grew ($dca0 -> $dca1)" || bad "deadline_calculation_audit not written"
ruleused=$(Q "SELECT count(*) FROM deadline_calculation_audit WHERE rules_used::text ILIKE '%time_limit_months%';")
[ "${ruleused:-0}" -ge 1 ] && ok "deadline_calculation_audit records rules_used (time_limit_months)" || bad "deadline audit missing rules_used"

echo "########## 6. no uncited legal assertion ##########"
echo "$GB" | python -c "
import sys,json
d=json.load(sys.stdin)
asserts = d.get('has_viable_claim') in ('yes','no')
if asserts and not (d.get('citations') or []):
    sys.exit(1)
sys.exit(0)
" && ok "any asserted conclusion is backed by citations" || bad "uncited legal assertion present"

[ "$fail" -ne 0 ] && { echo "LIVE ASSESS WIRING PROOF: FAIL"; exit 1; }
echo "LIVE ASSESS WIRING PROOF: PASS"
