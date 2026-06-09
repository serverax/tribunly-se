#!/usr/bin/env bash
# prove_lawapp_core.sh — master proof. Accepted only if it exits 0.
# DB-FIRST order (LEGAL DB FIRST -> CORPUS FIRST -> RULES FIRST -> CITATIONS FIRST -> AI SECOND):
#   1. UK legal dataset proof        (domain pack, registry, sections, rules, provenance, freshness)
#   2. employment-law corpus proof   (corpus cited/embedded/RAG, FCL fail-closed)
#   3. Workflow A/B/C E2E
#   4. assess provider integration
#   5. OpenRouter Workflow C provider plug (mocked, no key)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
fail=0
for s in prove_uk_legal_dataset.sh prove_employment_law_corpus.sh prove_workflow_abc.sh prove_assess_provider_integration.sh prove_openrouter_workflow_c.sh; do
  echo
  echo "================================================================"
  echo "  RUN: scripts/$s"
  echo "================================================================"
  if bash "scripts/$s"; then echo ">> $s: PASSED"; else echo ">> $s: FAILED"; fail=1; fi
done
echo
if [ "$fail" -ne 0 ]; then echo "LAWAPP CORE PROOF: FAILED"; exit 1; fi
echo "LAWAPP CORE PROOF: PASSED"
