---
description: Run the full hard-exit final gate — all blockers + e2e workflow proof — and issue READY / NOT READY.
---

# /final-proof

Final release gate across all layers.

## Steps
1. `qa-release-gatekeeper` confirms each blocker resolved with evidence: G1 brain Ready+200, G2 no secrets (tree+history) + rotation done, G3 CI green, G10 full provenance chain.
2. Verify e2e: frontend → backend → brain → RAG/rules → CitationGuard → answer with citations + deadline/risk; trace persisted.
3. Verify Docker build + K8s runtime (pods Ready, real endpoints) + CI green.
4. Run the gate scripts under `scripts/lawapp/final-*.sh`.
5. No `|| true`, no continue-on-error, no static PASS anywhere.

## Output
`READY — LAWAPP HARD BLOCKERS REPAIRED AND END-TO-END WORKFLOW PROVEN`
or
`NOT READY — LAWAPP HARD BLOCKERS REMAIN` (+ exact remaining items).
