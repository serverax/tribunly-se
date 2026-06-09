# Data Protection Impact Assessment (DPIA) — ARTEFACT IN PROGRESS

**Status:** IN PROGRESS — Not completed. Not legally reviewed.  
**Phase:** 6 placeholder. Legal and DPO review required.  
**Date:** 2026-06-01  
**Regulation:** UK GDPR / Data Protection Act 2018

---

## IMPORTANT

This is a DPIA artefact in progress. It has NOT been:
- Completed by a qualified data protection officer (DPO)
- Reviewed by legal counsel
- Submitted to the ICO for prior consultation (if required under Art.36)
- Approved for production deployment

A DPIA is likely required before deploying lawapp to real users, because:
1. The service processes employment-related personal data (financial, workplace)
2. Uploaded documents may contain special category data (health, trade union membership)
3. Automated decision-making elements (assessment, viability scoring)
4. Systematic processing of personal data

---

## 1. Description of processing

**Controller:** [TO BE COMPLETED]  
**Processor(s):** [AI provider if used — Anthropic, OpenRouter. TO BE CONFIRMED]

**Purposes:**
- Provide self-help employment law information
- Compute deterministic deadlines from statute
- Generate self-help document drafts
- Refer users to qualified employment solicitors

**Description of data flows:**
1. User enters employment facts (intake form)
2. Facts de-identified before any third-party API call
3. De-identified facts sent to AI model (if configured)
4. Results returned; facts not persisted (only structured assessment stored)
5. Handoff: user name/email collected with consent for solicitor referral
6. Documents uploaded: file stored locally (Phase 6: encrypted)

---

## 2. Necessity and proportionality

**Is this processing necessary for the purpose?** [TO BE ASSESSED]
**Is it proportionate to the risk?** [TO BE ASSESSED]
**Could a less privacy-invasive approach achieve the same?** [TO BE ASSESSED]

---

## 3. Risk identification

| Risk | Likelihood | Severity | Current controls | Residual risk |
|------|-----------|----------|-----------------|---------------|
| Unauthorised access to case data | Medium | High | Admin API key auth (Phase 6) | Medium |
| PII in handoff leads exposed | Medium | High | Fernet encryption (Phase 6) | Medium |
| Uploaded files contain special category data | High | High | Encryption at rest (Phase 6) | Medium |
| AI model receives PII | Low | Very High | 14-field de-identification; boundary_log | Low |
| Uploaded files leaked | Medium | High | Local encryption (Phase 6); no external storage | Medium |
| Data breach (key compromise) | Low | Very High | Env var key (Phase 6 only — HSM in Phase 7) | Medium-High |
| Inadequate retention | Medium | Medium | Soft-delete + retention script (Phase 6) | Low |
| Special category data in case summary | Medium | High | User-entered only; no systematic processing | Medium |

---

## 4. Article 9 (special category data) assessment

Employment claims may involve:
- Health/disability data: if claimant cites health-related reason
- Trade union membership: if dismissal relates to TU activity
- Age: for qualifying period calculation (indirect)

lawapp does NOT systematically collect Art.9 data.
Handoff lead case_summary field: user may voluntarily include Art.9 data.

**Mitigation:**
- Case summary limited to free text; no structured Art.9 collection
- Warning to be added to handoff form: "Do not include medical information"
- [TO BE REVIEWED]

---

## 5. Measures to mitigate risks

**Implemented (Phase 6):**
- Encryption at rest for uploads and handoff PII (Fernet AES-128-CBC)
- Admin API key protection
- Soft delete + PII clearing (Art.17 GDPR)
- Retention policy mechanism
- De-identification before AI boundary (14 field types)
- Boundary_log in every response

**Not yet implemented:**
- HSM/KMS key management (Phase 7)
- Full user authentication (Phase 7)
- Access control audit trail (Phase 7)
- Formal consent management system (Phase 7)
- Breach notification procedure (Phase 7)
- Subject access request process (Phase 7)

---

## 6. ICO prior consultation

Required under UK GDPR Art.36 if residual risk remains high after mitigation.

**Recommendation:** Consult ICO before production launch given:
- Potential Art.9 data in case summaries
- AI processing of employment facts
- [DPO to assess if prior consultation required]

---

## 7. Sign-off checklist

- [ ] Legal review completed
- [ ] DPO review completed (if applicable)
- [ ] Privacy notice finalised
- [ ] ICO consultation (if required)
- [ ] HSM key management implemented
- [ ] Full user authentication implemented
- [ ] Formal consent management implemented
- [ ] Breach notification procedure documented
- [ ] SAR process documented
- [ ] Approved for production deployment

---

## END OF DPIA ARTEFACT IN PROGRESS
