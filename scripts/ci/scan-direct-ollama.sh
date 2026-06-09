#!/usr/bin/env bash
set -euo pipefail
hits="$(grep -R "OLLAMA_BASE_URL\|ollama-inference\|11434\|/api/generate\|/api/chat" . \
  --exclude-dir=node_modules \
  --exclude-dir=.git \
  --exclude-dir=dist \
  --exclude-dir=build \
  --exclude-dir=.venv \
  --exclude-dir=venv || true)"
bad="$(printf "%s\n" "$hits" | grep -v "services/lawapp_llm_gateway" | grep -v "k8s/lawapp-ai/ollama-inference" | grep -v "k8s/lawapp-ai/lawapp-llm-gateway" | grep -v "scan-direct-ollama" | grep -v ".github/workflows" || true)"
if [ -n "$bad" ]; then
  echo "$bad"
  exit 1
fi
echo "PASS direct Ollama scanner"
