---
description: Enter lawapp autonomous recovery mode  -  read constitution + guides, freeze state, route blockers through the subagent workflow.
---

# /recover

Drive the recovery loop via the subagent operating system.

## Steps
1. Read `CLAUDE.md`, `BEHAVIOUR_CONSTITUTION.md`, `.claude/LEGAL_AI_*_GUIDE.md`. Confirm `BEHAVIOUR CONSTITUTION READ AND ACTIVE`.
2. Inspect git status, branch, HEAD.
3. Read `tasks/PROJECT_STATUS.md` + `tasks/SUBAGENT_OPERATING_STATUS.md`.
4. `project-manager` selects the next task (`/next-task`) and assigns the owning implementation subagent.
5. Implementation subagent does the work with command proof.
6. `qa-release-gatekeeper` issues ACCEPT/REJECT.
7. Update the report (binding contract fields) + PROJECT_STATUS. Commit/push to the recovery branch.

## Rules
No fake PASS. No scope-bounded PASS. Owner-only/destructive actions are escalated, not self-performed.
