#!/usr/bin/env bash
# prove_document_generation.sh — Particulars of Claim + Schedule of Loss generation.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE"
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" -d '{
  "query":"dismissed after 8 months for misconduct without a hearing",
  "facts":{"edt":"2024-05-01","service_start_date":"2023-09-01","reason_for_dismissal":"conduct","was_procedure_followed":false,"had_disciplinary_hearing":false,"weekly_pay":600},
  "jurisdiction":"EW","use_model":false}' > .dg_assess.json

gen(){
  python -c "
import json
a=json.load(open('.dg_assess.json'))
req={'document_type':'$1','assessment':a,'facts':{'edt':'2024-05-01','weekly_pay':600,'gross_annual_salary':31200,'age':35,'service_start_date':'2023-09-01','employer_name':'Acme Logistics Ltd'},'payment_token':'$2'}
open('.dg_doc.json','w').write(json.dumps(req))
"
  curl -s -X POST "$BASE/documents/generate" -H "Content-Type: application/json" --data @.dg_doc.json
}

echo "########## paid generation (real facts, disclaimer, safe) ##########"
for dt in particulars_of_claim schedule_of_loss; do
  gen "$dt" "test_dg" | python -c "
import sys,json
d=json.load(sys.stdin); c=d.get('content') or ''
assert d.get('payment_required') is False
assert d.get('disclaimer_included') is True
assert (d.get('safety_check') or {}).get('passed') is True
assert len(c) > 1000
assert ('self-help' in c.lower()) or ('not a law firm' in c.lower()) or ('not legal advice' in c.lower())
print('$dt len',len(c))
" && ok "$dt: full paid doc, disclaimer + self-help notice, safe" || bad "$dt paid generation failed"
done

echo "########## unpaid -> preview only (not full doc) ##########"
full=$(gen schedule_of_loss "test_dg" | python -c "import sys,json;print(len(json.load(sys.stdin).get('content') or ''))")
prev=$(gen schedule_of_loss "" | python -c "import sys,json;d=json.load(sys.stdin);print(len(d.get('content') or ''));")
preq=$(gen schedule_of_loss "" | python -c "import sys,json;print(json.load(sys.stdin).get('payment_required'))")
[ "$preq" = "True" ] && ok "unpaid request -> payment_required=True" || bad "unpaid not gated"
[ "${prev:-0}" -lt "${full:-0}" ] && ok "preview ($prev) shorter than full ($full)" || bad "preview not truncated"

echo "########## fail-closed on insufficient grounding ##########"
python -c "open('.dg_bad.json','w').write(__import__('json').dumps({'document_type':'particulars_of_claim','assessment':{'status':'not_supported','jurisdiction_supported':False},'facts':{'edt':'2024-05-01'},'payment_token':'test_dg'}))"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/documents/generate" -H "Content-Type: application/json" --data @.dg_bad.json)
[ "$code" = "422" ] && ok "unsupported/ungrounded -> 422 (no document)" || bad "ungrounded doc generated ($code)"

rm -f .dg_assess.json .dg_doc.json .dg_bad.json
[ "$fail" -ne 0 ] && { echo "DOCUMENT GENERATION PROOF: FAIL"; exit 1; }
echo "DOCUMENT GENERATION PROOF: PASS"
