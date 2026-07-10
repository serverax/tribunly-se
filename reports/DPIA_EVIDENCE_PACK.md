# DPIA Evidence Pack

Status: assembly only, owner sign-off pending
Repo: `F:\tribunly-se`
Branch: `cc/convergence`

## 1. Data Flow Map

The current application flow is:

1. Intake and funnel entry via `backend/api/login_gate_routes.py`
2. Assessment via `backend/api/main.py` and the `POST /assess` path
3. Storage and related audit writes via `ingestion/db.py`-backed SQL calls
4. Document and upload handling via `backend/api/upload_routes.py`
5. Feedback and learning-loop writes via `backend/api/feedback_routes.py`
6. Generation / payment gating via `backend/api/main.py` and `backend/api/payment_routes.py`

Third-party and boundary points visible in code:

- External model calls are intended to stay on the local Ollama boundary.
- The de-identification / governance path is part of the assessment route in `backend/api/main.py`.
- Uploads are explicitly fenced to the local app and are not sent to an external LLM.

Relevant code references:

- [backend/api/main.py](F:/tribunly-se/backend/api/main.py)
- [backend/api/upload_routes.py](F:/tribunly-se/backend/api/upload_routes.py)
- [backend/api/login_gate_routes.py](F:/tribunly-se/backend/api/login_gate_routes.py)
- [backend/api/feedback_routes.py](F:/tribunly-se/backend/api/feedback_routes.py)

## 2. Encryption Evidence

Current evidence available in this repo:

- Upload storage path is encrypted-at-rest by design in `backend/api/upload_routes.py`.
- The upload code currently fails closed on missing configuration by warning that unencrypted storage would otherwise be used.
- The standing owner-gated Art.9 runtime proof remains open until the dedicated SE stack is fully usable.

This pack does not claim a live Art.9 proof yet.

Relevant references:

- [backend/api/upload_routes.py](F:/tribunly-se/backend/api/upload_routes.py)
- [reports/security_sweep.md](F:/tribunly-se/reports/security_sweep.md)

## 3. Retention / Deletion Mechanics

The schema uses FK-driven deletion boundaries, including `ON DELETE CASCADE` and `ON DELETE SET NULL` on user/case-linked tables.

Examples visible in migration files:

- `db/migrations/001_initial.sql`
- `db/migrations/004_phase3_tables.sql`
- `db/migrations/005_phase4_evidence.sql`
- `db/migrations/046_payment_and_upload_tables.sql`
- `db/migrations/047_auth_stack.sql`
- `db/migrations/051_login_gate.sql`
- `db/migrations/059_workflow_schema_compat.sql`
- `db/migrations/077_feature_spec_operational.sql`
- `db/migrations/085_user_preferences_locale.sql`

The exact cascade chain is therefore schema-backed, not application-invented.

## 4. Security Sweep / Headers

The security sweep artifact records:

- pip-audit clean
- no real secrets found in the working tree
- response security headers deployed
- rate limiting active

Reference:

- [reports/security_sweep.md](F:/tribunly-se/reports/security_sweep.md)

## 5. Upload Route / Referral-Lane Fence Status

Upload route fence:

- `backend/api/upload_routes.py` is gated by `LAWAPP_ENABLE_API_UPLOADS`
- When uploads are disabled by environment, the route returns 404
- Raw uploads are stored encrypted and not sent to an external LLM

Referral / funnel lane fence:

- `backend/api/login_gate_routes.py` keeps the teaser/full-result split and gates the full result behind login capability
- `backend/api/feedback_routes.py` requires authenticated user context for writes

Relevant references:

- [backend/api/upload_routes.py](F:/tribunly-se/backend/api/upload_routes.py)
- [backend/api/login_gate_routes.py](F:/tribunly-se/backend/api/login_gate_routes.py)
- [backend/api/feedback_routes.py](F:/tribunly-se/backend/api/feedback_routes.py)

## 6. Open Items

- Owner sign-off on the DPIA pack
- Live Art.9 runtime fail-closed proof on the Swedish stack
- Stripe proof remains blocked on owner-controlled test keys
- Any Swedish product naming decision

This pack is an evidence assembly only. It is not a sign-off document.
