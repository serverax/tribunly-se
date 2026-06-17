# Release State

Generated: 2026-06-18
Branch: `release/lawapp-clean-snapshot`

## HEAD verification

| Ref | SHA | Match |
|-----|-----|-------|
| Local HEAD | `4209216` | — |
| `origin/release/lawapp-clean-snapshot` | `4209216` | Yes |
| Branch sync | 0 ahead / 0 behind | Yes |

Latest commit message: `fix(rag): align semantic retrieval with corpus_chunks 1024-dim plane`

## Working tree

Handoff docs may be modified during reconcile pass; code tree clean at `4209216`.

## RAG repair status

- **Shipped / provisionally complete** @ `4209216`.
- RAG 1024-dim repair appears shipped at `4209216`; verification should be re-run before beta promotion.
- Historical proof: `reports/rag_1024_retrieval_repair.txt` (exists; refresh required).
- **Required next step: verification, not fresh repair.**

## Embed proof (978/978 @ 1024-dim)

| Source | Result |
|--------|--------|
| Live DB (`localhost:5435`) | 978 rows, 978 embedded, max dim 1024 |
| `reports/prod_embed_hardening_cursor.txt` | 972 re-embedded + 6 prior; sync idempotent |
| `reports/BETA_PROMOTION_REVIEW.md` | Gate summary + beta NO recommendation |
| `scripts/reembed_corpus_1024.py` | Hardened (truncation retries, skip already-1024) |

**Beta ready:** No — corpus + retrieval plane aligned @ `4209216`; verification proof re-run and human review pending.

## RAG blockers (resolved @ 4209216)

1. ~~`retrieve_semantic` gated on empty `legislation.embedding`~~ → uses `corpus_chunks` 1024-dim.
2. ~~RAG service 384-dim query embed~~ → Ollama `bge-large-en-v1.5` 1024-dim (`ollama_embed.py`).
3. **Open (non-blocking):** source tables still `vector(384)`; corpus plane is authoritative for search.

## DB password note (operator)

| Context | Password | Port |
|---------|----------|------|
| Docker pgdata volume (initialized) | `lawapp` | 5435 host map |
| Host `.env` (gitignored) | `change_this_password` | 5432 default |
| `verify_ingestion_084.py` default | `lawapp` | 5435 |

**Safe host override:**

```powershell
$env:DATABASE_URL="postgresql://lawapp:lawapp@localhost:5435/lawapp"
```

Documented in: `.env.example`, `.env.docker.example`, `docs/qa/LAWAPP_DOCKER_TEST_ENV.md`, `reports/prod_embed_hardening_cursor.txt`.

## Gate status (reference bundle)

From `reports/beta_gate_evidence_unified.txt` (stamp @ 97a405b; release now @ `4209216`):

| Gate | Status |
|------|--------|
| C Case OS beta | PASS |
| D Ingestion 084 | PASS (re-run after RAG fix recommended) |
| E Grounding / CitationGuard | PASS |
| F i18n + domain fail-closed | PASS |
| SB Single Brain ADR-000 | PASS (16 pytest historical) |

## Pytest (release @ 4209216)

Historical from `reports/rag_1024_retrieval_repair.txt`:

```text
python -m pytest tests/test_rag_1024_retrieval_repair.py tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
21 passed
```

Re-run required as part of verification checklist.

## Next verification (release line)

1. Run RAG 1024 verification checklist (see [NEXT_TASKS.md](./NEXT_TASKS.md)).
2. Re-run `verify_ingestion_084.py` with `DATABASE_URL=postgresql://lawapp:lawapp@localhost:5435/lawapp`.
3. Rebuild RAG container if pulled on another host: `docker compose build lawapp-rag-service && docker compose up -d lawapp-rag-service`.
4. Refresh `/api/rag/search` API proof and update `reports/BETA_PROMOTION_REVIEW.md` after owner review.

**Do not push to `main`.** Commit on `release/lawapp-clean-snapshot`; owner merges.

## Docker / Ollama (from evidence reports)

- Profile: `docker compose --profile ollama up -d db ollama`
- Model alias workaround: `ollama cp mxbai-embed-large bge-large-en-v1.5` when direct pull fails
- Re-embed duration ~155 min for 972 chunks (historical run)
