
# Known issues (snapshot)

## Open bugs

- AKS kubeconfig host not resolving from this environment (blocks remote ops).

## Technical debt

- Stale handover docs flagged in `docs/07_PROJECT_HANDOVER.md`; active release context on `release/lawapp-clean-snapshot`.
- Untracked `_wt_feat/` directory in working tree.

## Failing tests

- Not executed in this handoff finalization pass (UNKNOWN - requires verification).

## Missing integrations

- Remote deployment visibility while offline from cluster.

## Data ingestion gaps

- Not re-audited in this pass; prior commit message references 084 e2e blocker documentation (see git history).

## Legal data verification

- Verification gate remains mandatory; no new curated promotions in this docs-only commit.

## Unstable pipeline components

- UNKNOWN - requires verification on connected environment.
