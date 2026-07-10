# CI/CD

This repository uses a tiered pipeline:

1. `CI` runs fast checks on every push and pull request.
2. `Docker` validates both compose files and builds the repo images.
3. `Security` runs secret scanning, dependency auditing, CodeQL, and Trivy.
4. `Nightly Floor` boots the stack and runs the full proof chain.
5. `Release` publishes immutable images to GHCR only.

## Local checks

Run the shared local entrypoints from the repo root:

```bash
bash scripts/ci-check.sh compose-only
bash scripts/ci-check.sh
```

```powershell
powershell -File scripts/ci-check.ps1 compose-only
powershell -File scripts/ci-check.ps1
```

## Compose validation

Both compose files are validated in CI:

- `docker-compose.yml`
- `docker-compose.se.yml`

The Sweden compose file is checked with the same placeholder environment values
used by the workflows so it can be parsed on a clean runner.

## Branch protection

Protect at least these branches:

- `main`
- `main-restored`
- `release/**`

Required checks should include:

- `CI / compose-config`
- `CI / lint-and-unit`
- `Docker / compose-config`
- `Docker / build-images`
- `Security / pip-audit`
- `Security / gitleaks`
- `Security / trivy`
- `Security / codeql`
- `Nightly Floor / full-floor`

## Release policy

- Publish to GHCR only.
- Keep release images immutable.
- Do not allow direct pushes to protected branches.
- Do not treat nightly runs as a release substitute.
