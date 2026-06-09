#!/usr/bin/env bash
# prove_no_fake_legal_data.sh — there is no fake/placeholder/uncited legal data.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp"
Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## no placeholder/empty bodies ##########"
for t in legislation acas_guidance official_guidance; do
  ph=$(Q "SELECT count(*) FROM $t WHERE body_text ILIKE '%lorem ipsum%' OR body_text ILIKE '%placeholder%' OR body_text ILIKE '%TODO%' OR body_text IS NULL OR body_text='';")
  [ "${ph:-1}" -eq 0 ] && ok "$t: no placeholder/empty bodies" || bad "$t: $ph placeholder/empty rows"
done

echo "########## every legal row sourced + hashed + dated ##########"
for t in legislation acas_guidance official_guidance; do
  bad_rows=$(Q "SELECT count(*) FROM $t WHERE source_url IS NULL OR source_url='' OR content_hash IS NULL OR content_hash='' OR last_verified_at IS NULL;")
  [ "${bad_rows:-1}" -eq 0 ] && ok "$t: all rows sourced+hashed+dated" || bad "$t: $bad_rows rows missing source_url/content_hash/last_verified_at"
done

echo "########## every rule cited + dated + verified-status ##########"
rulebad=$(Q "SELECT count(*) FROM rules WHERE authority_ref IS NULL OR authority_ref='' OR authority_url IS NULL OR authority_url='' OR effective_from IS NULL OR last_verified_at IS NULL OR verification_status NOT IN ('verified','case_law_verified','prospective','unverified','mismatch','blocked');")
[ "${rulebad:-1}" -eq 0 ] && ok "all rules cited + effective-dated + valid verification_status" || bad "$rulebad rules uncited/undated/invalid-status"

echo "########## no case_law unless licence granted (no fake cases) ##########"
g=$(Q "SELECT application_status FROM legal_sources WHERE source_id='find_case_law';")
cl=$(Q "SELECT count(*) FROM case_law_documents;")
{ [ "${cl:-0}" -eq 0 ] || [ "$g" = "granted" ]; } && ok "case_law=$cl, FCL=$g (no fake case law)" || bad "fake/unlicensed case_law present"

echo "########## no forbidden secondary sources in corpus ##########"
forb=$(Q "SELECT count(*) FROM corpus_chunks WHERE source_url ILIKE '%wikipedia%' OR source_url ILIKE '%reddit%' OR source_url ILIKE '%blogspot%';")
[ "${forb:-0}" -eq 0 ] && ok "no forbidden secondary sources in corpus_chunks" || bad "$forb forbidden-source chunks"

[ "$fail" -ne 0 ] && { echo "NO FAKE LEGAL DATA PROOF: FAIL"; exit 1; }
echo "NO FAKE LEGAL DATA PROOF: PASS"
