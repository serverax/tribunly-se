# Controlled-Beta Human Review Handover

**lawapp — UK Employment Claim Co-Pilot**
**Date:** 2026-06-01
**Status:** TECHNICAL PREPARATION COMPLETE — Awaiting DPO and legal reviews

---

## Summary for Reviewers

Phase 6 technical preparation is complete. Two human reviews are required before
the system can proceed to controlled beta. This document explains what each reviewer
must do, what they must record, and how to verify readiness afterwards.

**No DPO review has been performed. No legal review has been performed.**
**Neither review has been faked. All sign-off flags are currently false.**

---

## Current Readiness State

| Check | Status |
|---|---|
| Technical preparation (Phase 6) | COMPLETE |
| `controlled_beta_ready` | **FALSE** |
| `production_ready` | **FALSE** |
| DPIA reviewed by DPO | **NOT DONE** |
| Privacy notice legally reviewed | **NOT DONE** |
| DPO sign-off faked | No |
| Legal sign-off faked | No |

To check current state at any time:
```bash
python scripts/check_beta_readiness.py
```

---

## Review 1: DPO — DPIA Review

**Who:** Data Protection Officer (DPO) or qualified data protection practitioner
**Document to review:** `docs/dpia-artefact.md`
**Checklist:** `docs/dpia-review-checklist.md`

### What you must do

1. Read `docs/dpia-artefact.md` in full.
2. Work through every item in `docs/dpia-review-checklist.md` and confirm each.
3. If anything requires changes, raise them with the development team before signing.
4. When satisfied, sign the checklist (physical or digital signature on a printed/PDF copy).

### What you must record

Update `docs/compliance-signoff.json` — the `"dpia"` section:

```json
"dpia": {
  "drafted": true,
  "reviewed_by_dpo": true,
  "approved": false,
  "reviewer_name": "<Your Full Name and Role, e.g. Jane Smith, DPO>",
  "review_date": "<YYYY-MM-DD>",
  "approval_date": null,
  "review_scope": "Full DPIA review per checklist at docs/dpia-review-checklist.md",
  "evidence_reference": "<Reference to signed checklist, e.g. file location or meeting note ID>"
}
```

**All four fields — `reviewer_name`, `review_date`, `review_scope`, and
`evidence_reference` — are required. Setting `reviewed_by_dpo=true` alone
is not sufficient; the system will reject a boolean-only sign-off.**

### What the system checks

After you update the file, the system validates:
- `reviewed_by_dpo=true` AND
- `reviewer_name` is not null AND
- `review_date` is not null

If either evidence field is missing, `controlled_beta_ready` will remain false
and the blocker message will specify which fields are missing.

---

## Review 2: Legal — Privacy Notice Review

**Who:** Qualified legal counsel (solicitor, in-house lawyer, or equivalent)
**Document to review:** `docs/privacy-notice-draft.md`
**Checklist:** `docs/privacy-review-checklist.md`

### What you must do

1. Read `docs/privacy-notice-draft.md` in full.
2. Work through every item in `docs/privacy-review-checklist.md` and confirm each.
3. Note any changes required (placeholder fields, legal basis, retention periods).
4. Raise required changes with the development team before signing.
5. When satisfied with the document, sign the checklist.

### What you must record

Update `docs/compliance-signoff.json` — the `"privacy_notice"` section:

```json
"privacy_notice": {
  "drafted": true,
  "legally_reviewed": true,
  "published": false,
  "reviewer_name": "<Your Full Name and Role, e.g. Alex Jones, Solicitor>",
  "review_date": "<YYYY-MM-DD>",
  "publish_date": null,
  "review_scope": "Full privacy notice review per checklist at docs/privacy-review-checklist.md",
  "evidence_reference": "<Reference to engagement letter or file ID>"
}
```

**Note:** `published` remains `false` until the notice is live at a public URL.
Set `publish_date` only when published.

---

## After Both Reviews Are Recorded

Once both sections of `docs/compliance-signoff.json` are updated with genuine
evidence, run:

```bash
# From the project root (Docker required):
docker compose run --rm ingestion python scripts/check_beta_readiness.py
```

Or directly if Python environment is active:
```bash
python scripts/check_beta_readiness.py
```

Expected output when both reviews are recorded:
```
Result: CONTROLLED BETA READY
```

If any fields are still missing, the script reports the specific blockers.

---

## Hard Constraints for Reviewers

These constraints are enforced by the system and cannot be bypassed:

- `reviewed_by_dpo=true` requires `reviewer_name` AND `review_date` — no exceptions
- `legally_reviewed=true` requires `reviewer_name` AND `review_date` — no exceptions
- A boolean flag without evidence is rejected; `controlled_beta_ready` stays false
- `compliance-signoff.json` is the single source of truth — no env var overrides

---

## What Happens After Controlled Beta Approval

Once `controlled_beta_ready=true`:

1. Follow the full sequence in `docs/pre-beta-runbook.md`
2. Configure production environment using `docs/env-production.template`
3. Run all quality gates: legal accuracy, rules verification, full regression
4. Verify `GET /admin/production-readiness` reports `controlled_beta_ready=true`
5. Proceed to controlled beta with invited users only

**For full production:** Additional Phase 7 work is required. See `docs/pre-beta-runbook.md`.

---

## Document References

| Document | Purpose |
|---|---|
| `docs/dpia-artefact.md` | Full DPIA artefact for DPO review |
| `docs/dpia-review-checklist.md` | Itemised DPO sign-off checklist |
| `docs/privacy-notice-draft.md` | Privacy notice draft for legal review |
| `docs/privacy-review-checklist.md` | Itemised legal sign-off checklist |
| `docs/compliance-signoff.json` | Machine-readable sign-off state (update here) |
| `docs/pre-beta-runbook.md` | Full operational sequence for beta launch |
| `docs/env-production.template` | Production environment variable reference |
| `scripts/check_beta_readiness.py` | Quick readiness verification script |

---

*Handover document version: Phase 6 closure | 2026-06-01*
*Technical preparation status: COMPLETE*
*All sign-off flags: FALSE (no reviews performed, no reviews faked)*
