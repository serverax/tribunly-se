# G2 — Leaked GitHub PAT in Git History: Owner Remediation Runbook

**Status:** `G2 FAIL — PAT exposed in git history; owner-side rotation/history remediation required`
**Classification:** SECURITY OWNER-ACTION TRACKED — not a blocker for non-destructive engineering work.

## What was found

- **Working tree:** CLEAN (no secret/PAT patterns).
- **Remotes:** SSH only (`git@github.com:serverax/lawapp.git`) — no embedded credentials.
- **Git history:** a GitHub PAT pattern is present in 3 commits:
  `6c5882e`, `a0968b0`, `e165295`. (Raw token never printed; redacted everywhere.)
- Detection: `scripts/security/scan-secrets-history.sh` (now fails-closed on history hits).

## Why a remote URL change is NOT enough

Rewriting/removing the file or changing the remote does not invalidate a live credential, and the
blob remains reachable in history/forks/caches. The token must be **revoked at the source (GitHub)**,
and the history blobs purged.

## Owner remediation steps (in order)

1. **ROTATE / REVOKE the PAT first (PRIMARY, mandatory).**
   GitHub → Settings → Developer settings → Personal access tokens → revoke the exposed token(s).
   Re-issue a new token with least privilege if still needed; store it only in a secret manager /
   CI secret, never in the repo. This step alone neutralises the active risk.

2. **Purge the blobs from history (secondary, destructive).**
   ```bash
   # After rotation, on a clean checkout with all collaborators pushed:
   CONFIRM=1 bash scripts/security/remediate-git-history-pat.sh
   ```
   This builds a cleaned bare mirror with `git-filter-repo --replace-text` and verifies it is free
   of PAT patterns. It DOES NOT push.

3. **Force-push the cleaned history (owner-conscious, destructive).**
   ```bash
   cd ../lawapp-history-clean.git
   git push --force --mirror origin
   ```
   Tell all collaborators to re-clone afterwards (old clones still carry the leaked blob).

4. **Verify clean.**
   ```bash
   HISTORY_FAILS=1 bash scripts/security/scan-secrets-history.sh   # must print RESULT: PASS
   ```

5. **Invalidate forks/caches.** If the repo was ever public/forked, assume the token was harvested;
   rotation in step 1 is what actually protects you.

## CI posture

- `.github/workflows/lawapp-ci.yml` runs the working-tree secret gate (`SCAN_HISTORY=0`) on every
  build — blocks new leaks.
- The full scan (`HISTORY_FAILS=1`) correctly **fails closed** until history is purged; run it as the
  release/audit gate. Do not relax it to pass while the leak remains.

## Sign-off criteria (when G2 becomes PASS)

- [ ] PAT rotated/revoked in GitHub (owner-confirmed).
- [ ] History rewritten and force-pushed; collaborators re-cloned.
- [ ] `HISTORY_FAILS=1 bash scripts/security/scan-secrets-history.sh` → `RESULT: PASS`.
