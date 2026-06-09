#!/usr/bin/env bash
# prove_deadline_tracker.sh — deadlines come from rules; ACAS EC reflected; edge cases.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE"
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

asgb(){
  curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" \
    -d "{\"query\":\"unfair dismissal time limit\",\"facts\":$1,\"jurisdiction\":\"EW\",\"use_model\":false}"
}
dl(){ python -c "import sys,json;d=json.load(sys.stdin);print((d.get('deadline_info') or {}).get('limitation_date',''),(d.get('deadline_info') or {}).get('source',''))"; }
stt(){ python -c "import sys,json;print(json.load(sys.stdin).get('status',''))"; }

echo "########## no EC: deadline = EDT + 3 months - 1 day, from rules ##########"
r=$(asgb '{"edt":"2024-05-01","service_start_date":"2019-01-01","reason_for_dismissal":"conduct","was_procedure_followed":false}')
d=$(echo "$r" | dl); echo "  $d"
echo "$d" | grep -q "2024-07-31 rules" && ok "no-EC deadline 2024-07-31 from rules" || bad "no-EC deadline wrong: $d"

echo "########## EC applied: stop-the-clock reflected (deadline differs from base) ##########"
r=$(asgb '{"edt":"2024-05-01","service_start_date":"2019-01-01","reason_for_dismissal":"conduct","was_procedure_followed":false,"ec_day_a":"2024-06-01","ec_day_b":"2024-06-20"}')
d=$(echo "$r" | dl); echo "  $d"
echo "$d" | grep -q "rules" && ok "EC deadline from rules ($d)" || bad "EC deadline not from rules"
echo "$d" | grep -qv "2024-07-31" && ok "EC stop-the-clock shifted the deadline (!= base 2024-07-31)" || bad "EC not reflected"

echo "########## EC floor bites: 1 month after Day B when later than adjusted ##########"
r=$(asgb '{"edt":"2024-05-01","service_start_date":"2019-01-01","reason_for_dismissal":"conduct","was_procedure_followed":false,"ec_day_a":"2024-07-25","ec_day_b":"2024-07-29"}')
d=$(echo "$r" | dl); echo "  $d"
echo "$d" | grep -q "2024-08-29 rules" && ok "EC floor bites -> 2024-08-29 (1 month after Day B)" || bad "EC floor did not bite as expected: $d"

echo "########## missing date fails closed ##########"
s=$(asgb '{"service_start_date":"2019-01-01"}' | stt)
[ "$s" = "missing_edt" ] && ok "missing EDT -> missing_edt" || bad "missing EDT not handled ($s)"

echo "########## invalid date fails closed ##########"
s=$(asgb '{"edt":"not-a-date"}' | stt)
echo "$s" | grep -qi "invalid" && ok "invalid date -> $s" || bad "invalid date not handled ($s)"

echo "########## deterministic deadline unit tests (no EC / floor / no-floor) ##########"
docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion pytest tests/test_deadline.py -q 2>&1 | tail -2

[ "$fail" -ne 0 ] && { echo "DEADLINE TRACKER PROOF: FAIL"; exit 1; }
echo "DEADLINE TRACKER PROOF: PASS"
