-- 087_knowledge_proposal_type_compat.sql
-- Recovered schemas may carry the earlier graph-only proposal_type check from
-- 082_knowledge_ingestion_proposals.sql. The later proposal queue accepts
-- controlled legal-truth gap types as proposal_type values.

BEGIN;

ALTER TABLE knowledge.ingestion_proposals
    DROP CONSTRAINT IF EXISTS ingestion_proposals_proposal_type_check;

ALTER TABLE knowledge.ingestion_proposals
    ADD CONSTRAINT ingestion_proposals_proposal_type_check
    CHECK (length(trim(proposal_type)) > 0);

COMMIT;
