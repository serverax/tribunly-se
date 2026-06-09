#!/usr/bin/env bash
set -euo pipefail

REPO="serverax/lawapp"
BRANCH="${1:-main}"

gh workflow list --repo "$REPO"
gh workflow run lawapp-deploy-talos.yml --repo "$REPO" --ref "$BRANCH"
gh run watch --repo "$REPO"
