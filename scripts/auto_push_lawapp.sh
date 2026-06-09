#!/usr/bin/env bash
set -euo pipefail

cd /mnt/f/lawapp

BRANCH="${1:-master}"
MESSAGE="${2:-lawapp: automated CI/CD update}"

echo "=== lawapp auto-push ==="
echo "Branch: $BRANCH"
echo "Commit message: $MESSAGE"

echo "=== Git status before ==="
git status --short

echo "=== Running local legal accuracy gate if available ==="
if [ -d tests/legal_accuracy ]; then
  python -m pytest tests/legal_accuracy/ --tb=line -q
else
  echo "ERROR: tests/legal_accuracy missing. Refusing to auto-push without legal accuracy gate."
  exit 1
fi

echo "=== Running local Python tests if available ==="
if [ -d tests ]; then
  python -m pytest tests --tb=line -q
fi

echo "=== Running client checks if available ==="
if [ -f client/package.json ]; then
  cd client
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
  npm test --if-present
  npm run lint --if-present
  npm run build --if-present
  cd /mnt/f/lawapp
fi

echo "=== Running Rust tests if available ==="
if find . -name Cargo.toml | grep -q .; then
  while IFS= read -r manifest; do
    dir="$(dirname "$manifest")"
    echo "Testing Rust crate: $dir"
    (cd "$dir" && cargo test --locked || cargo test)
  done < <(find . -name Cargo.toml)
fi

echo "=== Secret check ==="
if grep -RInE "(ghp_|github_pat_|OPENAI_API_KEY=|sk-[A-Za-z0-9]|password *= *['\"][^'\"]{8,})" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=target --exclude-dir=.venv .; then
  echo "ERROR: Possible secret found. Push blocked."
  exit 1
fi

echo "=== Git add/commit/push ==="
git add .github/workflows scripts

if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$MESSAGE"
fi

git push origin "$BRANCH"

echo "=== Triggered GitHub Actions ==="
gh run list --repo serverax/lawapp --limit 5 || true
