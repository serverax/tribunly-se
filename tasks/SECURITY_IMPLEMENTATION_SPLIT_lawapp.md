# LawApp — Security Implementation: Code Track vs Owner Track

**Version:** 1.0
**Date:** 16 June 2026
**Owner:** Khalid
**Source:** Security Architecture Design v1.0
**Purpose:** split every control in the security architecture into what Cursor builds and what only you can own, and show where the two hand off.

---

## How to read this

A security architecture is mostly not application code. Roughly a third is buildable in the repo. The rest is decisions, custody of secrets and keys, legal ownership, appointments, and sign-offs that an AI coding agent cannot and must not do. If you give the whole architecture to Cursor, you get the code and lose the rest. So two tracks run in parallel.

- **Code track:** Cursor implements under your review.
- **Owner track:** you hold these. They are legal duties, custody, decisions, or external engagements.
- **Handoffs:** a few controls need both. Your action unblocks the code task. Those are called out in section 3, and you should do them first.

---

## 1. Code track — assign to Cursor (you review)

These are mechanisms. Each maps to a control in the security doc and to a Cursor task. Every one needs your review before merge; the security-sensitive ones (marked R) need line-by-line sign-off.

| Control | Cursor task | Governing rule | Needs from you first | Acceptance | R |
|---------|-------------|----------------|----------------------|-----------|---|
| MFA enforcement logic | Enforce MFA on privileged roles in the auth flow | 30-backend | MFA method chosen, accounts to enrol | A privileged login without a second factor is rejected | R |
| JWT hardening | Short-lived access, rotating refresh, asymmetric signing, iss/aud validation | 30-backend | Signing keys provisioned in the secret store | Expired/forged tokens rejected; keys read from secret store, not code | R |
| RBAC + object-level authz | Role model and per-object access checks | 10-security | Role definitions confirmed | A user cannot read another user's matter by ID | R |
| Row-level security | Postgres RLS on matter and matter-scoped tables | 20-database | none | Cross-tenant query returns nothing | R |
| Least-privilege DB roles | Separate corpus-read and app read-write roles, grants | 20-database | none | App role cannot write to corpus tables | R |
| Secrets integration | Read all credentials from refs, never literals | 10-security | Secret store provisioned and populated (your task 2.1) | No credential literal anywhere in the repo | R |
| TLS and mTLS config | Ingress TLS, service-to-service mTLS in manifests | security 6.2 | Certs/issuer provisioned (your task 2.3) | All traffic encrypted; no plaintext service path | R |
| Input validation, parameterised queries | Across the FastAPI surface | 30-backend | none | No string-built SQL; malformed input rejected |  |
| Lock down API surface | Disable or auth-protect /docs and /openapi.json outside dev | 30-backend | none | Swagger unreachable in non-dev |  |
| Rate limiting and bot protection | On anonymous tool endpoints | 30-backend | none | Abuse and cost-spike limits enforced |  |
| Redaction at the boundary | Pass input and uploads through redaction before logging or embedding | 10-security | none | No PII reaches logs |  |
| Verification gate as control | Staging-only writes, citation CHECK, gate flow | 40-ai-gate | none | No path writes model output to authoritative tables | R |
| Vector store isolation | Encrypt vector store, per-matter embedding namespaces | security 6.4 | none | One user's vectors never returned in another's query | R |
| Prompt-injection handling | Untrusted-data handling, input scanners, de-agented LLM | 40-ai-gate | none | Uploaded doc with hidden instructions does not alter behaviour | R |
| RAG Triad eval + adversarial tests | Groundedness/context/answer scoring, injection test suite | 40-ai-gate | none | Test set passes; low-groundedness output is gated |  |
| Default-deny segmentation | Network policies for the four zones | security 6.5 | none | Zone 0 cannot reach the data tier; Postgres not public | R |
| Container hardening | Non-root, read-only FS, dropped caps, minimal images | security 6.5 | none | Containers run hardened; no secrets baked in |  |
| Audit immutability | Append-only audit writes, no delete path | security 6.6 | none | Gate decisions logged and unalterable; chain reconstructable | R |
| Encryption at rest | Encrypted volumes for DBs, vector, audit, backups | security 6.2 | Storage/KMS configured (your task 2.2) | Volumes encrypted |  |
| SIEM shipping + detections | Log forwarding, brute-force/impossible-travel/mass-export rules | security 6.6 | SIEM destination chosen | Alerts fire on simulation |  |
| Backup automation | Scheduled encrypted backups, restore script | security 10 | Backup target and key custody decided (yours) | Backups run; restore verified |  |
| CI security gates | Trivy image scan, Checkov IaC scan, SBOM, image signing, admission control | security 10 | CI platform access | Unsigned or failing images blocked from deploy |  |

---

## 2. Owner track — you hold these (cannot be delegated to a coding agent)

These are duties, custody, decisions, and engagements. Cursor can draft a document for some, but you own the outcome.

**Legal and regulatory**
- **DPIA.** Mandatory: large-scale special category processing plus AI. You author and own it as controller. Cursor can draft a template; the assessment and sign-off are yours.
- **Appoint a DPO.** Likely mandatory under Article 37 and must be independent of you as controller. External or fractional. Pure org decision.
- **Lawful basis for special category data (Art 9).** You determine it and approve the consent wording. Legal decision.
- **ICO registration** as a data controller, and the fee.
- **Regulatory positioning.** Information and drafting, not advice or representation. You set the boundary and the partner-referral agreements.
- **Find Case Law Computational Analysis Licence.** You apply, stating intended use. Blocks the case-law code work.

**Custody and decisions**
- **Choose and provision the secret store** (Vault, SOPS, or sealed-secrets), generate the real secret values, and hold the master key custody. Code consumes these; it cannot create them safely.
- **Rotate the dev `lawapp/lawapp/lawapp` credentials** and guarantee they never promote beyond dev.
- **MFA policy and enrolment** of the real admin and privileged accounts, including seldom-used ones. This is the control that would have stopped the two most recent legal-sector fines.
- **TLS and domain:** provision certs or the cert-manager issuer, own the DNS and provider accounts.
- **Embedding model choice and 1024 dimension lock,** before any bulk embedding, because changing it later means re-embedding everything.
- **Backup encryption key custody** and the offline copy location and process.
- **Break-glass admin procedure:** who holds it, how it is logged.
- **Retention and erasure policy:** how long matters are kept and how erasure runs. You set the policy; code implements it.
- **Provider account security:** Hetzner and Talos root and console access, 2FA on the provider accounts, who has it.

**Assurance and people**
- **Engage a CREST pen tester** before you hold real user data. The builder cannot sign off the build as secure.
- **Cyber Essentials Plus** first, then ISO 27001 and ISO 42001 for the AI layer.
- **Name the incident response owner** and own the decision to notify the ICO within 72 hours and the NCA where relevant. DPP was fined partly for reporting 43 days late; this seat cannot be vacant.
- **Cyber and PII insurance.**
- **Vendor due diligence** on any external LLM provider and on referral partners.
- **Review the security-sensitive diffs** (the rows marked R). This is your stop, not the agent's.

---

## 3. The handoffs — your action unblocks the code

These are the points where the two tracks meet. Do your side first or the code task stalls or, worse, gets built insecurely.

| Code task waits on | Your action |
|--------------------|-------------|
| Secrets integration, JWT signing | Provision the secret store, generate and load the values, hold the key |
| TLS and mTLS config | Provision certs or the cert-manager issuer; own the domain and DNS |
| MFA enforcement | Decide the MFA method and enrol the privileged accounts |
| Encryption at rest, backups | Decide the KMS or storage encryption and the backup key custody |
| Case-law features (F6, ingestion) | Get the Find Case Law Computational Analysis Licence approved |
| Bulk embedding | Lock the embedding model and 1024 dimension |
| CI security gates | Grant CI platform access and decide the image registry and signing key |
| Anything marked R | Review and sign off the diff before merge |

---

## 4. Order of play

1. **You, now, in parallel:** provision the secret store, rotate the dev credentials, decide the MFA method, lock the embedding model, submit the Find Case Law licence, and start the DPO and pen-test engagements. These have lead time and several block code.
2. **Cursor, once secrets exist:** T0.2 secrets integration, then T0.3 schema with RLS, then T1.1 MFA enforcement and JWT, then T1.6 segmentation. This is the security spine and it lands with Wave 1.
3. **You, before any real user data:** DPIA complete, 72-hour breach process owned, DPO appointed, pen test booked.
4. **Cursor, Waves 2 and 3:** gate hardening and audit immutability, vector isolation, injection tests, SIEM detections.
5. **You, before launch:** pen test passed, Cyber Essentials Plus underway, DR restore verified, insurance in place.

The rule of thumb: Cursor builds the mechanism, you own the decision, the custody, and the legal duty. Keep the two rows marked as yours, the DPO and the pen test, outside yourself entirely. Everything else you can hold, but not those.
