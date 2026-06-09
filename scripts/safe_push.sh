#!/usr/bin/env bash
# Safe push — runs all quality gates before pushing to origin/master.
# WSL-safe: uses docker compose, no local venv.
# Exits non-zero if any gate fails. Never pushes on failure.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "======================================================================"
echo "LAWAPP — SAFE PUSH: Running all quality gates"
echo "======================================================================"

echo
echo "--- Gate 1: Legal accuracy regression ---"
docker compose run --rm ingestion python scripts/run_legal_accuracy.py

echo
echo "--- Gate 2: Rules verification ---"
docker compose run --rm ingestion python scripts/check_rules_verification.py

echo
echo "--- Gate 3: Full integration regression ---"
docker compose run --rm ingestion python -m pytest tests/integration -q

echo
echo "--- Gate 4: Docker build proof ---"
docker compose build backend

echo
echo "======================================================================"
echo "✓ ALL GATES PASSED — pushing to origin/master"
echo "======================================================================"
git push origin master
