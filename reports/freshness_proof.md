# Source Freshness Proof — WO009 Task 3

**Date:** 2026-07-09  
**Command:** `docker compose run --rm ingestion python -m ingestion.freshness.report --stale-days 30 --json`

## Report Output

| Source | Type | Jurisdiction | Rows | Stale | Age (days) | Status |
|--------|------|-------------|------|-------|-----------|--------|
| acas_guidance | acas | GB | 2 | 0 | 1 | OK |
| legislation | legislation | GB | 84 | 0 | 1 | OK |
| legislation | legislation | EW | 2982 | 0 | 0 | OK |
| rules | rules | GB | 125 | 0 | 1 | OK |

**All sources fresh.** 0 stale rows across all tables.

## ERA 2025 Commencement Watch

Status: **No commencement SI found** — provisional values remain suppressed (`is_prospective = true`).

Note: DNS resolution fails from inside the container (no internet in compose network). In production with internet access, the check hits `legislation.gov.uk/id?title=Employment+Rights+Act+2025+(Commencement)` to detect when commencement SIs are published.

## Infrastructure

- **Service:** `freshness-monitor` in `docker-compose.yml` (profile: `monitoring`)
- **Interval:** 7 days (configurable via `FRESHNESS_INTERVAL_SECONDS`)
- **Stale threshold:** 30 days (configurable via `FRESHNESS_STALE_DAYS`)
- **JSON output:** Written to `reports/freshness_latest.json` on each run
- **ERA 2025 watch:** Automatic — checks legislation.gov.uk for commencement SIs

## Activation

```bash
docker compose --profile monitoring up -d freshness-monitor
```
