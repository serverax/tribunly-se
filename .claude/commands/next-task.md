---
description: Select and start the next lawapp task via the project-manager, assigning the correct implementation + QA subagents.
---

# /next-task

Pick the next task and route it.

## Steps
1. `project-manager` reads `tasks/PROJECT_STATUS.md` + `tasks/backlog/`.
2. Choose the highest-priority unblocked task (blockers first: G1, G2, G3, G10).
3. Move its task file `backlog/ → in-progress/`.
4. Assign the owning implementation subagent (per routing rules in `project-manager.md`).
5. For legal-data work, enforce the sequence: scraper → legal-data-engineer → db-rag-ingestion → ai-brain-citationguard → qa-release-gatekeeper.
6. Record CURRENT TASK + assigned subagent in `tasks/SUBAGENT_OPERATING_STATUS.md`.

## Output
CURRENT TASK / IMPLEMENTATION SUBAGENT / QA SUBAGENT / TASK FILE — and the first action.
