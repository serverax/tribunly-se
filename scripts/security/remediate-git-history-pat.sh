#!/usr/bin/env bash
# remediate-git-history-pat.sh
# OWNER-RUN history remediation for the leaked GitHub PAT(s) in lawapp git history.
#
# This script DOES NOT force-push and DOES NOT rotate tokens — those are owner-only.
# It prepares a CLEANED MIRROR using git-filter-repo (preferred) or BFG, verifies the
# history is clean, and then PRINTS the exact (manual) force-push command for the owner
# to run consciously. Nothing destructive to the public remote happens automatically.
#
# Prereqs (owner machine):
#   1. ROTATE/REVOKE the exposed PAT in GitHub > Settings > Developer settings FIRST.
#      (Rewriting history does NOT invalidate a live token — rotation is mandatory and primary.)
#   2. Install git-filter-repo:  pip install git-filter-repo   (or use BFG jar)
#   3. Ensure all collaborators have pushed; history rewrite invalidates existing clones.
#
# Usage:
#   bash scripts/security/remediate-git-history-pat.sh           # dry-run analysis only
#   CONFIRM=1 bash scripts/security/remediate-git-history-pat.sh # build cleaned mirror (still no push)
#
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

SCAN="scripts/security/scan-secrets-history.sh"
WORK="../lawapp-history-clean.git"   # cleaned bare mirror, OUTSIDE the working tree

echo "== lawapp git-history PAT remediation (owner-run, non-pushing) =="

echo "[1/5] Current history scan (must show the leak before remediation):"
HISTORY_FAILS=1 bash "$SCAN" || true

if [ "${CONFIRM:-0}" != "1" ]; then
  cat <<'EOF'

DRY-RUN ONLY. To build the cleaned mirror (no push), re-run with CONFIRM=1.
Before that, confirm you have ALREADY rotated/revoked the exposed PAT in GitHub.
EOF
  exit 0
fi

command -v git-filter-repo >/dev/null 2>&1 || {
  echo "ERROR: git-filter-repo not installed. Run: pip install git-filter-repo"; exit 2; }

echo "[2/5] Fresh bare mirror -> $WORK"
rm -rf "$WORK"
git clone --mirror . "$WORK"

echo "[3/5] Strip GitHub PAT patterns from ALL history (replacement text, never the raw token):"
# git-filter-repo --replace-text rewrites matching blobs across all refs.
REPLACE_FILE="$(mktemp)"
cat > "$REPLACE_FILE" <<'EOF'
regex:ghp_[A-Za-z0-9]{36}==>***REMOVED-GITHUB-PAT***
regex:github_pat_[A-Za-z0-9_]{40,}==>***REMOVED-GITHUB-PAT***
EOF
( cd "$WORK" && git filter-repo --force --replace-text "$REPLACE_FILE" )
rm -f "$REPLACE_FILE"

echo "[4/5] Verify cleaned mirror has NO PAT pattern:"
if ( cd "$WORK" && git log --all -p 2>/dev/null | grep -nE 'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}' >/dev/null ); then
  echo "FAIL: PAT pattern still present in cleaned mirror — do NOT push."; exit 1
fi
echo "OK: cleaned mirror is free of GitHub PAT patterns."

cat <<EOF

[5/5] READY. The cleaned mirror is at: $WORK
The following step is DESTRUCTIVE and rewrites public history — run it CONSCIOUSLY,
only after the PAT is already rotated, and after telling collaborators to re-clone:

    cd "$WORK"
    git push --force --mirror origin

Then verify on a fresh clone:
    HISTORY_FAILS=1 bash scripts/security/scan-secrets-history.sh   # must PASS
EOF
