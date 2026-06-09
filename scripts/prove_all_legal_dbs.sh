#!/usr/bin/env bash
# prove_all_legal_dbs.sh — every required legal table/view exists and is populated
# where data is expected. Non-zero on hard failure.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## required tables exist ##########"
for t in legislation case_law_documents acas_guidance official_guidance rules \
         legal_sources legal_jurisdictions legal_taxonomy corpus_chunks \
         corpus_ingestion_runs legal_retrieval_audit legal_assessments \
         deadline_calculation_audit legal_chunk_labels; do
  n=$(Q "SELECT count(*) FROM information_schema.tables WHERE table_name='$t';")
  [ "${n:-0}" -ge 1 ] && ok "table $t" || bad "missing $t"
done
for v in source_freshness corpus_quality_report; do
  n=$(Q "SELECT count(*) FROM information_schema.views WHERE table_name='$v';")
  [ "${n:-0}" -ge 1 ] && ok "view $v" || bad "missing view $v"
done
mv=$(Q "SELECT count(*) FROM pg_matviews WHERE matviewname='mv_current_employment_legal_chunks';")
[ "${mv:-0}" -ge 1 ] && ok "mv_current_employment_legal_chunks" || bad "missing materialized view"

echo "########## populated where data is expected ##########"
for pair in "legislation:1" "acas_guidance:1" "official_guidance:1" "rules:1" \
            "legal_sources:7" "legal_jurisdictions:5" "legal_taxonomy:1" "corpus_chunks:1"; do
  t="${pair%%:*}"; min="${pair##*:}"
  n=$(Q "SELECT count(*) FROM $t;")
  [ "${n:-0}" -ge "$min" ] && ok "$t rows=$n (>= $min)" || bad "$t rows=$n (< $min)"
done

echo "########## case_law expected empty unless FCL granted ##########"
cl=$(Q "SELECT count(*) FROM case_law_documents;")
g=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
{ [ "${cl:-0}" -eq 0 ] || [ "$g" = "granted" ]; } && ok "case_law=$cl, FCL status=$g (consistent)" || bad "case_law populated without FCL grant"

[ "$fail" -ne 0 ] && { echo "ALL LEGAL DBS PROOF: FAIL"; exit 1; }
echo "ALL LEGAL DBS PROOF: PASS"
