# Privacy Notice — DRAFT ARTEFACT

**Status:** DRAFT — Not legally reviewed. Not suitable for publication.  
**Phase:** 6 artefact placeholder. Legal review required before use.  
**Date:** 2026-06-01

---

## IMPORTANT

This is a DRAFT placeholder artefact. It has NOT been:
- Reviewed by a qualified lawyer or data protection officer
- Finalised or approved for publication
- Tested against current UK GDPR / Data Protection Act 2018 requirements
- Reviewed by the ICO or any regulatory body

Do NOT publish this as a privacy notice. Do NOT rely on it for compliance.

---

## 1. Who we are

[OPERATOR NAME AND CONTACT DETAILS — TO BE COMPLETED]

lawapp is an online self-help tool for employment law information.
It is not a law firm and does not provide regulated legal advice.

**Data controller:** [NAME, ADDRESS, EMAIL — TO BE COMPLETED]  
**DPO / contact:** [EMAIL — TO BE COMPLETED IF DPO REQUIRED]

---

## 2. What personal data we collect

We collect the following categories of data:

**Assessment intake data (not stored directly):**
- Employment dates (EDT, service start)
- Reason for dismissal / wages information
- Weekly pay
- ACAS Early Conciliation dates
- Jurisdiction

**Account / case data (if saved):**
- Case reference (UUID)
- Assessment results (de-identified structured output)
- Key dates
- Document metadata

**Handoff referral data (if submitted):**
- Name, email, phone (optional)
- Brief case summary
- Consent record

**Upload data (if documents uploaded):**
- Document files (stored locally, Phase 6: Fernet-encrypted)
- Extracted metadata

We do NOT collect: names, addresses, or employer names as part of assessment intake.
PII submitted in handoff forms is stored with explicit consent.

---

## 3. Legal basis for processing

[TO BE DETERMINED WITH LEGAL ADVICE — CANDIDATE BASES:]
- Contract performance (Art.6(1)(b)): processing assessment facts to provide the service
- Legitimate interests (Art.6(1)(f)): improving accuracy of legal information
- Consent (Art.6(1)(a)): handoff referral data

Special category data (Art.9): [TO BE ASSESSED — see DPIA artefact]

---

## 4. How long we keep your data

| Data type          | Retention period |
|-------------------|-----------------|
| Assessment results | [TO BE SET — draft: 90 days]  |
| Handoff leads      | [TO BE SET — draft: 30 days]  |
| Uploaded files     | [TO BE SET — draft: 90 days]  |
| Audit logs         | [TO BE SET — minimum 6 years for legal records] |

Right to erasure requests: DELETE /cases/{id} and DELETE /handoff/leads/{id}
endpoints implemented in Phase 6.

---

## 5. Your rights

Under UK GDPR you have the right to:
- Access your personal data (Art.15)
- Rectification of inaccurate data (Art.16)
- Erasure ("right to be forgotten") (Art.17) — supported by Phase 6 deletion endpoints
- Restriction of processing (Art.18)
- Data portability (Art.20)
- Object to processing (Art.21)

To exercise rights: [CONTACT EMAIL — TO BE COMPLETED]

---

## 6. Security

Phase 6 security measures:
- PII in handoff leads encrypted at rest (Fernet AES-128-CBC)
- Uploaded files encrypted at rest (Fernet AES-128-CBC)
- Admin endpoints protected by API key
- Model boundary: PII stripped before any third-party AI call

Remaining gaps (see DPIA artefact):
- Encryption key management (env var — HSM required for production)
- User authentication (Phase 7)
- Full access control audit trail (Phase 7)

---

## 7. Transfers

[TO BE ASSESSED — third-party LLM usage requires SCCs or equivalent if outside UK/EEA]

Current: Anthropic API (when configured) receives de-identified facts only.
Raw PII is never sent to third parties.

---

## END OF DRAFT ARTEFACT
