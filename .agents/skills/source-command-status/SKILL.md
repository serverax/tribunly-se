---
name: "source-command-status"
description: "Print the lawapp recovery status board  -  blockers, owners, current task, QA verdict."
---

# source-command-status

Use this skill when the user asks to run the migrated source command `status`.

## Command Template

# /status

Show the current recovery state.

## Steps
1. Read `tasks/PROJECT_STATUS.md` and `tasks/SUBAGENT_OPERATING_STATUS.md`.
2. Read the latest `reports/hard-exit/lawapp-hard-exit-repair-report.md`.
3. Summarise: each blocker (G1, G2, G3, G10, hook, UI, auth, payment, microservices, 10k) → status + owning subagent.
4. State the current active task, assigned implementation subagent, and QA verdict.

## Output
A concise board: blocker → status → owner → evidence path. End with overall verdict (READY / NOT READY)  -  never fake.
