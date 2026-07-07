# PHASE 5 - BETA SHIP

**Owner of this phase:** Khalid only. Deploy is the permanently owner-gated action - no agent executes anything in this file.
**Precondition:** PHASE_0 through PHASE_4 hard exits all signed, all green in `reports/BETA_GATE_STATUS.md`.

## Pre-flight checklist (verify each against the dashboard, do not trust memory)
- [ ] PHASE_1: floor green or fully classified; XSS closed with evidence
- [ ] PHASE_2: new key live, old key retired; Stripe test-mode proof clean; Art.9 redaction live in production rag-service
- [ ] PHASE_3: real PoC + Schedule of Loss generated end-to-end, verified, and locked in as a floor E2E test
- [ ] PHASE_4: responsive matrix clean, P1 accessibility fixed, persistence and deadline recalc proven, notices on every surface, guarantee-grep zero
- [ ] Coverage labels honest: unfair dismissal only, beta, test-mode payments
- [ ] All 13 partial modules still unreachable (re-verify - regressions happen)
- [ ] `BETA_GATE_STATUS.md` fully green with evidence links

## Ship steps (owner)
1. Final full Docker floor run on the exact commit to be deployed. Paste the summary line into the dashboard with the commit hash.
2. Tag the release commit.
3. Deploy to the controlled beta environment.
4. Smoke-test the live deployment yourself, on a phone and a laptop: land → free diagnosis → honest assessment + deadline → pay (test mode) → download both documents. Every step must work on both devices.
5. Record the deployed commit hash, date, and smoke-test result in `BETA_GATE_STATUS.md`.
6. Open beta to the controlled audience.

## Definition of BETA LIVE (all true simultaneously)
1. A real user completes the full journey on mobile and desktop.
2. Every legal output cites its source; statutory figures come only from `rules`.
3. Weak/no-claim outcomes stated plainly; out-of-scope returns "not supported".
4. No secrets in any artifact, log, or chat. Test-mode keys only.
5. "Not a law firm / not legal advice" on every surface.
6. The dashboard shows the evidence trail for every phase exit.

## After ship - the post-beta backlog (in order, do not pull forward)
1. Phase 5 DPIA - includes the clinical free-text / local-embedder design decision already logged.
2. FCL computational-analysis licence application (owner submits; no bulk case-law until granted).
3. 13-module finish-or-cut batches using the rules-spine source-verification method. Finish to production standard or delete - no third state.
4. Corpus expansion + load testing (Track B).
5. SEO command dashboard integration per `07_SEO_COMMAND_INTEGRATION_ORDER.md` (GSC + GA4, read-only, service-account auth).
6. Live Stripe (owner-gated), then Phase 4 depth features (upload/extraction, full bundle, timeline), then referrals/B2B.

---

## HARD EXIT - PHASE 5
- [ ] Deployed commit hash + tag recorded
- [ ] Owner smoke-test passed on phone and laptop (evidence noted)
- [ ] Dashboard fully green with the deploy record
- [ ] Beta audience has access

**OWNER SHIP SIGN-OFF:** ____________  **Date:** ____________

Signing this line means the beta is live. The next work order is item 1 of the post-beta backlog - nothing else.
