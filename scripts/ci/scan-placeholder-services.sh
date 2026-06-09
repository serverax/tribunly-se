#!/usr/bin/env bash
set -euo pipefail
bad="$(grep -R "placeholder\|fake response\|TODO-only" services k8s 2>/dev/null || true)"
if [ -n "$bad" ]; then echo "$bad"; exit 1; fi
echo "PASS placeholder scanner"
