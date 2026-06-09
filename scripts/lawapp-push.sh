#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

BRANCH="${1:-main}"
MESSAGE="${2:-lawapp: setup CI/CD}"

if grep -R "sk-ant-\|sk_live_\|ghp_\|BEGIN OPENSSH PRIVATE KEY\|BEGIN RSA PRIVATE KEY" -n . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  --exclude="*.md"; then
  echo "Possible secret found. Remove it before pushing."
  exit 1
fi

git add .

if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "$MESSAGE"
fi

git branch -M "$BRANCH"
git remote set-url origin git@github.com:serverax/lawapp.git
git push -u origin "$BRANCH"
