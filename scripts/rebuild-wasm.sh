#!/usr/bin/env bash
# lawapp WASM rebuild script
# Compiles Rust deadline logic to WebAssembly using wasm-pack.
# Output: client/public/wasm/
# Usage: bash scripts/rebuild-wasm.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "=== lawapp WASM rebuild ==="

# Check wasm-pack is installed
if ! command -v wasm-pack >/dev/null 2>&1; then
  echo ""
  echo "ERROR: wasm-pack is not installed."
  echo "Install it with:"
  echo "  curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh"
  echo "  OR: cargo install wasm-pack"
  echo ""
  exit 1
fi

echo "wasm-pack version: $(wasm-pack --version)"
echo ""

# Check Rust toolchain
if ! command -v cargo >/dev/null 2>&1; then
  echo "ERROR: Rust/cargo not found. Install from https://rustup.rs/"
  exit 1
fi

WASM_SRC="client/wasm"
WASM_OUT="client/public/wasm"

echo "Source: $WASM_SRC"
echo "Output: $WASM_OUT"
echo ""

# Build WASM
echo "=== Building ==="
cd "$WASM_SRC"
wasm-pack build --target web --out-dir "../public/wasm" --no-typescript
cd "$(git rev-parse --show-toplevel)"

echo ""
echo "=== WASM build complete ==="
ls -lh "$WASM_OUT"/*.wasm 2>/dev/null || echo "WARNING: No .wasm files found"

echo ""
echo "NOTE: WASM binary uses rule values passed in from the backend."
echo "      Legal values (deadline months, caps) must NOT be hardcoded in Rust source."
echo "      Verify: grep -RIn '= 3\|= 2\|123543\|751' client/wasm/src/"
