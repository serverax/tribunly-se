#!/usr/bin/env bash
# Smoke test the staged lawapp backend via kubectl exec.
# Alias for smoke-iterlaw-ai.sh — kept for automation naming consistency.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec bash scripts/smoke-iterlaw-ai.sh
