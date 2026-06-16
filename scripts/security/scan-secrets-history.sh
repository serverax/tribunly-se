#!/usr/bin/env bash
# scan-secrets-history.sh
# Fail-closed secret scanner for lawapp.
#   [1] Working-tree scan  -> exit 1 on any real secret (this is the CI gate).
#   [2] Git-history scan    -> reports commits whose blobs still carry real GitHub PATs
#                              (owner action: rotate + history rewrite). Set SCAN_HISTORY=0 to skip.
# All matches are REDACTED in output  -  a raw secret is never printed.
#
# Allowlist: a line containing the literal marker  pragma: allowlist secret
# is skipped (use ONLY for genuinely-fake test fixtures).
#
# Usage:
#   bash scripts/security/scan-secrets-history.sh
#   SCAN_HISTORY=0 bash scripts/security/scan-secrets-history.sh   # working tree only (pre-commit / CI gate)
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

# PRECISE secret shapes  -  narrow enough to avoid base64/hash false positives.
RE_WT='ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}|sk-ant-[A-Za-z0-9-]{30,}|sk-proj-[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----'
# History gate: GitHub PATs only (the credentials actually leaked in this repo).
RE_HIST='ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}'

# Paths excluded from the WORKING-TREE scan: the scanner itself + ephemeral session logs + binaries.
EXCLUDES=(':(exclude)scripts/security/scan-secrets-history.sh' ':(exclude).claude-flow/sessions/*' ':(exclude)*.png' ':(exclude)*.lock')

redact() { sed -E 's#(ghp_|github_pat_|gho_|ghu_|ghs_|ghr_|sk-ant-|sk-proj-|AKIA)[A-Za-z0-9_-]+#\1[REDACTED]#g'; }

fail=0

echo "== [1/2] Working-tree scan =="
# Drop allowlisted lines, then test for any remaining match.
hits="$(git grep -nI -E "$RE_WT" -- . "${EXCLUDES[@]}" 2>/dev/null | grep -v 'pragma: allowlist secret' || true)"
if [ -n "$hits" ]; then
  echo "LEAK: secret pattern(s) in working tree (redacted):"
  printf '%s\n' "$hits" | redact
  fail=1
else
  echo "OK: no real secrets in working tree."
fi

if [ "${SCAN_HISTORY:-1}" = "1" ]; then
  echo "== [2/2] Git-history scan (GitHub PATs) =="
  histc="$(git log --all --oneline -G "$RE_HIST" 2>/dev/null || true)"
  if [ -n "$histc" ]; then
    echo "WARNING: GitHub PAT pattern present in git history (commits touching PAT lines):"
    printf '%s\n' "$histc"
    echo
    echo "OWNER ACTION REQUIRED (not automatable here):"
    echo "  1. Rotate/revoke the exposed PAT(s) in GitHub > Settings > Developer settings."
    echo "  2. Rewrite history (git filter-repo / BFG) to purge the blobs, then force-push."
    echo "  Changing the remote URL is NOT sufficient. (Force-push = owner-approved destructive step.)"
    # FAIL-CLOSED: a known leaked PAT in history means the security gate MUST fail until the
    # owner rotates the token AND rewrites history. Set HISTORY_FAILS=0 ONLY for a working-tree-only
    # pre-commit check  -  never for the CI security gate.
    [ "${HISTORY_FAILS:-1}" = "1" ] && fail=1
  else
    echo "OK: no GitHub PATs in git history."
  fi
else
  echo "== [2/2] History scan skipped (SCAN_HISTORY=0) =="
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAIL  -  leaked secret patterns detected (working tree and/or git history)."
  exit 1
fi
echo "RESULT: PASS  -  no leaked secrets in working tree or git history."
exit 0
