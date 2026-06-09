#!/usr/bin/env bash
# prove_corpus_quality.sh — data-science quality gates over the legal corpus.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## rows missing source_url by table ##########"
for t in legislation acas_guidance official_guidance corpus_chunks; do
  n=$(Q "SELECT count(*) FROM $t WHERE source_url IS NULL OR source_url='';")
  [ "${n:-1}" -eq 0 ] && ok "$t: 0 missing source_url" || bad "$t: $n rows missing source_url"
done
rurl=$(Q "SELECT count(*) FROM rules WHERE authority_url IS NULL OR authority_url='';")
[ "${rurl:-1}" -eq 0 ] && ok "rules: 0 missing authority_url" || bad "rules: $rurl missing authority_url"

echo "########## rows missing jurisdiction_code ##########"
for t in legislation acas_guidance official_guidance corpus_chunks rules; do
  n=$(Q "SELECT count(*) FROM $t WHERE jurisdiction_code IS NULL;")
  [ "${n:-1}" -eq 0 ] && ok "$t: 0 missing jurisdiction_code" || bad "$t: $n missing jurisdiction_code"
done

echo "########## chunks missing chunk_hash / embeddings ##########"
ch=$(Q "SELECT count(*) FROM corpus_chunks WHERE chunk_hash IS NULL OR chunk_hash='';")
[ "${ch:-1}" -eq 0 ] && ok "corpus_chunks: 0 missing chunk_hash" || bad "corpus_chunks: $ch missing chunk_hash"
emb_missing=$(Q "SELECT count(*) FROM corpus_chunks WHERE embedding IS NULL;")
echo "  REPORT: corpus_chunks missing embeddings = ${emb_missing:-?} (of $(Q "SELECT count(*) FROM corpus_chunks;"))"
[ "${emb_missing:-1}" -eq 0 ] && ok "all corpus_chunks embedded" || bad "$emb_missing chunks missing embedding"

echo "########## duplicate chunk_hash (idempotency) ##########"
dup=$(Q "SELECT count(*)-count(DISTINCT chunk_hash) FROM corpus_chunks;")
[ "${dup:-1}" -eq 0 ] && ok "no duplicate chunk_hash" || bad "$dup duplicate chunk_hash"

echo "########## unknown-licence active rows ##########"
unk=$(Q "SELECT count(*) FROM corpus_chunks WHERE licence_status IS NOT NULL AND licence_status NOT IN ('open','GRANTED','granted');")
[ "${unk:-0}" -eq 0 ] && ok "no active chunks with unknown/blocked licence" || bad "$unk chunks with non-open licence"

echo "########## stale rows (>120d) ##########"
stale=$(Q "SELECT coalesce(sum(stale_rows_count),0) FROM source_freshness;")
echo "  REPORT: stale rows across sources = ${stale:-?}"
[ "${stale:-1}" -eq 0 ] && ok "no stale rows" || bad "$stale stale rows (>120d)"

echo "########## required sources present in legal_sources ##########"
for s in legislation_gov_uk find_case_law acas govuk_et_decisions govuk_eat_decisions parliament_bills govuk_courts_tribunals_publishing; do
  n=$(Q "SELECT count(*) FROM legal_sources WHERE source_id='$s';")
  [ "${n:-0}" -ge 1 ] && ok "legal_sources has $s" || bad "legal_sources missing $s"
done

echo "########## Find Case Law not bulk-ingested without grant ##########"
fcl_app=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
cl=$(Q "SELECT count(*) FROM case_law_documents;")
if [ "$fcl_app" = "granted" ]; then ok "FCL application granted"; else
  [ "${cl:-0}" -eq 0 ] && ok "FCL not granted ($fcl_app) AND case_law empty (no illegal bulk)" || bad "case_law populated without FCL grant"
fi

echo "########## corpus_quality_report grouped output ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT source_type, jurisdiction_code, total_chunks, chunks_with_embedding, chunks_without_source_url, avg_quality_score, duplicate_hash_count FROM corpus_quality_report ORDER BY source_type;" 2>&1 | head -12

[ "$fail" -ne 0 ] && { echo "CORPUS QUALITY PROOF: FAIL"; exit 1; }
echo "CORPUS QUALITY PROOF: PASS"
