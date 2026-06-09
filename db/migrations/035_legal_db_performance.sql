-- 035_legal_db_performance.sql
-- Performance layer for legal RAG + deterministic rules lookup: extensions,
-- vector indexes (HNSW preferred, ivfflat fallback), full-text GIN, trigram,
-- rules composite/partial, BRIN on audit tables, JSONB GIN. Embedding dim = 384.
-- Idempotent. pg_stat_statements is attempted but tolerated if not preloaded.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_stat_statements not available (needs shared_preload_libraries): %', SQLERRM;
END $$;

-- is_current on rules + acas_guidance (for current-law partial indexes/queries)
ALTER TABLE rules         ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT true;
ALTER TABLE acas_guidance ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT true;
UPDATE rules SET is_current = (effective_to IS NULL) WHERE is_current IS NULL OR is_current = true;
UPDATE acas_guidance SET is_current = true WHERE is_current IS NULL;

-- ── A. vector indexes (HNSW preferred, ivfflat fallback) ────────────────────
DO $$
DECLARE t TEXT; tbls TEXT[] := ARRAY['corpus_chunks','legislation','acas_guidance'];
BEGIN
  FOREACH t IN ARRAY tbls LOOP
    BEGIN
      EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING hnsw (embedding vector_cosine_ops)', t||'_emb_hnsw', t);
    EXCEPTION WHEN OTHERS THEN
      EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING ivfflat (embedding vector_cosine_ops) WITH (lists=10)', t||'_emb_ivf', t);
    END;
  END LOOP;
END $$;

-- ── B. full-text GIN (English) ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS corpus_chunks_fts_idx     ON corpus_chunks     USING gin (to_tsvector('english', body_text));
CREATE INDEX IF NOT EXISTS legislation_fts_idx       ON legislation       USING gin (to_tsvector('english', body_text));
CREATE INDEX IF NOT EXISTS acas_guidance_fts_idx     ON acas_guidance     USING gin (to_tsvector('english', body_text));
CREATE INDEX IF NOT EXISTS official_guidance_fts_idx ON official_guidance USING gin (to_tsvector('english', body_text));

-- ── C. trigram (fuzzy) ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS legislation_acttitle_trgm   ON legislation     USING gin (act_title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS legislation_section_trgm    ON legislation     USING gin (section_ref gin_trgm_ops);
CREATE INDEX IF NOT EXISTS acas_doctitle_trgm          ON acas_guidance   USING gin (doc_title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS rules_rulekey_trgm          ON rules           USING gin (rule_key gin_trgm_ops);
CREATE INDEX IF NOT EXISTS corpus_chunks_authref_trgm  ON corpus_chunks   USING gin (authority_ref gin_trgm_ops);
CREATE INDEX IF NOT EXISTS corpus_chunks_title_trgm    ON corpus_chunks   USING gin (title gin_trgm_ops);
-- case_law trigram only where columns exist (schema minimal until FCL licence)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='case_law_documents' AND column_name='case_name') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS case_law_casename_trgm ON case_law_documents USING gin (case_name gin_trgm_ops)';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='case_law_documents' AND column_name='neutral_citation') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS case_law_ncn_trgm ON case_law_documents USING gin (neutral_citation gin_trgm_ops)';
  END IF;
END $$;

-- ── D. rules composite + status indexes ─────────────────────────────────────
CREATE INDEX IF NOT EXISTS rules_key_juris_eff_idx   ON rules (rule_key, jurisdiction_code, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS rules_claim_juris_eff_idx ON rules (claim_type, jurisdiction_code, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS rules_juris_current_idx   ON rules (jurisdiction_code, is_current);
CREATE INDEX IF NOT EXISTS rules_verif_idx           ON rules (verification_status);
CREATE INDEX IF NOT EXISTS rules_prospective_idx     ON rules (is_prospective);

-- ── E. current-law partial indexes ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS legislation_current_idx   ON legislation   (section_ref) WHERE is_prospective = false;
CREATE INDEX IF NOT EXISTS rules_current_partial_idx ON rules         (rule_key, jurisdiction_code) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS acas_current_partial_idx  ON acas_guidance (doc_title) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS corpus_chunks_current_partial_idx ON corpus_chunks (jurisdiction_code, claim_type) WHERE is_current = true;

-- ── F. BRIN on time-series audit tables ─────────────────────────────────────
CREATE INDEX IF NOT EXISTS cir_started_brin    ON corpus_ingestion_runs     USING brin (started_at);
CREATE INDEX IF NOT EXISTS lra_created_brin     ON legal_retrieval_audit     USING brin (created_at);
CREATE INDEX IF NOT EXISTS la_created_brin      ON legal_assessments         USING brin (created_at);
CREATE INDEX IF NOT EXISTS dca_created_brin     ON deadline_calculation_audit USING brin (created_at);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='created_at') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS documents_created_brin ON documents USING brin (created_at)';
  END IF;
END $$;

-- ── G. JSONB GIN on audit/assessment columns ────────────────────────────────
CREATE INDEX IF NOT EXISTS la_citations_gin     ON legal_assessments     USING gin (citations);
CREATE INDEX IF NOT EXISTS la_weaknesses_gin    ON legal_assessments     USING gin (key_weaknesses);
CREATE INDEX IF NOT EXISTS la_valuerange_gin    ON legal_assessments     USING gin (value_range);
CREATE INDEX IF NOT EXISTS lra_bundle_gin       ON legal_retrieval_audit USING gin (retrieved_bundle);
CREATE INDEX IF NOT EXISTS cir_proof_gin        ON corpus_ingestion_runs USING gin (proof_json);
CREATE INDEX IF NOT EXISTS cir_config_gin       ON corpus_ingestion_runs USING gin (config_json);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='extracted_facts') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS documents_facts_gin ON documents USING gin (extracted_facts)';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cases' AND column_name='key_dates') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS cases_keydates_gin ON cases USING gin (key_dates)';
  END IF;
END $$;

ANALYZE corpus_chunks;
ANALYZE legislation;
ANALYZE rules;
ANALYZE acas_guidance;
