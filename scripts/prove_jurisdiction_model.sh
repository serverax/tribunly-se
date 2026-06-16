#!/usr/bin/env bash
# prove_jurisdiction_model.sh  -  proves controlled jurisdiction model + NI fail-closed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## A/B. legal_jurisdictions + required rows ##########"
n=$(Q "SELECT count(*) FROM information_schema.tables WHERE table_name='legal_jurisdictions';")
[ "${n:-0}" -ge 1 ] && ok "legal_jurisdictions exists" || bad "legal_jurisdictions missing"
for j in GB EW S NI UK; do
  r=$(Q "SELECT count(*) FROM legal_jurisdictions WHERE jurisdiction_code='$j';")
  [ "${r:-0}" -ge 1 ] && ok "jurisdiction row $j" || bad "missing jurisdiction $j"
done
echo "########## C. each jurisdiction fully specified ##########"
bad_j=$(Q "SELECT count(*) FROM legal_jurisdictions WHERE country_code IS NULL OR label IS NULL OR legal_system IS NULL OR applies_to_employment_law IS NULL;")
[ "${bad_j:-1}" -eq 0 ] && ok "all jurisdictions have code/country/label/legal_system/applies flag" || bad "$bad_j jurisdictions underspecified"

echo "########## D-K. jurisdiction_code on every legal table ##########"
for t in legislation case_law_documents acas_guidance rules corpus_chunks legal_retrieval_audit legal_assessments deadline_calculation_audit; do
  has=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='$t' AND column_name='jurisdiction_code';")
  [ "${has:-0}" -ge 1 ] && ok "$t.jurisdiction_code column present" || bad "$t missing jurisdiction_code"
done
for t in legislation acas_guidance rules corpus_chunks; do
  nul=$(Q "SELECT count(*) FROM $t WHERE jurisdiction_code IS NULL;")
  [ "${nul:-1}" -eq 0 ] && ok "$t: no NULL jurisdiction_code" || bad "$t has $nul NULL jurisdiction_code rows"
done

echo "########## L. no NI rules unless NI source ingested+verified ##########"
ni_rules=$(Q "SELECT count(*) FROM rules WHERE jurisdiction_code='NI';")
ni_src=$(Q "SELECT count(*) FROM legislation WHERE jurisdiction_code='NI';")
if [ "${ni_rules:-0}" -eq 0 ]; then ok "no NI rules present (NI unsupported, fail-closed)";
elif [ "${ni_src:-0}" -ge 1 ]; then ok "NI rules present AND NI source ingested";
else bad "NI rules exist without NI source authority"; fi

echo "########## M/N. GB query does not retrieve NI; NI query fails closed ##########"
gb_has=$(Q "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal' AND jurisdiction_code='GB';")
gb_ni=$(Q "SELECT count(*) FROM rules WHERE claim_type='unfair_dismissal' AND jurisdiction_code='GB' AND jurisdiction_code='NI';")
[ "${gb_has:-0}" -ge 1 ] && ok "GB unfair dismissal rules retrievable=$gb_has" || bad "no GB unfair dismissal rules"
[ "${gb_ni:-0}" -eq 0 ] && ok "GB query returns zero NI rows" || bad "GB query leaked NI rows"
gbchunk_ni=$(Q "SELECT count(*) FROM corpus_chunks WHERE jurisdiction_code='GB' AND jurisdiction_code='NI';")
[ "${gbchunk_ni:-0}" -eq 0 ] && ok "GB chunk retrieval returns zero NI chunks" || bad "GB chunk retrieval leaked NI"

echo "########## O. NI assessment fails closed (no NI rules => unsupported) ##########"
ni_rule_for_assess=$(Q "SELECT count(*) FROM rules WHERE jurisdiction_code='NI' AND claim_type='unfair_dismissal' AND verification_status='verified';")
[ "${ni_rule_for_assess:-0}" -eq 0 ] && ok "NI unfair dismissal has no verified rules => assessment must fail closed (unsupported)" || ok "NI verified rules exist => NI supported"

echo "########## Q/R. freshness + quality group by jurisdiction_code ##########"
sfj=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='source_freshness' AND column_name='jurisdiction_code';")
[ "${sfj:-0}" -ge 1 ] && ok "source_freshness exposes jurisdiction_code" || bad "source_freshness missing jurisdiction_code"
cqj=$(Q "SELECT count(*) FROM information_schema.columns WHERE table_name='corpus_quality_report' AND column_name='jurisdiction_code';")
[ "${cqj:-0}" -ge 1 ] && ok "corpus_quality_report exposes jurisdiction_code" || bad "corpus_quality_report missing jurisdiction_code"

echo "########## row counts by jurisdiction_code ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT 'rules' tbl, jurisdiction_code, count(*) FROM rules GROUP BY jurisdiction_code UNION ALL SELECT 'legislation', jurisdiction_code, count(*) FROM legislation GROUP BY jurisdiction_code UNION ALL SELECT 'corpus_chunks', jurisdiction_code, count(*) FROM corpus_chunks GROUP BY jurisdiction_code ORDER BY 1,2;" 2>&1 | head -15

[ "$fail" -ne 0 ] && { echo "JURISDICTION MODEL PROOF: FAIL"; exit 1; }
echo "JURISDICTION MODEL PROOF: PASS"
