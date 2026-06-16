---
name: "source-command-load-readiness"
description: "Measure lawapp readiness for the 10k concurrent-user target  -  load test + resource/headroom evidence."
---

# source-command-load-readiness

Use this skill when the user asks to run the migrated source command `load-readiness`.

## Command Template

# /load-readiness

Assess scale readiness.

## Steps
1. `platform-devops-scale-agent` reads `tasks/LOAD_TARGET_10K.md`.
2. Run a load test against a representative endpoint (e.g. `/health`, `/assess`) at increasing concurrency.
3. Record throughput, p50/p95/p99 latency, error rate, resource use.
4. Identify bottlenecks (DB pool, workers, replicas) + remediation.
5. State whether the 10k target is met with evidence (never assume).

## Output
Load numbers table + bottleneck list + PASS/FAIL against the 10k target.
