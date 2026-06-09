#!/usr/bin/env bash
# prove_all_chunking_embeddings.sh — all fetched legal text is chunked, hashed, embedded.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## corpus_chunks: every chunk hashed + sourced + jurisdiction-coded ##########"
tot=$(Q "SELECT count(*) FROM corpus_chunks;")
[ "${tot:-0}" -ge 1 ] && ok "corpus_chunks total=$tot" || bad "corpus_chunks empty"
nohash=$(Q "SELECT count(*) FROM corpus_chunks WHERE chunk_hash IS NULL OR chunk_hash='';")
[ "${nohash:-1}" -eq 0 ] && ok "0 chunks missing chunk_hash" || bad "$nohash chunks missing chunk_hash"
nourl=$(Q "SELECT count(*) FROM corpus_chunks WHERE source_url IS NULL OR source_url='';")
[ "${nourl:-1}" -eq 0 ] && ok "0 chunks missing source_url" || bad "$nourl chunks missing source_url"
nojur=$(Q "SELECT count(*) FROM corpus_chunks WHERE jurisdiction_code IS NULL;")
[ "${nojur:-1}" -eq 0 ] && ok "0 chunks missing jurisdiction_code" || bad "$nojur chunks missing jurisdiction_code"

echo "########## embeddings: coverage reported, none missing ##########"
miss=$(Q "SELECT count(*) FROM corpus_chunks WHERE embedding IS NULL;")
echo "  REPORT: corpus_chunks missing embeddings = ${miss:-?} / $tot"
[ "${miss:-1}" -eq 0 ] && ok "all corpus_chunks embedded" || bad "$miss chunks missing embedding"
legmiss=$(Q "SELECT count(*) FROM legislation WHERE embedding IS NULL;")
echo "  REPORT: legislation missing embeddings = ${legmiss:-?}"
[ "${legmiss:-1}" -eq 0 ] && ok "all legislation embedded" || bad "$legmiss legislation rows missing embedding"
model=$(Q "SELECT count(DISTINCT embedding_model) FROM corpus_chunks WHERE embedding_model IS NOT NULL;")
[ "${model:-0}" -ge 1 ] && ok "embedding_model recorded on chunks" || bad "embedding_model not recorded"

echo "########## chunk linkage back to source + no duplicate hash ##########"
nolink=$(Q "SELECT count(*) FROM corpus_chunks WHERE source_row_uuid IS NULL AND source_row_id IS NULL;")
[ "${nolink:-1}" -eq 0 ] && ok "every chunk links back to a source row" || bad "$nolink chunks not linked to source"
dup=$(Q "SELECT count(*)-count(DISTINCT chunk_hash) FROM corpus_chunks;")
[ "${dup:-1}" -eq 0 ] && ok "no duplicate chunk_hash (idempotent)" || bad "$dup duplicate chunk_hash"

[ "$fail" -ne 0 ] && { echo "ALL CHUNKING/EMBEDDINGS PROOF: FAIL"; exit 1; }
echo "ALL CHUNKING/EMBEDDINGS PROOF: PASS"
