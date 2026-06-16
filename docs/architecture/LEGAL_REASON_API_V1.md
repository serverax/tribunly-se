# Legal Reason API V1

> **SUPERSEDED - not implemented per [ADR-000](../adr/ADR-000-langgraph-gate.md).**  
> Historical design only. No `/api/v1/legal/reason` route exists. Legal assessment uses Brain-backed routes (`/assess`, brain trace APIs).

**Endpoint:** `POST /api/v1/legal/reason` (removed)  
**Router:** `backend/api/legal_reason_routes.py`  
**Orchestration:** LangGraph adapter (see `LANGGRAPH_ORCHESTRATION_V1.md`)

## Request

```json
{
  "claim_type": "unfair_dismissal",
  "facts": {
    "edt": "2026-05-10",
    "employment_length": 18,
    "dismissal_type": "conduct"
  },
  "message": "optional free text",
  "jurisdiction": "EW",
  "case_id": "optional-uuid"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| claim_type | Yes | e.g. `unfair_dismissal` |
| facts.edt | Yes for dismissal claims | Effective date of termination |
| jurisdiction | No | Default `EW` |

Auth: same as `/assess` (Bearer or `X-User-ID` in dev modes).

## Response

```json
{
  "claim_type": "unfair_dismissal",
  "viability": "yes|no|uncertain",
  "strength": "low|medium|high|uncertain",
  "weaknesses": ["..."],
  "citations": [{"cite": "ERA 1996 s.98", "url": "https://..."}],
  "confidence": 0.0,
  "deadline": {
    "limitation_date": "2026-08-09",
    "source": "rules",
    "authority": "ERA 1996 s.111",
    "is_prospective": false
  },
  "reasoning_summary": "...",
  "grounding_score": 0.0,
  "status": "ok|missing_edt|insufficient_grounding|not_supported",
  "trace_id": "uuid",
  "governance": {"passed": true, "blocked": false, "status": "ok"},
  "graph_context_nodes": 0
}
```

## Latency design

| Stage | Target | Strategy |
|-------|--------|----------|
| classify + rules | < 50ms | Deterministic, DB-only |
| retrieve | < 150ms | pgvector + BM25 (existing retrieve) |
| graph_enrich | < 100ms | Postgres traversal (8018 logic in-process) |
| reason | 2-8s | Local Ollama via pipeline; fail-soft to rules-only |
| govern | inline | CitationGuard inside pipeline |

Rate limit: inherits global FastAPI limiter (same middleware as monolith).

## Error codes

| HTTP | Condition |
|------|-----------|
| 503 | Pipeline exception / inference unavailable |
| 200 + status field | Business failures (missing_edt, insufficient_grounding) |

## Example

```bash
curl -X POST http://localhost:8000/api/v1/legal/reason \
  -H "Content-Type: application/json" \
  -d '{"claim_type":"unfair_dismissal","facts":{"edt":"2026-05-10","employment_length":18,"dismissal_type":"conduct"}}'
```

## Conflict resolution

- Does not bypass Brain for product flows that require full 19-step trace; use `/api/brain/trace` when audit completeness is required.
- Citations must pass CitationGuard inside `pipeline.assess`; no static success payloads.
