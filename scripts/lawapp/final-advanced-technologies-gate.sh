#!/usr/bin/env bash
# Advanced-tech gate — WASM built+tested+fail-closed; pip-audit clean; no hardcoded legal values.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "Advanced technologies (WASM + SCA)"

# 1. WASM binary committed
[ -f client/public/wasm/lawapp_wasm_bg.wasm ] && pass "WASM binary present" || fail "WASM binary missing"

# 2. WASM builds + tests pass (incl. bad-input fail-closed)
if command -v cargo >/dev/null 2>&1; then
  if ( cd client/wasm && cargo test --release >/tmp/wasm_test.out 2>&1 ); then
    n=$(grep -oE '[0-9]+ passed' /tmp/wasm_test.out | head -1); pass "WASM cargo test ($n)"
  else fail "WASM cargo test failed"; fi
else info "cargo not on PATH (CI installs rust) — skipping local build; binary presence still required"; fi

# 3. No hardcoded legal values in Rust source
if grep -RInE "= 2.*years|123543|118223" client/wasm/src/ 2>/dev/null | grep -vE "//|test|spec" >/dev/null; then
  fail "possible hardcoded legal value in WASM source"; else pass "no hardcoded legal values in WASM source"; fi

# 4. pip-audit clean (uses an isolated venv install of the project)
if command -v python3 >/dev/null 2>&1; then
  V=/tmp/lawapp-gate-venv
  if [ ! -x "$V/bin/pip-audit" ]; then python3 -m venv "$V" >/dev/null 2>&1; "$V/bin/pip" install -q -e . pip-audit >/dev/null 2>&1; fi
  if "$V/bin/pip-audit" >/tmp/pipaudit.out 2>&1; then pass "pip-audit: no known vulnerabilities"; else
    grep -qi "no known vulnerabilities" /tmp/pipaudit.out && pass "pip-audit: no known vulnerabilities" || fail "pip-audit found vulnerabilities (see /tmp/pipaudit.out)"; fi
else fail "python3 unavailable for pip-audit"; fi

# 5. Microservice placeholder/mock scan (SA-014) — no placeholder behaviour in active product path.
if [ -x scripts/lawapp/scan-microservice-placeholders.sh ]; then
  if bash scripts/lawapp/scan-microservice-placeholders.sh >/tmp/phscan.out 2>&1; then pass "no microservice placeholders in product path"; else fail "microservice placeholder scan flagged issues (see /tmp/phscan.out)"; fi
else fail "scripts/lawapp/scan-microservice-placeholders.sh missing"; fi

gate_result "final-advanced-technologies-gate"
