-- Migration 016: Change embedding vector dimension from 1536 to 384
-- Reason: switching from OpenAI text-embedding-3-small (1536-dim, requires paid API)
--         to sentence-transformers all-MiniLM-L6-v2 (384-dim, runs locally, no API key)
-- This enables pgvector semantic retrieval without any external API dependency.
--
-- SAFE: All embedding columns are currently NULL (no embeddings generated yet).
--       Dropping and re-adding the column loses nothing.

-- Drop IVFFlat indexes (reference the old vector type)
DROP INDEX IF EXISTS legislation_embedding_idx;
DROP INDEX IF EXISTS cl_chunk_embedding_idx;
DROP INDEX IF EXISTS acas_embedding_idx;
DROP INDEX IF EXISTS official_guidance_embedding_idx;

-- Alter embedding columns to vector(384)
ALTER TABLE legislation        ALTER COLUMN embedding TYPE vector(384);
ALTER TABLE case_law_chunks    ALTER COLUMN embedding TYPE vector(384);
ALTER TABLE acas_guidance      ALTER COLUMN embedding TYPE vector(384);
ALTER TABLE official_guidance  ALTER COLUMN embedding TYPE vector(384);

-- Recreate IVFFlat indexes for vector(384)
-- lists=10 for small corpus; increase when corpus exceeds 10k rows.
CREATE INDEX IF NOT EXISTS legislation_embedding_idx
    ON legislation USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS cl_chunk_embedding_idx
    ON case_law_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS acas_embedding_idx
    ON acas_guidance USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS official_guidance_embedding_idx
    ON official_guidance USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
