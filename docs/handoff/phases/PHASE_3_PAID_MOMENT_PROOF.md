# PHASE 3 - PAID-MOMENT PROOF (DOCUMENT GENERATION END-TO-END)

**Owner of this phase:** Cursor.
**Precondition:** PHASE_2 hard exit signed. New encryption key live, Art.9 fix deployed, floor green.
**Why this phase exists:** the 402 payment gate is proven, but no one has ever generated a real Particulars of Claim + Schedule of Loss from a seeded case and verified the output. The paid moment is the product. It cannot ship unverified.

## Read first
1. `docs/handoff/LAWAPP_RESET_AND_EXECUTION_PLAN.md` - Gate 3 section
2. `04_RAG_REASONING_SPEC.md` - §8 generation, structured assessment schema
3. `reports/BETA_GATE_STATUS.md`

## Task - full end-to-end run on the beta surface (`client/public/`)
Seed a realistic unfair-dismissal case, then execute the complete user journey:

**diagnosis → assessment shown → pay (£99, Stripe test mode) → generate → download**

Verify every one of the following on the produced documents:

### Particulars of Claim
- [ ] Correct legal structure per the validated template
- [ ] Populated with the seeded case's actual facts - no placeholder text, no invented facts
- [ ] Every legal assertion traces to a citation from the retrieval bundle
- [ ] Marked as a user-owned self-help draft, not legal advice
- [ ] No guarantee/outcome language, no implication of solicitor status

### Schedule of Loss
- [ ] Arithmetic correct and recomputed independently against `rules` table values (basic award, compensatory elements, caps)
- [ ] Statutory figures match the `rules` rows exactly - zero generated/recalled values
- [ ] Effective-dated rule rows selected correctly for the seeded dismissal date

### Journey integrity
- [ ] Document bytes unreachable before payment (402 gate holds in the same run)
- [ ] Payment idempotency holds on a duplicate webhook
- [ ] Per-case unlock only - a second seeded case remains locked
- [ ] Downloaded files open correctly and are complete

## Codify it
Convert the proven journey into an automated E2E test added to the floor, so this can never silently regress. Paste the new test name and a passing run.

## STOP conditions
Universal set applies. Additional: if generation produces a legally wrong document (bad structure, wrong figures, missing citations), that is a REAL DEFECT - fix in the owning lane with owner informed, re-run the full journey from scratch. Do not hand-patch the output document.

---

## HARD EXIT - PHASE 3
All items proven with evidence in `reports/BETA_GATE_STATUS.md` before PHASE_4 may be opened:

- [ ] Full journey executed on the beta surface with evidence at each step (screenshots/output paste)
- [ ] Both documents pass every verification item above
- [ ] Schedule arithmetic independently recomputed and matching
- [ ] Gate/idempotency/per-case checks held during the run
- [ ] New E2E test committed and passing on the floor (test name + summary line pasted)
- [ ] `git diff --stat` proves lane isolation

**OWNER EXIT APPROVAL:** ____________  **Date:** ____________

No agent opens PHASE_4_SURFACE_PROOF.md until signed.
