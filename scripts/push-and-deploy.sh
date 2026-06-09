#!/usr/bin/env bash
set -euo pipefail

MSG="${1:-lawapp ci cd update}"
REPO="serverax/lawapp"
BRANCH="$(git branch --show-current)"

echo "Current branch: $BRANCH"

git status --short

git add .
git commit -m "$MSG" || echo "No changes to commit"

git push -u origin "$BRANCH"

echo ""
echo "Triggering GitHub Actions workflow..."
gh workflow run lawapp-ci-cd.yml --repo "$REPO" --ref "$BRANCH"

echo ""
echo "Latest runs:"
gh run list --repo "$REPO" --workflow lawapp-ci-cd.yml --limit 5

echo ""
echo "To watch:"
echo "gh run watch --repo $REPO --workflow lawapp-ci-cd.yml"
