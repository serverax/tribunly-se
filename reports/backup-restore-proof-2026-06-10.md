# Backup & Restore Proof — 2026-06-10

## Backups taken

| Instance | Command | Artifact | Size |
|---|---|---|---|
| `lawapp-rag/lawapp-postgres-0` (data spine: rules, corpus, brain traces) | `pg_dump -U lawapp_user -d lawapp --format=custom` | `.local/backups/lawapp-rag-20260610T213819Z.dump` | 3.4 MB |
| `lawapp-api/lawapp-postgres-0` | `pg_dump -U lawapp -d lawapp --format=custom` | `.local/backups/lawapp-api-20260610T213819Z.dump` | 116 KB |

## Restore proof (spine backup)

Restored `lawapp-rag-20260610T213819Z.dump` into a fresh database
(`lawapp_restore_test` on the local Docker Postgres) with `pg_restore
--no-owner`. Exit code 0, zero errors. Row-count verification, source vs
restored:

| Table | Source | Restored | Match |
|---|---|---|---|
| rules | 24 | 24 | ✅ |
| corpus_chunks | 903 | 903 | ✅ |
| brain_traces | 15 | 15 | ✅ |
| legislation | 22 | 22 | ✅ |

## Gaps / owner items

- These are **manual one-off backups**. A scheduled backup (CronJob pg_dump to
  off-cluster storage, e.g. S3/restic) plus retention policy is still required
  before public launch. The backup currently lives on the operator
  workstation only (`.local/` is git-ignored).
- The cluster's shared Prometheus (ordinox-monitoring) is CrashLoopBackOff
  (`/prometheus/queries.active: permission denied` on its local-path PVC —
  fix is a chown to 1000:2000 on the volume, which is outside lawapp's
  namespace authority). Until the owner heals it, alert evaluation for the new
  `lawapp-alerts` PrometheusRule is inactive; operational monitoring is
  provided by the lawapp-monitoring CronJobs:
  - health probe (every 5 min) — PASS (HTTP 200) on 2026-06-10
  - E2E smoke (every 15 min) — PASS (rules-sourced deadline, no PII) on 2026-06-10
  - freshness check (daily), legal accuracy check (daily)
