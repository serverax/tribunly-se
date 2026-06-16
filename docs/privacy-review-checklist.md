# Privacy Notice Legal Review Checklist

**For lawapp  -  UK Employment Claim Co-Pilot**
**Status:** PENDING  -  awaiting legal review

---

## Before You Sign Off

This document lists what legal counsel must verify before setting `legally_reviewed: true` in `docs/compliance-signoff.json`.

**GUARDRAIL:** Do not set `legally_reviewed: true` unless you have reviewed each item below. A boolean flag without reviewer name, date, and review_scope is not accepted as evidence.

---

## 1. Legal Basis  -  Verify

- [ ] The legal basis for processing is correctly stated for each purpose
  - Assessment intake: candidate basis [to be determined by lawyer  -  Art.6(1)(b) or (f)]
  - Handoff leads: consent (Art.6(1)(a))  -  consent mechanism reviewed
  - Uploaded files: [legal basis to be determined]
- [ ] Legal basis is adequate and accurately described in the notice

## 2. Data Controller Identity  -  Verify

- [ ] Controller name and contact details are correct and up to date
- [ ] DPO contact details (if applicable) are included
- [ ] ICO registration number is correct (if registered)

## 3. Categories of Data  -  Verify

- [ ] All categories of personal data collected are listed
- [ ] Special category data handling is addressed (uploaded documents may contain health data)
- [ ] No categories are omitted or understated

## 4. Retention Periods  -  Verify

- [ ] Retention periods are stated for each category
- [ ] Periods are legally defensible
- [ ] Note: current implementation uses configurable retention (Phase 7 gap  -  must be set before publication)

## 5. Subject Rights  -  Verify

- [ ] All eight UK GDPR rights are addressed
- [ ] Erasure process described (DELETE endpoints implemented  -  Phase 6)
- [ ] SAR process described (not yet implemented  -  acknowledge gap or defer publication)
- [ ] Contact details for rights requests are correct

## 6. Third-Party Processing  -  Verify

- [ ] Anthropic (if used) is listed as a processor with appropriate basis
- [ ] De-identification before AI call is accurately described
- [ ] No processor is omitted

## 7. International Transfers  -  Verify

- [ ] If Anthropic is outside UK/EEA, transfer mechanism is identified (SCCs or adequacy)
- [ ] Transfer section is accurate

## 8. Plain English Test

- [ ] The notice is understandable to a lay user without legal training
- [ ] No misleading or ambiguous language
- [ ] "Not a law firm / not legal advice" boundary is clear

## 9. Pre-Publication Checklist

Before setting `published: true`:
- [ ] Legal review complete and signed
- [ ] Placeholder fields (controller details, retention periods) are filled in
- [ ] Notice is live at a publicly accessible URL
- [ ] URL recorded in compliance-signoff.json

---

## Recording Your Sign-Off

Once legal review is complete:

```json
"privacy_notice": {
  "legally_reviewed": true,
  "reviewer_name": "<Your Full Name, Solicitor/Legal Counsel>",
  "review_date": "<YYYY-MM-DD>",
  "review_scope": "Full privacy notice review per checklist at docs/privacy-review-checklist.md v6D",
  "evidence_reference": "<File reference / engagement letter ref>"
}
```

After publication (separate action):
```json
"published": true,
"publish_date": "<YYYY-MM-DD>",
```

---
*Checklist version: 6D | Last updated: 2026-06-01*
