#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

BRANCH="${1:-main}"
MESSAGE="${2:-lawapp update: CI/CD pipeline and deployment workflow}"

echo "=== Git state before push ==="
git status --short
git branch --show-current

echo "=== Safety check: no obvious secrets ==="
grep -R "sk-ant-\|sk_live_\|BEGIN OPENSSH PRIVATE KEY\|BEGIN RSA PRIVATE KEY\|KUBE_CONFIG" -n . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  --exclude="*.md" || true

echo "=== Adding files ==="
git add .

echo "=== Commit ==="
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "$MESSAGE"
fi

echo "=== Push ==="
git branch -M "$BRANCH"
git push -u origin "$BRANCH"

echo "=== Done. GitHub Actions should start automatically. ==="
