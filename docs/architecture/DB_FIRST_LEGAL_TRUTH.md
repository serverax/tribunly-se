# DB-First Legal Truth Architecture

**Status:** Implemented (release branch)  
**Principle:** DB is LAW, LLM is INTERPRETER  
**Related:** [`OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md), [`LAWAPP_PRODUCTION_GO_LIVE.md`](LAWAPP_PRODUCTION_GO_LIVE.md)

---

## User diagram

```
                    +------------------+
                    | External sources |
                    | legislation.gov  |
                    | ACAS, case law   |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Ingestion only   |
                    | ingestion/*      |
                    | db/migrations    |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Local PostgreSQL |
                    | rules            |
                    | legislation      |
                    | corpus_chunks    |
                    | knowledge.*      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
       +-----------+  +------------+  +-------------+
       | Rules SQL |  | RAG hybrid |  | Graph RAG   |
       | engine    |  | retrieve   |  | traverse    |
       +-----+-----+  +------+-----+  +------+------+
             |               |               |
             +-------+-------+---------------+
                     |
                     v
            +--------------------+
            | LLM explain only   |
            | local Ollama       |
            | no law invention   |
            +---------+----------+
                      |
                      v
            +--------------------+
            | CitationGuard      |
            | corpus UUID gate   |
            +---------+----------+
                      |
                      v
            +--------------------+
            | Legal Truth        |
            | Validator          |
            +---------+----------+
                      |
         +------------+------------+
         |                         |
         v                         v
  +-------------+          +------------------+
  | User answer |          | Proposal queue   |
  | fail-closed |          | ingestion only   |
  +-------------+          +------------------+
```

---

## Three enforceable invariants

### Rule 1: DB is LAW, LLM is INTERPRETER

The LLM never invents statutes, never overwrites database rows, and never guesses legal thresholds. Deadlines and numeric rules come from the `rules` table via `retrieve_rules` and `compute_limitation_date`. The reasoning model receives a retrieval bundle and produces explanation text bound to those sources.

**Enforcement:** `backend/core/pipeline.py` (retrieve before reason), `backend/core/brain.py` step 10 before step 14, `legal_truth_validator.py` cross-check.

### Rule 2: Controlled write-back

When the Brain detects a knowledge gap (missing rule, unverified citation class), it creates a row in `knowledge.ingestion_proposals` only. Admin approval on port 8007 or monolith `/admin/*` enqueues an `ingestion_proposal_approved` outbox event. No LLM or Brain path performs direct SQL INSERT into `rules`, `legislation`, or `case_law`.

**Enforcement:** `backend/core/knowledge_proposer.py`, migration `082_knowledge_proposals.sql`, admin routes, `ingestion_write_guard.py`.

### Rule 3: Ingestion-only core tables

Writes to `rules`, `legislation`, `case_law_documents`, `corpus_chunks`, and `knowledge.legal_source` / `knowledge.provision` are confined to `ingestion/*` and `db/migrations/*`.

**Enforcement:** `backend/core/ingestion_write_guard.py`, tests in `tests/test_knowledge_proposals.py` and ingestion import scan.

---

## Mother Algorithm

The Mother Algorithm is the governed stack that sits above raw LLM calls:

| Component | Role | Code location |
|-----------|------|---------------|
| Query planner | Classify claim, select RAG/graph sources | `brain.py` steps 3-9, `orchestrator.py` |
| Reasoning | Structured assessment from facts + bundle | `pipeline.py` stage 4 |
| Consistency checker | Legal Truth Validator + CitationGuard | `legal_truth_validator.py`, `corpus_citation_guard.py` |
| Learning proposer | Queue gaps, never auto-apply | `knowledge_proposer.py` |
| Safety gatekeeper | Evaluation, safety policy, injection guard | `brain.py` steps 15-16, `govern.py` |

---

## Brain pipeline order (enforced)

```
Ingestion (external)
  -> Local DB
  -> RAG + Graph retrieve        (brain step 11)
  -> Rules engine (SQL)          (brain step 10)
  -> LLM explain only            (brain step 14 / pipeline assess)
  -> CitationGuard               (inside pipeline assess)
  -> Legal Truth Validator       (brain substage legal_truth_validation)
  -> Knowledge proposal (if gap) (brain substage knowledge_proposal_created)
  -> Evaluate + safety           (brain steps 15-16)
  -> Response                    (brain step 19)
```

### Trace stages

Brain traces record:

- `legal_truth_validation` with pass/fail and mismatch detail
- `knowledge_proposal_created` when a gap is queued (proposal id in detail)

---

## Case outcome feedback (scaffold)

`case_outcome_feedback` links predicted vs actual tribunal outcomes to `trace_id` and optional `agent_feedback`. API: `POST /api/feedback/outcome` (auth-gated). Used for eval harness and future DSPy read-only optimizer, not RLHF on the generator.

---

## Admin workflow

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/ingestion-proposals` | List pending/approved proposals |
| `POST /admin/ingestion-proposals/{id}/approve` | Approve and enqueue ingestion job via outbox |

Reviewer UI target: `lawapp-admin-service` (8007). Monolith exposes the same contract behind `X-Admin-Key`.
