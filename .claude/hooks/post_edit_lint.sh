#!/usr/bin/env bash
# Post-edit lint hook: auto-format + check Python files on every edit.
# Runs via Claude Code PostToolUse. Silent on pass; exits 2 on violations.

set -euo pipefail

FILE="${1:-}"

# Only act on Python files
[[ "$FILE" == *.py ]] || exit 0

# Must be inside the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Phase 1: auto-format (silent)
uv run ruff format "$FILE" --quiet 2>/dev/null || true

# Phase 2: check for remaining violations
if ! uv run ruff check "$FILE" --quiet 2>&1; then
    echo "[hook] ruff violations remain in $FILE  -  run: uv run ruff check $FILE"
    exit 2
fi

exit 0
