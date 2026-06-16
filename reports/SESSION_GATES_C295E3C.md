# LawApp Session Gates  -  c295e3c

**Date:** 2026-06-16  
**Repo:** `F:\lawapp`  
**Branch:** `release/lawapp-clean-snapshot`  
**HEAD:** `c295e3c`

## One-line verdicts

| Gate | Verdict |
|------|---------|
| 1  -  Stack + docker pytest | **PASS** |
| 2  -  Live legal accuracy (Ollama) | **FAIL** |
| 3  -  k6 load test (50 VU) | **FAIL** |
| 4  -  Migration 075 + bootstrap | **PASS** |
| 5  -  Gatekeeper re-review | **REJECT** |

## Artifact files

1. `reports/pytest_docker_full_c295e3c.txt`
2. `reports/legal_accuracy_live.txt`
3. `reports/k6_100k_readiness_post_repair.txt`
4. `reports/bootstrap_gate4_c295e3c.txt`

Additional: `reports/legal_accuracy_live_console_rerun.txt`, `docs/qa/GATEKEEPER_TRACK_AB_VERDICT.md`

---

## Gate 1  -  Stack + full docker pytest

**PASS**  -  `1728 passed, 48 skipped` in 406s (initial run). A later full-suite rerun failed **1** test (`test_brain_outbox`) because the **backend image was stale**; after `docker compose build backend`, that test passes. Re-run full suite after image rebuild to refresh the artifact.

```text
docker compose up -d
curl localhost:8000/health → ok, db connected, auth jwt, payment test
docker compose run --rm backend python -m pytest tests/ -q
```

**Stack note:** 13 compose services up; `lawapp-graph-rag-service` in restart loop (not gate-blocking for pytest).

### Fixes applied (gate 1 repair batch)

| Fix | File / action |
|-----|----------------|
| Copy `.gitignore`, `.env.example`, `.github` into backend image | `Dockerfile` |
| Outbox worker tolerates JSONB as dict or string | `backend/core/outbox_worker.py` |
| Rules `verification_status` invalid enum → `verified` | DB SQL (11 rows) |
| `corpus_chunks.jurisdiction_code` NULL → `GB` | DB SQL (26 rows) |
| Legislation embeddings backfill | `ingestion.embeddings.embedder --table legislation` |

---

## Gate 2  -  Live legal accuracy with Ollama

**FAIL**  -  script exit 0 is misleading; live generative path not proven.

- Ollama: `docker compose --profile ollama up -d`; model `qwen2.5:3b` pulled
- `python scripts/run_legal_accuracy.py --live` with `LAWAPP_OLLAMA_MODEL=qwen2.5:3b`
- **FLAG:** `Local inference unavailable (timed out)` ×2 → `fallback_used=True`, `source=rules_table`
- Grounded/refusal outputs are **rules-backed and correct in substance** but **not from live LLM**
- Default model id `qwen2.5-3b-instruct` 404s against pulled tag; patched caller to use `qwen2.5:3b` in `scripts/run_legal_accuracy.py`
- **P0-002, P0-003, P0-008 NOT closed**

---

## Gate 3  -  k6 with load-test mode

**FAIL**  -  rate-limit repair works; latency threshold breached.

```text
LAWAPP_LOAD_TEST_MODE=1 docker compose up -d backend
k6 run scripts/load/k6_100k_readiness.js
```

| Metric | Result | Threshold |
|--------|--------|-----------|
| `assessment responds 200` | 100% | >90% ✓ |
| `http_req_failed{type:assess}` | 0% | <2% ✓ |
| `http_req_duration{type:assess}` p95 | **36.93s** | <3s ✗ |

**Assessment:** At 50 VU, assess is functionally stable (no 429 on assess with load-test mode) but **far too slow** for readiness target  -  genuine product/infra issue (heavy synchronous pipeline, possible Ollama timeout under concurrent load). Login bad-creds check 25% pass under load (secondary).

---

## Gate 4  -  Migration 075 cold bootstrap

**PASS**

- `_migrations` contains `075_official_guidance_multi_chunk.sql`
- `official_guidance_source_url_key` unique constraint removed (multi-chunk per URL allowed)
- `docker compose run --rm db-bootstrap` → exit 0, `Bootstrap complete.`
- `corpus_chunks` count: **941** (added 14 this run)

---

## Gate 5  -  Gatekeeper

**REJECT**  -  Gate 1+4 pass; Gates 2+3 fail. See `docs/qa/GATEKEEPER_TRACK_AB_VERDICT.md`.

---

## Regressions / flags

- **No Track A pytest regressions** (gate 1 green vs prior repair intent)
- **Live accuracy:** no wrong legal answers observed, but **not live-model proven**
- **k6:** assess latency p95 ~37s @ 50 VU
- **graph-rag-service** unhealthy (pre-existing)

## Out of scope (untouched)

Corpus 1000, a11y, scope-cut pages, Track C, push to main, secret rotation.
