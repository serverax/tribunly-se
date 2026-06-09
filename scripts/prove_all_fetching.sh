#!/usr/bin/env bash
# prove_all_fetching.sh — every required source was fetched (or its blocker recorded).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## legislation.gov.uk — required Acts/sections fetched ##########"
for s in 94 95 97 98 108 111 119 120 122 123 124 207B 227; do
  n=$(Q "SELECT count(*) FROM legislation WHERE act_title ILIKE '%Employment Rights Act 1996%' AND section_ref='$s';")
  [ "${n:-0}" -ge 1 ] && ok "ERA 1996 s.$s" || bad "ERA 1996 s.$s missing"
done
eta=$(Q "SELECT count(*) FROM legislation WHERE act_title ILIKE '%Employment Tribunals Act 1996%' AND section_ref='18A';")
[ "${eta:-0}" -ge 1 ] && ok "ETA 1996 s.18A" || bad "ETA 1996 s.18A missing"
tu=$(Q "SELECT count(*) FROM legislation WHERE act_title ILIKE '%Trade Union%' AND section_ref='207A';")
[ "${tu:-0}" -ge 1 ] && ok "TULRCA 1992 s.207A" || bad "TULRCA s.207A missing"

echo "########## UKSI Increase of Limits Orders fetched ##########"
uksi=$(Q "SELECT count(*) FROM legislation WHERE leg_type='uksi';")
[ "${uksi:-0}" -ge 3 ] && ok "UKSI Increase of Limits source rows=$uksi" || bad "UKSI orders missing ($uksi)"

echo "########## ACAS + GOV.UK fetched ##########"
ac=$(Q "SELECT count(DISTINCT doc_title) FROM acas_guidance;")
[ "${ac:-0}" -ge 5 ] && ok "ACAS distinct docs=$ac" || bad "ACAS breadth low ($ac)"
gv=$(Q "SELECT count(DISTINCT title) FROM official_guidance;")
[ "${gv:-0}" -ge 10 ] && ok "GOV.UK distinct docs=$gv" || bad "GOV.UK breadth low ($gv)"

echo "########## per-source fetch checkpoints recorded ##########"
ck=$(Q "SELECT count(DISTINCT source_id) FROM corpus_ingestion_runs;")
[ "${ck:-0}" -ge 3 ] && ok "ingestion checkpoints for $ck sources" || bad "insufficient ingestion checkpoints ($ck)"

echo "########## Find Case Law — blocker recorded, not faked ##########"
g=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
cl=$(Q "SELECT count(*) FROM case_law_documents;")
if [ "$g" = "granted" ]; then ok "FCL granted"; else
  [ "${cl:-0}" -eq 0 ] && ok "FCL blocked ($g), case_law empty (no fake fetch)" || bad "case_law fetched without grant"
fi

[ "$fail" -ne 0 ] && { echo "ALL FETCHING PROOF: FAIL"; exit 1; }
echo "ALL FETCHING PROOF: PASS"
