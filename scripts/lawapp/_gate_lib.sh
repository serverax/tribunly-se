#!/usr/bin/env bash
# Shared helpers for lawapp final gates. FAIL-CLOSED by design.
# No `|| true`, no `continue-on-error`, no `echo PASS`, no static PASS, no mock success.
set -uo pipefail

GATE_FAILS=0
NS_AI="${NS_AI:-lawapp-ai}"; NS_API="${NS_API:-lawapp-api}"; NS_RAG="${NS_RAG:-lawapp-rag}"
KT() { timeout "${KUBE_TIMEOUT:-30}" kubectl "$@"; }

pass() { printf '  [PASS] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; GATE_FAILS=$((GATE_FAILS+1)); }
info() { printf '  [info] %s\n' "$1"; }
hdr()  { printf '\n== %s ==\n' "$1"; }

# require <description> <command...> : passes iff command exits 0
require() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$d"; else fail "$d"; fi; }

# brain pod name (Running)
brain_pod() { KT get pods -n "$NS_AI" -l app=lawapp-brain --field-selector=status.phase=Running -o name 2>/dev/null | head -1 | sed 's#pod/##'; }
# run a curl inside the brain pod, echo HTTP code
brain_http() { local path="$1"; local p; p=$(brain_pod); [ -z "$p" ] && { echo 000; return; }
  KT exec -n "$NS_AI" "$p" -- python3 -c "import urllib.request,sys
try:
 r=urllib.request.urlopen('http://localhost:8000'+sys.argv[1],timeout=8);print(r.status)
except urllib.error.HTTPError as e:print(e.code)
except Exception:print('000')" "$path" 2>/dev/null; }

ragpg() { echo "${RAGPG:-lawapp-postgres-0}"; }
psql_rag() { KT exec -i -n "$NS_RAG" "$(ragpg)" -- psql -U "${RAG_USER:-lawapp_user}" -d "${RAG_DB:-lawapp}" -tAc "$1" 2>/dev/null; }

gate_result() {
  local name="$1"
  printf '\n=== GATE RESULT: %s ===\n' "$name"
  if [ "$GATE_FAILS" -eq 0 ]; then printf 'RESULT: PASS\n'; exit 0
  else printf 'RESULT: FAIL (%d check(s) failed)\n' "$GATE_FAILS"; exit 1; fi
}
