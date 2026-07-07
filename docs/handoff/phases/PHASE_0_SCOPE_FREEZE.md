# PHASE 0 - SCOPE FREEZE & DOC HYGIENE

**Owner of this phase:** Khalid (decisions) + CC1 (doc work)
**Precondition:** none - this is the entry phase.
**Project root:** `F:\lawapp`. `E:\lawapp` is a dead archive - never touch. `F:\SakinaAL` is unrelated - never touch.

## Read first
1. `docs/handoff/LAWAPP_CURRENT_STATE.md`
2. `docs/handoff/LAWAPP_RESET_AND_EXECUTION_PLAN.md`

Any doc claiming "no application code written", "Phase 1 not started", or root `E:\lawapp` is SUPERSEDED. Stop reading it, report it, do not act on it.

## Locked decisions (already made - do not relitigate)
- D1: Beta scope = unfair dismissal, England & Wales, only. No new features, modules, or refactors outside the phase files until beta ships.
- D2: All 13 partial modules CUT from beta. Feature-flag or branch-park them. Out-of-scope queries return "not supported" - never a guess.
- D3: Beta ships in Stripe test mode behind controlled access. Live keys permanently owner-gated.
- D4: No bulk case-law ingestion until the FCL computational-analysis licence is granted. OGL sources remain fine.

## Tasks (CC1)
1. Verify `LAWAPP_CURRENT_STATE.md` reflects the reset plan and decisions D1-D4. Patch if not - paste the diff.
2. Add a SUPERSEDED banner referencing the reset plan to every stale doc, including the old kickoff handoff wherever it exists in the repo. List each file marked.
3. Verify all 13 partial modules are unreachable from the beta surface (`client/public/`). Paste route/flag evidence per module.
4. Confirm the six phase files (PHASE_0 to PHASE_5) are saved at `docs/handoff/phases/` and committed on your branch.

## STOP conditions (all phases, all agents)
- Never push, merge, or deploy to main. Owner merges and deploys.
- Never rotate, generate, print, or request secrets.
- Never touch `E:\lawapp` or `F:\SakinaAL`.
- Own branch only. Prove lane isolation with `git diff --stat` at exit.
- Every claim needs pasted command output + evidence file paths. Assertions without evidence are rejected.
- Legal values come from the `rules` table or live official sources - never model memory.
- Stale doc detected → stop, cite the reset plan, request confirmation.

---

## HARD EXIT - PHASE 0
All items proven with evidence recorded in `reports/BETA_GATE_STATUS.md` before PHASE_1 may be opened:

- [ ] One authoritative state doc exists and matches the reset plan (diff or "no change needed" pasted)
- [ ] Every stale doc carries a SUPERSEDED banner (file list pasted)
- [ ] All 13 partial modules proven unreachable from the beta surface (evidence per module)
- [ ] Phase files committed at `docs/handoff/phases/` (commit hash pasted)
- [ ] `git diff --stat` proves no files touched outside CC1's lane

**OWNER EXIT APPROVAL:** ____________  **Date:** ____________

No agent opens PHASE_1_FLOOR_TRIAGE.md until this approval line is signed and the checklist is green in BETA_GATE_STATUS.md.
