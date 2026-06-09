-- 030_acas_guidance_unique.sql
-- Make ACAS guidance ingestion idempotent. acas_guidance had only a PK on id, so
-- upsert_acas_guidance's `ON CONFLICT DO NOTHING` never matched and re-runs created
-- duplicate rows. This: (1) de-duplicates existing rows keeping the embedded/lowest-id
-- row per (source_url, chunk_index), (2) adds the UNIQUE constraint the upsert needs.
-- Idempotent; safe to re-run.

-- 1) de-duplicate (prefer the row that already has an embedding; else lowest id)
DELETE FROM acas_guidance a
USING acas_guidance b
WHERE a.source_url = b.source_url
  AND a.chunk_index = b.chunk_index
  AND (
        (b.embedding IS NOT NULL AND a.embedding IS NULL)
     OR ((a.embedding IS NULL) = (b.embedding IS NULL) AND a.id > b.id)
      );

-- 2) add the unique constraint (guarded — skip if it already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'acas_guidance_source_chunk_key'
    ) THEN
        ALTER TABLE acas_guidance
            ADD CONSTRAINT acas_guidance_source_chunk_key UNIQUE (source_url, chunk_index);
    END IF;
END$$;
