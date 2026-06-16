-- 039_corpus_chunks_ingestion_run_id.sql
-- Perpetual Law Brain provenance: link each chunk to the ingestion run that
-- produced it (PART 7  -  "Every legal source/chunk must include ingestion_run_id").
-- Additive + idempotent. Does NOT recreate legal_sources / corpus_ingestion_runs /
-- corpus_ingestion_errors  -  those already exist (migrations 028, 037).
ALTER TABLE corpus_chunks ADD COLUMN IF NOT EXISTS ingestion_run_id UUID;
CREATE INDEX IF NOT EXISTS corpus_chunks_run_idx ON corpus_chunks (ingestion_run_id);
