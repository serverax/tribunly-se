# Merge Readiness

Repo: `F:\tribunly-se`
Branch: `cc/convergence`
Base: `main-restored@526cbcc`

## Probe Summary

The merge-base check shows `main-restored` is still the shared ancestor:

```text
git rev-parse --verify main-restored
526cbccdf9ade651fa8157316f13c183e01ae520

git rev-parse --verify cc/convergence
a7bf636f8e3bca20f7900d240a2a3bd053cc5dee

git merge-base main-restored cc/convergence
526cbccdf9ade651fa8157316f13c183e01ae520
```

The throwaway worktree merge probe completed without conflicts:

```text
git worktree add F:\merge-probe main-restored
git -C F:\merge-probe merge --no-commit --no-ff origin/cc/convergence
Automatic merge went well; stopped before committing as requested
```

`git -C F:\merge-probe status --short` showed the full staged merge result and no conflicted files. The probe therefore reports:

- Conflict count: `0`
- Protected-file conflict count: `0`
- Merge state: clean, staged only because `--no-commit` was requested

The diffstat between the target base and the feature branch is large but clean:

```text
git diff --stat main-restored..cc/convergence
122 files changed, 17558 insertions, 191 deletions
```

## Owner Execution Sequence

1. Confirm the floor is green on the Sweden branch.
2. Create a merge tag on `main-restored` before any integration step.
3. Merge `cc/convergence` into `main-restored` with a no-commit dry run first.
4. If the dry run matches this probe, commit the merge and push fast-forward only.
5. If anything diverges, abort, tag the pre-merge state, and stop for review.

## Rollback Plan

- `git merge --abort` if the merge stops for any reason.
- Remove the temporary probe worktree after every simulation.
- Keep the pre-merge tag so the owner can restore the exact starting point.

## Evidence

- Merge-base and diffstat: pasted above.
- Worktree probe: `F:\merge-probe`.
- Conflict-free merge output: pasted above.
