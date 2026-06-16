---
name: "source-command-qa-review"
description: "Run the qa-release-gatekeeper over a finished task and issue ACCEPT/REJECT with evidence."
---

# source-command-qa-review

Use this skill when the user asks to run the migrated source command `qa-review`.

## Command Template

# /qa-review

Independent QA gate for a completed task.

## Steps
1. `qa-release-gatekeeper` reads the task file + the implementation subagent's evidence.
2. Re-run / inspect the command evidence (do not trust claims).
3. Check the rejection criteria (mock data, brain bypass, external LLM, missing provenance/CitationGuard, missing ownership/entitlement, fake frontend API, pod not Ready, CI red, secret leakage, skipped legal-data stage).
4. Issue ACCEPT or REJECT with the exact failing gate.
5. On ACCEPT move the task file `in-progress/ → done/` (else back to `backlog/` with notes).

## Output
QA VERDICT: ACCEPT/REJECT + per-gate PASS/FAIL + evidence paths + next action.
