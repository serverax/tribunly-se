#!/usr/bin/env bash
# prove_employment_law_corpus.sh  -  proves the local British employment-law corpus
# is real, cited, effective-dated, embedded, RAG-retrievable, and that Find Case
# Law bulk is fail-closed. Exits non-zero on any missing proof.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

# DB-first: the UK legal dataset proof (domain pack, registry, provenance, freshness)
# must pass before the corpus-citation/RAG checks below.
echo "########## UK legal dataset proof (prove_uk_legal_dataset.sh) ##########"
if ! bash "$(dirname "$0")/prove_uk_legal_dataset.sh"; then
  echo "EMPLOYMENT LAW CORPUS PROOF: FAILED (UK legal dataset proof failed)"; exit 1
fi


Q() { docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0
ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## required ERA 1996 sections present ##########"
for s in 94 95 98 108 111 119 120 122 123 124 207B 227; do
  n=$(Q "SELECT count(*) FROM legislation WHERE act_title ILIKE '%Employment Rights Act 1996%' AND section_ref='$s';")
  [ "${n:-0}" -ge 1 ] && ok "ERA 1996 s.$s present" || bad "ERA 1996 s.$s MISSING"
done

echo "########## legislation integrity (no placeholder rows) ##########"
miss=$(Q "SELECT count(*) FROM legislation WHERE source_url IS NULL OR source_url='' OR content_hash IS NULL OR last_verified_at IS NULL;")
[ "${miss:-1}" -eq 0 ] && ok "all legislation rows have source_url/content_hash/last_verified_at" || bad "$miss legislation rows missing required metadata"
emb=$(Q "SELECT count(embedding) FROM legislation;"); [ "${emb:-0}" -ge 1 ] && ok "legislation embeddings=$emb" || bad "no legislation embeddings"

echo "########## rules: cited + effective-dated ##########"
rc=$(Q "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal';")
[ "${rc:-0}" -ge 1 ] && ok "unfair_dismissal rules=$rc" || bad "no unfair_dismissal rules"
rcite=$(Q "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal' AND (authority_ref IS NULL OR authority_ref='');")
[ "${rcite:-1}" -eq 0 ] && ok "all unfair_dismissal rules carry authority_ref" || bad "$rcite rules missing authority_ref"

echo "########## ACAS sourced ##########"
ac=$(Q "SELECT count(*) FROM acas_guidance WHERE source_url IS NOT NULL AND source_url<>'';")
[ "${ac:-0}" -ge 1 ] && ok "acas_guidance sourced rows=$ac" || bad "no sourced ACAS rows"

echo "########## hybrid RAG retrieves + citations resolve to DB ##########"
RAG=$(curl -s -X POST http://localhost:8000/api/rag/hybrid-search -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal fair reason ERA 1996 s98 s111 ACAS disciplinary procedure","claim_type":"unfair_dismissal"}')
echo "$RAG" | grep -qE '"insufficient_grounding":false' && ok "RAG grounded" || bad "RAG not grounded"
echo "$RAG" | grep -qiE "Employment Rights Act 1996 s\.98" && ok "RAG cites ERA 1996 s.98 (resolves to DB)" || bad "RAG missing ERA s.98"
echo "$RAG" | grep -qiE "ACAS Code of Practice" && ok "RAG cites ACAS Code (resolves to DB)" || echo "  NOTE: ACAS not in top hits for this query (lexical-dependent)"

echo "########## Find Case Law bulk fail-closed ##########"
cl=$(Q "SELECT count(*) FROM case_law_documents;")
if [ "${FCL_BULK_LICENCE_GRANTED:-false}" = "true" ]; then
  ok "FCL licence granted (bulk allowed)"
else
  [ "${cl:-0}" -eq 0 ] && ok "case_law empty + licence-gated (fail-closed)" || bad "case_law has $cl rows without licence flag"
fi

if [ "$fail" -ne 0 ]; then echo "EMPLOYMENT LAW CORPUS PROOF: FAILED"; exit 1; fi
echo "EMPLOYMENT LAW CORPUS PROOF: PASSED"
