-- Migration 056: chatbot conversation events
-- Stores controlled-chatbot message and pipeline state. This is audit data,
-- not long-term unrestricted memory.

CREATE TABLE IF NOT EXISTS conversation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    user_id         TEXT NOT NULL,
    case_id         UUID,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    message         TEXT NOT NULL,
    intent          TEXT,
    claim_type      TEXT,
    pipeline_state  TEXT NOT NULL DEFAULT 'NEW_MESSAGE',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversation_events_conversation_idx
    ON conversation_events (conversation_id, created_at);

CREATE INDEX IF NOT EXISTS conversation_events_user_idx
    ON conversation_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS conversation_events_case_idx
    ON conversation_events (case_id, created_at DESC)
    WHERE case_id IS NOT NULL;
