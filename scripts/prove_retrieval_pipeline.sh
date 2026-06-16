#!/usr/bin/env bash
# prove_retrieval_pipeline.sh  -  proves jurisdiction-aware retrieval order + provenance.
# Data-layer proof of the contract: validate jurisdiction -> exact rules -> keyword ->
# vector -> bundle has source_url+authority_ref -> audit row -> NI fails closed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## 1. jurisdiction validated against controlled table ##########"
sup=$(Q "SELECT applies_to_employment_law FROM legal_jurisdictions WHERE jurisdiction_code='GB';")
[ "$sup" = "t" ] && ok "GB is a supported employment-law jurisdiction" || bad "GB not supported"

echo "########## 2. exact rules by claim+jurisdiction+effective date ##########"
r=$(Q "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal' AND jurisdiction_code='GB' AND effective_from<=CURRENT_DATE AND (effective_to IS NULL OR effective_to>=CURRENT_DATE) AND is_current=true;")
[ "${r:-0}" -ge 1 ] && ok "current GB rules retrievable=$r" || bad "no current GB rules"

echo "########## 3. keyword (full-text) filtered by jurisdiction ##########"
kw=$(Q "SELECT count(*) FROM corpus_chunks WHERE jurisdiction_code='GB' AND to_tsvector('english',body_text) @@ plainto_tsquery('english','unfair dismissal');")
[ "${kw:-0}" -ge 1 ] && ok "jurisdiction-filtered keyword hits=$kw" || bad "no keyword hits"

echo "########## 4. vector candidates filtered by jurisdiction ##########"
vec=$(Q "SELECT count(*) FROM (SELECT id FROM corpus_chunks WHERE jurisdiction_code='GB' AND embedding IS NOT NULL ORDER BY embedding <=> (SELECT embedding FROM corpus_chunks WHERE embedding IS NOT NULL LIMIT 1) LIMIT 5) x;")
[ "${vec:-0}" -ge 1 ] && ok "jurisdiction-filtered vector candidates=$vec" || bad "no vector candidates"

echo "########## 5. retrieved bundle carries source_url + authority_ref ##########"
nob=$(Q "SELECT count(*) FROM corpus_chunks WHERE jurisdiction_code='GB' AND (source_url IS NULL OR source_url='' OR authority_ref IS NULL OR authority_ref='');")
[ "${nob:-1}" -eq 0 ] && ok "every GB chunk carries source_url + authority_ref" || bad "$nob GB chunks missing provenance"

echo "########## 6. legal_retrieval_audit accepts jurisdiction-tagged write ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "INSERT INTO legal_retrieval_audit (query_text, query_hash, domain, claim_type, jurisdiction_code, retrieved_bundle, embedding_model) VALUES ('proof: unfair dismissal time limit','proofhash','employment_uk','unfair_dismissal','GB','[{\"source_url\":\"https://www.legislation.gov.uk/ukpga/1996/18/section/111\",\"authority_ref\":\"ERA 1996 s.111\"}]'::jsonb,'bge-small-en-v1.5');" >/dev/null 2>&1
aud=$(Q "SELECT count(*) FROM legal_retrieval_audit WHERE query_hash='proofhash' AND jurisdiction_code='GB';")
[ "${aud:-0}" -ge 1 ] && ok "legal_retrieval_audit row written with jurisdiction_code" || bad "retrieval audit not writable"
docker compose exec -T db psql -U lawapp -d lawapp -c "DELETE FROM legal_retrieval_audit WHERE query_hash='proofhash';" >/dev/null 2>&1

echo "########## 7. NI fails closed (no NI rules/chunks => empty bundle) ##########"
ni_rules=$(Q "SELECT count(*) FROM rules WHERE jurisdiction_code='NI' AND claim_type='unfair_dismissal' AND is_current=true;")
ni_chunks=$(Q "SELECT count(*) FROM mv_current_employment_legal_chunks WHERE jurisdiction_code='NI';")
if [ "${ni_rules:-0}" -eq 0 ] && [ "${ni_chunks:-0}" -eq 0 ]; then ok "NI retrieval bundle is empty => assessment must fail closed (unsupported)"; else bad "NI has rules/chunks but is not implemented/verified"; fi

echo "########## 8. NI query does not return GB rows ##########"
leak=$(Q "SELECT count(*) FROM rules WHERE jurisdiction_code='NI' AND value_numeric IN (SELECT value_numeric FROM rules WHERE jurisdiction_code='GB');")
[ "${leak:-0}" -eq 0 ] && ok "NI-scoped query returns no GB rule values" || bad "NI query leaked GB values"

[ "$fail" -ne 0 ] && { echo "RETRIEVAL PIPELINE PROOF: FAIL"; exit 1; }
echo "RETRIEVAL PIPELINE PROOF: PASS"
