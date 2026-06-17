# Release State

Generated: 2026-06-17  
Branch: `release/lawapp-clean-snapshot`

## HEAD verification

| Ref | SHA | Match |
|-----|-----|-------|
| Local HEAD | `804a232` | — |
| `origin/release/lawapp-clean-snapshot` | `804a232` | Yes |
| Owner expected | `804a232` or newer | **At expected** |

Latest commit message: `docs: embed hardening evidence and local DB password guidance`

## Working tree

```text
$ git status --short
(clean)
```

No uncommitted RAG repair on release at handoff time. Commit hash `fda7afca` **not found** in repository history.

## Embed proof (978/978 @ 1024-dim)

| Source | Result |
|--------|--------|
| Live DB (`localhost:5435`) | 978 rows, 978 embedded, max dim 1024 |
| `reports/prod_embed_hardening_cursor.txt` | 972 re-embedded + 6 prior; sync idempotent |
| `reports/BETA_PROMOTION_REVIEW.md` | Gate summary + beta NO recommendation |
| `scripts/reembed_corpus_1024.py` | Hardened (truncation retries, skip already-1024) |

**Beta ready:** NO (corpus plane yes; retrieval stack no)

## RAG blockers (owner-aligned)

1. **`retrieve_semantic`** still checks `legislation.embedding` (384 schema, empty) instead of `corpus_chunks` 1024 embeddings.
2. **RAG microservice** query embedder uses 384-dim fastembed while corpus index is 1024 — live `/api/rag/search` returns 0 hits.
3. **Source table migration** not applied — `legislation` / `acas_guidance` remain `vector(384)`.

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

From `reports/beta_gate_evidence_unified.txt` (stamp @ 97a405b; release now @ 804a232):

| Gate | Status |
|------|--------|
| C Case OS beta | PASS |
| D Ingestion 084 | PASS (re-run after RAG fix recommended) |
| E Grounding / CitationGuard | PASS |
| F i18n + domain fail-closed | PASS |
| SB Single Brain ADR-000 | PASS (16 pytest this session) |

## Pytest (release @ 804a232)

```text
python -m pytest tests/test_single_brain_architecture.py tests/test_build_order_gates.py -q
16 passed, 33 warnings in 15.11s
```

## Next repair (release line)

1. Repoint semantic retrieve to `corpus_chunks` **OR** migrate source tables to 1024-dim.
2. Switch RAG service query embedding to Ollama `bge-large-en-v1.5` (1024).
3. Re-run hybrid search integration + `verify_ingestion_084.py`.
4. Update `reports/BETA_PROMOTION_REVIEW.md` after proof.

**Do not push to `main`.** Commit on `release/lawapp-clean-snapshot`; owner merges.

## Docker / Ollama (from evidence reports)

- Profile: `docker compose --profile ollama up -d db ollama`
- Model alias workaround: `ollama cp mxbai-embed-large bge-large-en-v1.5` when direct pull fails
- Re-embed duration ~155 min for 972 chunks (historical run)
