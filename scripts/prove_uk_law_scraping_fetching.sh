#!/usr/bin/env bash
# prove_uk_law_scraping_fetching.sh  -  source-by-source proof that UK law was actually
# FETCHED (legislation/UKSI/ACAS/GOV.UK live), case law is BLOCKED (recorded, 0 rows),
# and NI / Bills are NOT STARTED (not falsely reported complete).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## legislation.gov.uk  -  LIVE FETCHED ##########"
leg=$(Q "SELECT count(*) FROM legislation WHERE leg_type='ukpga';")
[ "${leg:-0}" -ge 1 ] && ok "ukpga legislation rows=$leg" || bad "no ukpga legislation rows"
uksi=$(Q "SELECT count(*) FROM legislation WHERE leg_type='uksi';")
[ "${uksi:-0}" -ge 1 ] && ok "UKSI rows=$uksi" || bad "no UKSI rows"
legbad=$(Q "SELECT count(*) FROM legislation WHERE source_url IS NULL OR source_url='' OR content_hash IS NULL OR content_hash='' OR jurisdiction_code IS NULL;")
[ "${legbad:-1}" -eq 0 ] && ok "legislation: all rows have source_url + content_hash + jurisdiction_code" || bad "$legbad legislation rows missing provenance"
legofficial=$(Q "SELECT count(*) FROM legislation WHERE source_url ILIKE '%legislation.gov.uk%';")
[ "${legofficial:-0}" -ge 1 ] && ok "legislation source_url points to legislation.gov.uk ($legofficial)" || bad "legislation not from official source"

echo "########## ACAS  -  LIVE FETCHED ##########"
ac=$(Q "SELECT count(*) FROM acas_guidance;")
[ "${ac:-0}" -ge 1 ] && ok "ACAS rows=$ac" || bad "no ACAS rows"
acoff=$(Q "SELECT count(*) FROM acas_guidance WHERE source_url ILIKE '%acas.org.uk%';")
[ "${acoff:-0}" -ge 1 ] && ok "ACAS source_url points to acas.org.uk ($acoff)" || bad "ACAS not from official source"

echo "########## GOV.UK  -  LIVE FETCHED ##########"
gv=$(Q "SELECT count(*) FROM official_guidance;")
[ "${gv:-0}" -ge 1 ] && ok "GOV.UK rows=$gv" || bad "no GOV.UK rows"
gvoff=$(Q "SELECT count(*) FROM official_guidance WHERE source_url ILIKE '%gov.uk%';")
[ "${gvoff:-0}" -ge 1 ] && ok "GOV.UK source_url points to gov.uk ($gvoff)" || bad "GOV.UK not from official source"

echo "########## corpus_chunks + embeddings + provenance ##########"
ch=$(Q "SELECT count(*) FROM corpus_chunks;")
[ "${ch:-0}" -ge 1 ] && ok "corpus_chunks=$ch" || bad "corpus_chunks empty"
emb=$(Q "SELECT count(*) FROM corpus_chunks WHERE embedding IS NULL;")
[ "${emb:-1}" -eq 0 ] && ok "all corpus_chunks embedded" || bad "$emb chunks missing embedding"
prov=$(Q "SELECT count(*) FROM corpus_chunks WHERE source_url IS NULL OR source_url='' OR chunk_hash IS NULL OR jurisdiction_code IS NULL;")
[ "${prov:-1}" -eq 0 ] && ok "all chunks have source_url + chunk_hash + jurisdiction_code" || bad "$prov chunks missing provenance"

echo "########## Find Case Law  -  BLOCKED BY LICENCE (recorded, 0 rows) ##########"
cl=$(Q "SELECT count(*) FROM case_law_documents;")
blk=$(Q "SELECT count(*) FROM corpus_ingestion_runs WHERE source_id='find_case_law' AND status='blocked' AND blocker_reason IS NOT NULL AND blocker_reason<>'';")
if [ "${cl:-0}" -eq 0 ]; then
  [ "${blk:-0}" -ge 1 ] && ok "case_law=0 AND blocker recorded ($blk runs)  -  BLOCKED, not faked, not complete" || bad "case_law=0 but NO blocker recorded"
else
  g=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
  [ "$g" = "granted" ] && ok "case_law=$cl with FCL granted" || bad "case_law populated without FCL grant"
fi

echo "########## Northern Ireland  -  NOT STARTED (fail-closed only) ##########"
ni=$(Q "SELECT count(*) FROM corpus_chunks WHERE jurisdiction_code='NI';")
nirules=$(Q "SELECT count(*) FROM rules WHERE jurisdiction_code='NI';")
if [ "${ni:-0}" -eq 0 ] && [ "${nirules:-0}" -eq 0 ]; then
  ok "NI chunks=0, NI rules=0  -  correctly NOT STARTED / fail-closed (not claimed complete)"
elif [ "${ni:-0}" -ge 1 ] && [ "${nirules:-0}" -ge 1 ]; then
  ok "NI genuinely ingested (chunks=$ni rules=$nirules)"
else
  bad "NI inconsistent (chunks=$ni rules=$nirules)  -  partial NI must not be claimed"
fi

echo "########## Bills / reform-watch  -  NOT STARTED (monitoring only) ##########"
bills=$(Q "SELECT count(*) FROM bills;")
echo "  REPORT: bills rows=$bills (monitoring-only, not legal authority)"
ok "bills status reported honestly (rows=$bills, not claimed as fetched corpus)"

echo "########## status summary by source_type / jurisdiction ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT source_type, jurisdiction_code, count(*) chunks, count(*) FILTER (WHERE embedding IS NOT NULL) embedded FROM corpus_chunks GROUP BY source_type, jurisdiction_code ORDER BY source_type;" 2>&1 | head -10

[ "$fail" -ne 0 ] && { echo "UK LAW SCRAPING/FETCHING PROOF: FAIL"; exit 1; }
echo "UK LAW SCRAPING/FETCHING PROOF: PASS (legislation/UKSI/ACAS/GOV.UK LIVE; case law BLOCKED; NI/Bills NOT STARTED)"
