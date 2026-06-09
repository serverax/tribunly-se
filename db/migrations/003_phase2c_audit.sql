-- Migration 003: Phase 2C assessment audit log
-- Every governed assessment creates an immutable audit record.
-- Never delete; use case_id cascade for user erasure of case data.

CREATE TABLE IF NOT EXISTS assessment_audit_logs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid        REFERENCES cases(id) ON DELETE CASCADE,
    fact_snapshot_hash  text        NOT NULL,    -- SHA256 of de-identified facts at assessment time
    rules_used          jsonb,                   -- rules rows consumed (key, value, authority)
    retrieval_bundle    jsonb,                   -- BM25/pgvector authorities returned
    model_provider      text        NOT NULL,    -- StubReasoningModel | ClaudeReasoningModel | OpenRouterReasoningModel
    model_name          text,                    -- specific model id used
    boundary_log        jsonb       NOT NULL,    -- de-identification proof
    grounding_score     numeric(4,3),
    confidence_score    numeric(4,3),
    governance_result   jsonb       NOT NULL,    -- {passes, failure_reason}
    output_version      text        NOT NULL DEFAULT '1.0',
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS aal_case_idx ON assessment_audit_logs (case_id);
CREATE INDEX IF NOT EXISTS aal_created_idx ON assessment_audit_logs (created_at);
