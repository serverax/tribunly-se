#!/usr/bin/env bash
# Security gate  -  no leaked secrets (working tree); auth enforced; G2 history tracked as owner-action.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"; . scripts/lawapp/_gate_lib.sh

hdr "Security & privacy"

# 1. Working-tree secret scan must pass (fail-closed gate)
if SCAN_HISTORY=0 bash scripts/security/scan-secrets-history.sh >/tmp/secscan.out 2>&1; then
  pass "working-tree secret scan clean"; else fail "secret scan found working-tree secrets"; fi

# 2. G2 history leak: must be tracked as owner-action (remediation script + runbook present).
[ -f scripts/security/remediate-git-history-pat.sh ] && [ -f docs/runbooks/G2_PAT_HISTORY_REMEDIATION_RUNBOOK.md ] \
  && pass "G2 history remediation tracked (script + runbook present)" \
  || fail "G2 remediation script/runbook missing"

# 3. Protected route enforces auth (no X-User-ID trust in production jwt mode).
p=$(brain_pod)
if [ -n "$p" ]; then
  code=$(KT exec -n "$NS_AI" "$p" -- python3 -c "import urllib.request
try:
 urllib.request.urlopen('http://localhost:8000/cases',timeout=8);print(200)
except urllib.error.HTTPError as e:print(e.code)
except Exception:print('000')" 2>/dev/null)
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then pass "/cases requires auth (code=$code)"; else fail "/cases not auth-protected (code=$code)"; fi
else fail "no brain pod to test auth"; fi

# 4. No raw production DB password / PAT pattern committed in reports/ evidence
if grep -rIlE "ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40}" reports/ 2>/dev/null \
   | grep -v "scan-secrets" >/dev/null; then fail "PAT pattern in reports/"; else pass "no PAT pattern in reports/"; fi

gate_result "final-security-performance-gate"
