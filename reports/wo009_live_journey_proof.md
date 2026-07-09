# WO009 Live Journey Re-Proof

Date: 2026-07-09
Branch: `cc/convergence`
Stack: 15/15 services healthy

## Health Check

```
status: ok
db: connected
auth_mode: jwt
payment_mode: test
ai_provider.active: true
ai_provider.model: qwen2.5:3b-instruct-q6_K
ai_provider.base_url: http://ollama:11434
openrouter_configured: false
```

## Live /assess

Request:
- claim_type: unfair_dismissal
- edt: 2026-05-01
- service_start_date: 2020-01-01
- reason_for_dismissal: conduct
- was_procedure_followed: false
- weekly_pay: 600
- jurisdiction: EW

Response:
- status: ok
- citations: 8 (legislation-backed)
- limitation_date: 2026-07-31
- deadline source: rules
- deadline authority: ERA 1996 s.111(2)
- is_prospective field present (ERA 2025 gate)
- trace_id: 46b0ed10-5c71-461d-9...

## Census at Proof Time

- Distinct acts: 27
- Legislation rows: 3066
- Corpus chunks: 6038
- Services: 15/15 healthy

## k6 Smoke (same session)

- Health p95: 926ms (cold-start), median: 130ms
- Assess p95: 28.5s (under 60s threshold)
- Failure rate: 0%
- All 5 iterations: citations present
