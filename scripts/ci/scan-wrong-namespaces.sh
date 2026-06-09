#!/usr/bin/env bash
set -euo pipefail
bad="$(grep -R "namespace:" k8s 2>/dev/null | grep -v "lawapp-api" | grep -v "lawapp-ai" | grep -v "lawapp-rag" | grep -v "lawapp-security" | grep -v "lawapp-monitoring" || true)"
if [ -n "$bad" ]; then echo "$bad"; exit 1; fi
echo "PASS namespace scanner"
