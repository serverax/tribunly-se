# DPIA DPO Review Checklist

**For lawapp — UK Employment Claim Co-Pilot**
**Status:** PENDING — awaiting DPO review

---

## Before You Sign Off

This document lists what the Data Protection Officer (DPO) must verify before setting `reviewed_by_dpo: true` in `docs/compliance-signoff.json`.

**GUARDRAIL:** Do not set `reviewed_by_dpo: true` unless you have genuinely reviewed each item below. A boolean flag without a reviewer name and date is not accepted as evidence.

---

## 1. Processing Description — Verify

- [ ] The DPIA at `docs/dpia-artefact.md` accurately describes all data flows
- [ ] The categories of personal data collected (assessment intake, handoff leads, uploads) are correctly identified
- [ ] The purposes of processing are clearly stated
- [ ] The legal basis for processing (Art.6 UK GDPR) is identified for each purpose
- [ ] Special category data (Art.9) risk is assessed — particularly for uploaded documents and case summaries

## 2. Necessity and Proportionality — Verify

- [ ] Processing is necessary for the stated purposes
- [ ] Less privacy-invasive alternatives have been considered
- [ ] Data minimisation is in place (assessment facts de-identified before AI call)

## 3. Risk Assessment — Verify

- [ ] All risks in the DPIA risk table have been assessed
- [ ] Residual risks after mitigation are acceptable
- [ ] The following implemented controls are accurately described:
  - Fernet encryption for handoff PII and uploaded files
  - 14-field de-identification before any model boundary
  - Admin API key protection
  - Soft-delete + PII clearing (Art.17)
  - JWT HS256 user authentication

## 4. Encryption and Key Management — Note Gaps

- [ ] Reviewer has noted that encryption key is stored in env var (NOT HSM-backed — Phase 7)
- [ ] Reviewer accepts this as acceptable for controlled beta with documented intent to upgrade

## 5. Third-Party Model Boundary — Verify

- [ ] De-identification strips 14 PII field types before any external AI call
- [ ] `boundary_log` is returned in every `/assess` response as evidence
- [ ] No raw uploaded document content is sent to third parties

## 6. Data Retention — Verify

- [ ] Retention policy and deletion endpoints are implemented (Phase 6)
- [ ] Reviewer has noted that retention periods are not yet formally set (Phase 7 gap)

## 7. Subject Rights — Verify

- [ ] Right to erasure (Art.17): `DELETE /cases/{id}` and `DELETE /handoff/leads/{id}` are implemented
- [ ] Right of access (Art.15): SAR process not yet implemented (Phase 7 gap — acceptable for limited beta)

## 8. ICO Prior Consultation — Decide

- [ ] Reviewer has assessed whether ICO prior consultation (Art.36) is required
- [ ] Decision documented in evidence_reference field

## 9. Approval Criteria for Controlled Beta

The controlled beta is limited to:
- Invited users only (no public access)
- England and Wales jurisdiction
- Unfair dismissal and unpaid wages claim types only

Reviewer confirms this scope is acceptable for limited beta operation: [ ]

---

## Recording Your Sign-Off

Once all items are verified, update `docs/compliance-signoff.json`:

```json
"dpia": {
  "reviewed_by_dpo": true,
  "reviewer_name": "<Your Full Name, DPO>",
  "review_date": "<YYYY-MM-DD>",
  "review_scope": "Full DPIA review per checklist at docs/dpia-review-checklist.md v6D",
  "evidence_reference": "<Meeting note / document ref / sign-off email reference>"
}
```

**Do not set `approved: true` unless a second, independent legal sign-off has also occurred.**

---
*Checklist version: 6D | Last updated: 2026-06-01*
