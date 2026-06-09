# T-003 Dataset Transform Plan

Transform-only. NO scraping. Inputs are the SA-001 validated artefacts on local disk.

## Inputs
- `reports/hard-exit/evidence/legal-data-scrape/raw-source-manifest.json` (9 entries)
- `reports/hard-exit/evidence/legal-data-scrape/raw/*.xml` (3 CLML Acts)
- `reports/hard-exit/evidence/legal-data-scrape/raw/*.html` (6 ACAS/GOV.UK pages)
- `reports/hard-exit/evidence/legal-data-scrape/hash-proof.txt` (SA-001 sha256 per file)

## Target DB (in-cluster lawapp-rag Postgres)
Access path: `kubectl exec -i -n lawapp-rag lawapp-postgres-0 -- psql -U lawapp_user -d lawapp`
(localhost cannot reach the DB; SQL is generated locally then piped via kubectl exec).

### Real schema (inspected, not assumed)
- `legal_sources` is a **licence/provenance registry** keyed by `(domain, source_id)` and
  `source_key`. It has **no `source_url`/`content_hash` columns**. It has `base_url`,
  `jurisdiction`, `licence_*`, `last_verified_at`, `notes`.
  Decision: the precise SA-001 `source_url` is stored in `base_url`; the SA-001
  `content_hash` and full provenance is stored in `notes` (`content_hash=<sha256>; ...`).
- `corpus_chunks` carries the binding provenance: `source_id` (FK -> legal_sources.id),
  `source_url` (NOT NULL), `chunk_hash` (NOT NULL, UNIQUE), `authority_ref`,
  `source_table`, `source_type`, `jurisdiction_code` (FK -> legal_jurisdictions),
  `heading`, `title`, `body_text`, `chunk_index`, `legal_topics`, `embedding` (left NULL).
- `legal_jurisdictions` allows codes: EW, GB, NI, S, UK. Legislation Acts -> `UK`
  (RestrictExtent = E+W+S+N.I.); HTML guidance -> `EW` per manifest.

## Source -> parser mapping
| source_id | type | parser |
|---|---|---|
| era-1996 | legislation | CLML/XML, P1group (section) chunks |
| equality-act-2010 | legislation | CLML/XML, P1group (section) chunks |
| eta-1996 | legislation | CLML/XML, P1group (section) chunks |
| acas-dismissals | acas_guidance | lxml.html `<main>` heading+paragraph chunks |
| acas-disciplinary-grievance | acas_guidance | lxml.html `<main>` |
| acas-early-conciliation | acas_guidance | lxml.html `<main>` |
| govuk-et-make-a-claim | govuk_guidance | lxml.html `<main>` |
| govuk-redundancy | govuk_guidance | lxml.html `<main>` |
| govuk-holiday-entitlement | govuk_guidance | lxml.html `<main>` |

### Legislation parsing
CLML structure confirmed: each `P1group` = one numbered section, containing a `Title`
(heading) and a `P1` element whose `DocumentURI` ends in `/section/N` and `id='section-N'`.
This yields:
- `source_url` = the precise per-section URI (e.g. `.../ukpga/1996/18/section/1`)
- `authority_ref` = e.g. `Employment Rights Act 1996 s.1`
- `heading` = section Title, `body_text` = full collapsed section text
- `effective_from` = root `RestrictStartDate`
Reuses the namespace + `_extract_text` logic of `ingestion/legislation/clml_parser.py`
(the shipped parser targets per-section fragments; the transform applies the same
extraction at whole-Act P1group granularity, which is the correct legal provision unit).

### HTML parsing
Each page has exactly one `<main>`. Strip script/style/nav/form/footer/etc, walk
`h1..h4` + `p`/`li` in document order, group paragraphs under the current heading,
cap at ~2500 chars per chunk. `source_url` = page URL; `authority_ref` = title + URL.

## Binding (every chunk)
`source_id` (FK) + `source_url` + `chunk_hash=sha256(body_text)` + `authority_ref` +
`source_table='legal_sources'`. The parent legal_sources row carries the SA-001
`content_hash`, so each chunk traces to a real validated scrape.

## Rules
ADDITIVE ONLY. INSERT only. `legal_sources` uses `ON CONFLICT (domain,source_id) DO NOTHING`;
`corpus_chunks` uses `ON CONFLICT (chunk_hash) DO NOTHING`. No DROP/TRUNCATE/UPDATE.

## Artefacts
- `transform.py` — the transform (run under `/tmp/lawapp-audit-venv`, lxml 6.1.1).
- `insert-sources.sql`, `insert-chunks.sql` — generated SQL piped into psql.
