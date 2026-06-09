#!/usr/bin/env bash
# prove_uk_legal_dataset.sh — DB-FIRST proof for the UK employment legal dataset.
#
# Principle: LEGAL DB FIRST -> CORPUS FIRST -> RULES FIRST -> CITATIONS FIRST.
# Proves, and exits non-zero on ANY gap:
#   1. domain pack present (domains/employment_uk/ + all required manifests)
#   2. legal_sources registry populated from the pack
#   3. every legislation section declared in sources.yaml is present + cited + dated
#   4. required deterministic rules are cited + effective-dated
#   5. legislation embeddings exist; corpus is fresh (last_verified_at not stale)
#   6. hybrid RAG retrieves and citations resolve to real DB rows
#   7. Find Case Law bulk is fail-closed (case_law empty unless licence flag set)
#   8. no fake/placeholder/uncited rows
# Records the outcome in corpus_ingestion_runs.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DOMAIN="${LAWAPP_DOMAIN:-employment_uk}"
FRESH_DAYS="${CORPUS_FRESH_DAYS:-120}"


Q() { docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
ING() { docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion "$@"; }
fail=0
ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## 1. domain pack present (source list NOT only in code) ##########"
PACK=$(ING python -c "
from ingestion.domain_loader import check_pack
import json,sys
c=check_pack('$DOMAIN'); print(json.dumps(c)); sys.exit(0 if c['ok'] else 1)
" 2>/dev/null | tail -1)
echo "$PACK" | grep -q '"ok": true' && ok "domain pack + all manifests present" || bad "domain pack incomplete: $PACK"

echo "########## 2. legal_sources registry populated ##########"
ING python -c "from backend.core.agents.corpus_ingestion_aia import register_legal_sources; print(register_legal_sources('$DOMAIN'))" >/dev/null 2>&1
ls=$(Q "SELECT count(*) FROM legal_sources WHERE domain='$DOMAIN';")
[ "${ls:-0}" -ge 3 ] && ok "legal_sources registry rows=$ls" || bad "legal_sources registry empty/low ($ls)"

echo "########## 3+4. authoritative dataset gate (sections + rules cited/dated) ##########"
DS=$(ING python -c "
from backend.core.agents.corpus_ingestion_aia import validate_dataset
r=validate_dataset('$DOMAIN')
print('PASSED' if r['passed'] else 'FAILED')
[print('   -',f) for f in r['failures']]
" 2>/dev/null)
echo "$DS" | grep -q '^PASSED' && ok "dataset gate: every declared section + rule present, cited, dated" || { bad "dataset gate failed:"; echo "$DS" | sed 's/^/    /'; }

echo "########## 4b. every legal row fully provenanced ##########"
for t in legislation acas_guidance official_guidance; do
  mp=$(Q "SELECT count(*) FROM $t WHERE country_code IS NULL OR domain IS NULL OR source_type IS NULL OR licence_status IS NULL OR parser_type IS NULL OR source_url IS NULL OR source_url='' OR content_hash IS NULL OR content_hash='' OR last_verified_at IS NULL;")
  [ "${mp:-1}" -eq 0 ] && ok "$t: all rows have country_code/domain/source_type/licence_status/parser_type/source_url/content_hash/last_verified_at" || bad "$t: $mp rows missing provenance"
done

echo "########## 4c. ACAS + GOV.UK guidance present + cited ##########"
ac=$(Q "SELECT count(*) FROM acas_guidance WHERE source_url IS NOT NULL AND source_url<>'';")
[ "${ac:-0}" -ge 1 ] && ok "ACAS guidance sourced rows=$ac" || bad "no sourced ACAS guidance"
gv=$(Q "SELECT count(*) FROM official_guidance WHERE source_url IS NOT NULL AND source_url<>'';")
[ "${gv:-0}" -ge 1 ] && ok "GOV.UK guidance sourced rows=$gv" || bad "no sourced GOV.UK guidance"

echo "########## 4d. rules carry full field set (key/claim/juris/authority/url/date/value) ##########"
rbad=$(Q "SELECT count(*) FROM rules WHERE rule_key IS NULL OR claim_type IS NULL OR jurisdiction IS NULL OR authority_ref IS NULL OR authority_ref='' OR effective_from IS NULL OR (value_numeric IS NULL AND (value_text IS NULL OR value_text='')) OR last_verified_at IS NULL OR domain IS NULL;")
[ "${rbad:-1}" -eq 0 ] && ok "all rules fully specified + cited + effective-dated" || bad "$rbad rules missing required fields"

echo "########## 4e. UKSI Increase of Limits Orders present + caps tied to official source ##########"
uksi=$(Q "SELECT count(*) FROM legislation WHERE leg_type='uksi';")
[ "${uksi:-0}" -ge 2 ] && ok "Increase of Limits Order source rows (legislation uksi)=$uksi" || bad "UKSI Increase of Limits source missing ($uksi)"
uksih=$(Q "SELECT count(*) FROM legislation WHERE leg_type='uksi' AND (content_hash IS NULL OR content_hash='');")
[ "${uksih:-1}" -eq 0 ] && ok "all UKSI source rows hashed" || bad "$uksih UKSI rows missing content_hash"
for rk in unfair_dismissal.weeks_pay_cap_amount unfair_dismissal.compensatory_cap_amount unfair_dismissal.basic_award_min_automatic; do
  tied=$(Q "SELECT count(*) FROM rules WHERE rule_key='$rk' AND authority_url ILIKE '%legislation.gov.uk/uksi/%' AND effective_from IS NOT NULL;")
  [ "${tied:-0}" -ge 1 ] && ok "$rk tied to official UKSI + effective-dated ($tied row(s))" || bad "$rk not tied to official UKSI source"
done
# historical depth: weeks_pay cap must have multiple effective-dated rows (backdated cases)
hist=$(Q "SELECT count(*) FROM rules WHERE rule_key='unfair_dismissal.weeks_pay_cap_amount' AND authority_url ILIKE '%uksi%';")
[ "${hist:-0}" -ge 3 ] && ok "week's-pay cap historical depth=$hist effective-dated rows" || bad "insufficient backdated cap history ($hist)"

echo "########## 4f. ACAS breadth + GOV.UK tribunal guidance ##########"
acd=$(Q "SELECT count(DISTINCT doc_title) FROM acas_guidance;")
[ "${acd:-0}" -ge 5 ] && ok "ACAS distinct guidance documents=$acd" || bad "ACAS guidance breadth too low ($acd, expected >=5)"
gvd=$(Q "SELECT count(DISTINCT title) FROM official_guidance;")
[ "${gvd:-0}" -ge 10 ] && ok "GOV.UK distinct guidance documents=$gvd" || bad "GOV.UK guidance breadth too low ($gvd, expected >=10)"
trib=$(Q "SELECT count(*) FROM official_guidance WHERE title ILIKE '%tribunal%' OR source_url ILIKE '%tribunal%';")
[ "${trib:-0}" -ge 1 ] && ok "GOV.UK tribunal-procedure guidance present=$trib" || bad "GOV.UK tribunal guidance missing"

echo "########## 5. embeddings + freshness ##########"
emb=$(Q "SELECT count(*) FROM legislation WHERE embedding IS NOT NULL;")
[ "${emb:-0}" -ge 1 ] && ok "legislation embeddings=$emb" || bad "no legislation embeddings"
stale=$(Q "SELECT count(*) FROM legislation WHERE last_verified_at < now() - interval '$FRESH_DAYS days';")
[ "${stale:-1}" -eq 0 ] && ok "corpus fresh (none older than ${FRESH_DAYS}d)" || bad "$stale legislation rows stale (> ${FRESH_DAYS}d)"
secs=$(Q "SELECT count(DISTINCT section_ref) FROM legislation;")
[ "${secs:-0}" -ge 30 ] && ok "distinct sections=$secs (expanded beyond initial 13)" || bad "only $secs distinct sections (expected >=30)"
sf=$(Q "SELECT count(*) FROM source_freshness;")
[ "${sf:-0}" -ge 1 ] && ok "source_freshness reporting rows=$sf" || bad "source_freshness empty (freshness reporting not working)"
wb=$(Q "SELECT count(DISTINCT section_ref) FROM legislation WHERE section_ref IN ('43A','43B','43C','43D','43E','43F','43G','43H','43J','43K','43L','47B');")
[ "${wb:-0}" -ge 11 ] && ok "whistleblowing corpus present (s.43A-43L + s.47B)=$wb sections" || bad "whistleblowing sections incomplete ($wb)"

echo "########## 6. hybrid RAG retrieves + citations resolve to DB ##########"
RAG=$(curl -s -X POST http://localhost:8000/api/rag/hybrid-search -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal fair reason section 98 ERA 1996 reasonableness","claim_type":"unfair_dismissal"}')
echo "$RAG" | grep -qE '"insufficient_grounding":false' && ok "RAG grounded" || bad "RAG not grounded"
# Robust citation->DB resolution: extract the ERA section refs the RAG actually
# returned and confirm at least one resolves to a real legislation row (not rank-dependent).
CITED=$(echo "$RAG" | grep -oE "Employment Rights Act 1996 s\.[0-9A-Z]+" | grep -oE "s\.[0-9A-Z]+" | sed 's/s\.//' | sort -u)
if [ -z "$CITED" ]; then
  bad "RAG returned no ERA 1996 citations"
else
  resolved=0
  for sec in $CITED; do
    n=$(Q "SELECT count(*) FROM legislation WHERE section_ref='$sec' AND act_title ILIKE '%Employment Rights Act 1996%';")
    [ "${n:-0}" -ge 1 ] && resolved=$((resolved+1))
  done
  [ "$resolved" -ge 1 ] && ok "RAG citations resolve to DB rows ($resolved/$(echo "$CITED" | wc -w | tr -d ' ') ERA sections resolved)" || bad "no RAG ERA citation resolves to a DB row"
fi

echo "########## 7. Find Case Law bulk fail-closed ##########"
cl=$(Q "SELECT count(*) FROM case_law_documents;")
if [ "${FCL_BULK_LICENCE_GRANTED:-false}" = "true" ]; then
  ok "FCL licence granted (bulk allowed)"
else
  [ "${cl:-0}" -eq 0 ] && ok "case_law empty + licence-gated (fail-closed)" || bad "case_law has $cl rows without FCL_BULK_LICENCE_GRANTED"
fi
fcls=$(Q "SELECT licence_status FROM legal_sources WHERE domain='$DOMAIN' AND source_type='case_law';")
{ [ "$fcls" = "BLOCKED_BY_OWNER" ] || [ "${FCL_BULK_LICENCE_GRANTED:-false}" = "true" ]; } && ok "FCL registry status=$fcls" || bad "FCL registry status unexpected: $fcls"

echo "########## 8. no fake/placeholder rows ##########"
ph=$(Q "SELECT count(*) FROM legislation WHERE body_text ILIKE '%lorem ipsum%' OR body_text ILIKE '%placeholder%' OR body_text='';")
[ "${ph:-1}" -eq 0 ] && ok "no placeholder/empty legislation bodies" || bad "$ph placeholder/empty legislation rows"

echo "########## 8b. no duplicate rows (idempotent ingestion) ##########"
ldup=$(Q "SELECT count(*) - count(DISTINCT (source_url,chunk_index)) FROM legislation;")
[ "${ldup:-1}" -eq 0 ] && ok "legislation: no duplicate (source_url,chunk_index)" || bad "$ldup duplicate legislation rows"
adup=$(Q "SELECT count(*) - count(DISTINCT (source_url,chunk_index)) FROM acas_guidance;")
[ "${adup:-1}" -eq 0 ] && ok "acas_guidance: no duplicate (source_url,chunk_index)" || bad "$adup duplicate ACAS rows"
gdup=$(Q "SELECT count(*) - count(DISTINCT source_url) FROM official_guidance;")
[ "${gdup:-1}" -eq 0 ] && ok "official_guidance: no duplicate source_url" || bad "$gdup duplicate GOV.UK rows"

echo "########## 8c. chunked ingestion checkpoints recorded ##########"
ckpt=$(Q "SELECT count(DISTINCT source_id) FROM corpus_ingestion_runs WHERE domain='$DOMAIN' AND run_kind NOT IN ('full');")
[ "${ckpt:-0}" -ge 3 ] && ok "corpus_ingestion_runs per-batch checkpoints=$ckpt distinct sources" || bad "no per-batch ingestion checkpoints recorded ($ckpt)"

# record the run
status="passed"; [ "$fail" -ne 0 ] && status="failed"
docker compose exec -T db psql -U lawapp -d lawapp -c \
  "INSERT INTO corpus_ingestion_runs (domain, run_kind, status, sections_present, validation_passed, completed_at) \
   VALUES ('$DOMAIN','full','$status', ${secs:-0}, $([ "$fail" -eq 0 ] && echo true || echo false), now());" >/dev/null 2>&1

if [ "$fail" -ne 0 ]; then echo "UK LEGAL DATASET PROOF: FAILED"; exit 1; fi
echo "UK LEGAL DATASET PROOF: PASSED"
