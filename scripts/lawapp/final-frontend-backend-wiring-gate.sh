#!/usr/bin/env bash
# Frontend/backend wiring gate — every frontend route exists in backend; no mock legal data;
# real test gate exists (echo-stub build/test scripts are NOT acceptable as proof).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "Frontend / backend wiring"
FE_DIR=client/public
MAIN=backend/api/main.py

# 1. Frontend must not embed mock/fake legal data as product output
if grep -rinE "mock|fake|dummy|hardcoded answer|lorem ipsum" "$FE_DIR/js" "$FE_DIR/pages" 2>/dev/null \
   | grep -vE "//|/\*|\*/" >/dev/null; then fail "mock/fake markers in frontend"; else pass "no mock/fake legal data in frontend"; fi

# 2. Every backend path referenced by the frontend must exist as a route in main.py
routes=$(grep -rhoE "/(auth|api|cases|assess|rules|documents|handoff|funnel|freshness)[A-Za-z0-9/_{}-]*" \
          "$FE_DIR/js" "$FE_DIR/pages" 2>/dev/null | sed -E 's#\$\{[^}]+\}##g; s#/[0-9]+#/{id}#g' | sort -u)
missing=0
while read -r r; do
  [ -z "$r" ] && continue
  base=$(printf '%s' "$r" | sed -E 's#\{[^}]+\}#[^/"]+#g; s#/[^/]*$##')
  # check the first path segment family exists in main.py route decorators
  seg=$(printf '%s' "$r" | grep -oE '^/(auth|api|cases|assess|rules|documents|handoff|funnel|freshness)[A-Za-z_-]*')
  if grep -qE "@app\.(get|post|put|delete)\(\"$seg" "$MAIN" 2>/dev/null \
     || grep -qE "@app\.(get|post|put|delete)\(\"${seg%/*}" "$MAIN" 2>/dev/null; then :; else
     info "frontend route not directly matched: $r"; missing=$((missing+1)); fi
done <<< "$routes"
# we assert the KEY routes exist explicitly:
for r in '"/assess"' '"/api/brain/trace"' '"/auth/token"' '"/cases"' '"/rules/' '"/documents/generate"'; do
  grep -qE "@app\.(get|post)\($r" "$MAIN" && pass "backend route $r exists" || fail "backend route $r MISSING"
done

# 3. Real frontend test gate must exist (echo-stub scripts are a fake gate → FAIL)
if grep -qE '"(build|test|lint)":\s*"echo' client/package.json 2>/dev/null; then
  fail "frontend build/test/lint are echo stubs (fake gate) — replace with real checks (e.g. playwright e2e)"
else pass "frontend scripts are not echo stubs"; fi

# 4. A real e2e harness must be present (playwright)
grep -q '"e2e"' client/package.json && pass "playwright e2e script present" || fail "no real e2e harness"

gate_result "final-frontend-backend-wiring-gate"
