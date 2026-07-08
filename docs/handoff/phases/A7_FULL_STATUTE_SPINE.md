# PHASE A - CHECKPOINT A7 (REVISED): FULL UK EMPLOYMENT STATUTE SPINE - INGEST NOW

Issued: 2026-07-08
Authority: Owner directive (replaces prior A7)

## Scope Split (Absolute)

- `legislation`, `acas_guidance`, `corpus_chunks` = fill now, fully, from OGL sources.
- `case_law` = **DO NOT TOUCH** - Find Case Law bulk extraction is licence-gated until granted (D4). No exceptions, no "small samples."

## Legal Basis

Statutes and SIs from legislation.gov.uk are Open Government Licence - no application, no waiting, bulk ingestion permitted, commercial use included. Same for gov.uk and ACAS guidance. The case_law gate (D4) covers tribunal and EAT judgments from Find Case Law only, where bulk computational extraction needs the FCL licence (applied for, expected ~13 July 2026).

Law ingested for fenced modules costs disk space, not risk, and pre-loads the shelves for the module finish-or-cut batches later. UI stays at 11 topics; the data spine goes wide.

## Manifest (Minimum)

Build the UK employment statute manifest - primary Acts and key SIs across employment law:

### Core Acts
- Employment Rights Act 1996
- Equality Act 2010
- Employment Relations Act 1999
- Employment Act 2002
- Trade Union and Labour Relations (Consolidation) Act 1992
- Employment Tribunals Act 1996
- National Minimum Wage Act 1998

### Key Statutory Instruments
- National Minimum Wage Regulations 2015
- Working Time Regulations 1998
- Transfer of Undertakings (Protection of Employment) Regulations 2006
- Part-time Workers (Prevention of Less Favourable Treatment) Regulations 2000
- Fixed-term Employees (Prevention of Less Favourable Treatment) Regulations 2002
- Agency Workers Regulations 2010
- Flexible Working Regulations
- Maternity and Parental Leave etc. Regulations 1999
- Paternity and Adoption Leave Regulations 2002
- Shared Parental Leave Regulations 2014
- Employment Tribunals (Early Conciliation: Exemptions and Rules of Procedure) Regulations 2014

### 2023-24 Wave
- Carer's Leave Act 2023
- Neonatal Care (Leave and Pay) Act 2023
- Protection from Redundancy (Pregnancy and Family Leave) Act 2023
- Workers (Predictable Terms and Conditions) Act 2023 (if in force)
- Employment (Allocation of Tips) Act 2023

### 2024-25 Reform Provisions
- Any Employment Rights Act 2024/25 reform provisions in force or prospective

## Resolution Rule

Resolve every title via the `/id?title=` endpoint on legislation.gov.uk - **never hardcode chapter numbers from memory**. Flag anything ambiguous instead of guessing.

## Ingestion Pipeline

- Ingest via the existing CLML pipeline: `/data.xml` per Act/section
- Dated or prospective URIs where commencement matters
- Required columns on every row: `source_url`, `version`, `effective_from/to`, `last_verified_at`
- Throttle politely per the Fair Use policy - this is a large crawl, pace it

## ACAS

- Code of Practice + key guidance pages, current editions
- Same provenance columns as legislation

## Embeddings

- Embed all new chunks at 1024-dim through the local Ollama pipeline into `corpus_chunks`

## Evidence Required

- Before/after census: acts count, named list, chunk counts, rules by claim_type
- Source-freshness report
- Spot-check: 5 random sections diffed against the live API for fidelity
- Floor still >= 1829 passed / 0 failed

## State Recording

Record in LAWAPP_CURRENT_STATE.md:
- statute spine = FULL
- case_law = empty pending FCL grant (expected ~13 July 2026)
- UI scope unchanged at 11 topics

## STOPs

- OGL sources only
- Zero Find Case Law requests
- No UI/module changes
- No rules-table value changes without citation from the ingested source
