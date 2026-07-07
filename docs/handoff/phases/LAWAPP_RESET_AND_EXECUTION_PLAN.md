# LAWAPP - RESET REVIEW & FINAL EXECUTION PLAN (v2 - POST-RECOVERY)

**Status:** AUTHORITATIVE. Supersedes every prior handoff, kickoff, status doc, and v1 of this plan. Any document claiming "no application code written", "Phase 1 not started", or root `E:\lawapp` is dead - agents handed one must stop and request this file.
**Project root:** `F:\lawapp-restore`, branch `main-restored`, tracking `origin/release/lawapp-clean-snapshot` @ `8432368` (GitHub: `github.com/serverax/lawapp`).
**Forbidden paths:** `E:\lawapp`, `F:\lawapp`, `F:\lawapp-ingestion`, `F:\SakinaAL` - never read or write.
**Forbidden refs:** `origin/master` and `origin/main` are stale lines - never base work on them.
**Owner:** Khalid. Sole decision-maker.
**Objective:** verify the recovered near-beta build, close the remaining gates in order, ship a controlled beta - UK employment law, unfair dismissal, England & Wales only.

---

## PART 1 - STATE AFTER RECOVERY

### 1.1 What the recovery established
The local working tree was destroyed in July 2026. The project survived on GitHub. Forensics confirmed `origin/release/lawapp-clean-snapshot` @ `8432368` (18 June 2026) is the true near-beta state - roughly 100 commits ahead of the stale `origin/main` @ `bcb5240`. Its history contains: the data spine and licensed corpus expansion (legislation.gov.uk + ACAS, OGL), the 1024-dim embedding standardisation and RAG repair with verification proof, ADR-000 single-brain enforcement with the LangGraph rollback completed, formal scope-cut fencing of the 13 partial employment modules (`6bd8bdd`), beta UI scope enforced to 11 production employment topics (`8fb5459`), Track A GO WITH RISK + Track B completion evidence, the responsive Case OS shell, beta-blocker fixes, a secrets-rotation pass (`b1c65de`), and a full evidence trail in `reports/`.

### 1.2 Known losses (bounded)
Two branches were never pushed and died with the old disk: `cc2/ingestion-metadata-repair` (5198f8f, Art.9 embed_query redaction) and `feature/beta-gate-dashboard` (231e39c, gate dashboard + payment hardening suite). The snapshot's own history covers adjacent ground (special-category persistence stripped at `970a41f`, secrets rotation, RAG verification) - PHASE_0 Task 0.3 verifies exactly what survived at tip. Anything genuinely missing gets rebuilt from the documented specs, not from memory. `reports/BETA_GATE_STATUS.md` and `docs/handoff/LAWAPP_CURRENT_STATE.md` also never reached the remote - the snapshot carries its own handoff set (`docs/handoff/HANDOFF.md`, `RELEASE_STATE.md`, `KNOWN_ISSUES.md`, `NEXT_TASKS.md`, `PROOF_INDEX.md`), which is newer and replaces them; a fresh `LAWAPP_CURRENT_STATE.md` is created in PHASE_0.

### 1.3 Void baselines
All pre-recovery floor numbers (including 1866/16/49) belonged to a destroyed tree and are VOID. The new baseline is whatever the full Docker pytest floor returns on `main-restored` in PHASE_0 Task 0.5. All pre-recovery file paths and branch names are equally void.

### 1.4 Open owner decisions
- **Price discrepancy:** repo history shipped £29.99 (`263966a`); the owner's decision on record was £99. Verify the live config value in PHASE_0, then owner reconfirms one figure. Single tunable config value, per-case unlock, idempotency required, honest non-subscription copy.
- **ENCRYPTION_KEY:** a Fernet key was previously pasted into chat - treat as exposed. A rotation commit (`b1c65de`) exists in the snapshot; PHASE_2 verifies whether the live key post-dates the exposure and rotates regardless if uncertain.

---

## PART 2 - LOCKED DECISIONS (do not relitigate)

- **D1 - Beta scope frozen:** unfair dismissal, England & Wales, only. No new features, modules, or refactors outside the phase files until beta ships.
- **D2 - The 13 partial modules stay CUT from beta.** The snapshot already fences them (`6bd8bdd`); PHASE_0 re-proves the fencing at tip. Out-of-scope queries return "not supported" - never a guess. Post-beta: finish to production standard in batches using the rules-spine source-verification method, or delete. No third state.
- **D3 - Stripe test mode only** behind controlled access. Live keys permanently owner-gated.
- **D4 - No bulk case-law ingestion** until the FCL computational-analysis licence is granted. No alternative bulk source. OGL sources (legislation.gov.uk, gov.uk, ACAS) remain permitted.
- **Architecture holds:** modular monolith, single brain per ADR-000, 1024-dim local embeddings via Ollama, Postgres + pgvector, local Docker only, Fernet encryption, static `client/public/` as the beta surface.

---

## PART 3 - THE PHASE SEQUENCE

Executed via the six phase files at `docs/handoff/phases/`. Each ends with a HARD EXIT the owner signs before the next opens.

- **PHASE 0 - Baseline verification & doc hygiene** (Codex): repo identity, survival checks, NEW floor baseline, price evidence, authoritative state doc, SUPERSEDED sweep, 13-module fencing re-proof.
- **PHASE 1 - Floor triage & real-defect closure** (Cursor coordinates, all lanes fix): classify every floor failure ENVIRONMENT / KNOWN-BENIGN / REAL DEFECT against the NEW baseline; any XSS or injection finding on Art.9 data is a hard blocker; fix real defects only, in-lane, with proof.
- **PHASE 2 - Owner security gates** (Khalid only): encryption-key verification/rotation into an untracked secret file; Stripe webhook round-trip proof (test mode, redacted artifacts); confirm Art.9 redaction live on the embed path or dispatch its rebuild.
- **PHASE 3 - Paid-moment proof** (Cursor): full journey diagnosis -> pay -> generate -> download; Particulars of Claim + Schedule of Loss verified for structure, real facts, citations, and rules-exact arithmetic; codified as a floor E2E test.
- **PHASE 4 - Surface proof** (CC1): responsive width matrix (360/390/768/1024/1440) on `client/public/`; WCAG 2.2 AA with P1 fixes; workspace persistence; deadline WASM live recalc; legal notices on every surface; guarantee-language grep = zero. Existing snapshot evidence (`a11y_mobile_audit_cursor.txt`, Case OS responsive proofs) may be verified rather than redone - but must be re-proven at tip.
- **PHASE 5 - Beta ship** (Khalid): pre-flight checklist, final floor run, tag, deploy, phone + laptop smoke test, controlled audience.

**Post-beta backlog, in order - do not pull forward:** DPIA (incl. the logged clinical free-text/local-embedder decision) -> FCL licence application -> 13-module finish-or-cut batches -> corpus expansion + load testing -> SEO command integration (GSC + GA4, read-only) -> live Stripe (owner-gated) -> Phase 4 depth features -> referrals/B2B.

---

## PART 4 - RULES OF EXECUTION

**Universal STOP conditions (all agents):**
- Never push, merge, or deploy to any remote. Owner only.
- Never rotate, generate, print, or request secrets. Key material found = path only, never contents.
- Never touch the forbidden paths or base work on the forbidden refs.
- Own branch only; lane isolation proven by `git diff --stat` at every hard exit.
- Every claim backed by pasted command output + evidence file paths. Assertions without evidence are rejected.
- Legal values come from the `rules` table or live official sources - never model memory.
- Stale doc detected -> stop, cite this plan, request confirmation.

**Working method:** one phase in an agent's hands at a time. Audit-fix-verify loop mandatory. Proof over assertion. Stop at phase boundaries and report against the hard exit. Flag, don't guess.

---

## PART 5 - DEFINITION OF BETA LIVE

All true simultaneously, evidenced in the state doc / gate dashboard:
1. Floor green on `main-restored` (or every non-pass carries a written classification); no open security findings.
2. Encryption key verified clean or rotated; no secrets in any artifact, log, or chat.
3. Stripe test-mode round-trip proven with redacted artifacts.
4. Art.9 redaction live on the embed path in the running service.
5. Real PoC + Schedule of Loss generated end-to-end, verified, locked in as an E2E test.
6. Responsive and accessible on the width matrix; notices on every surface; honest coverage labels (unfair dismissal only, beta, test-mode payments).
7. Price reconfirmed by owner and consistent across homepage, checkout, and config.
8. Owner has performed the deploy and passed the phone + laptop smoke test.
