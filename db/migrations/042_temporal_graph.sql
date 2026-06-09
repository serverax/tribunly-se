-- 042_temporal_graph.sql
-- Temporal Graph RAG: events (nodes) + temporal/statutory relations (edges) for
-- NetworkX serialization and direct SQL traversal. Idempotent + additive.
--
-- CORRECTIONS vs the original blueprint:
--   * FK references workspaces(id) (this schema's table), NOT lawapp_workspaces.
--   * NO Postgres session RLS (this stack does not set request.jwt.claim.*).
--     Isolation is enforced at the application layer: every query filters by
--     (user_id [, workspace_id]). workspace_id is nullable for unowned/test rows.
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL,
    event_label   VARCHAR(100) NOT NULL,        -- e.g. 'Suspension', 'Dismissal'
    asserted_date DATE NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id, event_label)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id               UUID NOT NULL,
    source_node_id        UUID NOT NULL REFERENCES graph_nodes(node_id) ON DELETE CASCADE,
    target_node_id        UUID NOT NULL REFERENCES graph_nodes(node_id) ON DELETE CASCADE,
    relationship_type     VARCHAR(100) NOT NULL,  -- e.g. 'next_event','statutory_deadline_trigger'
    calculated_delta_days INTEGER NOT NULL,       -- pre-computed day gap
    metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_self_referential_edges CHECK (source_node_id <> target_node_id)
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_lookup    ON graph_nodes (user_id, workspace_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_traversal ON graph_edges (user_id, workspace_id, source_node_id);
