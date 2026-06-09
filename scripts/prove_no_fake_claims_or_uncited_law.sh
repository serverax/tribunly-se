#!/usr/bin/env bash
# prove_no_fake_claims_or_uncited_law.sh — honest diagnosis: no fake encouragement,
# no uncited legal assertion, weak cases shown plainly.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## no promotional 'win/guarantee' wording in pages ##########"
HITS=$(grep -rinE "win your case|we guarantee|guaranteed (win|outcome|success)|you will win|sure to win" client/public/pages/ | grep -vinE "not guarantee|no .*guarantee|does not|outcome is guaranteed|not guaranteed" || true)
[ -z "$HITS" ] && ok "no fake-encouragement wording" || { bad "promotional wording:"; echo "$HITS" | sed 's/^/      /'; }

echo "########## weak / no-claim case shown honestly with weaknesses ##########"
WEAK=$(curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" -d '{"query":"dismissed after 8 months for misconduct","facts":{"edt":"2024-05-01","service_start_date":"2023-09-01","reason_for_dismissal":"conduct","was_procedure_followed":true},"jurisdiction":"EW","use_model":false}')
echo "$WEAK" | python -c "
import sys,json
d=json.load(sys.stdin)
assert d.get('has_viable_claim') in ('no','uncertain'), d.get('has_viable_claim')
assert d.get('key_weaknesses'), 'weaknesses must be shown'
print('VIABLE',d.get('has_viable_claim'),'WEAKNESSES',len(d.get('key_weaknesses') or []))
" && ok "weak case shown plainly with key_weaknesses (no fake encouragement)" || bad "weak case not shown honestly"

echo "########## every asserted conclusion is cited ##########"
echo "$WEAK" | python -c "
import sys,json
d=json.load(sys.stdin)
if d.get('has_viable_claim') in ('yes','no'):
    assert d.get('citations'), 'asserted conclusion must carry citations'
print('OK')
" && ok "asserted conclusions are cited (no uncited legal assertion)" || bad "uncited legal assertion"

echo "########## citations resolve to real DB rows ##########"
CITED=$(echo "$WEAK" | python -c "import sys,json;d=json.load(sys.stdin);print('|'.join(c.get('url','') for c in (d.get('citations') or [])))")
res=0
for u in $(echo "$CITED" | tr '|' ' '); do
  case "$u" in
    *legislation.gov.uk*) sec=$(echo "$u" | grep -oE "section/[0-9A-Z]+" | grep -oE "[0-9A-Z]+$");
      [ -n "$sec" ] && n=$(Q "SELECT count(*) FROM legislation WHERE section_ref='$sec';") && [ "${n:-0}" -ge 1 ] && res=$((res+1));;
    *acas.org.uk*) n=$(Q "SELECT count(*) FROM acas_guidance WHERE source_url ILIKE '%acas.org.uk%';"); [ "${n:-0}" -ge 1 ] && res=$((res+1));;
  esac
done
[ "$res" -ge 1 ] && ok "at least one citation resolves to a real DB row ($res)" || bad "no citation resolves to DB"

echo "########## DB has no fake/uncited legal data ##########"
bash scripts/prove_no_fake_legal_data.sh >/dev/null 2>&1 && ok "prove_no_fake_legal_data.sh passes" || bad "fake/uncited legal data present"

[ "$fail" -ne 0 ] && { echo "NO FAKE CLAIMS / UNCITED LAW PROOF: FAIL"; exit 1; }
echo "NO FAKE CLAIMS / UNCITED LAW PROOF: PASS"
