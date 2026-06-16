# LawApp — Security Architecture Design

**Classification:** OFFICIAL (commercial)
**Version:** 1.0
**Date:** 16 June 2026
**Author:** Khalid (Solution Architect)
**Audience:** LawApp dev and security team
**Companion docs:** Deployment Work Order, Architecture Decisions, Feature Build Spec

---

## 1. Executive summary

LawApp processes UK GDPR special category data (discrimination, health, and disclosure facts) through an LLM-assisted pipeline. That combination puts it in the highest-risk processing band the ICO recognises, and the legal sector is being actively targeted: the UK legal sector recorded 2,284 data breach incidents in the year to September 2024, a 39% rise on the prior year, and the ICO can fine up to 4% of total annual worldwide turnover or £17.5 million, whichever is higher.

The design rests on four principles: Zero Trust (no implicit trust between the twelve services), assume breach (the recent ICO fines were all lateral-movement and credential cases), privacy and security by design (the anonymous-versus-registered boundary is a privacy control, not just a product one), and provenance as a security control (the verification gate already defends against the AI failure mode that is sanctioning lawyers in court).

The single most important architectural truth for this product: the verification gate is not only a quality feature, it is your primary control against OWASP LLM09 Misinformation and against the line of UK judgments now penalising fabricated AI citations. Build it as a security control with the same rigour as authentication.

---

## 2. Scope and objectives

In scope: identity, data, application, AI/LLM, network, monitoring, incident response, forensic readiness, deployment hardening, and compliance for the LawApp platform (the twelve services, the corpus and operational Postgres, the vector and graph stores, and the LLM feeder).

Objectives: protect special category data to UK GDPR Article 32 standard, prevent the LLM layer from becoming an attack surface or a source of fabricated legal content, contain any single compromise to one segment, and produce court-defensible audit evidence.

Out of scope: physical security of the Hetzner facility (provider responsibility), and court representation (always referred to a regulated partner).

---

## 3. Operational context and threat landscape

The threat picture is not theoretical. Recent UK legal-sector enforcement gives the exact attack paths this design must close.

**Credential and privileged-access attacks.** DPP Law was fined £60,000 in April 2025 after a brute-force attempt gained access to an administrator account on a legacy case management system, enabling attackers to move laterally and take 32GB of data, which the firm only learned about when the National Crime Agency found it on the dark web. The administrator account did not have multi-factor authentication enabled because it was little-used. Levales Solicitors was reprimanded in October 2024 after an attacker used legitimate credentials to access its cloud server and leaked criminal-law data on over 8,000 people to the dark web.

**Ransomware.** Tuckers Solicitors was fined £98,000 in 2022 after a ransomware attack encrypted 972,191 files, including court bundles.

**Inadequate technical and organisational measures (TOMs) as the recurring finding.** The largest ICO fines of 2025, including £14m across the Capita group, £3.07m against Advanced Computer Software, £2.31m against 23andMe and £1.23m against LastPass UK, were all issued for breaching the UK GDPR security provisions through inadequate technical and organisational measures after cyber attacks. TOMs are the legal yardstick. This document is, in effect, your TOMs evidence.

**The AI failure mode.** Generative AI fabricates citations, and courts are now penalising it. The UK Divisional Court ruling in Ayinde v London Borough of Haringey and Al-Haroun v Qatar National Bank [2025] EWHC 1383 (Admin) addressed fabricated authorities placed before the court and considered contempt. A public database tracks over 1,600 cases of AI-hallucinated citations and is growing. The Judicial Office issued guidance on AI in April 2025, and the Law Society published Generative AI: The Essentials in May 2025, with courts expecting near-perfection from regulated lawyers. LawApp serves litigants in person, but a tool that emits a fabricated authority still harms its user and destroys trust.

**The regulatory benchmark.** When the SRA authorised the first AI law firm, it specifically checked client data confidentiality, quality assurance, conflict-of-interest safeguards, and mitigation of AI hallucinations, and required human oversight with client approval for every action. Design to that bar even though LawApp is not a regulated firm.

---

## 4. Security architecture principles

- **Zero Trust (NIST 800-207).** No service trusts another by default. Every call is authenticated and authorised. This directly answers the DPP and Levales lateral-movement pattern.
- **Assume breach.** Segment so one compromised service cannot reach the corpus, the audit store, or another tenant's data.
- **Least privilege.** Per-service database roles, scoped tokens, no shared admin, MFA on every privileged and service account including infrequently used ones.
- **Defence in depth.** Controls at edge, network, application, data, and AI layers so no single failure is catastrophic.
- **Privacy and security by design (GDPR Art 25).** Anonymous tools never persist special category data; persistence requires a consented account.
- **Provenance as control.** Every served answer and document carries a citation and a verified or unverified badge, enforced at the data layer.

---

## 5. High-level architecture: trust zones

Four trust zones, each a separate network segment with default-deny between them.

```
Zone 0  Public edge      WAF, rate limiting, bot/DoW protection, TLS termination
   |                     (anonymous free tools live here, no persistence)
Zone 1  Application      main API (8000), rules (8016), RAG (8017), graph (8018),
   |                     redaction (8019), admin (8007), case (8008), notify (8009)
Zone 2  AI feeder        LLM inference (Ollama or API egress), gated, no inbound
   |                     from public, output returns to the verification gate only
Zone 3  Data tier        corpus Postgres + pgvector, operational Postgres, Redis,
                         audit store (append-only). Reachable only from Zone 1.
```

Rules: Zone 0 cannot reach Zone 3. The LLM in Zone 2 has no standing access to Zone 3; it receives prompts and returns candidates that land in `answer_candidate` for the gate. The audit store accepts writes but never deletes.

---

## 6. Detailed architecture by domain

### 6.1 Identity and access (IAM)
- MFA mandatory on all human and privileged accounts, including service and seldom-used admin accounts. This is the single control that would have stopped DPP and Levales.
- RBAC: end user, reviewer (operates the verification gate in admin 8007), engineer, and break-glass admin. No standing admin; elevate through time-bound, logged access.
- JWT hardening (you run `LAWAPP_AUTH_MODE=jwt`): short-lived access tokens, rotating refresh tokens, asymmetric signing with keys in the secrets manager, audience and issuer validation, and immediate revocation on logout. Do not store secrets in the token or the system prompt.
- Per-service identities for service-to-service calls (mTLS client certs or workload identity), not a shared credential.
- Map: Cyber Essentials (access control), NCSC CAF B2, GDPR Art 32, ISO 27001 A.5.15 to A.5.18.

### 6.2 Data protection and cryptography
- Encryption in transit: TLS 1.3 at the edge and mTLS between services. No plaintext service traffic, even internally.
- Encryption at rest: encrypted volumes for both Postgres instances, the vector store, the audit store, and all backups.
- Key management: a secrets manager or KMS (HashiCorp Vault, or SOPS-encrypted secrets reconciled by Flux). No credentials in `docker-compose.override.yml` or environment files in any non-dev environment. Your dev override currently carries `lawapp/lawapp/lawapp` Postgres credentials in plaintext; that pattern must never reach staging or prod.
- Data minimisation and classification: tag special category data; anonymous tool runs process in memory and persist nothing; persisted matters live only behind a consented account.
- Tenant and matter isolation: row-level security in Postgres keyed on tenant and matter; per-matter embedding namespaces so one user's document vectors are never retrievable in another's query.
- Map: GDPR Art 32 and Art 9, NCSC Cloud Principles 1 and 2, ISO 27001 A.8.24.

### 6.3 Application security
- Input validation and output encoding across the FastAPI surface; parameterised queries only (the corpus uses Postgres, so no string-built SQL).
- Lock down the API surface in production: the dev stack exposes `/docs` and `/openapi.json` openly on 8000; disable or authenticate these in prod.
- Broken access control is the first web risk: enforce object-level authorisation on every matter, document, and deadline so a user cannot read another's by ID.
- Rate limiting and abuse protection on the anonymous free tools, both to stop scraping and to cap LLM cost abuse (see LLM10 below).
- Secure SDLC: SAST, dependency and container scanning, and secrets scanning in CI before any deploy.
- Map: OWASP Top 10 (web) and ASVS, Cyber Essentials.

### 6.4 AI and LLM security layer (the crown jewel)
This maps directly to the OWASP Top 10 for LLM Applications 2025, because that is the framework the market and regulators now reference.

| OWASP LLM 2025 | Risk to LawApp | Control |
|----------------|----------------|---------|
| LLM01 Prompt Injection | A user-uploaded document in the F3 decoder, or poisoned corpus text, carries hidden instructions. Indirect injection is especially dangerous in RAG because the model may treat malicious external content as trusted instructions | Treat all retrieved corpus content and all user uploads as untrusted data, never instruction. Input scanning (LLM-Guard, Azure Prompt Shields, Llama Guard). Separate the instruction and data channels. The LLM holds no tools, so an injection cannot trigger an action |
| LLM02 Sensitive Info Disclosure | PII leaks into logs, prompts, or model output | Redaction service (8019) strips PII before any logging or embedding. Minimal system prompt with no secrets |
| LLM03 Supply Chain | Compromised model or library | Pin and scan dependencies; verify model provenance and integrity (especially a local Ollama model); SBOM |
| LLM04 Data and Model Poisoning | Malicious content enters the corpus and is retrieved as fact | Ingest only from trusted authorities with checksum verification; the staging-to-verified promotion gate blocks poisoned or fabricated content from reaching the first-line store |
| LLM05 Improper Output Handling | Model output executed or rendered unsafely | Never execute model output; encode on render; the gate sits between generation and any persistence |
| LLM06 Excessive Agency | An autonomous agent takes harmful actions | Deliberate de-agenting: the LLM proposes text only. It has no tools, no write access, no autonomous actions. This is a design control, mirroring the SRA's human-approval requirement for Garfield |
| LLM07 System Prompt Leakage | Prompt reveals secrets or logic | No secrets in prompts; assume the prompt is public |
| LLM08 Vector and Embedding Weaknesses | Embedding inversion can recover the source text from the mathematical vectors in the database, and weak access control exposes data across tenants | Encrypt and access-control the vector store; treat user-document embeddings (F9) as sensitive as the documents; strict per-matter namespace isolation |
| LLM09 Misinformation | The model invents a citation or states the wrong law-as-at date, the exact failure penalised in Ayinde | The verification gate, mandatory citations, the RAG Triad evaluation (context relevance, groundedness, answer relevance), the verified or unverified badge, and temporal accuracy from the law-as-at-date query. This is the control that defines the product |
| LLM10 Unbounded Consumption | Denial of wallet through mass free-tool abuse | Rate limits, per-session token budgets, cost alerts, bot protection at the edge |

- Frameworks: OWASP LLM Top 10 2025, NIST AI RMF (Govern, Map, Measure, Manage), MITRE ATLAS, EU AI Act and the forthcoming ISO 42001 for the AI management system.

### 6.5 Network and infrastructure
- Default-deny network policies between the four zones and between services within Zone 1; explicit allow only for required paths.
- Neither Postgres instance is publicly reachable. The dev stack exposes Postgres on host port 5435; production keeps the database internal to Zone 3 only.
- Container hardening: non-root, read-only root filesystem, dropped capabilities, minimal base images, no secrets baked into images.
- Talos Linux is an asset here: it is immutable and API-managed with no SSH and no shell, which removes a large class of host-level lateral movement and interactive-attacker techniques. Treat that as a deliberate control, not an inconvenience.
- Map: NCSC Cloud Principle 3 (separation), CIS Benchmarks, Cyber Essentials (firewalls and secure configuration).

### 6.6 Monitoring, detection and forensic readiness
- Centralised logging to a SIEM with the redaction service applied at the logging boundary so PII never lands in logs.
- Detections tuned to the real attack patterns: brute-force and credential-stuffing spikes (the DPP entry path), impossible-travel and anomalous logins (Levales legitimate-credential abuse), mass data export or unusual bulk reads (the exfiltration stage), and admission of unsigned images.
- The audit store (8020) is append-only and WORM-style. Every gate decision, promotion, and rejection is logged with actor, timestamp, and the source it was checked against, giving a court-defensible chain for any served answer, from output back through `curated_answer`, `answer_candidate`, reviewer, and source.
- Map: GDPR Art 33, NCSC CAF C and D, ISO 27001 A.8.15 and A.8.16.

---

## 7. Threat model (STRIDE, ATT&CK-coded, classified by outcome)

| Threat | ATT&CK | Real precedent | Outcome class | Primary control |
|--------|--------|----------------|---------------|-----------------|
| Privileged account brute force | T1110 | DPP Law £60k | Successful in precedent | MFA on all privileged accounts, lockout, alerting |
| Valid-credential abuse | T1078 | Levales | Successful in precedent | MFA, impossible-travel detection, session binding |
| Lateral movement to data tier | T1021 | DPP Law | Successful in precedent | Zone segmentation, default-deny, per-service identity |
| Data exfiltration | T1048, T1567 | DPP, Levales | Successful in precedent | Egress control, DLP-style export alerting, encryption |
| Ransomware | T1486 | Tuckers £98k | Successful in precedent | Immutable offline backups, tested restore, segmentation |
| Indirect prompt injection via uploaded doc | ATLAS, LLM01 | Industry-wide | Emerging | Untrusted-data handling, input scanning, de-agented LLM |
| Corpus or vector poisoning | LLM04, LLM08 | Industry-wide | Emerging | Trusted sources, checksums, verification gate |
| Fabricated citation served to user | LLM09 | Ayinde [2025] EWHC 1383 | Active | Verification gate, mandatory citations, RAG Triad |
| Denial of wallet | LLM10 | Industry-wide | Emerging | Rate limits, token budgets, bot protection |
| Supply chain compromise | T1195, LLM03 | Industry-wide | Emerging | SBOM, image signing, scanning, model integrity |

---

## 8. Risk matrix (impact x likelihood)

| Risk | Impact | Likelihood | Rating | Treatment |
|------|--------|------------|--------|-----------|
| Special category data breach | Critical | Medium | High | MFA, segmentation, encryption, monitoring |
| Fabricated legal content served | Critical | Medium-High | High | Verification gate (primary), badges, temporal accuracy |
| Lateral movement after one compromise | High | Medium | High | Zero Trust segmentation, least privilege |
| Late breach reporting | High | Medium | High | IR runbook with 72-hour clock, see section 9 |
| Prompt injection via uploads | High | Medium | Medium-High | Untrusted-data handling, de-agented LLM |
| Denial of wallet on free tools | Medium | High | Medium | Rate limits, cost caps, bot protection |
| Embedding inversion of user docs | High | Low-Medium | Medium | Encrypt and isolate vector store |

---

## 9. Incident response and the 72-hour clock

DPP was penalised partly because it did not consider loss of access a personal data breach and reported it 43 days after becoming aware. UK GDPR requires notification to the ICO within 72 hours of awareness where there is a risk to individuals. Build that as a hard control.

Runbook per incident: detect and triage, contain without destroying evidence, preserve evidence (volatile first, hash on collection), investigate and reconstruct timeline, eradicate root cause, recover under monitoring, and capture lessons. A standing decision gate at detection asks one question early: is personal data affected, and if so the 72-hour clock starts and a named owner runs the ICO notification path. Treat loss of availability (ransomware, lockout) as a potential breach, which is exactly the call DPP got wrong.

---

## 10. Deployment and hardening: dev to production

Your path runs from Docker Compose on the dev box to a Talos Linux Kubernetes cluster on Hetzner bare metal, reconciled by Flux. Harden along that path.

**Secrets.** Remove all plaintext credentials from compose and env files for anything beyond local dev. In the cluster, use Vault or SOPS-encrypted secrets reconciled by Flux, or sealed-secrets. Rotate the dev `lawapp/lawapp/lawapp` Postgres credentials and never promote them.

**Network.** Default-deny NetworkPolicies, namespace isolation matching the four zones, mTLS between services (a mesh such as Linkerd, or Talos-native options). Postgres stays internal; do not expose 5435 in prod. Egress allow-listing from Zone 2 so the LLM layer can reach only its inference endpoint.

**Images and CI/CD.** Scan images (Trivy) and IaC (Checkov) in CI before Flux deploys. Sign images and enforce signatures with an admission controller (Kyverno or OPA Gatekeeper) so unsigned or non-compliant images are rejected. Generate an SBOM per build.

**Database.** TLS on Postgres, encrypted volumes, separate least-privilege roles per service (the corpus read role is distinct from the app read-write role), row-level security for tenant and matter isolation.

**Backups and DR.** Encrypted, immutable, offline-capable backups with tested restores, sized against the ransomware scenario. The audit store is append-only and backed up independently.

**Edge.** TLS via cert-manager, a WAF, rate limiting, and bot protection in front of the public free tools. Lock down `/docs` and `/openapi.json`.

**Platform posture.** Talos gives you an immutable, shell-less, API-only host. Keep it that way: no breaking glass into nodes, all changes through the declarative pipeline, which also gives you a clean audit trail of infrastructure change.

Sequence the security work to the build waves: identity, secrets, segmentation, and TLS land with Wave 1; the gate hardening, vector isolation, and audit immutability with Waves 2 and 3; full SIEM detections and DR testing before any public launch.

---

## 11. Compliance and legal posture

- **UK GDPR and DPA 2018.** You are a data controller for sensitive and special category data. A Data Protection Impact Assessment is mandatory here because large-scale special category processing combined with AI is high risk under Article 35. Maintain a Record of Processing Activities, honour the right to erasure on matters, and document your TOMs (this design is the core of that record).
- **Lawful basis for special category data (Art 9).** Establish it explicitly, with logged consent at the registration and persistence boundary.
- **Regulatory positioning.** LawApp provides information and drafting, not regulated advice or representation, and refers anything crossing that line to a regulated partner. Even so, design to the SRA's stated expectations for AI services: confidentiality, quality assurance, conflict safeguards, and hallucination mitigation.
- **Credibility certifications.** Cyber Essentials Plus is the right near-term UK baseline and unlocks B2B and public-sector buyers; ISO 27001 and, for the AI layer, ISO 42001 are the medium-term targets.

---

## 12. Assumptions, limitations, recommendations

**Assumptions.** Talos, Hetzner, and Flux are the production substrate; the LLM runs either locally via Ollama or through a controlled API egress; the twelve-service topology and the corpus and gate from the companion docs are the system under design.

**Limitations.** This design covers the platform, not the security of any third-party LLM provider's own infrastructure if an external API is used, and not the conduct of referred partner solicitors.

**Prioritised recommendations.**
1. MFA on every privileged and service account, now. It is the cheapest control and it closes the exact path of the two most recent legal-sector fines.
2. Move all secrets out of plaintext compose and env files before any non-dev deployment.
3. Build the verification gate as a security control with audit immutability, since it is your primary defence against the AI failure mode now reaching the courts.
4. Implement default-deny segmentation across the four zones before public launch.
5. Run the DPIA and stand up the 72-hour breach process before you hold a single real user's case data.
6. Target Cyber Essentials Plus as the first external assurance milestone.
