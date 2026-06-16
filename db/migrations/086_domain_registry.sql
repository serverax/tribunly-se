-- 086_domain_registry.sql
-- Optional metadata spine for domain packs (filesystem packs remain authoritative at runtime).

CREATE TABLE IF NOT EXISTS domain_registry (
    module_code       TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('production', 'partial', 'stub', 'unavailable')),
    enabled           BOOLEAN NOT NULL DEFAULT false,
    rules_namespace   TEXT,
    retrieval_domain  TEXT,
    pack_path         TEXT NOT NULL,
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE domain_registry IS
    'Mirror of domains/*/domain_config.json for admin reporting. Loader reads JSON packs first.';

-- Seed from current employment catalog linkage (honest: only employment enabled)
INSERT INTO domain_registry (module_code, title, status, enabled, rules_namespace, retrieval_domain, pack_path)
VALUES
    ('employment', 'UK Employment Law', 'production', true, 'employment_rules', 'employment_uk', 'domains/employment'),
    ('immigration', 'UK Immigration Law', 'stub', false, NULL, NULL, 'domains/immigration'),
    ('housing', 'UK Housing Law', 'stub', false, NULL, NULL, 'domains/housing'),
    ('benefits', 'UK Benefits and Social Security', 'stub', false, NULL, NULL, 'domains/benefits'),
    ('debt', 'UK Debt and Consumer Rights', 'stub', false, NULL, NULL, 'domains/debt')
ON CONFLICT (module_code) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    enabled = EXCLUDED.enabled,
    rules_namespace = EXCLUDED.rules_namespace,
    retrieval_domain = EXCLUDED.retrieval_domain,
    pack_path = EXCLUDED.pack_path,
    synced_at = now();
