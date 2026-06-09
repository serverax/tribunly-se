#!/usr/bin/env bash
# prove_ingestion_runs.sh — ingestion is tracked, auditable, fail-closed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## corpus_ingestion_runs has tracking columns ##########"
for c in run_kind status records_inserted records_failed blocker_reason ingestion_mode; do
  n=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='corpus_ingestion_runs' AND column_name='$c';")
  [ "${n:-0}" -ge 1 ] && ok "column $c" || bad "missing column $c"
done

echo "########## ingestion runs exist + per-source checkpoints ##########"
runs=$(Q "SELECT count(*) FROM corpus_ingestion_runs;")
[ "${runs:-0}" -ge 1 ] && ok "corpus_ingestion_runs rows=$runs" || bad "no ingestion runs tracked"
srcs=$(Q "SELECT count(DISTINCT source_id) FROM corpus_ingestion_runs WHERE run_kind NOT IN ('full');")
[ "${srcs:-0}" -ge 3 ] && ok "per-source ingestion checkpoints=$srcs" || bad "insufficient per-source checkpoints ($srcs)"

echo "########## partial runs must carry blocker_reason ##########"
badpartial=$(Q "SELECT count(*) FROM corpus_ingestion_runs WHERE status IN ('partial','blocked') AND (blocker_reason IS NULL OR blocker_reason='');")
[ "${badpartial:-0}" -eq 0 ] && ok "all partial/blocked runs carry blocker_reason" || bad "$badpartial partial/blocked runs without blocker_reason"

echo "########## Find Case Law bulk not started without grant ##########"
fcl_app=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
clruns=$(Q "SELECT count(*) FROM corpus_ingestion_runs WHERE source_id='find_case_law' AND status IN ('completed','running') AND COALESCE(records_inserted,0)>0;")
if [ "$fcl_app" = "granted" ]; then ok "FCL granted"; else
  [ "${clruns:-0}" -eq 0 ] && ok "no FCL bulk ingestion run with rows (grant=$fcl_app)" || bad "FCL bulk ingestion ran without grant"
fi

echo "########## recent checkpoints ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT source_id, run_kind, status, rows_ingested, COALESCE(records_failed,0) failed FROM corpus_ingestion_runs ORDER BY created_at DESC LIMIT 8;" 2>&1 | head -12

[ "$fail" -ne 0 ] && { echo "INGESTION RUNS PROOF: FAIL"; exit 1; }
echo "INGESTION RUNS PROOF: PASS"
