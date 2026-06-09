# Find Case Law — Computational Analysis Application Prep

**Submit at:** https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process
**Contact:** caselawlicence@nationalarchives.gov.uk
**Timeline:** A few weeks; monthly Discovery Board review (occasionally quarterly Senior Data Governance Panel).
**Fee:** None.
**Format:** 29-question online form, 6 sections. Cannot be saved mid-session — download the Word doc of questions first, draft your answers here, then complete the form in one sitting.

> **Note:** This application covers bulk/programmatic ingestion of EAT decisions via the atom feed. Per-document fetches of individual decisions are already permitted under the Open Justice Licence without application.

---

## Important: legal classification

The answer to "does the system provide automated legal advice?" is **No**. This is not a framing choice — it is legally accurate:

- The system provides automated legal **information and assessment** — unreserved activities under the Legal Services Act 2007, explicitly distinct from regulated legal advice.
- It never conducts litigation, claims rights of audience, or implies it is a solicitor or law firm.
- Every output is grounded in cited retrieved sources; the governance gate routes to solicitors when confidence or grounding is insufficient.
- Answering "yes" to legal advice would contradict the product's legal model and introduce risk.

The generative AI answer must be consistent: "uses generative AI, strictly grounded in retrieved cited authority, provides information not advice." The two answers must not read as "generative AI giving legal advice."

---

## Section 1 — Responsible Person

*(Fill in your own details — not drafted here.)*

- Full name: [YOUR NAME]
- Email: [YOUR EMAIL]
- Licence holder (if different): [ORG NAME, if applicable]

---

## Section 2 — Organisation Details

*(Fill in your own details.)*

- Legal organisation name: [NAME]
- Alternative names: none / [if applicable]
- Country of registration: United Kingdom
- Address: [YOUR ADDRESS]
- Organisation type: [sole trader / limited company / etc.]
- Company/charity number: [IF APPLICABLE]
- Partner/collaborating organisations: none at this stage

---

## Section 3 — Purpose of Re-use (~150 words)

**Suggested draft (edit to fit your voice):**

> We are building a UK employment law self-help tool that helps workers assess whether they have an unfair dismissal claim, understand their rights and deadlines, and prepare tribunal documents. The system retrieves and cites primary legal sources (legislation, EAT and ET decisions, ACAS guidance) to produce grounded, source-cited assessments — rather than relying on generative model memory.
>
> EAT decisions are central to this: they establish how s.98 ERA 1996 "band of reasonable responses" is applied, how the ACAS Code is weighted, and how compensation is assessed. Without current EAT case law, the retrieval layer cannot properly ground its reasoning in judicial authority.
>
> The system is designed for self-representing claimants who cannot afford solicitors. It explicitly tells users when their case is weak, routes complex cases to human solicitors, and carries clear "not a law firm / not legal advice" notices on every surface.

---

## Section 4 — Public Statement (~150 words)

**Suggested draft:**

> This project aims to make employment law accessible to ordinary workers who cannot afford legal representation. Most employment tribunal claimants represent themselves; many do so without understanding their rights, the relevant time limits, or the likely value of their claim.
>
> Our tool provides honest, grounded assessments — including telling users plainly when their case is weak — based on cited statutory authority and tribunal decisions. EAT decisions are the primary source for understanding how Employment Tribunals apply the law in practice, and computational access to them allows us to surface relevant authority for each user's fact pattern rather than relying on static summaries.
>
> The communities we serve are dismissed workers (particularly those on lower incomes) and the broader public interest in accessible justice. Our methodology prioritises citation transparency, grounding every legal statement in a retrievable source, and honest acknowledgement of uncertainty.

---

## Section 5 — Working Practices (Yes/No questions)

Answer as accurately as possible. Suggested answers for likely questions:

| Question | Answer | Notes |
|---|---|---|
| Does your work focus on specific individuals? | No | Aggregated retrieval; no individual profiling |
| Do you anonymise data before analysis? | No (corpus) / Yes (user data) | Ingested decisions are already-published public records; no corpus anonymisation is required. User case data is de-identified before any third-party model call. |
| Do you conduct algorithm bias reviews? | Yes (planned) | Accuracy regression suite with known-correct fact patterns from Phase 2 onwards |
| Do you have a code of ethics? | Yes | Six documented guardrails: legal boundary, grounding, determinism, honesty, data protection, depth before breadth |
| Independent ethical review? | No | No independent ethical review at this stage. DPIA planned before launch (Phase 5). Documented guardrails and the accuracy regression process are the interim internal governance. |
| Are records available for inspection? | Yes | Every citation shown to user with source URL |
| Will data be published? | No | Retrieval is internal; user output cites sources, not raw corpus |
| Is methodology transparent? | Yes | System cites every source; "not legal advice" disclosed on every surface |
| Will findings be published? | No | Individual assessments are private to the user |
| Does the system provide automated legal advice? | **No** | Provides automated legal information and assessment — unreserved activities under the Legal Services Act 2007, explicitly not regulated legal advice. Governance flags uncertainty and routes to solicitors. Never files, represents, or litigates. |
| Does it use generative AI? | Yes | Uses generative AI strictly grounded in retrieved cited authority. Provides legal information and assessment, not regulated legal advice. Every output traces to a cited source; model cannot override citations or operate from memory. |
| Collection limitations disclosed? | Yes | Coverage gaps disclosed: EAT digital records approximately 2021 onwards; some decisions verbal/untranscribed |

---

## Section 6 — Nine MoJ Principles

**1. Dignity:** Case law will not be used to target, profile, or make decisions about individuals. It is used in aggregate for legal research retrieval only.

**2. Independence:** The system does not influence ongoing legal proceedings. It provides information to claimants before or instead of proceedings — not during. No automated filing or representation.

**3. Scrutiny:** Every assessment cites its legal authority. Users can follow the source links to verify the underlying decisions. The governance layer explicitly rejects uncited claims.

**4. Anti-discriminatory harm:** The retrieval system does not differentiate by protected characteristics. Retrieval is by legal relevance only. Accuracy regression testing (Phase 2+) will include diverse fact patterns.

**5. Anti-bias:** We maintain a fact-pattern regression set with known-correct outcomes. Any systematic bias in the retrieval results is detectable and correctable. The system is trained to flag when it lacks grounding rather than guess.

**6. Privacy:** Retrieved decisions are publicly available under the Open Justice Licence. No personal data about parties is extracted for any purpose other than citation display. User case data is encrypted and never sent to third-party models without de-identification.

**7. Discoverability:** Every piece of law or case cited in a user output includes its citation and URL, allowing the user to find and read the original decision.

**8. Algorithmic transparency:** The system is source-first: it retrieves authority before reasoning. The reasoning model's role is explicitly bounded by the retrieved bundle. Confidence and grounding scores are computed and available.

**9. Accurate data representation:** We do not claim our retrieval is complete. Coverage gaps (EAT ~2021+, ET from 2017; some decisions verbal/untranscribed) are known and will be disclosed to users. The system routes to a human when grounding is insufficient rather than proceeding.

---

## After submission

1. Keep the reference number you receive.
2. Set `FCL_BULK_LICENCE_GRANTED=false` in `.env` until you receive written grant confirmation.
3. Once granted, set `FCL_BULK_LICENCE_GRANTED=true` and run:
   ```
   python -m ingestion.case_law.ingest --bulk
   ```
4. The first bulk run should target `--max-pages 5` to validate before full crawl.
