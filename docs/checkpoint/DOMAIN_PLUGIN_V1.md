# Domain Plugin Checkpoint

Updated: 2026-06-16  
Branch: `release/lawapp-clean-snapshot`

## Done

- Standardized pack tree under `domains/` (employment + 4 stub packs)
- JSON schema: `domains/_schema/domain_pack.schema.json`
- Backend loader/registry/context/API (`loader.py`, `registry.py`, `context.py`, `/api/domains`)
- Mother controller + reasoning router pass `domain_code` into retrieval
- Case OS domain badge + coming-soon indicator (`client/public/js/domain-badge.js`)
- Tests: `test_domain_pack_loader.py`, `test_domain_plugin_system.py`
- Migration stub: `086_domain_registry.sql`
- Architecture doc: `docs/architecture/DOMAIN_PLUGIN_SYSTEM_V1.md`

## Active domain

- Default: `employment` (`LAWAPP_DOMAIN` override supported)
- Retrieval tag: `employment_uk`

## Stub packs (honest unavailable)

- immigration, housing, benefits, debt

## Gaps / follow-up

- Wire `rules_namespace` column filter in `retrieve_rules` when multi-domain rules coexist
- Migrate legacy `domains/employment_uk/` YAML fully into `domains/employment/`
- Admin UI to display `domain_registry` table rows
- Next.js client parity for domain badge (static Case OS done)

## Verify

```bash
pytest tests/test_domain_pack_loader.py tests/test_domain_plugin_system.py tests/test_domain_modularity.py -q
curl -s http://localhost:8000/api/domains
curl -s -X POST http://localhost:8000/assess -H "Content-Type: application/json" \
  -d '{"query":"unfair dismissal","facts":{"dismissal_date":"2025-01-01"},"domain_code":"employment"}'
curl -s -X POST http://localhost:8000/assess -H "Content-Type: application/json" \
  -d '{"query":"visa refusal","facts":{},"domain_code":"immigration"}'
```
