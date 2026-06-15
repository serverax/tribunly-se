-- 059_workflow_schema_compat.sql
-- Additive compatibility columns for shared/pre-existing databases.
-- These columns are required by LawApp's core workflow routes.

ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'none';

ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS action text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS resource_type text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS resource_id text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS result text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS documents_user_idx ON documents (user_id);
CREATE INDEX IF NOT EXISTS audit_events_user_idx ON audit_events (user_id);
CREATE INDEX IF NOT EXISTS audit_events_action_idx ON audit_events (action);
