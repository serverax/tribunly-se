# WO015 Progress

- Flag in summary, not buried in pasted output: any future evidence showing public repo visibility, exposed ports beyond intended lane scope, or licence/re-use anomalies.
- P0 visibility status as of 2026-07-10: `serverax/tribunly-se` still reports `isPrivate=false` via `gh repo view`; this is an active security finding until the owner flip is confirmed.
- P1 `infra/k8s` consumption check: kept for now because it is referenced outside its own tree by deployment scripts and GitHub workflows.
- A0 rename accounting note: the fact of the move to `serverax/tribunly-se` is proven by the current remote and GitHub repo metadata, but the actor and exact moment of the `origin` URL change are not recoverable from local git history alone because remotes are stored in `.git/config`, not commit history.
- Earliest repo-side rename signal found locally: commit `5c05c6b` (`lawapp CI: fix DB auth + rename workflow + add connectivity check`); this is evidence of rename-era activity, not proof of who changed `origin`.
