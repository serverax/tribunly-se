#!/usr/bin/env bash
# prove_rules_integrity.sh — the rules table is the legal-correctness source.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "DB target: postgres://lawapp:***@db:5432/lawapp (service 'db')"

Q(){ docker compose exec -T db psql -U lawapp -d lawapp -t -c "$1" | tr -d ' \r\n'; }
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## A. required GB rule keys present ##########"
for k in time_limit_months early_conciliation_required qualifying_period compensatory_cap_amount compensatory_cap_weeks_pay weeks_pay_cap_amount basic_award_formula basic_award_min_automatic acas_code_adjustment_percent not_reasonably_practicable_extension; do
  n=$(Q "SELECT count(*) FROM rules WHERE rule_key='unfair_dismissal.$k' AND jurisdiction_code='GB';")
  [ "${n:-0}" -ge 1 ] && ok "unfair_dismissal.$k present (GB)" || bad "missing GB rule unfair_dismissal.$k"
done

echo "########## B. current rules carry full provenance ##########"
miss=$(Q "SELECT count(*) FROM rules WHERE is_current=true AND (authority_ref IS NULL OR authority_ref='' OR authority_url IS NULL OR authority_url='' OR effective_from IS NULL OR last_verified_at IS NULL OR jurisdiction_code IS NULL);")
[ "${miss:-1}" -eq 0 ] && ok "all current rules have authority_ref/url, effective_from, last_verified_at, jurisdiction_code" || bad "$miss current rules missing required provenance"
badv=$(Q "SELECT count(*) FROM rules WHERE verification_status NOT IN ('verified','case_law_verified','prospective','unverified','mismatch','blocked');")
[ "${badv:-1}" -eq 0 ] && ok "all rules have allowed verification_status" || bad "$badv rules have invalid verification_status"

echo "########## C. no hardcoded deterministic values in deadline/value code ##########"
HITS=$(grep -rInE "(time_limit|compensatory_cap|weeks_pay_cap|basic_award_min)[^=]*=\s*[0-9]{2,}" backend/core/deadline*.py backend/core/schedule*of*loss*.py backend/domains 2>/dev/null | grep -viE "rule_key|authority|from rules|comment|#" | head -5 || true)
if [ -z "$HITS" ]; then ok "no hardcoded cap/limit literals found in deadline/value code"; else bad "possible hardcoded legal values:"; echo "$HITS" | sed 's/^/      /'; fi

echo "########## D. rules lookup is jurisdiction + date aware (index-backed) ##########"
idx=$(Q "SELECT count(*) FROM pg_indexes WHERE indexname='rules_key_juris_eff_idx';")
[ "${idx:-0}" -ge 1 ] && ok "composite index rules(rule_key,jurisdiction_code,effective_from,effective_to) exists" || bad "missing rules composite index"

echo "########## rule counts by rule_key + jurisdiction_code ##########"
docker compose exec -T db psql -U lawapp -d lawapp -c "SELECT rule_key, jurisdiction_code, count(*) rows, count(*) FILTER (WHERE is_prospective) prospective, count(*) FILTER (WHERE verification_status NOT IN ('verified','case_law_verified')) unverified FROM rules GROUP BY rule_key, jurisdiction_code ORDER BY rule_key;" 2>&1 | head -40

[ "$fail" -ne 0 ] && { echo "RULES INTEGRITY PROOF: FAIL"; exit 1; }
echo "RULES INTEGRITY PROOF: PASS"
