#!/usr/bin/env bash
# prove_case_law_blocker_or_ingestion.sh — Find Case Law is either lawfully ingested
# (licence granted) OR its blocker is recorded with ZERO fake rows. Fail-closed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
ING(){ docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion "$@"; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## FCL module exists + is fail-closed ##########"
out=$(ING python -m ingestion.sources.find_case_law 2>/dev/null | tail -1)
echo "  module output: $out"
g=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
cl=$(Q "SELECT count(*) FROM case_law_documents;")

if [ "${FCL_BULK_LICENCE_GRANTED:-false}" = "true" ] && [ "$g" = "granted" ]; then
  echo "$out" | grep -q "completed" && ok "FCL licence granted — ingestion ran" || bad "FCL granted but ingestion did not run"
else
  echo "$out" | grep -q "blocked" && ok "FCL bulk fail-closed (status=blocked)" || bad "FCL module did not fail closed"
  [ "${cl:-0}" -eq 0 ] && ok "case_law empty (no fake/placeholder rows)" || bad "case_law has $cl rows without licence"
fi

echo "########## blocker recorded in corpus_ingestion_runs ##########"
blk=$(Q "SELECT count(*) FROM corpus_ingestion_runs WHERE source_id='find_case_law' AND status='blocked' AND blocker_reason IS NOT NULL AND blocker_reason<>'';")
[ "${blk:-0}" -ge 1 ] && ok "blocker_reason recorded for find_case_law ($blk run rows)" || bad "no recorded FCL blocker"

echo "########## registry marks FCL application_required / pending ##########"
{ [ "$g" = "pending" ] || [ "$g" = "unknown" ] || [ "$g" = "granted" ]; } && ok "FCL application_status=$g" || bad "unexpected FCL application_status: $g"

[ "$fail" -ne 0 ] && { echo "CASE LAW BLOCKER/INGESTION PROOF: FAIL"; exit 1; }
echo "CASE LAW BLOCKER/INGESTION PROOF: PASS"
