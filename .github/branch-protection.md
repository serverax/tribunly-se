# Branch Protection

This file records the intended GitHub branch-protection posture for the repo.
It is a human-readable target, not an API-configured state.

## Protected branches

- `main`
- `main-restored`
- `release/**`

## Required rules

- Require pull request reviews before merging.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Restrict direct pushes to owners only.
- Keep linear history if the repository policy allows it.

## Required checks

- `CI / compose-config`
- `CI / lint-and-unit`
- `Docker / compose-config`
- `Docker / build-images`
- `Security / pip-audit`
- `Security / gitleaks`
- `Security / codeql (javascript)`
- `Security / codeql (python)`
- `Security / trivy`
- `Nightly Floor / full-floor`

## Notes

- Release publishes should go to GHCR only.
- The Sweden lane compose file should remain a validated input to CI.
- The `CODEOWNERS` file currently contains placeholders and must be replaced
  with real owners before branch protection is enforced.
