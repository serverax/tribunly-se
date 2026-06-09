#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p reports

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel

pip install \
  pytest pytest-asyncio httpx requests \
  fastapi uvicorn pydantic python-multipart \
  psycopg2-binary sqlalchemy asyncpg \
  pgvector python-dotenv \
  beautifulsoup4 lxml \
  numpy

export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

REPORT="reports/local-regression-$(date +%Y%m%d-%H%M%S).txt"

{
  echo "LawApp local regression"
  echo "Date: $(date -Is)"
  echo

  echo "=== Python ==="
  which python
  python --version
  echo

  echo "=== Git status ==="
  git status --short || true
  echo

  echo "=== Integration tests ==="
  pytest tests/integration -q

  echo
  echo "RESULT: PASS"
} | tee "$REPORT"

echo
echo "Report written: $REPORT"
