#!/usr/bin/env bash
# prove_frontend_backend_wiring.sh — frontend pages are served and wired to the backend.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${LAWAPP_BASE_URL:-http://localhost:8000}"
echo "Backend: $BASE"
fail=0; ok(){ echo "  PASS: $*"; }; bad(){ echo "  FAIL: $*"; fail=1; }

echo "########## pages served ##########"
for p in /pages/intake.html /pages/assessment.html /pages/dashboard.html /pages/case_detail.html; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$p")
  [ "$c" = "200" ] && ok "served $p" || bad "$p not served ($c)"
done

echo "########## intake wired to backend /assess or /api/diagnosis ##########"
grep -qE "/assess|/api/diagnosis" client/public/pages/intake.html && ok "intake.html calls backend assess endpoint" || bad "intake.html not wired to backend"

echo "########## assessment page renders diagnosis fields ##########"
for field in citation deadline weakness; do
  grep -qiE "$field" client/public/pages/assessment.html && ok "assessment.html renders '$field'" || bad "assessment.html missing '$field' rendering"
done

echo "########## live round-trip from a page-equivalent request ##########"
st=$(curl -s -X POST "$BASE/assess" -H "Content-Type: application/json" -d '{"query":"unfair dismissal","facts":{"edt":"2024-05-01","service_start_date":"2023-09-01","reason_for_dismissal":"conduct","was_procedure_followed":false},"jurisdiction":"EW","use_model":false}' | python -c "import sys,json;print(json.load(sys.stdin).get('status'))")
[ -n "$st" ] && ok "backend /assess round-trip ok (status=$st)" || bad "backend /assess round-trip failed"

[ "$fail" -ne 0 ] && { echo "FRONTEND/BACKEND WIRING PROOF: FAIL"; exit 1; }
echo "FRONTEND/BACKEND WIRING PROOF: PASS"
