# LawApp  -  UK Employment Law Knowledge Architecture
## Deployment Work Order

**Version:** 1.0
**Date:** 16 June 2026
**Owner:** Khalid (Solution Architect)
**Audience:** LawApp dev team
**Repo:** serverax/lawapp (`F:\lawapp`)

---

## 1. Purpose and scope

Build the knowledge layer that makes LawApp's UK employment law answers deterministic, citable, and defensible. The server databases are the first line of every answer. The LLM is a feeder that proposes new content, but nothing the model produces reaches the authoritative store without passing a verification gate.

In scope: legal content taxonomy, datastore design, schema, ingestion from trusted sources, the LLM write-back governance gate, retrieval, and the deployment sequence.

Out of scope for this order: payments, frontend redesign, and Ollama model selection. Those get separate work orders.

---

## 2. Architecture principles

Three principles drive every decision below.

**DB-first.** Retrieval from the curated corpus runs before any generation. If the answer exists in the store, the LLM does not generate it.

**LLM as gated feeder.** The model only generates when retrieval is insufficient. Its output lands in a staging table, gets checked against a primary source, and is promoted to the first-line store only after verification. No direct writes to authoritative tables. Treat this as chain of custody for legal content.

**Temporal versioning is mandatory.** The Employment Rights Act 2025 became law on 18 December 2025, but most provisions commence in phases through 2026 and 2027 (for example, the unfair dismissal qualifying period drops to six months from 1 January 2027). Every provision must carry effective-from and effective-to dates so the system can answer "what was the law on the date of the alleged act," which is the question a tribunal actually asks.

---

## 3. Datastore inventory

Two tiers. Do not conflate them.

**Knowledge tier (the law), 3 logical stores:**

1. Source-of-truth corpus  -  curated, versioned, provenance-tracked legal content. Postgres.
2. Vector index  -  embeddings for semantic retrieval. `pgvector` inside the same Postgres engine.
3. Knowledge graph  -  relationships between statute, section, case, ACAS code, concept. Neo4j (served by the graph-RAG service on 8018).

Physically this is two engines: Postgres (corpus plus pgvector) and Neo4j.

**Operational tier (the platform):**

4. Application Postgres  -  users, cases, intake, sessions (existing, host port 5435).
5. Redis  -  cache, hot answers, sessions, rate limiting.
6. Audit store  -  append-only, served by the audit service on 8020.

---

## 4. Content taxonomy: 14 modules plus cross-cutting

Seed these as the `module` table. Each is its own module because it has distinct legislation, tests, and remedies.

| code | name | primary legislation |
|------|------|---------------------|
| EMP_STATUS | Employment status and contracts | s.1 ERA 1996; ERA 2025 single worker status |
| PAY_WAGES | Pay and wages | NMWA 1998; Part II ERA 1996 |
| WORKING_TIME | Working time, holiday and rest | WTR 1998 |
| UNFAIR_DISMISSAL | Unfair dismissal | Part X ERA 1996; ERA 2025 |
| WRONGFUL_DISMISSAL | Wrongful dismissal and notice | common law; s.86 ERA 1996 |
| REDUNDANCY | Redundancy and collective consultation | ERA 1996; s.188 TULRCA 1992 |
| DISCRIMINATION | Discrimination and equality | Equality Act 2010 |
| TUPE | Transfer of undertakings | TUPE Regs 2006 |
| FAMILY_FLEX | Family and flexible working rights | ERA 1996; ERA 2025 |
| WHISTLEBLOWING | Protected disclosures | Part IVA ERA 1996; PIDA 1998 |
| TRADE_UNION | Trade unions and industrial action | TULRCA 1992; ERA 2025 |
| HEALTH_SAFETY | Health and safety, employment dimension | HSWA 1974 |
| DISCIPLINARY | Disciplinary and grievance | ACAS Code of Practice |
| TRIBUNAL_PROC | Tribunal procedure, time limits, remedies | ET Rules; ERA 2025 |

**Cross-cutting modules (seed as standalone):**

| code | name | primary legislation |
|------|------|---------------------|
| DATA_PROTECTION | Data protection and workplace monitoring | UK GDPR; DPA 2018 |
| ATYPICAL_WORKERS | Fixed-term, part-time, agency workers | FTE Regs 2002; PTW Regs 2000; AWR 2010 |

Total: 16 rows.

---

## 5. Schema specification (Postgres corpus)

Apply in this order.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Legal modules (seed with the 16 above)
CREATE TABLE module (
  id          SMALLINT PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  description TEXT
);

-- A source document: a statute, SI, judgment, ACAS code, or guidance page
CREATE TABLE legal_source (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type  TEXT NOT NULL CHECK (source_type IN
                 ('statute','si','judgment','acas_code','guidance','ehrc_code')),
  authority    TEXT NOT NULL,   -- legislation.gov.uk | nationalarchives | acas | gov.uk | ehrc | hse
  citation     TEXT NOT NULL,   -- 'Employment Rights Act 1996' | '[2024] EAT 123'
  url          TEXT NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  checksum     TEXT NOT NULL,   -- hash of fetched payload for change detection
  UNIQUE (authority, citation, url)
);

-- The heart of the corpus: temporally versioned provisions
CREATE TABLE provision (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id      UUID NOT NULL REFERENCES legal_source(id),
  module_id      SMALLINT NOT NULL REFERENCES module(id),
  ref            TEXT NOT NULL,        -- 's.98 ERA 1996' | 'reg 4 TUPE 2006' | judgment para
  heading        TEXT,
  body           TEXT NOT NULL,
  effective_from DATE NOT NULL,
  effective_to   DATE,                 -- NULL = currently in force
  version_label  TEXT NOT NULL,        -- 'as enacted' | 'as in force 2027-01-01' | 'amended by ERA 2025'
  status         TEXT NOT NULL DEFAULT 'in_force' CHECK (status IN
                   ('in_force','prospective','repealed','superseded')),
  supersedes_id  UUID REFERENCES provision(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_provision_module   ON provision(module_id);
CREATE INDEX ix_provision_validity ON provision(effective_from, effective_to);

-- LLM staging: candidates start here, never in provision/curated_answer
CREATE TABLE answer_candidate (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  module_id           SMALLINT REFERENCES module(id),
  query_text          TEXT NOT NULL,
  generated_body      TEXT NOT NULL,
  model_name          TEXT NOT NULL,
  cited_provision_ids UUID[],          -- provisions the model claims support this
  state               TEXT NOT NULL DEFAULT 'unverified' CHECK (state IN
                        ('unverified','auto_checked','human_review','verified','rejected')),
  auto_check_score    NUMERIC,         -- groundedness / citation-match score
  reviewer            TEXT,
  reviewed_at         TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- First-line curated answers. No citation, no promotion.
CREATE TABLE curated_answer (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id   UUID REFERENCES answer_candidate(id),
  module_id      SMALLINT NOT NULL REFERENCES module(id),
  question       TEXT NOT NULL,
  answer         TEXT NOT NULL,
  citation_ids   UUID[] NOT NULL CHECK (array_length(citation_ids,1) >= 1),
  effective_from DATE NOT NULL,
  effective_to   DATE,
  approved_by    TEXT NOT NULL,
  approved_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Embeddings over provisions and curated answers
CREATE TABLE embedding (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  object_type    TEXT NOT NULL CHECK (object_type IN ('provision','curated_answer')),
  object_id      UUID NOT NULL,
  chunk_idx      INT NOT NULL,
  content        TEXT NOT NULL,
  embedding      vector(1024),         -- set dimension to your embedding model
  module_id      SMALLINT REFERENCES module(id),
  effective_from DATE,                 -- carry validity into retrieval
  effective_to   DATE
);
CREATE INDEX ix_embedding_hnsw ON embedding USING hnsw (embedding vector_cosine_ops);
```

**Temporal query helper.** Every retrieval filters by a reference date:

```sql
-- Law in force as at :as_at_date for a module
SELECT * FROM provision
WHERE module_id = :module_id
  AND effective_from <= :as_at_date
  AND (effective_to IS NULL OR effective_to > :as_at_date)
  AND status IN ('in_force');
```

---

## 6. Knowledge graph model (Neo4j)

Nodes: `Module`, `Statute`, `Provision`, `Judgment`, `AcasCode`, `Concept`, `Test`, `Remedy`.

Relationships:

```
(Provision)-[:BELONGS_TO]->(Module)
(Provision)-[:AMENDED_BY]->(Provision)
(Provision)-[:SUPERSEDES]->(Provision)
(Judgment)-[:INTERPRETS]->(Provision)
(Judgment)-[:APPLIES]->(Test)
(Concept)-[:GOVERNED_BY]->(Provision)
(Provision)-[:GIVES_RISE_TO]->(Remedy)
```

The graph carries `provision.id` as a property so traversal results join back to the Postgres corpus for the authoritative text and dates. The graph stores relationships, not the canonical text.

---

## 7. Trusted source connectors

Build one adapter per authority. Each adapter: fetch, hash, compare to `legal_source.checksum`, and on change create a new versioned `provision` row, re-embed, and update the graph. Build in this priority order.

1. **legislation.gov.uk** (primary). Pull statutes and SIs using its data interface, taking both "as enacted" and point-in-time versions. Map sections to `provision` rows with correct effective dates. First targets: ERA 1996, Equality Act 2010, TULRCA 1992, WTR 1998, TUPE Regs 2006, NMWA 1998, and ERA 2025 (the last as `prospective` rows linked via `AMENDED_BY` to the provisions they change).
2. **Find Case Law** (caselaw.nationalarchives.gov.uk). Official tribunal and court judgments with structured access for bulk and per-judgment retrieval. Seed the leading authority per module.
3. **ACAS**. Codes of practice and guidance.
4. **gov.uk**. Guidance and calculators via the content API.
5. **EHRC** and **HSE**. HTML with checksum-based change detection.

**Licensing check (blocking before go-live):** confirm reuse terms for case law and ACAS material. Note the licence on each `legal_source`. Do not assume; verify per source.

---

## 8. LLM write-back governance gate

The only path by which generated content enters the first line.

```
retrieval miss
   -> LLM generates candidate
   -> INSERT answer_candidate (state = 'unverified')
   -> auto-check: groundedness + citation-match score
        score >= threshold -> state = 'auto_checked'
        score <  threshold -> state = 'human_review'
   -> reviewer (admin service 8007) verifies or rejects
        verify  -> state = 'verified'
        reject  -> state = 'rejected'  (never served as settled law)
   -> promotion job: verified -> curated_answer
        requires non-empty citation_ids and approved_by
        then embed + create graph links
   -> audit every transition to the audit service (8020), append-only
```

Hard rules:

- No code path writes model output directly to `provision` or `curated_answer`.
- `curated_answer` rejects rows with empty `citation_ids` at the schema level.
- Unverified content may be served to users only with a clear "unverified" badge, never as settled law.

---

## 9. Service topology mapping

| service | port | role in this order |
|---------|------|--------------------|
| main API | 8000 | orchestration, static frontend |
| rules | 8016 | module routing, time-limit logic |
| RAG | 8017 | DB-first retrieval over corpus + vector |
| graph-RAG | 8018 | Neo4j traversal (currently broken, see Phase 0) |
| redaction | 8019 | strip PII from queries before logging |
| audit | 8020 | append-only governance log |
| admin | 8007 | reviewer UI for the gate |
| case | 8008 | case-backed flows |
| notification | 8009 | reviewer and user alerts |

---

## 10. Phased deployment sequence

Each phase has tasks and acceptance criteria. Do not start a phase until the previous one passes its criteria.

### Phase 0  -  Foundations and unblock (week 1)
- Fix the graph-RAG crash on 8018. The import `backend.core.rag.graphrag_traversal` is failing. Diagnose in this order: confirm whether `backend/core/rag/graphrag_traversal.py` exists in the repo (check git history for a rename or a missed commit); confirm `backend/core/rag/__init__.py` exists; confirm the container `PYTHONPATH` / WORKDIR includes the repo root so `backend` is importable; rebuild.
- Stand up the corpus in Postgres (separate schema in the existing engine is fine) and enable `pgvector`.
- Stand up Neo4j.
- Seed the `module` table with the 16 rows.

**Acceptance:** `docker compose ps` shows all services healthy including 8018; `module` has 16 rows; pgvector and the HNSW index exist; Neo4j is reachable from the graph-RAG service.

### Phase 1  -  Schema and temporal core (week 2)
- Apply the full corpus DDL from section 5.
- Implement the "law as at date" query helper.
- Write unit tests covering ERA 2025 prospective rows.

**Acceptance:** with seeded sample provisions that have a 2027 `effective_from`, a query for "law as at 2026-06-16" excludes them and a query for "law as at 2027-01-01" includes them.

### Phase 2  -  Ingestion connectors (weeks 3 to 4)
- Build the legislation.gov.uk connector first, ingesting the seven target statutes from section 7.
- Build the Find Case Law connector and seed one leading authority per module.
- Build the ACAS connector.
- Implement checksum change detection and re-versioning.

**Acceptance:** ERA 1996 is ingested with section-level provisions, citations, URLs, and effective dates; ERA 2025 amendments exist as `prospective` provisions linked by `AMENDED_BY`; re-running a connector with no upstream change produces zero new versions.

### Phase 3  -  DB-first retrieval (week 5)
- RAG service (8017) queries corpus plus vector with module and date filters, returning provisions with citations.
- Graph-RAG service (8018) traverses statute, case, and concept.
- Answer assembly is retrieval-first with mandatory citations.

**Acceptance:** a query returns an answer grounded only in retrieved provisions, every claim carries a provision citation, and the result is correctly date-scoped.

### Phase 4  -  LLM feeder and gate (week 6)
- LLM generates a candidate only on retrieval miss.
- Candidate flows through the gate in section 8.
- Reviewer UI in the admin service (8007).
- Promotion job moves verified candidates to `curated_answer`, embeds, and links the graph.

**Acceptance:** no path writes model output directly to `provision` or `curated_answer`; promotion requires non-empty `citation_ids` and `approved_by`; rejected candidates are never served as settled law.

### Phase 5  -  Hardening (week 7)
- Audit every promotion and rejection to 8020, append-only.
- Redaction service (8019) strips user PII from queries before logging.
- Every served answer shows source citation, effective date, and a verified or unverified badge.

**Acceptance:** the full chain from a served answer back through `curated_answer`, `answer_candidate`, reviewer, and source is reconstructable from the audit log.

---

## 11. Definition of done

- All 16 modules seeded and queryable.
- The seven priority statutes plus ERA 2025 amendments ingested and temporally versioned.
- Retrieval is date-scoped and citation-bearing.
- The governance gate is the only write path to the first line, enforced at schema and code level.
- Every answer is traceable to a source through the audit log.
- Licensing confirmed and recorded per source.

---

## 12. Risks and guardrails

- **Hallucination contamination of the corpus.** Mitigated by the gate. This is the single most important control; do not weaken it for speed.
- **Stale law.** Scheduled re-crawl plus checksum detection. Track the ERA 2025 commencement calendar as `prospective` rows and flip them to `in_force` on their commencement dates.
- **Wrong-date answers.** Enforce the temporal filter at retrieval, not just storage. A correctly stored provision served without a date filter is still a wrong answer.
- **Over-reliance on the LLM.** Retrieval runs first; the model only fires on a miss.
- **Licensing exposure** on case law and ACAS content. Blocking check before go-live.

---

## 13. Out of scope (separate work orders)

Payments, frontend redesign, Ollama model and inference configuration.
