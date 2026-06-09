-- 032_corpus_chunks_and_audits.sql
-- Unified retrieval table (corpus_chunks) + retrieval/assessment/deadline audit
-- tables, all jurisdiction-aware. Embedding dim = 384 (local bge-small).
-- Idempotent; additive. corpus_chunks is populated from the source tables with a
-- deterministic chunk_hash (no duplicates on re-run).

-- ── corpus_chunks (unified retrieval target) ────────────────────────────────
CREATE TABLE IF NOT EXISTS corpus_chunks (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table         TEXT NOT NULL,                 -- legislation|acas_guidance|official_guidance|case_law
    source_row_id        BIGINT,
    source_row_uuid      UUID,
    source_id            BIGINT REFERENCES legal_sources(id),
    domain               TEXT NOT NULL DEFAULT 'employment_uk',
    claim_type           TEXT,
    jurisdiction_code    TEXT NOT NULL REFERENCES legal_jurisdictions(jurisdiction_code),
    country_code         TEXT,
    authority_ref        TEXT,
    source_url           TEXT NOT NULL,
    title                TEXT,
    heading              TEXT,
    body_text            TEXT NOT NULL,
    chunk_index          INT NOT NULL,
    chunk_hash           TEXT NOT NULL UNIQUE,
    tokens_estimate      INT,
    embedding            vector(384),
    embedding_model      TEXT,
    embedding_created_at TIMESTAMPTZ,
    effective_from       DATE,
    effective_to         DATE,
    is_current           BOOLEAN DEFAULT true,
    is_prospective       BOOLEAN DEFAULT false,
    quality_score        NUMERIC,
    legal_topics         TEXT[],
    source_type          TEXT,
    authority_weight     TEXT,
    licence_status       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS corpus_chunks_juris_idx  ON corpus_chunks (jurisdiction_code, claim_type, domain);
CREATE INDEX IF NOT EXISTS corpus_chunks_src_idx    ON corpus_chunks (source_table, source_row_uuid);
CREATE INDEX IF NOT EXISTS corpus_chunks_current_idx ON corpus_chunks (is_current) WHERE is_current = true;

-- ── legal_retrieval_audit ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_retrieval_audit (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id           UUID,
    assessment_id     UUID,
    query_text        TEXT,
    query_hash        TEXT,
    domain            TEXT,
    claim_type        TEXT,
    jurisdiction_code TEXT NOT NULL REFERENCES legal_jurisdictions(jurisdiction_code),
    retrieved_bundle  JSONB NOT NULL,
    exact_rules       JSONB,
    semantic_results  JSONB,
    keyword_results   JSONB,
    grounding_score   NUMERIC,
    retrieval_model   TEXT,
    embedding_model   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS legal_retrieval_audit_case_idx ON legal_retrieval_audit (case_id);

-- ── legal_assessments ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_assessments (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id                UUID,
    retrieval_audit_id     UUID REFERENCES legal_retrieval_audit(id),
    claim_type             TEXT NOT NULL,
    jurisdiction_code      TEXT NOT NULL REFERENCES legal_jurisdictions(jurisdiction_code),
    jurisdiction_supported BOOLEAN DEFAULT true,
    has_viable_claim       TEXT NOT NULL,
    strength               TEXT NOT NULL,
    reasoning_summary      TEXT,
    value_range            JSONB,
    key_weaknesses         JSONB,
    deadline               JSONB,
    recommended_next_step  TEXT,
    citations              JSONB NOT NULL,
    grounding_score        NUMERIC NOT NULL,
    confidence_score       NUMERIC NOT NULL,
    insufficient_grounding BOOLEAN DEFAULT false,
    governance_passed      BOOLEAN DEFAULT false,
    governance_fail_reasons JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS legal_assessments_case_idx ON legal_assessments (case_id);

-- ── deadline_calculation_audit ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deadline_calculation_audit (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id              UUID,
    claim_type           TEXT NOT NULL,
    jurisdiction_code    TEXT NOT NULL REFERENCES legal_jurisdictions(jurisdiction_code),
    edt                  DATE NOT NULL,
    ec_start_date        DATE,
    ec_end_date          DATE,
    base_limit_date      DATE NOT NULL,
    paused_days          INT,
    one_month_floor_date DATE,
    final_limitation_date DATE NOT NULL,
    rules_used           JSONB NOT NULL,
    calculation_version  TEXT NOT NULL,
    calculated_by        TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── jurisdiction_code on case/document/referral tables ──────────────────────
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['cases','documents','referrals'] LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name=t AND table_schema='public') THEN
      EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS jurisdiction_code TEXT', t);
      EXECUTE format('UPDATE %I SET jurisdiction_code=''GB'' WHERE jurisdiction_code IS NULL', t);
    END IF;
  END LOOP;
END $$;

-- ── populate corpus_chunks from the source tables (idempotent via chunk_hash) ─
INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   effective_from, effective_to, is_current, is_prospective, source_type, licence_status)
SELECT 'legislation', l.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='legislation_gov_uk' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', l.jurisdiction_code, l.country_code,
       (l.act_title||' s.'||COALESCE(l.section_ref,'')), l.source_url, l.act_title, l.heading,
       l.body_text, l.chunk_index,
       encode(sha256(('legislation:'||l.source_url||':'||l.chunk_index||':'||l.body_text)::bytea),'hex'),
       (length(l.body_text)/4)::int, l.embedding, 'bge-small-en-v1.5', l.last_verified_at,
       l.effective_from, l.effective_to, (NOT COALESCE(l.is_prospective,false)), COALESCE(l.is_prospective,false),
       l.source_type, l.licence_status
FROM legislation l
ON CONFLICT (chunk_hash) DO NOTHING;

INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   is_current, source_type, licence_status)
SELECT 'acas_guidance', a.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='acas' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', a.jurisdiction_code, a.country_code,
       a.doc_title, a.source_url, a.doc_title, NULL,
       a.body_text, a.chunk_index,
       encode(sha256(('acas:'||a.source_url||':'||a.chunk_index||':'||a.body_text)::bytea),'hex'),
       (length(a.body_text)/4)::int, a.embedding, 'bge-small-en-v1.5', a.last_verified_at,
       true, a.source_type, a.licence_status
FROM acas_guidance a
ON CONFLICT (chunk_hash) DO NOTHING;

INSERT INTO corpus_chunks
  (source_table, source_row_uuid, source_id, domain, claim_type, jurisdiction_code, country_code,
   authority_ref, source_url, title, heading, body_text, chunk_index, chunk_hash,
   tokens_estimate, embedding, embedding_model, embedding_created_at,
   is_current, source_type, licence_status)
SELECT 'official_guidance', o.id,
       (SELECT id FROM legal_sources s WHERE s.source_id='govuk_courts_tribunals_publishing' AND s.domain='employment_uk' LIMIT 1),
       'employment_uk', 'unfair_dismissal', o.jurisdiction_code, o.country_code,
       o.title, o.source_url, o.title, NULL,
       o.body_text, o.chunk_index,
       encode(sha256(('govuk:'||o.source_url||':'||o.chunk_index||':'||o.body_text)::bytea),'hex'),
       (length(o.body_text)/4)::int, o.embedding, 'bge-small-en-v1.5', o.last_verified_at,
       COALESCE(o.is_current,true), o.source_type, o.licence_status
FROM official_guidance o
ON CONFLICT (chunk_hash) DO NOTHING;

-- quality_score: simple data-science score from provenance completeness (0..1)
UPDATE corpus_chunks SET quality_score = (
    (CASE WHEN source_url IS NOT NULL AND source_url<>'' THEN 0.25 ELSE 0 END)
  + (CASE WHEN jurisdiction_code IS NOT NULL THEN 0.2 ELSE 0 END)
  + (CASE WHEN authority_ref IS NOT NULL AND authority_ref<>'' THEN 0.2 ELSE 0 END)
  + (CASE WHEN embedding IS NOT NULL THEN 0.2 ELSE 0 END)
  + (CASE WHEN chunk_hash IS NOT NULL THEN 0.15 ELSE 0 END)
) WHERE quality_score IS NULL;
