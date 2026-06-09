#!/usr/bin/env bash
# prove_legal_data_spine.sh — proves the legal data spine schema exists and is wired.
# DB target printed with password redacted. Real SQL only. Non-zero on hard failure.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (docker compose service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## required tables ##########"
for t in legal_jurisdictions legal_sources corpus_ingestion_runs legislation case_law_documents acas_guidance official_guidance rules legal_taxonomy legal_chunk_labels corpus_chunks legal_retrieval_audit legal_assessments deadline_calculation_audit users cases documents referrals; do
  n=$(Q "SELECT count(*) FROM information_schema.tables WHERE table_name='$t' AND table_schema='public';")
  [ "${n:-0}" -ge 1 ] && ok "table $t" || bad "missing table $t"
done

echo "########## required views ##########"
for v in source_freshness corpus_quality_report; do
  n=$(Q "SELECT count(*) FROM information_schema.views WHERE table_name='$v';")
  [ "${n:-0}" -ge 1 ] && ok "view $v" || bad "missing view $v"
done
mv=$(Q "SELECT count(*) FROM pg_matviews WHERE matviewname='mv_current_employment_legal_chunks';")
[ "${mv:-0}" -ge 1 ] && ok "materialized view mv_current_employment_legal_chunks" || bad "missing mv_current_employment_legal_chunks"

echo "########## required extensions ##########"
for e in vector pgcrypto pg_trgm; do
  n=$(Q "SELECT count(*) FROM pg_extension WHERE extname='$e';")
  [ "${n:-0}" -ge 1 ] && ok "extension $e" || bad "missing extension $e"
done

echo "########## vector + key indexes ##########"
vi=$(Q "SELECT count(*) FROM pg_indexes WHERE (indexname LIKE '%emb_hnsw' OR indexname LIKE '%emb_ivf' OR indexname LIKE '%embedding_idx');")
[ "${vi:-0}" -ge 1 ] && ok "vector indexes present=$vi" || bad "no vector index"
fts=$(Q "SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%_fts_idx';")
[ "${fts:-0}" -ge 3 ] && ok "full-text indexes=$fts" || bad "full-text indexes missing ($fts)"
trg=$(Q "SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%_trgm';")
[ "${trg:-0}" -ge 5 ] && ok "trigram indexes=$trg" || bad "trigram indexes missing ($trg)"

echo "########## required GB unfair dismissal rule keys ##########"
for k in time_limit_months early_conciliation_required qualifying_period compensatory_cap_amount compensatory_cap_weeks_pay weeks_pay_cap_amount basic_award_formula basic_award_min_automatic acas_code_adjustment_percent not_reasonably_practicable_extension; do
  n=$(Q "SELECT count(*) FROM rules WHERE rule_key='unfair_dismissal.$k' AND jurisdiction_code='GB';")
  [ "${n:-0}" -ge 1 ] && ok "rule unfair_dismissal.$k (GB)" || bad "missing GB rule unfair_dismissal.$k"
done

echo "########## views execute ##########"
sf=$(Q "SELECT count(*) FROM source_freshness;"); [ "${sf:-0}" -ge 1 ] && ok "source_freshness returns $sf rows" || bad "source_freshness empty/broken"
cq=$(Q "SELECT count(*) FROM corpus_quality_report;"); [ "${cq:-0}" -ge 1 ] && ok "corpus_quality_report returns $cq rows" || bad "corpus_quality_report broken"

[ "$fail" -ne 0 ] && { echo "LEGAL DATA SPINE PROOF: FAIL"; exit 1; }
echo "LEGAL DATA SPINE PROOF: PASS"
