#!/usr/bin/env bash
# Gate: WASM  -  no hardcoded legal values, binary present, rebuild path exists
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PASS=0; FAIL=0

check() { local label="$1" result="$2"
  if [ "$result" = "PASS" ]; then echo "PASS: $label"; PASS=$((PASS+1))
  else echo "FAIL: $label"; FAIL=$((FAIL+1)); fi
}

test -f "client/public/wasm/lawapp_wasm_bg.wasm" && check "WASM binary exists" PASS || check "WASM binary exists" FAIL
test -f "client/public/js/deadline.js" && check "JS fallback exists" PASS || check "JS fallback exists" FAIL
test -f "client/wasm/src/lib.rs" && check "Rust source exists" PASS || check "Rust source exists" FAIL

if grep -rn "123543\|118223\|\b751\b" client/wasm/src/ 2>/dev/null | grep -v "//" | grep -q .; then
  check "No hardcoded legal caps in Rust WASM" FAIL
else
  check "No hardcoded legal caps in Rust WASM" PASS
fi

if grep -n "123543\|118223" client/public/js/deadline.js 2>/dev/null | grep -q .; then
  check "No hardcoded legal caps in JS fallback" FAIL
else
  check "No hardcoded legal caps in JS fallback" PASS
fi

RUST_SRC="client/wasm/src/lib.rs"; WASM_BIN="client/public/wasm/lawapp_wasm_bg.wasm"
if [ -f "$RUST_SRC" ] && [ -f "$WASM_BIN" ] && [ "$RUST_SRC" -nt "$WASM_BIN" ]; then
  check "WASM binary not stale vs Rust source" FAIL
  echo "  Rust source newer than WASM binary  -  run: bash scripts/rebuild-wasm.sh"
else
  check "WASM binary not stale vs Rust source" PASS
fi

echo ""; echo "WASM gate: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
