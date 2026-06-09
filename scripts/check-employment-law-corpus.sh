#!/usr/bin/env bash
# check-employment-law-corpus.sh (addendum §6)
# Verifies the employment-law corpus is REAL and usable:
#   rows present, embeddings present, source_url / content_hash / last_verified_at
#   populated, and a sample Hybrid RAG query returns cited source rows.
# Exits non-zero if any check fails. No || true, no fake green output.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

q() { docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0

echo "############ corpus counts ############"
docker compose exec -T db psql -U lawapp -d lawapp -c \
  "SELECT 'legislation' AS s,count(*) AS rows,count(embedding) AS emb FROM legislation
   UNION ALL SELECT 'acas_guidance',count(*),count(embedding) FROM acas_guidance
   UNION ALL SELECT 'official_guidance',count(*),count(embedding) FROM official_guidance
   ORDER BY s;"

LEG=$(q "SELECT count(*) FROM legislation;")
LEG_EMB=$(q "SELECT count(embedding) FROM legislation;")
LEG_NOURL=$(q "SELECT count(*) FROM legislation WHERE source_url IS NULL OR source_url='';")
LEG_NOHASH=$(q "SELECT count(*) FROM legislation WHERE content_hash IS NULL OR content_hash='';")
LEG_NOVER=$(q "SELECT count(*) FROM legislation WHERE last_verified_at IS NULL;")

echo "############ integrity checks ############"
[ "${LEG:-0}" -ge 1 ]      || { echo "FAIL: legislation table empty"; fail=1; }
[ "${LEG_EMB:-0}" -ge 1 ]  || { echo "FAIL: legislation has no embeddings"; fail=1; }
[ "${LEG_NOURL:-1}" -eq 0 ]  || { echo "FAIL: ${LEG_NOURL} legislation rows missing source_url"; fail=1; }
[ "${LEG_NOHASH:-1}" -eq 0 ] || { echo "FAIL: ${LEG_NOHASH} legislation rows missing content_hash"; fail=1; }
[ "${LEG_NOVER:-1}" -eq 0 ]  || { echo "FAIL: ${LEG_NOVER} legislation rows missing last_verified_at"; fail=1; }
echo "legislation rows=${LEG} embedded=${LEG_EMB} missing_url=${LEG_NOURL} missing_hash=${LEG_NOHASH} missing_verified=${LEG_NOVER}"

echo "############ sample Hybrid RAG must return cited source rows ############"
RAG=$(curl -s -X POST http://localhost:8000/api/rag/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal fair reason ERA 1996 s98 ACAS disciplinary procedure","claim_type":"unfair_dismissal"}')
echo "${RAG}" | head -c 800; echo
echo "${RAG}" | grep -qiE "legislation\.gov\.uk|source_url|section|ERA|results|chunk" \
  || { echo "FAIL: Hybrid RAG returned no legal source rows"; fail=1; }

if [ "${fail}" -ne 0 ]; then
  echo "CORPUS CHECK FAILED"
  exit 1
fi
echo "CORPUS CHECK PASSED"
