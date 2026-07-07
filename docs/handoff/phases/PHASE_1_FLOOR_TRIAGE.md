# PHASE 1 - TREE STABILISATION, FLOOR TRIAGE & REAL-DEFECT CLOSURE

**Owner of this phase:** Codex (tree + backend lane) and Cursor (triage coordinator), then all agents for fixes in their own lanes.
**Precondition:** PHASE_0 hard exit signed by owner. Do not start otherwise.
**Baseline:** full Docker pytest floor on main @ bcb5240 = 1866 passed / 16 failed / 49 skipped. Current honest status: NO-GO until the 16 are triaged.

## Read first
1. `docs/handoff/LAWAPP_CURRENT_STATE.md`
2. `docs/handoff/LAWAPP_RESET_AND_EXECUTION_PLAN.md`
3. `reports/BETA_GATE_STATUS.md`

## Step 1 - Codex: stabilise the dirty main tree (blocks everything else)
1. Paste `git status` and `git stash list` BEFORE touching anything.
2. On branch `codex/tree-stabilise`, classify every dirty/untracked file (~108) into exactly one: COMMIT (real work - state which lane produced it), STASH (uncertain provenance - preserve), DISCARD (build artefacts/caches - justify each before removal).
3. Secret sweep: check for `.env*`, key material, `whsec_`, `sk_test_`, proof artifacts in staged or untracked files. If found, report the PATH only - never print contents.
4. Paste `git check-ignore -v` output for `.env.proof.local` and the Stripe proof directory.
5. Paste `git status` AFTER - target: clean tree, every file accounted for in the classification table.
6. Re-run the full Docker floor. Paste the summary line. If the numbers moved from 1866/16/49, report the delta - do not investigate or fix.

## Step 2 - Cursor: triage-only pass on the 16 failures
Classify each as ENVIRONMENT / KNOWN-BENIGN (cite the accepted-risk record) / REAL DEFECT. For each: test name, one-line root cause, classification, owning lane. NO FIXES in this pass. Priority order:
1. `test_no_unsafe_inner_html` (XSS) - paste the test and the rendering path. Determine whether user-supplied case data can reach unsafe HTML rendering. This is a hard security blocker on Art.9 data until proven a false positive.
2. The 8 UI failures - do they hit the live `client/public/` surface or the unwired Next.js scaffold? CC1's earlier spine-PASS verdict contradicts these - reconcile.
3. The intake deterministic-lane failure - the product's front door.
4. The semantic-retrieval integration failures - Ollama environment or real regression on main.
5. The embedding-family failures - confirm they are the known legacy-dimension set; cite the accepted-risk record. Reminder: the live dimension is 1024; 384 and 1536 are dead artefacts.

Output: triage table, isolated REAL-DEFECT count, recommended GO / GO-WITH-RISK / NO-GO based on real defects only.

## Step 3 - Fix pass (after owner reviews the triage table)
- REAL DEFECTS fixed only in the owning lane, each with test-level proof: Codex (backend/tests), Cursor (payment/UI), CC1 (client/workflow), CC2 (retrieval/embedding).
- ENVIRONMENT failures get a documented run-condition in the test or a skip with written justification.
- KNOWN-BENIGN failures get a written accepted-risk line in `BETA_GATE_STATUS.md`.
- CC1 must resolve the UI-vs-PASS contradiction as part of any UI fix.

## STOP conditions
Universal set from PHASE_0 applies. Additional: no mass-fixing, no refactors beyond the failing test's root cause, no scope additions.

---

## HARD EXIT - PHASE 1
All items proven with evidence in `reports/BETA_GATE_STATUS.md` before PHASE_2 may be opened:

- [ ] Main tree clean; classification table complete; secret sweep clean (paths only if found)
- [ ] `.env.proof.local` and proof directory proven gitignored
- [ ] Triage table complete for all 16 - zero unclassified failures
- [ ] XSS failure resolved with fix + passing test, OR proven false positive with the rendering path pasted
- [ ] Fresh full Docker floor on main: green, or every non-pass carries a written ENVIRONMENT/BENIGN classification
- [ ] Floor summary line pasted with commit hash
- [ ] Each fixing agent's `git diff --stat` proves lane isolation

**OWNER EXIT APPROVAL:** ____________  **Date:** ____________

No agent opens PHASE_2_OWNER_SECURITY_GATES.md until signed. PHASE_2 is owner-executed - agents are parked at this boundary.
