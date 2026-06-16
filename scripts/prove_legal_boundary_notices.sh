#!/usr/bin/env bash
# prove_legal_boundary_notices.sh  -  every user surface carries the legal-boundary notice
# and reserved-activity wording is blocked.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
echo "Scanning client/public/pages + document templates"
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## 'not a law firm / not legal advice / self-help' on every page ##########"
for f in client/public/pages/*.html; do
  base=$(basename "$f")
  if grep -qiE "not a law firm|not legal advice|self-help|does not provide (regulated )?legal advice|not a solicitor" "$f"; then
    ok "$base has boundary notice"
  else
    bad "$base MISSING boundary notice"
  fi
done

echo "########## reserved-activity / promissory wording absent (positive assertions) ##########"
HITS=$(grep -rinE "we will file your|we guarantee|guaranteed to win|we will represent you|we have rights of audience|win your case for you" client/public/pages/ || true)
[ -z "$HITS" ] && ok "no promissory/reserved-activity claims in pages" || { bad "promissory wording found:"; echo "$HITS" | sed 's/^/      /'; }

echo "########## document safety_check blocks reserved-activity wording ##########"
RES=$(docker compose run --rm -T -e POSTGRES_HOST=db -e POSTGRES_PASSWORD=lawapp ingestion python -c "
from backend.core.documents import safety_check
bad = safety_check('We guarantee we will file your claim and represent you with rights of audience.')
good = safety_check('This is a self-help draft. lawapp is not a law firm and does not provide legal advice.')
print('BAD_BLOCKED', not bad['passed'])
print('GOOD_PASSED', good['passed'])
" 2>/dev/null | tail -2)
echo "$RES" | grep -q "BAD_BLOCKED True" && ok "safety_check blocks reserved-activity/guarantee wording" || bad "safety_check did not block reserved wording"
echo "$RES" | grep -q "GOOD_PASSED True" && ok "safety_check passes a clean self-help disclaimer" || bad "safety_check rejected clean text"

[ "$fail" -ne 0 ] && { echo "LEGAL BOUNDARY NOTICES PROOF: FAIL"; exit 1; }
echo "LEGAL BOUNDARY NOTICES PROOF: PASS"
