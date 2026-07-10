#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

MODE="${1:-all}"
ROOT_COMPOSE_FILE="${ROOT_COMPOSE_FILE:-docker-compose.yml}"
SE_COMPOSE_FILE="${SE_COMPOSE_FILE:-docker-compose.se.yml}"
SE_ENV_FILE="${SE_ENV_FILE:-}"

PYTHON_BIN=()
if [ -n "${PYTHON_BIN_OVERRIDE:-}" ]; then
  PYTHON_BIN=("${PYTHON_BIN_OVERRIDE}")
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=(python)
elif command -v py >/dev/null 2>&1; then
  PYTHON_BIN=(py -3)
elif [ -x "C:/Python314/python.exe" ]; then
  PYTHON_BIN=("C:/Python314/python.exe")
elif [ -x "C:/Users/kalsh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" ]; then
  PYTHON_BIN=("C:/Users/kalsh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
else
  echo "python not found"
  exit 1
fi

TMP_ENV_FILE=""
cleanup() {
  if [ -n "$TMP_ENV_FILE" ] && [ -f "$TMP_ENV_FILE" ]; then
    rm -f "$TMP_ENV_FILE"
  fi
}
trap cleanup EXIT

if [ -z "$SE_ENV_FILE" ]; then
  TMP_ENV_FILE="$(mktemp)"
  cat >"$TMP_ENV_FILE" <<'EOF'
POSTGRES_PASSWORD=ci-password
POSTGRES_DB=postgres
POSTGRES_USER=lawapp
JWT_SECRET=ci-jwt-secret
ADMIN_API_KEY=ci-admin-key
ENCRYPTION_KEY=ci-encryption-key-00000000000000000000000000000000
LAWAPP_DOMAIN=employment_se
LAWAPP_ENABLE_SE=true
LAWAPP_LLM_PROVIDER=ollama_local
LAWAPP_OLLAMA_BASE_URL=http://ollama:11434
LAWAPP_OLLAMA_MODEL=qwen2.5:3b-instruct-q6_K
BACKEND_PORT=6450
OLLAMA_PORT=11450
REDACTION_SERVICE_PORT=8150
RATELIMIT_STORAGE_URI=redis://redis:6379
PAYMENT_MODE=disabled
LOG_LEVEL=INFO
ENVIRONMENT=development
EOF
  SE_ENV_FILE="$TMP_ENV_FILE"
fi

compose_check() {
  local label="$1"
  shift
  echo "==> docker compose config: $label"
  docker compose --env-file "$SE_ENV_FILE" "$@" config >/dev/null
}

if [ "$MODE" = "compose-only" ] || [ "$MODE" = "all" ]; then
  compose_check root -f "$ROOT_COMPOSE_FILE"
  compose_check sweden -f "$SE_COMPOSE_FILE"
fi

if [ "$MODE" = "compose-only" ]; then
  echo "CI CHECK: compose-only pass"
  exit 0
fi

if [ "$MODE" != "test-only" ] && [ "$MODE" != "all" ]; then
  echo "Unknown mode: $MODE"
  exit 1
fi

if ! "${PYTHON_BIN[@]}" -c "import pytest, ruff" >/dev/null 2>&1; then
  "${PYTHON_BIN[@]}" -m pip install --upgrade pip
  "${PYTHON_BIN[@]}" -m pip install -e ".[dev]"
else
  echo "Dev deps already available; skipping install"
fi

"${PYTHON_BIN[@]}" -m ruff check backend ingestion scripts tests

"${PYTHON_BIN[@]}" -m pytest \
  tests/test_jurisdiction_registry_se.py \
  tests/ingestion/test_riksdagen_parser.py \
  tests/test_rag_1024_retrieval_repair.py \
  -q

echo "CI CHECK: pass"
