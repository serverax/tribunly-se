#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MSG="${1:-Automate CI pipelines and process checks}"

echo "=== Current repo ==="
pwd
git status
echo

echo "=== Add all files ==="
git add -A

echo "=== Commit ==="
git commit -m "$MSG" || echo "Nothing to commit"

echo "=== Push ==="
git push origin master || git push origin main

echo "DONE"
