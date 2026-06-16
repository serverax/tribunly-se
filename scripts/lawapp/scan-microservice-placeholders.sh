#!/usr/bin/env bash
#
# SA-014  -  scan services/** and backend/** for placeholder / stub / fake-success patterns.
# Reports findings honestly; does NOT auto-fix product code.
# Exit 0 always (it is a report), but prints a FINDINGS COUNT for downstream gating.
#
set -uo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
SVC="$ROOT/services"
BE="$ROOT/backend"

hdr(){ printf '\n=== %s ===\n' "$*"; }
count=0
scan(){ # label  pattern  path...
  local label="$1"; shift; local pat="$1"; shift
  local hits
  hits=$(grep -rInE "$pat" "$@" \
        --include='*.py' \
        --exclude-dir='__pycache__' --exclude-dir='.git' --exclude-dir='tests' \
        2>/dev/null)
  printf '\n--- %s ---\n' "$label"
  if [ -n "$hits" ]; then printf '%s\n' "$hits"; count=$((count + $(printf '%s\n' "$hits" | grep -c .))); else echo "(none)"; fi
}

hdr "SA-014 placeholder / stub scan  ($(date -u))"
echo "scope: $SVC  +  $BE"

scan "TODO/FIXME/PLACEHOLDER in services"        'TODO|FIXME|PLACEHOLDER|XXX[^a-z]'               "$SVC"
scan "literal 'placeholder'/'mock'/'stub'/'dummy' (services)" '\b(placeholder|mock|stub|dummy|fake)\b' "$SVC"
scan "return {\"status\":\"ok\"} without dep check (services)" 'return\s*\{[^}]*"status"\s*:\s*"ok"' "$SVC"
scan "echo PASS / hardcoded PASS"                'echo\s+PASS|=\s*"PASS"|return\s+"PASS"'         "$SVC" "$BE"
scan "hardcoded localhost / 127.0.0.1 in services" 'localhost|127\.0\.0\.1'                       "$SVC"
scan "disabled / skipped dependency checks"      'needs_db\s*=\s*False|skip.*db|disable.*check|verify\s*=\s*False' "$SVC"
scan "bare pass / NotImplemented (services)"      '^\s*pass\s*$|NotImplementedError|raise NotImplemented' "$SVC"
scan "no-op worker sleep loops"                  'while\s+True:\s*$|time\.sleep\('               "$SVC"
scan "static success without grounding (backend brain path)" 'return\s*\{[^}]*"answer"[^}]*\}' "$BE/core/brain.py"

hdr "FINDINGS REQUIRING HUMAN JUDGEMENT (recorded, not auto-fixed)"
cat <<'NOTE'
1. services/lawapp_worker/app.py  -  `while True: time.sleep(...)` NO-OP body. The deployed
   lawapp-worker does no real task processing. Either wire it to a real queue or mark non-product.
2. DEPLOYED lawapp-citation-guard image returns valid:true for the all-zeros fake UUID and for
   empty citations (live test, evidence/microservices/05). The SOURCE (services/lawapp_citation_guard/app.py)
   is CORRECT (DB-backed valid_corpus_uuids + fail-closed). => stale/divergent deployed image. REDEPLOY.
3. brain/backend LOCAL_INFERENCE_URL -> llm-inference-service (DEAD svc, 0 endpoints). Repoint to
   ollama-inference. (owner-authorization pending)
4. needs_db=False on lawapp_llm_gateway / lawapp_document_service / lawapp_crawler is BY DESIGN
   (they proxy/generate, not DB-owning)  -  NOT a placeholder, recorded for completeness.
NOTE

hdr "PATTERN-MATCH FINDINGS COUNT"
echo "raw_grep_hits=$count  (most are benign factory defaults; see human-judgement section)"
exit 0
