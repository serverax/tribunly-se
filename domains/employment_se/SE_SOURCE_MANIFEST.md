# SE_SOURCE_MANIFEST.md

## Clone Proof
```text
526cbcc docs(frontend): log remaining accessibility findings
7339e9f fix(frontend): restore rules-backed deadline preview
dfd4780 test(frontend): prove workspace persistence
```

I kept this pass in `F:\tribunly-se` only and did not write to the repo.

## Repo Context
These local files define the current UK pipeline shape and the SE delta:

- [ingestion/legislation/client.py](F:/tribunly-se/ingestion/legislation/client.py)
- [ingestion/legislation/clml_parser.py](F:/tribunly-se/ingestion/legislation/clml_parser.py)
- [ingestion/legislation/ingest.py](F:/tribunly-se/ingestion/legislation/ingest.py)
- [ingestion/config.py](F:/tribunly-se/ingestion/config.py)
- [ingestion/domain_loader.py](F:/tribunly-se/ingestion/domain_loader.py)
- [domains/employment_uk/sources.yaml](F:/tribunly-se/domains/employment_uk/sources.yaml)
- [domains/employment_uk/workflows.yaml](F:/tribunly-se/domains/employment_uk/workflows.yaml)
- [domains/employment_uk/rules_manifest.yaml](F:/tribunly-se/domains/employment_uk/rules_manifest.yaml)
- [domains/employment_uk/domain_config.json](F:/tribunly-se/domains/employment_uk/domain_config.json)
- [backend/api/i18n_routes.py](F:/tribunly-se/backend/api/i18n_routes.py)
- [shared/i18n_contracts.ts](F:/tribunly-se/shared/i18n_contracts.ts)
- [db/migrations/085_user_preferences_locale.sql](F:/tribunly-se/db/migrations/085_user_preferences_locale.sql)

Key readout from the code:
- The current legislation pipeline is CLML/XML-first, aimed at `legislation.gov.uk`, with section fetches and namespace-aware parsing.
- The i18n layer is presentation-only; it does not translate the legal corpus.
- The embedding default in [ingestion/config.py](F:/tribunly-se/ingestion/config.py) is `bge-large-en-v1.5`, which is not a good default for Swedish legal retrieval.

## Live Riksdagen Verification
Official docs and live endpoints checked:
- [Riksdagens öppna data, dokumentlista](https://data.riksdagen.se/dokumentlista/)
- [Riksdagens koder och termer](https://data.riksdagen.se/sv/koder.html)

Live endpoint tests:
- `https://data.riksdagen.se/dokumentlista/?sok=1982:80&doktyp=sfs&utformat=json`
- `https://data.riksdagen.se/dokumentlista/?sok=1982:80&doktyp=sfs&utformat=xml`
- `https://data.riksdagen.se/dokument/sfs-1982-80.text`
- `https://data.riksdagen.se/dokument/sfs-1982-80.html`

What the live responses showed:
- `dokumentlista` returns JSON and XML.
- The document pages return plain text and HTML.
- Response headers observed: `Cache-Control: private`, `Content-Type`, `Date`, `Strict-Transport-Security`. I did not see any `X-RateLimit-*` headers.
- I did not find a published numeric rate limit in the official docs I checked. The safe interpretation is fair-use plus conservative self-throttling.
- The repo’s current 1 req/s throttle is a local safety policy, not an official Riksdagen limit.

Response schema observed for `dokumentlista`:
- Root element/object: `dokumentlista`
- Metadata attrs: `@ms`, `@version`, `@q`, `@datum`, `@nasta_sida`, `@sida`, `@sidor`, `@traff_fran`, `@traff_till`, `@traffar`, `@dPre`, `@dSol`, `@dDt`, `@dR`
- Child nodes: `facettlista`, `dokument[]`
- Useful `dokument` fields: `id`, `dok_id`, `titel`, `beteckning`, `undertitel`, `dokument_url_text`, `dokument_url_html`, `datum`, `publicerad`, `systemdatum`, `rm`, `organ`, `doktyp`, `typ`, `subtyp`, `summary`, `notis`, `sokdata.statusrad`

Important ambiguity flag:
- Searching `sok=1982:80` returns many hits because other laws cite `1982:80`.
- I used the first hit plus title/undertitel cross-check to confirm the LAS row. This should be treated as a resolver pattern, not blind number matching.

## Verified Swedish Statutes
All rows below were live-checked against Riksdagen on 2026-07-09.

| Swedish law | SFS | Live amendment state | SE role |
|---|---:|---|---|
| Lag (1982:80) om anställningsskydd | 1982:80 | `Ändrad: t.o.m. SFS 2022:836` | Core dismissal, notice, fixed-term, TUPE, and termination framework. |
| Lag (1976:580) om medbestämmande i arbetslivet | 1976:580 | `Ändrad: t.o.m. SFS 2026:886` | Collective bargaining, consultation, industrial action, and union rights. |
| Diskrimineringslag (2008:567) | 2008:567 | `Ändrad: t.o.m. SFS 2025:736` | Equality, anti-discrimination, and retaliation rules. |
| Arbetstidslag (1982:673) | 1982:673 | `Ändrad: t.o.m. SFS 2022:450` | Working time, rest, overtime, and collective-agreement overrides. |
| Semesterlag (1977:480) | 1977:480 | `Ändrad: t.o.m. SFS 2014:424` | Holiday entitlement, holiday pay, and leave timing. |
| Föräldraledighetslag (1995:584) | 1995:584 | `Ändrad: t.o.m. SFS 2025:733` | Parental leave, maternity leave, flexible working forms, and anti-missgynnande. |
| Lag (1991:1047) om sjuklön | 1991:1047 | `Ändrad: t.o.m. SFS 2025:938` | Sick pay entitlement, karens, and employer reporting duties. |

Additional live anchors for SE mapping:
- [Arbetsmiljölag (1977:1160)](https://data.riksdagen.se/dokument/sfs-1977-1160.text) is `Ändrad: t.o.m. SFS 2026:1001`
- [Lag (2021:890) om skydd för personer som rapporterar om missförhållanden](https://data.riksdagen.se/dokument/sfs-2021-890.html) is the whistleblowing analogue
- [Lag (2012:854) om uthyrning av arbetstagare](https://data.riksdagen.se/dokument/sfs-2012-854.html) is the agency-worker analogue

### LAS 2022 reform note
The `sakliga skäl` reform is real and source-backed:
- Current LAS text says `7 § Uppsägning från arbetsgivarens sida ska grunda sig på sakliga skäl`.
- The consolidated LAS text shows the reform package under `2022:835`.
- Live transitional text states:
  - `Denna lag träder i kraft den 30 juni 2022`
  - `Lagen tillämpas första gången den 1 oktober 2022`
  - `Äldre föreskrifter gäller fram till den 1 oktober 2022`
- The same consolidated text also shows `2 c §` allowing collective agreements to vary what counts as `sakliga skäl` and the omission/structure around omplacering, subject to central union conditions.

## AD Case Law Access Routes
Assessment only, no bulk fetch.

Official access routes:
- [Arbetsdomstolen](https://arbetsdomstolen.se/)
- [Meddelade domar](https://arbetsdomstolen.se/sv/meddelade-domar/)
- [Publicering av AD:s domar](https://arbetsdomstolen.se/sv/meddelade-domar/publicering-av-ads-domar/)
- [Arkiverade domar](https://arbetsdomstolen.se/sv/meddelade-domar/arkiverade-domar/)
- [Beställning av kopior](https://arbetsdomstolen.se/sv/meddelade-domar/bestaellning-av-kopior/)

What matters operationally:
- The court publishes referated and otherwise important decisions on its site and in the annual report.
- Older decisions can be requested from the court, and the site says copies are available in some cases by email and at a fee.
- This is enough for an SE module to cite and summarize, but not enough for bulk crawling without a separate access policy.

## Collective-Agreement Boundary Map
This is the honest-caveat layer for Sweden. Where Swedish law allows collective agreement deviation, the module must say so.

| Law family | Boundary |
|---|---|
| LAS | Significant derogation is allowed in specific places, especially via `2 b §` and `2 c §`. Core dismissal reasoning, some notice rules, fixed-term details, and some information duties can be varied under the statute’s gateway rules. |
| MBL | Very broad collective-agreement role. `4 §` allows deviations from many bargaining, strike, and procedural sections. The module must not present MBL as fully mandatory. |
| Arbetstidslagen | Broad derogation through central collective agreements in `3 §`, plus limited local agreement flexibility in some sections. The statute also keeps an EU directive floor. |
| Semesterlagen | Moderate derogation. `2 a §` permits deviations from specified sections, but the core statutory holiday entitlement should not be described as freely waivable. |
| Föräldraledighetslagen | Limited derogation. `2 §` only opens specific procedural and timing points; the core leave rights remain statutory. |
| Sjuklön | Limited derogation via central collective agreements in `2 §`; the statute itself remains the baseline. |
| Diskrimineringslagen | Core prohibition is mandatory. Agreements that reduce the protected rights are void in the relevant part. Do not imply collective agreements can contract out of discrimination law. |
| Arbetsmiljölagen | Core safety duties are statutory. Collective agreements can add operational detail, but not erase baseline safety obligations. |
| Whistleblowing law | Core protection is mandatory. Treat any policy detail as supplemental, not a waiver of rights. |
| National minimum wage | Sweden has no statutory minimum wage. The boundary is collective bargaining, not statutory override. |

## UK to SE Topic Mapping
Where there is no one-to-one equivalent, I flag it explicitly instead of guessing.

| UK production topic | SE equivalent | Caveat / boundary |
|---|---|---|
| `unfair_dismissal` | LAS 1982:80 | Core analogue. Use LAS `7`, `11`, `18`, `34-36`, `38-43`. Collective-agreement caveats apply. |
| `unpaid_wages` | No single statute | Closest is ordinary wage claim under contract law plus procedural rules in LAS/MBL/Arbetstvistlagen. Flag as non-1:1. |
| `constructive_dismissal` | LAS 1982:80 + contract law | No direct Swedish statutory twin. Closest analogue is employer breach leading to termination/termination dispute; must be caveated. |
| `wrongful_dismissal` | LAS 1982:80 | Closest analogue is unlawful termination, notice, and damages under LAS; not a perfect fit. |
| `redundancy` | LAS 1982:80 + MBL 1976:580 | Closest analogue is arbetsbrist, turordning, and consultation. No standalone redundancy act. |
| `discrimination` | Diskrimineringslag 2008:567 | Direct analogue. Mandatory baseline. |
| `pregnancy_maternity_discrimination` | Diskrimineringslag 2008:567 + Föräldraledighetslag 1995:584 | Use both: discrimination + parental-leave missgynnande rules. |
| `equal_pay` | Diskrimineringslag 2008:567 | Direct equal-pay/equal-treatment analogue. |
| `whistleblowing` | Lag 2021:890 | Direct modern analogue. Keep scope/eligibility caveats. |
| `health_and_safety` | Arbetsmiljölag 1977:1160 | Direct analogue for workplace safety. |
| `trade_union_rights` | MBL 1976:580 | Direct analogue for bargaining, union rights, and industrial action. |
| `flexible_working` | Föräldraledighetslag 1995:584 | Closest analogue is `15 a-15 c §§` on flexible working forms. Not a general all-worker UK-style request right. |
| `maternity_rights` | Föräldraledighetslag 1995:584 | Direct analogue. |
| `paternity_rights` | Föräldraledighetslag 1995:584 | Direct analogue, but Swedish framing is parental rather than strictly paternity. |
| `parental_leave` | Föräldraledighetslag 1995:584 | Direct analogue. |
| `shared_parental_leave` | Föräldraledighetslag 1995:584 | Closest analogue only. Sweden does not use the UK concept in the same way; mark as approximate. |
| `holiday_pay` | Semesterlag 1977:480 | Direct analogue. |
| `working_time` | Arbetstidslag 1982:673 | Direct analogue. |
| `national_minimum_wage` | No statutory equivalent | Sweden uses collective agreements. This must be a hard caveat, not a guessed statute. |
| `part_time_workers` | No standalone statute | Closest is a mix of LAS, equal-treatment principles, and collective agreements. Flag as partial only. |
| `fixed_term_workers` | LAS 1982:80 | Direct analogue through fixed-term rules in LAS. |
| `agency_workers` | Lag 2012:854 | Direct analogue for hired-out workers. |
| `tupe` | LAS 6 b + MBL 28 | Closest analogue for transfer of undertaking. Cross-reference both. |
| `employment_contracts` | LAS 6 c-6 e, 4, 4 a, 6 h | Closest analogue for written information, full-time default, and change requests. |
| `unpaid_wages` | No single statute | Repeated here to mark it as an ambiguity: do not pretend a dedicated Swedish wage statute exists. |

## Cross-Lingual Retrieval Assessment
Current risk:
- The configured embedder is `bge-large-en-v1.5` in [ingestion/config.py](F:/tribunly-se/ingestion/config.py).
- That model is English-optimised.
- Swedish source text plus Arabic queries is a worst-case cross-lingual scenario.
- A Swedish corpus retrieved through an English embedder is likely to under-recall the exact statutory passages we care about.

Options:

| Option | Benefit | Cost / risk |
|---|---|---|
| Translate-at-boundary retrieval | Cheapest, fastest, keeps the canonical corpus in Swedish, avoids rebuilding the index immediately. | Depends on translation quality; legal nuance can drift if the translation layer is weak. |
| Multilingual local embeddings (`bge-m3` / multilingual-e5 class via Ollama) | Better semantic retrieval across Arabic/Swedish, better long-term fit for bilingual use cases. | More infra, reindexing, benchmark work, and model-ops overhead. |

Recommendation, owner-gated:
- Launch SE retrieval with translate-at-boundary as the default.
- Benchmark a multilingual local embedder in parallel on a Swedish legal golden set.
- Promote the multilingual embedder only if it clearly beats translation on recall, precision, and latency for the SE corpus.
- Do not silently swap the production embedder before that benchmark.

## Parser Delta
The current pipeline assumes CLML from `legislation.gov.uk`:
- XML namespace is hard-coded for CLML.
- It fetches section-level `.../section/{n}/data.xml` endpoints.
- It extracts act metadata from CLML tags like `Title`, `Year`, `Number`, and `DocumentMainType`.
- It chunks by paragraphs found in `P1`, `P2`, `P3`, and `Text`.

Riksdagen differs materially:
- The discovery endpoint is `dokumentlista`, not CLML.
- The live output is JSON/XML search metadata plus separate `.text` and `.html` law pages.
- The Swedish law body is consolidated text, not sectioned CLML XML.
- Amendment state lives in the response headers and consolidated document metadata, not CLML version tags.

Implication:
- SE needs a new resolver + parser module that:
  - resolves SFS number/title to the correct `dokument` record,
  - fetches consolidated text/HTML,
  - splits Swedish law text into stable section chunks,
  - preserves amendment provenance from the Riksdagen metadata,
  - and does not depend on CLML namespaces.

Effort estimate:
- Resolver/fetcher: 1 day
- Text/HTML normalizer and sectionizer: 2 to 3 days
- Provenance + tests + fixtures: 1 to 2 days
- Hardened first pass: about 1 workweek
- If multilingual retrieval is added in the same phase, add 1 to 2 days for benchmark harnessing

## SE-1 Plan
1. Build the Riksdagen resolver and fetcher for SFS records, with exact-number and title cross-checks. Estimate: 1 day.
2. Build the Swedish law normalizer and section chunker for consolidated `.text` / `.html` pages. Estimate: 2 to 3 days.
3. Seed the Swedish topic map and boundary notes into the SE domain pack. Estimate: 1 to 2 days.
4. Add regression tests for SFS numbering, amendment state, and retrieval provenance. Estimate: 1 to 2 days.
5. Run a retrieval benchmark comparing translate-at-boundary vs multilingual embeddings. Estimate: 1 day for a first pass, then owner-gated follow-up.

Working estimate for a first usable SE-1 slice: 5 to 8 working days.

## Hard Exit
SE-0 is complete as a source-manifest pass:
- Live Riksdagen API verified
- Requested SFS numbers source-verified
- AD access routes documented
- Collective-agreement caveats mapped
- Embedding recommendation stated
- SE-1 plan with effort estimates included

Owner sign-off: ______

## Sources
Official web sources used:
- [Riksdagens öppna data: dokumentlista](https://data.riksdagen.se/dokumentlista/)
- [Riksdagens koder och termer](https://data.riksdagen.se/sv/koder.html)
- [LAS text](https://data.riksdagen.se/dokument/sfs-1982-80.text)
- [LAS HTML](https://data.riksdagen.se/dokument/sfs-1982-80.html)
- [MBL text](https://data.riksdagen.se/dokument/sfs-1976-580.text)
- [Diskrimineringslagen text](https://data.riksdagen.se/dokument/sfs-2008-567.text)
- [Arbetstidslagen text](https://data.riksdagen.se/dokument/sfs-1982-673.text)
- [Semesterlagen text](https://data.riksdagen.se/dokument/sfs-1977-480.text)
- [Föräldraledighetslagen text](https://data.riksdagen.se/dokument/sfs-1995-584.text)
- [SjLL text](https://data.riksdagen.se/dokument/sfs-1991-1047.text)
- [Arbetsmiljölagen text](https://data.riksdagen.se/dokument/sfs-1977-1160.text)
- [Whistleblowing law](https://data.riksdagen.se/dokument/sfs-2021-890.html)
- [Agency-workers law](https://data.riksdagen.se/dokument/sfs-2012-854.html)
- [Arbetsdomstolen](https://arbetsdomstolen.se/)
- [AD published judgments](https://arbetsdomstolen.se/sv/meddelade-domar/)
- [AD publication policy](https://arbetsdomstolen.se/sv/meddelade-domar/publicering-av-ads-domar/)
- [AD archived judgments](https://arbetsdomstolen.se/sv/meddelade-domar/arkiverade-domar/)
- [AD copy ordering](https://arbetsdomstolen.se/sv/meddelade-domar/bestaellning-av-kopior/)

Local repo context used:
- [ingestion/legislation/client.py](F:/tribunly-se/ingestion/legislation/client.py)
- [ingestion/legislation/clml_parser.py](F:/tribunly-se/ingestion/legislation/clml_parser.py)
- [ingestion/legislation/ingest.py](F:/tribunly-se/ingestion/legislation/ingest.py)
- [ingestion/config.py](F:/tribunly-se/ingestion/config.py)
- [ingestion/domain_loader.py](F:/tribunly-se/ingestion/domain_loader.py)
- [domains/employment_uk/sources.yaml](F:/tribunly-se/domains/employment_uk/sources.yaml)
- [domains/employment_uk/workflows.yaml](F:/tribunly-se/domains/employment_uk/workflows.yaml)
- [domains/employment_uk/rules_manifest.yaml](F:/tribunly-se/domains/employment_uk/rules_manifest.yaml)
- [backend/api/i18n_routes.py](F:/tribunly-se/backend/api/i18n_routes.py)
- [shared/i18n_contracts.ts](F:/tribunly-se/shared/i18n_contracts.ts)
- [db/migrations/085_user_preferences_locale.sql](F:/tribunly-se/db/migrations/085_user_preferences_locale.sql)
