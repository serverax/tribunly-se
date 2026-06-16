-- 080_embedding_1024_prep.sql
-- Owner Deployment Q5: standardise on 1024-dim local embeddings (Ollama).
-- Existing 384-dim vectors are cleared; run scripts/reembed_corpus_1024.py after Ollama model pull.

BEGIN;

ALTER TABLE corpus_chunks
    ADD COLUMN IF NOT EXISTS embedding_dim INT;

UPDATE corpus_chunks
   SET embedding_dim = 384
 WHERE embedding IS NOT NULL AND embedding_dim IS NULL;

DROP MATERIALIZED VIEW IF EXISTS mv_current_employment_legal_chunks;
DROP VIEW IF EXISTS corpus_quality_report;

DROP INDEX IF EXISTS corpus_chunks_embedding_ivfflat_idx;

ALTER TABLE corpus_chunks
    ALTER COLUMN embedding TYPE vector(1024)
    USING NULL;

ALTER TABLE corpus_chunks
    ALTER COLUMN embedding_model SET DEFAULT 'bge-large-en-v1.5';

COMMENT ON COLUMN corpus_chunks.embedding IS
    'vector(1024) local Ollama embedding. Re-populate via scripts/reembed_corpus_1024.py';

CREATE VIEW corpus_quality_report AS
SELECT
   c.source_type, c.domain, c.claim_type, c.jurisdiction_code,
   count(*) AS total_chunks,
   count(*) FILTER (WHERE c.embedding IS NOT NULL) AS chunks_with_embedding,
   count(*) FILTER (WHERE c.embedding IS NULL) AS chunks_without_embedding,
   count(*) FILTER (WHERE c.source_url IS NOT NULL AND c.source_url <> '') AS chunks_with_source_url,
   count(*) FILTER (WHERE c.source_url IS NULL OR c.source_url = '') AS chunks_without_source_url,
   round(avg(c.quality_score), 3) AS avg_quality_score,
   (SELECT count(*) FROM rules WHERE verification_status NOT IN ('verified','case_law_verified')) AS unverified_rules_count,
   (SELECT count(*) FROM rules WHERE is_prospective) AS prospective_rows_count,
   (count(*) - count(DISTINCT c.chunk_hash)) AS duplicate_hash_count
FROM corpus_chunks c
GROUP BY c.source_type, c.domain, c.claim_type, c.jurisdiction_code;

CREATE MATERIALIZED VIEW mv_current_employment_legal_chunks AS
SELECT c.id, c.source_table, c.source_row_uuid, c.source_id, c.domain, c.claim_type,
       c.jurisdiction_code, c.authority_ref, c.source_url, c.title, c.heading,
       c.body_text, c.chunk_index, c.chunk_hash, c.embedding, c.embedding_model,
       c.effective_from, c.effective_to, c.quality_score, c.source_type, c.licence_status
FROM corpus_chunks c
WHERE c.is_current = true
  AND COALESCE(c.is_prospective,false) = false
  AND c.jurisdiction_code IN ('GB','EW','S','UK')
  AND c.source_url IS NOT NULL AND c.source_url <> ''
  AND c.chunk_hash IS NOT NULL AND c.chunk_hash <> ''
  AND c.body_text IS NOT NULL AND c.body_text <> ''
  AND COALESCE(c.quality_score, 0) >= 0.6
  AND (c.licence_status IS NULL OR c.licence_status IN ('open','GRANTED','granted'));

CREATE UNIQUE INDEX IF NOT EXISTS mv_current_chunks_hash_idx ON mv_current_employment_legal_chunks (chunk_hash);
CREATE INDEX IF NOT EXISTS mv_current_chunks_juris_idx ON mv_current_employment_legal_chunks (jurisdiction_code, claim_type);

COMMIT;
