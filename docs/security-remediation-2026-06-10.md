# Security Remediation Record — 2026-06-10

## 1. Historical GitHub PAT exposure (commits 3611c37, 6c5882e, a0968b0, e165295)

Six distinct token patterns were extracted from those commits and each was
tested against `GET https://api.github.com/user` on 2026-06-10:

| Token (redacted) | Type | Result |
|---|---|---|
| ghp_FPO6iy…M3OC | classic PAT | HTTP 401 — inactive |
| ghp_vFFuRx…bW0G | classic PAT | HTTP 401 — inactive |
| github_pat…KRZB | fine-grained (partial) | HTTP 401 — inactive |
| github_pat…FZtD | fine-grained | HTTP 401 — inactive |
| github_pat…Dxtx | fine-grained (partial) | HTTP 401 — inactive |
| github_pat…46qq | fine-grained | HTTP 401 — inactive |

**Conclusion: no live credential exists in git history.** All leaked tokens are
already revoked or expired.

## 2. History rewrite decision

**Recommendation: ACCEPT history as-is.** Rationale:
- Every leaked token is verified inactive (above), so the history exposure is
  inert — rewriting removes patterns, not risk.
- A rewrite (git filter-repo/BFG + force-push) invalidates every clone, breaks
  the recorded CI evidence trail (run ↔ commit SHA mappings), and the release
  artifact provenance (image tags are commit SHAs).
- The working tree is clean (`scan-secrets-history.sh` working-tree scan: OK).

If the owner still wants the rewrite, it must be owner-executed/approved:
force-push invalidates the release evidence chain and requires re-tagging.
Owner countersign of this decision: ____________________ (name/date)

## 3. Stale external-LLM keys removed from cluster

`iterlaw-ai/lawapp-secrets` contained `ANTHROPIC_API_KEY` (28-char placeholder,
API test 401) and `OPENAI_API_KEY` (value began `sk-REPL…`, API test 401).
Both keys were **deleted from the secret** on 2026-06-10 and the staging
backend was restarted cleanly. No live external-LLM credential existed; no
provider-side revocation required. Local-Ollama-only policy now matches the
cluster state.

## 4. Auto-commit/auto-push automation — found and disabled

Root cause of the unexplained "chore: recover lawapp session and latest fixes"
commit and the historical tarball-push failures:

- A WSL **crontab entry** ran `./scripts/auto-push.sh origin "auto: 12-hour
  lawapp push"` every 12 hours (log: `reports/auto-push-cron.log`, which shows
  it repeatedly committing `.codex-clean-*.tar` files and being rejected by
  GitHub's 100 MB limit).
- The crontab entry was **removed** on 2026-06-10. The user crontab now has no
  active entries.
- The five auto-commit/push scripts (`scripts/auto_push_lawapp.sh`,
  `lawapp-push.sh`, `push-all.sh`, `push-to-github.sh`, `push-and-deploy.sh`)
  were **removed from the repo** — they enabled unreviewed pushes and the
  original PAT leak came from the "add auto push scripts" commit. They
  contained no live tokens at removal time (only scan-pattern strings).
- `.codex-clean-*.tar` files: already absent from the working tree.

Residual owner check: confirm no *other* machine/session still has a similar
cron entry or scheduled task pointing at this repo.
