# Database Design — UK Employment Claim Co-Pilot

**Engine:** PostgreSQL 15+ with the `pgvector` extension.
**Pairs with:** `02_HLD_ARCHITECTURE.md` (Layer 5), `04_RAG_REASONING_SPEC.md`.
**Principle (GUARDRAIL):** Deterministic legal facts (deadlines, caps, thresholds) live in the structured `rules` table and are queried by code — they are NEVER stored only as embedded free text and NEVER inferred by a model. Every legal record carries source + version + verification date.

---

## 1. Extensions & conventions
```sql
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
```
- Primary keys: `uuid` via `gen_random_uuid()`.
- Timestamps: `timestamptz`, default `now()`.
- Embeddings: `vector(N)` where N matches the chosen embedding model's dimensions (set once, keep consistent).
- Every legal-source row carries: `source_url`, `version`/`effective_from`/`effective_to`, `last_verified_at`.

---

## 2. Legal source tables (the moat)

### 2.1 `legislation`
Statute text from legislation.gov.uk (CLML XML), chunked for retrieval.
```sql
CREATE TABLE legislation (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  act_title       text NOT NULL,                 -- e.g. "Employment Rights Act 1996"
  leg_type        text NOT NULL,                 -- ukpga, uksi, asp ...
  year            int  NOT NULL,
  chapter         text,                           -- e.g. "18"
  section_ref     text,                           -- e.g. "94" (unfair dismissal right)
  jurisdiction    text NOT NULL DEFAULT 'EW',     -- EW, S, NI, UK  (do NOT assume EW==S)
  heading         text,
  body_text       text NOT NULL,                  -- plain text of the chunk
  chunk_index     int  NOT NULL DEFAULT 0,        -- ordering within a section
  embedding       vector(1536),                   -- adjust dim to model
  source_url      text NOT NULL,                  -- canonical legislation.gov.uk URI fetched
  version_date    date,                           -- point-in-time version fetched
  effective_from  date,
  effective_to    date,                           -- NULL = currently in force
  is_prospective  boolean NOT NULL DEFAULT false, -- enacted but not yet commenced
  last_verified_at timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON legislation USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON legislation (act_title, section_ref);
CREATE INDEX ON legislation (jurisdiction);
```

### 2.2 `case_law`
Tribunal / EAT decisions from Find Case Law (Akoma Ntoso / LegalDocML).
```sql
CREATE TABLE case_law (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_uri    text NOT NULL UNIQUE,           -- STABLE Find Case Law URI (store this)
  neutral_citation text,                          -- e.g. "[2024] EAT 12"
  fclid           text,                           -- Find Case Law identifier
  case_name       text,
  court_code      text NOT NULL,                  -- e.g. "eat"
  decision_date   date,
  judges          text[],
  parties         text[],
  body_text       text NOT NULL,                  -- chunk
  chunk_index     int  NOT NULL DEFAULT 0,
  embedding       vector(1536),
  content_hash    text NOT NULL,                  -- SHA256 from <uk:hash>/<tna:contenthash>
  source_url      text NOT NULL,
  published_date  date,                           -- handed-down
  updated_date    timestamptz,                    -- last XML update
  last_verified_at timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON case_law USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON case_law (court_code, decision_date);
CREATE INDEX ON case_law (content_hash);   -- change detection
```

### 2.3 `acas_guidance`
ACAS Code of Practice + guidance, ingested as static authoritative documents (no API).
```sql
CREATE TABLE acas_guidance (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_title       text NOT NULL,                  -- e.g. "ACAS Code of Practice on Disciplinary and Grievance Procedures"
  edition         text,                            -- track the version/edition
  section_ref     text,                            -- e.g. "para 5"
  body_text       text NOT NULL,
  chunk_index     int  NOT NULL DEFAULT 0,
  embedding       vector(1536),
  source_url      text NOT NULL,
  effective_from  date,
  last_verified_at timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON acas_guidance USING ivfflat (embedding vector_cosine_ops);
```

### 2.4 `rules` — DETERMINISTIC legal facts (the critical table)
This is where exactness lives. Time limits, caps, thresholds. Queried by code, never by the model. Each rule cites its authority.
```sql
CREATE TABLE rules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_key        text NOT NULL,                  -- machine key, e.g. "unfair_dismissal.time_limit_months"
  claim_type      text NOT NULL,                  -- e.g. "unfair_dismissal"
  jurisdiction    text NOT NULL DEFAULT 'EW',
  value_numeric   numeric,                        -- e.g. 3 (months) or 115115 (cap £)
  value_text      text,                           -- for non-numeric rules
  unit            text,                           -- "months", "GBP", "weeks_pay" ...
  description     text NOT NULL,                  -- human explanation
  authority_type  text NOT NULL,                  -- "legislation" | "case_law" | "acas"
  authority_ref   text NOT NULL,                  -- citation, e.g. "ERA 1996 s.111(2)"
  authority_url   text NOT NULL,
  effective_from  date NOT NULL,
  effective_to    date,                           -- NULL = current
  last_verified_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (rule_key, jurisdiction, effective_from)
);
CREATE INDEX ON rules (claim_type, jurisdiction);
CREATE INDEX ON rules (rule_key);
```
> Caps and limits change (e.g. annual uprating of the compensation cap). Versioning by `effective_from`/`effective_to` lets you compute the correct figure for the relevant date. NEVER hardcode a cap in code; read it from here.

---

## 3. Application tables

### 3.1 `users`
```sql
CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email           text UNIQUE,                    -- consider encryption/hash
  created_at      timestamptz NOT NULL DEFAULT now(),
  subscription_status text DEFAULT 'none'         -- none | active | cancelled
);
```

### 3.2 `cases`
A user's matter. Holds facts (special-category data → encrypt) and the latest structured assessment.
```sql
CREATE TABLE cases (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES users(id) ON DELETE CASCADE,
  claim_type      text NOT NULL DEFAULT 'unfair_dismissal',
  jurisdiction    text NOT NULL DEFAULT 'EW',
  facts_encrypted bytea,                           -- encrypted JSON of user facts (Art.9 data)
  assessment      jsonb,                           -- latest structured assessment object
  key_dates       jsonb,                           -- e.g. {"dismissal_date":..., "limitation_date":...}
  status          text NOT NULL DEFAULT 'diagnosis', -- diagnosis | paid | bundle | handoff
  payment_tier    text,                            -- core | full | none
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON cases (user_id);
```

### 3.3 `documents`
Generated outputs + uploaded user evidence.
```sql
CREATE TABLE documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id         uuid REFERENCES cases(id) ON DELETE CASCADE,
  doc_type        text NOT NULL,                   -- particulars_of_claim | schedule_of_loss | witness_statement | upload
  storage_ref     text NOT NULL,                   -- encrypted blob location
  is_user_upload  boolean NOT NULL DEFAULT false,
  extracted_facts jsonb,                            -- for uploads, post-OCR extraction (needs user confirm)
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON documents (case_id);
```

### 3.4 `referrals` (Phase 6)
```sql
CREATE TABLE referrals (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id         uuid REFERENCES cases(id),
  partner_firm    text,
  status          text NOT NULL DEFAULT 'triggered', -- triggered | sent | accepted | rejected
  fee_status      text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

### 3.5 `source_freshness` (operational)
Backs the Phase 1 freshness report.
```sql
CREATE VIEW source_freshness AS
  SELECT 'legislation' AS source, count(*) AS rows, min(last_verified_at) AS oldest_verified FROM legislation
  UNION ALL SELECT 'case_law', count(*), min(last_verified_at) FROM case_law
  UNION ALL SELECT 'acas_guidance', count(*), min(last_verified_at) FROM acas_guidance
  UNION ALL SELECT 'rules', count(*), min(last_verified_at) FROM rules;
```

---

## 4. Data-protection notes (UK GDPR Article 9)
- `cases.facts_encrypted` and `documents.storage_ref` hold special-category data (discrimination/health) → encrypt at rest; minimise; define retention + deletion (`ON DELETE CASCADE` supports user erasure).
- Never copy raw fact data into logs or into payloads bound for third-party models — de-identify at the boundary (see `04_RAG_REASONING_SPEC.md`).
- Build a DPIA before launch (Phase 5).

## 5. Seed-data note (unfair dismissal)
Phase 1 must seed `rules` for unfair dismissal, each row citing the in-force authority. Examples of rule_keys to populate (VERIFY values + citations against the live API at ingest — do not trust any number from memory):
- `unfair_dismissal.time_limit_months`
- `unfair_dismissal.early_conciliation_required`
- `unfair_dismissal.qualifying_period`
- `unfair_dismissal.compensation_cap_basic`
- `unfair_dismissal.compensation_cap_compensatory`
> A dedicated seed spec with exact sections can be produced separately; values must be pulled and verified from legislation.gov.uk, not hardcoded.
