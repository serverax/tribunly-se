# PHASE 2 - OWNER SECURITY GATES (v2 - RECOVERED TREE)

**Owner of this phase:** Khalid only. Agents perform read-only support where named. No agent executes any step in this file.
**Precondition:** PHASE_1 hard exit signed. Floor triaged on `main-restored`, main tree clean, merges safe.
**Root:** `F:\lawapp-restore`, branch `main-restored` (base `8432368`).

## Read first
1. `docs/handoff/phases/LAWAPP_RESET_AND_EXECUTION_PLAN.md` - Part 1.4 and Phase 2 section
2. `docs/handoff/LAWAPP_CURRENT_STATE.md` (created in Phase 0)
3. `scripts/proof/prove_lawapp_full_workflows.sh` - this tree's payment/workflow proof script

## Task 1 - ENCRYPTION_KEY verification and rotation
Context: a Fernet key was pasted into a chat session in the past - treat as exposed. The snapshot contains a secrets-rotation commit (b1c65de), but whether the LIVE key post-dates the exposure is unproven.
1. Determine whether the currently configured encryption key is the one rotated at b1c65de or the exposed one. If there is any uncertainty at all, rotate.
2. Rotation procedure: confirm the secrets file is untracked (git check-ignore <path> - establish the path from the repo's env template, do not invent one). Generate a new 44-char urlsafe-base64 Fernet key LOCALLY. Never paste it into any chat, prompt, or log.
3. Handle data sealed under the old key per the repo's encryption/migration notes: re-encrypt or invalidate. Record which path was taken.
4. Retire the old key everywhere it lived.

## Task 2 - Stripe webhook round-trip proof (test mode only)
1. Locate the payment proof path in scripts/proof/prove_lawapp_full_workflows.sh (webhook section near line 384) and any dedicated webhook proof script this tree carries.
2. Before running: verify the script never echoes secrets, and that any log/tee capture of Stripe CLI output redacts whsec_ values. If a redaction gap exists, dispatch Cursor to patch the script first - do not run with a known leak.
3. Confirm the proof output directory is gitignored.
4. Place the sk_test_ key in the untracked secrets file - never in chat.
5. Run the proof. Verify the full round-trip: checkout event -> webhook received -> signature verified -> case unlocked.
6. Search the produced artifacts for whsec_ and sk_test_ - both must return zero hits before archiving.

## Task 3 - Art.9 redaction live verification
Phase 0 located redaction code on the embed path (backend/services/lawapp-rag-service/ollama_embed.py, main.py:261, backend/core/deidentify.py). Code present is not proof it fires at runtime.
1. Bring the stack up locally (Docker).
2. Send a test query containing synthetic personal identifiers (fake name, fake email, fake employer) through the diagnosis path.
3. Capture the outbound body to the embedder and the Redis cache keys. Assert: raw identifiers ABSENT, redaction placeholders PRESENT.
4. CC2 (support, read-only) may script and run this proof - but only the owner starts/stops the stack and holds the env.
5. If redaction does NOT fire: STOP. That is a P0 - dispatch CC2 with a repair order before this phase can close.

## STOP conditions
- Live Stripe keys: never. Test mode only, permanently owner-gated beyond beta.
- Any secret appearing in any artifact: stop, purge the artifact, fix the leak source, re-run.
- Merge conflicts or floor breakage during this phase: stop and dispatch the owning agent - never force.

---

## HARD EXIT - PHASE 2
All items proven with evidence recorded in docs/handoff/LAWAPP_CURRENT_STATE.md before PHASE_3 may be opened:

- [ ] Encryption key verified post-exposure or rotated; old key retired; sealed-data handling recorded
- [ ] No key material has appeared in any chat, prompt, artifact, or log
- [ ] Stripe test-mode round-trip proven end-to-end; artifacts verified clean of whsec_ and sk_test_
- [ ] Art.9 redaction proven firing at runtime on the live local stack (outbound body + cache evidence)
- [ ] Floor still green on main-restored after any changes (summary line pasted)

**OWNER EXIT APPROVAL:** ____________  **Date:** ____________

No agent opens PHASE_3_PAID_MOMENT_PROOF.md until this approval line is signed.
