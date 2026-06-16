# Matter and cases alias plan

**Owner decision:** Feature Spec §5 #1 ([`OWNER_DECISIONS_2026-06-16.md`](../decisions/OWNER_DECISIONS_2026-06-16.md)).

## Principle

`matter` is canonical. `cases` is legacy. Replace over time; do not sync forever.

## Bridge (migration 077)

```sql
matter.case_id UUID REFERENCES cases(id)  -- optional link during transition
```

New feature-layer APIs use `/api/features/matter/*`. Existing Case Hub continues on `/cases/*` until alias period ends.

## Transition phases

| Phase | Behaviour |
|-------|-----------|
| **Now (Wave 2 prep)** | Creating a `matter` may set `case_id` when user already has a `cases` row |
| **Wave 2** | `POST /api/features/matter` creates matter; hub reads matter + linked case |
| **Wave 3+** | New writes go to `matter` / `evidence_item` only |
| **Deprecation** | `/cases/*` routes become thin aliases to matter service, then removed |

## API alias map (planned)

| Legacy | Canonical (future) |
|--------|-------------------|
| `POST /cases` | `POST /api/features/matter` (+ optional case back-compat) |
| `GET /cases/{id}` | `GET /api/features/matter/{id}/hub` |
| `POST /cases/{id}/uploads` | `POST /api/features/matter/{id}/evidence` |

## Document storage (Feature §5 #7)

Registered uploads land in `evidence_item` only. Legacy `documents` table is read-only during migration.

## Acceptance

- No dual-write sync jobs between `cases` and `matter`
- Brain trace and audit reference `matter_id` where spec requires
- Deprecation announced in API OpenAPI before route removal
