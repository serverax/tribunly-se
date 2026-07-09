# SE-0.5 Exit Report

## Deliverables
- [Source manifest](F:/tribunly-se/domains/employment_se/SE_SOURCE_MANIFEST.md)
- [Manifest appendix](F:/tribunly-se/domains/employment_se/SE_SOURCE_MANIFEST_APPENDIX.md)
- [Sweden domain config](F:/tribunly-se/domains/employment_se/domain_config.json)
- [Sweden source manifest](F:/tribunly-se/domains/employment_se/sources.yaml)
- [Sweden rules manifest](F:/tribunly-se/domains/employment_se/rules_manifest.yaml)
- [Sweden workflows](F:/tribunly-se/domains/employment_se/workflows.yaml)
- [Sweden citation policy](F:/tribunly-se/domains/employment_se/citation_policy.yaml)
- [Sweden licence policy](F:/tribunly-se/domains/employment_se/licence_policy.yaml)
- [Sweden glossary](F:/tribunly-se/domains/employment_se/glossary_sv_en_ar.md)
- [Sweden caveats](F:/tribunly-se/domains/employment_se/caveats_sv_en_ar.md)
- [SE fact patterns](F:/tribunly-se/tests/se_fact_patterns/scenarios.yaml)
- [SE retrieval golden set](F:/tribunly-se/tests/se_retrieval_golden/golden_set.json)
- [SE retrieval benchmark harness](F:/tribunly-se/scripts/benchmark_se_retrieval.py)
- [Riksdagen parser package](F:/tribunly-se/ingestion/riksdagen/parser.py) and siblings under [ingestion/riksdagen](F:/tribunly-se/ingestion/riksdagen)
- [Fixture fetcher](F:/tribunly-se/scripts/fetch_riksdagen_fixtures.py)

## Parser Test Run
```text
.......                                                                  [100%]
============================== warnings summary ===============================
tests/ingestion/test_riksdagen_parser.py: 32 warnings
  C:\Python314\Lib\site-packages\slowapi\extension.py:717: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 32 warnings in 5.08s
```

## Citation / Jurisdiction Regression Run
```text
.....                                                                    [100%]
============================== warnings summary ===============================
tests/test_citation_verifier_slug.py: 32 warnings
  C:\Python314\Lib\site-packages\slowapi\extension.py:717: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 32 warnings in 5.34s
```

## Combined Regression Run
```text
............                                                             [100%]
============================== warnings summary ===============================
tests/ingestion/test_riksdagen_parser.py: 32 warnings
  C:\Python314\Lib\site-packages\slowapi\extension.py:717: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 32 warnings in 5.66s
```

## Fixture Timestamps
- `sfs-1982-80` fetched at `2026-07-09T01:04:19.452751+00:00` with amendment state `2022-10-01` for `Lag (1982:80) om anställningsskydd`
- `sfs-1976-580` fetched at `2026-07-09T01:04:26.785785+00:00` with amendment state `None` for `Lag (1976:580) om medbestämmande i arbetslivet`
- `sfs-2008-567` fetched at `2026-07-09T01:04:35.599265+00:00` with amendment state `None` for `Diskrimineringslag (2008:567)`

## Draft Status Ledger
- `DRAFT-UNVALIDATED`: [rules manifest](F:/tribunly-se/domains/employment_se/rules_manifest.yaml), [boundary notes](F:/tribunly-se/domains/employment_se/rules_manifest.yaml), [fact patterns](F:/tribunly-se/tests/se_fact_patterns/scenarios.yaml)
- `TRANSLATION-UNREVIEWED`: [glossary](F:/tribunly-se/domains/employment_se/glossary_sv_en_ar.md)
- `COPY-UNREVIEWED`: [caveats](F:/tribunly-se/domains/employment_se/caveats_sv_en_ar.md)
- `DRAFT`: [sources](F:/tribunly-se/domains/employment_se/sources.yaml), [workflows](F:/tribunly-se/domains/employment_se/workflows.yaml), [domain config](F:/tribunly-se/domains/employment_se/domain_config.json), [citation policy](F:/tribunly-se/domains/employment_se/citation_policy.yaml), [licence policy](F:/tribunly-se/domains/employment_se/licence_policy.yaml), [retrieval golden set](F:/tribunly-se/tests/se_retrieval_golden/golden_set.json)
- `fixture-ready`: [Riksdagen bundles](F:/tribunly-se/tests/fixtures/riksdagen)

## File Inventory
- [SE_SOURCE_MANIFEST.md](F:/tribunly-se/domains/employment_se/SE_SOURCE_MANIFEST.md)
- [SE_SOURCE_MANIFEST_APPENDIX.md](F:/tribunly-se/domains/employment_se/SE_SOURCE_MANIFEST_APPENDIX.md)
- [domains/employment_se/domain_config.json](F:/tribunly-se/domains/employment_se/domain_config.json)
- [domains/employment_se/sources.yaml](F:/tribunly-se/domains/employment_se/sources.yaml)
- [domains/employment_se/rules_manifest.yaml](F:/tribunly-se/domains/employment_se/rules_manifest.yaml)
- [domains/employment_se/workflows.yaml](F:/tribunly-se/domains/employment_se/workflows.yaml)
- [domains/employment_se/citation_policy.yaml](F:/tribunly-se/domains/employment_se/citation_policy.yaml)
- [domains/employment_se/licence_policy.yaml](F:/tribunly-se/domains/employment_se/licence_policy.yaml)
- [domains/employment_se/glossary_sv_en_ar.md](F:/tribunly-se/domains/employment_se/glossary_sv_en_ar.md)
- [domains/employment_se/caveats_sv_en_ar.md](F:/tribunly-se/domains/employment_se/caveats_sv_en_ar.md)
- [tests/se_fact_patterns/scenarios.yaml](F:/tribunly-se/tests/se_fact_patterns/scenarios.yaml)
- [tests/se_retrieval_golden/golden_set.json](F:/tribunly-se/tests/se_retrieval_golden/golden_set.json)
- [tests/fixtures/riksdagen/sfs-1982-80/metadata.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1982-80/metadata.json)
- [tests/fixtures/riksdagen/sfs-1982-80/listing.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1982-80/listing.json)
- [tests/fixtures/riksdagen/sfs-1982-80/text.txt](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1982-80/text.txt)
- [tests/fixtures/riksdagen/sfs-1982-80/html.html](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1982-80/html.html)
- [tests/fixtures/riksdagen/sfs-1976-580/metadata.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1976-580/metadata.json)
- [tests/fixtures/riksdagen/sfs-1976-580/listing.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1976-580/listing.json)
- [tests/fixtures/riksdagen/sfs-1976-580/text.txt](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1976-580/text.txt)
- [tests/fixtures/riksdagen/sfs-1976-580/html.html](F:/tribunly-se/tests/fixtures/riksdagen/sfs-1976-580/html.html)
- [tests/fixtures/riksdagen/sfs-2008-567/metadata.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-2008-567/metadata.json)
- [tests/fixtures/riksdagen/sfs-2008-567/listing.json](F:/tribunly-se/tests/fixtures/riksdagen/sfs-2008-567/listing.json)
- [tests/fixtures/riksdagen/sfs-2008-567/text.txt](F:/tribunly-se/tests/fixtures/riksdagen/sfs-2008-567/text.txt)
- [tests/fixtures/riksdagen/sfs-2008-567/html.html](F:/tribunly-se/tests/fixtures/riksdagen/sfs-2008-567/html.html)
- [ingestion/riksdagen/__init__.py](F:/tribunly-se/ingestion/riksdagen/__init__.py)
- [ingestion/riksdagen/client.py](F:/tribunly-se/ingestion/riksdagen/client.py)
- [ingestion/riksdagen/parser.py](F:/tribunly-se/ingestion/riksdagen/parser.py)
- [ingestion/riksdagen/provenance.py](F:/tribunly-se/ingestion/riksdagen/provenance.py)
- [ingestion/riksdagen/resolver.py](F:/tribunly-se/ingestion/riksdagen/resolver.py)
- [ingestion/riksdagen/sectionizer.py](F:/tribunly-se/ingestion/riksdagen/sectionizer.py)
- [ingestion/riksdagen/types.py](F:/tribunly-se/ingestion/riksdagen/types.py)
- [scripts/fetch_riksdagen_fixtures.py](F:/tribunly-se/scripts/fetch_riksdagen_fixtures.py)
- [scripts/benchmark_se_retrieval.py](F:/tribunly-se/scripts/benchmark_se_retrieval.py)

## Parked Ambiguities
- The draft pack lives under `domains/employment_se/`, but there are also root-level scratch copies from the generation pass (`domain_config.json`, `sources.yaml`, `citation_policy.yaml`, `licence_policy.yaml`, `rules_manifest.yaml`, `workflows.yaml`). The authoritative Sweden pack is the version under `domains/employment_se/`.
- I verified the open Riksdagen endpoints and the two official access routes for Migrationsverket/Migrationsöverdomstolen, but I did not verify separate bulk-reuse terms for those non-fixture sources in this phase.
- The retrieval benchmark is data-ready and runnable later, but I did not pull any models or run the benchmark itself in SE-0.5.

## SE-1 Execution Note
1. Merge the verified source manifests and fixture bundles first, because they unblock the rest of the Sweden corpus.
2. Wire the parser and golden-set checks next, since they are already fixture-based and pass offline.
3. Review and sign the rules manifest, glossary, and caveat copy after that, because those carry the lawyer-facing wording and the collective-agreement caveats.
4. Only after lawyer sign-off should the owner promote the workflows and scenario drafts into regression coverage and connect any retrieval strategy switch decision.
5. Keep the branch local until the owner opens the SE-1 gate; no push, no merge, no runtime stack changes in this phase.


