#!/usr/bin/env bash
# prove_assess_provider_integration.sh  -  proves the Workflow C provider plug is
# wired into /assess and gated by the 4 AIA validators, in mock/no-key mode.
# Exits non-zero on any failure. No key, no network to the provider.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
docker compose exec -T db psql -U lawapp -d lawapp -c "ALTER USER lawapp PASSWORD 'lawapp';" >/dev/null 2>&1
fail=0

echo "########## unit: provider stage + 4 AIA gates (weak-RAG / fail-closed / de-id / reject) ##########"
docker compose run --rm -e POSTGRES_PASSWORD=lawapp ingestion python -m pytest -q \
  tests/test_assess_provider_integration.py || fail=1

echo "########## live /assess carries provider_stage (ENABLED unset -> safe, not accepted) ##########"
R=$(curl -s -X POST http://localhost:8000/assess -H "Content-Type: application/json" \
  -d '{"query":"I was dismissed for performance after 6 years with no appeal","facts":{"edt":"2026-05-10","service_start_date":"2020-01-01","reason_for_dismissal":"performance","weekly_pay":700,"jurisdiction":"EW"},"use_model":false}')
echo "$R" | python -c "
import sys,json
d=json.load(sys.stdin)
ps=d.get('provider_stage')
assert ps is not None, 'provider_stage missing from /assess'
print('provider_stage:', json.dumps(ps)[:160])
assert ps.get('status')!='accepted', 'provider must not be accepted without enabled+keyed provider'
print('PASS: provider_stage present and fail-closed (status=%s)'%ps.get('status'))
" || fail=1

if [ "$fail" -ne 0 ]; then echo "ASSESS PROVIDER INTEGRATION: FAILED"; exit 1; fi
echo "ASSESS PROVIDER INTEGRATION: PASSED"
