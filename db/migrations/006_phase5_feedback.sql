-- Migration 006: Phase 5 user feedback and AI quality tracking
-- Placeholder — finalised before Phase 5 build starts.

CREATE TABLE IF NOT EXISTS user_feedback (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     uuid        REFERENCES cases(id) ON DELETE CASCADE,
    rating      int         CHECK (rating BETWEEN 1 AND 5),
    issue_type  text,       -- wrong_assessment | missing_weakness | deadline_error
                             -- document_quality | coaching | other
    comment     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS uf_case_idx ON user_feedback (case_id);
