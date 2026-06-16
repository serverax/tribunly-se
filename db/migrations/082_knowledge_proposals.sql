-- 082_knowledge_proposals.sql
-- DB-first Legal Truth: controlled write-back queue + case outcome feedback scaffold.
-- LLM/human proposals only; no auto-apply to rules/legislation/case_law.

BEGIN;

-- ── Controlled write-back queue (ingestion proposals) ───────────────────────
CREATE TABLE IF NOT EXISTS knowledge.ingestion_proposals (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposed_by                 TEXT NOT NULL DEFAULT 'llm'
                                CHECK (proposed_by IN ('llm', 'human')),
    proposal_type               TEXT NOT NULL DEFAULT 'missing_rule',
    payload                     JSONB NOT NULL DEFAULT '{}',
    source_verification_status  TEXT NOT NULL DEFAULT 'unverified'
                                CHECK (source_verification_status IN (
                                    'unverified', 'pending_review', 'verified', 'rejected'
                                )),
    approval_status             TEXT NOT NULL DEFAULT 'pending'
                                CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    trace_id                    TEXT,
    reviewed_by                 TEXT,
    reviewed_at                 TIMESTAMPTZ,
    ingestion_job_id            TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Older 082_* migrations may have created this table with `status` instead of `approval_status`.
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS proposed_by TEXT NOT NULL DEFAULT 'llm';
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS source_verification_status TEXT NOT NULL DEFAULT 'unverified';
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS trace_id TEXT;
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS ingestion_job_id TEXT;
ALTER TABLE knowledge.ingestion_proposals
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS ingestion_proposals_status_idx
    ON knowledge.ingestion_proposals (approval_status, created_at DESC);

CREATE INDEX IF NOT EXISTS ingestion_proposals_trace_idx
    ON knowledge.ingestion_proposals (trace_id)
    WHERE trace_id IS NOT NULL;

-- ── Case outcome feedback loop (scaffold) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS case_outcome_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    case_id             UUID NOT NULL,
    trace_id            TEXT,
    predicted_outcome   TEXT,
    actual_outcome      TEXT NOT NULL,
    reasoning_gaps      JSONB NOT NULL DEFAULT '[]',
    linked_feedback_id  UUID REFERENCES agent_feedback(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS case_outcome_feedback_case_idx
    ON case_outcome_feedback (case_id, created_at DESC);

CREATE INDEX IF NOT EXISTS case_outcome_feedback_user_idx
    ON case_outcome_feedback (user_id);

COMMIT;
