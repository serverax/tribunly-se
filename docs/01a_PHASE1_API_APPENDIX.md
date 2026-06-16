# Phase 1 Technical Appendix  -  UK Legal Data APIs

**Purpose:** Concrete endpoint, schema, licensing and rate-limit detail for the two core retrieval sources, so the agent can build the Phase 1 ingestion pipeline without further research. Pairs with `EMPLOYMENT_COPILOT_BUILD_PLAN.md` Phase 1.

> **Verification note (do not skip):** The endpoints and rules below were captured from the official developer docs. Rate limits and application processes can change. Before bulk ingestion, the agent should make one or two live test calls to confirm behaviour, and confirm the Find Case Law computational-analysis application is granted before any bulk crawl.

---

## SOURCE 1  -  legislation.gov.uk (statute backbone)

**Base domain:** `https://www.legislation.gov.uk`
**Licence:** Open Government Licence v3.0 (free, commercial use permitted). Crown/database right.
**Developer docs:** `https://www.legislation.gov.uk/developer` (URIs, formats, limitations, samples).
**Style:** RESTful, content-negotiated. No API key. Respect the Fair Use Policy  -  throttle, do not aggressively crawl.

### URI scheme (three levels)

1. **Identifier URI** (the abstract concept of a piece of legislation  -  recommended for linking/storage):
   ```
   http://www.legislation.gov.uk/id/{type}/{year}/{number}[/{section}]
   ```
2. **Document URI** (a specific version):
   ```
   http://www.legislation.gov.uk/{type}/{year}/{number}[/{section}][/{authority}][/{extent}][/{version}]
   ```
3. **Representation URI** (a specific format  -  what you actually fetch):
   ```
   http://www.legislation.gov.uk/{type}/{year}/{number}/.../data.xml
   ```
   Shortcut: append `/data.xml` (or `/data.rdf`) to ANY legislation page to get the raw machine-readable data.

### Type codes relevant to this project
- `ukpga` = UK Public General Act (this is what you need  -  ERA 1996, Equality Act 2010 are `ukpga`)
- `uksi` = UK Statutory Instrument (for regulations/reforms made as SIs)
- `asp` = Acts of the Scottish Parliament (flag, do not assume E&W = Scotland)

### Resolving a title to a URI (use when you don't know the chapter number)
```
http://www.legislation.gov.uk/id?title={url-encoded title}
```
Returns `301 Moved Permanently` to the canonical URI if matched; `303/300 Multiple Choices` (an XHTML `<ul>` of options) if ambiguous. Parse and disambiguate.

### Targeting specific sections (critical for the rules engine)
Append the structure path to the URI. For an Act, the division name is `section`:
```
http://www.legislation.gov.uk/ukpga/1996/18/section/94          # ERA 1996, unfair dismissal right
http://www.legislation.gov.uk/ukpga/1996/18/section/94/data.xml # as XML
```
Sub-sections use further slashes: `/section/1/1/ba`. Schedules: `/schedule/{n}` and `/schedule/{n}/paragraph/{p}`. Keywords (always English regardless of the legislation's language): `group`, `part`, `chapter`, `schedule`. A non-existent division returns `404`.

> Note: confirm the exact Act chapter numbers at ingestion time via the title-resolution endpoint rather than hardcoding from memory. (ERA 1996 is c.18; Equality Act 2010 is c.15  -  but verify via the API, do not trust this line.)

### Versions / point-in-time (essential for legal accuracy)
- **No version in URI** → the *currently in force* version. (Caution: may lag actual current law  -  see limitations.)
- **Dated version**: append `/{YYYY-MM-DD}` → the law as in force on that date.
- **Prospective version**: append `/prospective` → law as it would be if all not-yet-in-force changes were live. **Important for 2025/26 reforms that are enacted but not yet commenced.**
- **Enacted/made version**: append `/enacted` (primary) or `/made` (secondary) → original text as passed.
- **Explanatory Notes**: append `/notes` (plain-language notes  -  useful for the diagnosis layer's plain-English explanations).

> GUARDRAIL: Because commencement matters (a section can be enacted but not yet in force), store the version/date you fetched and prefer dated/prospective URIs over the bare "current" URI when accuracy is critical. Record `effective_from`/`effective_to` in the `legislation` table.

### Formats
Content negotiation via `Accept` header, or append the extension: `data.xml` (CLML  -  the base format), `data.rdf`, `data.htm`. **Use `data.xml` (CLML schema) as the canonical ingest format.** CLML is a specialist schema  -  build a dedicated, maintainable parser module.

### Ingestion approach (Phase 1)
1. Resolve target Acts via `/id?title=` → canonical `ukpga` URIs.
2. Fetch whole-Act XML and/or section-level XML (`/section/{n}/data.xml`) for the sections the rules engine needs.
3. Parse CLML → store full text + structure in `legislation` table with `source_url`, `version`/date, `effective_from/to`, `last_verified_at`.
4. Throttle politely. No API key required.

---

## SOURCE 2  -  Find Case Law (National Archives) (tribunal & EAT decisions)

**Base domain:** `https://caselaw.nationalarchives.gov.uk`
**API docs:** `https://nationalarchives.github.io/ds-find-caselaw-docs/public` (OpenAPI 0.5.1)
**Contact:** caselaw@nationalarchives.gov.uk

### Licensing  -  READ CAREFULLY (this gates the whole approach)
- **Open Justice Licence**: lets you copy, publish, distribute, transmit case law data, **including commercial use in your own product**. No application needed *for ordinary re-use within the licence terms*.
- **BUT: the Open Justice Licence does NOT permit computational analysis.** If you do **programmatic bulk searching/extraction/enrichment across records** (i.e. exactly what an ingestion pipeline does), you **must apply** to perform computational analysis:
  `https://caselaw.nationalarchives.gov.uk/re-use-find-case-law-records/licence-application-process`
  **There are no application charges.**

> GUARDRAIL / ACTION: Submit the computational-analysis application at the very start of Phase 1. Do NOT run a bulk ingestion crawl before it is granted. Per-document, within-licence fetches are fine; bulk extraction is what triggers the requirement.

### Rate limits
- **1,000 requests per rolling 5-minute window per IP.** Exceeding → `HTTP 429`. Email the address above if you need more. Build backoff/throttling to stay well under this.

### Document identifiers (store the stable one)
- **Document URI** = stable, globally unique, machine-facing. **Prefer this internally.**
  - Pre-April-2025 docs: form `court/year/sequence`, e.g. `eat/2024/123`. (Do NOT parse meaning out of it.)
  - From April 2025: form `d-{uuid}`, e.g. `d-f11e093f-8a53-4e43-8dd8-1531b5d8f018` (always starts `d-`).
- **Structured identifiers** = human-facing. Types include `ukncn` (Neutral Citation, e.g. `[2024] EAT 12`) and `fclid` (Find Case Law ID). Not guaranteed unique. Don't assume which is "preferred"  -  the system decides and it can change.

### Court/tribunal codes you need
- `eat` = Employment Appeal Tribunal (use the `tribunal=eat` query param  -  it's an alias for `court`).
- First-tier Employment Tribunal decisions are also in the service; confirm the exact code at ingest via the search/atom feed (browse the EAT/ET listings). Coverage: EAT digital records ~2021 onward; archive explicitly incomplete; some decisions given verbally are never transcribed.

### Endpoint A  -  Atom feed (discovery + change detection)
```
GET https://caselaw.nationalarchives.gov.uk/atom.xml
```
Query params (same as the site's advanced search):
- `query`  -  full-text (phrase match if quoted; multiple words = AND)
- `court` / `tribunal`  -  e.g. `tribunal=eat` (repeatable array)
- `party`, `judge`  -  name matches
- `order`  -  `date | -date | updated | -updated | transformation | -transformation` (prefix `-` = newest first)
- `page` (>=1), `per_page` (default 50)

Each `<entry>` gives: `<published>` (handed-down date), `<updated>` (last XML update), `<tna:uri>` (the Document URI  -  store this), `<tna:identifier>` (NCN/FCLID), `<tna:contenthash>` (SHA256 of body text, markup-stripped), a `rel="alternate" type="application/akn+xml"` link (the XML), and a PDF link.

Scoped feeds: `/{court}/{subdivision}/{year}/atom.xml` (subdivision requires a court).

### Endpoint B  -  fetch a single document's XML
```
GET https://caselaw.nationalarchives.gov.uk/{document_uri}/data.xml
```
e.g. `.../eat/2024/123/data.xml` or `.../d-f11e093f-.../data.xml`
Returns **Akoma Ntoso / LegalDocML XML**. Metadata in the XML includes Neutral Citation, court/chamber, date, case name, party names, judges' names. Some older docs are PDF-only (less metadata).

### Change detection (keep the store current  -  this is the moat)
Two stable signals, store one on first fetch and compare on refresh:
- **Date**: `<FRBRdate name="transform"/>`'s `date` attribute in the XML, or `<updated>` in the Atom entry. (Changes on any update, including formatting.)
- **Content hash** (preferred for "did the *text* change"): `<uk:hash>` inside `<proprietary>` in the XML, or `<tna:contenthash>` in the Atom entry. SHA256 of markup-stripped body text  -  stable across formatting-only changes.
Recommended: poll `atom.xml?order=-transformation` (most-recently-changed first) on a schedule, compare hashes, re-fetch only changed docs.

### Images caveat
Image URLs in the XML are relative to a per-document `assets_base` (only available via the Atom feed). Do not hotlink; `assets_base` is not stable. For this project, text is what matters  -  you can ignore images.

### Ingestion approach (Phase 1)
1. Submit computational-analysis application (free)  -  **wait for grant before bulk crawl**.
2. Discover EAT (and ET) docs via `atom.xml?tribunal=eat&order=-date`, paginate.
3. Store each doc's `tna:uri` + identifiers + `contenthash` + dates.
4. Fetch `{uri}/data.xml`, parse Akoma Ntoso/LegalDocML, extract body text + metadata, embed + store in `case_law` table.
5. Schedule a change-detection refresh job using `order=-transformation` + contenthash comparison.
6. Throttle to stay well under 1,000 req / 5 min.

---

## SOURCE 3  -  ACAS (Code of Practice + guidance)

- **No confirmed open data API.** Treat as **ingested static authoritative documents**: the ACAS Code of Practice on Disciplinary and Grievance Procedures, and key guidance. This is stable text  -  ingest as documents into the `acas_guidance` table with source URL + version + `last_verified_at`.
- **Action:** at ingest time, verify whether ACAS has published any feed/API (default assumption: no). Check the ACAS Code's current version/edition and re-check periodically, as it is occasionally revised.
- The ACAS Code matters legally (tribunals can adjust awards for unreasonable failure to follow it), so accuracy and currency here are important for the diagnosis layer.

---

## Summary table for the agent

| Source | Endpoint base | Format | Auth | Bulk-use gate | Rate limit |
|---|---|---|---|---|---|
| Legislation | `legislation.gov.uk/{type}/{year}/{num}/.../data.xml` | CLML XML | None | OGL v3.0, none | Fair Use (throttle) |
| Case law | `caselaw.nationalarchives.gov.uk/atom.xml` + `/{uri}/data.xml` | Akoma Ntoso / LegalDocML XML | None | **Must apply (free) for computational analysis before bulk** | 1,000 req / 5 min / IP |
| ACAS | n/a (web pages) | Document ingest | None | n/a | be polite |

## Hard reminders
- Two specialist XML schemas (CLML, LegalDocML/Akoma Ntoso) → build two maintainable parser modules; budget real time.
- Point-in-time matters: store version/date, prefer dated/prospective legislation URIs for accuracy, record effective dates.
- Deterministic facts (deadlines, caps) live in the structured `rules` table sourced from the correct in-force section  -  never inferred by the model.
- Submit the Find Case Law computational-analysis application first thing; don't bulk-crawl before grant.
- Verify chapter numbers, court codes, ACAS Code edition, and current rate limits with live calls before committing the ingestion design.
