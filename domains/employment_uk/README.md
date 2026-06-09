# employment_uk — domain pack

The first lawapp legal domain pack. The platform core is domain-agnostic; this
pack supplies everything UK-employment-specific so future domains
(`housing_uk`, `immigration_uk`, `employment_saudi`, …) can be added by copying
this structure — **not** by rewriting the platform.

## Files (loaded by the Corpus Ingestion AIA via `ingestion/domain_loader.py`)
- `domain_config.json` — domain identity, jurisdictions, active claim types, manifest paths.
- `sources.yaml` — official legal source manifest (legislation sections, ACAS/GOV.UK, FCL). **Source list lives here, not only in code.**
- `rules_manifest.yaml` — required deterministic rules + their statutory authority.
- `citation_policy.yaml` — RAG citation acceptance + source trust order.
- `licence_policy.yaml` — per-source licence; Find Case Law bulk is **fail-closed**.
- `workflows.yaml` — workflows this domain enables.
- `document_templates/` — self-help document templates (added with the document-generation workflow).

## Principle
LEGAL DB FIRST → CORPUS FIRST → RULES FIRST → CITATIONS FIRST → AI SECOND → FAIL-CLOSED ALWAYS.

## Adding a new domain
Copy this directory, edit the manifests, point the Corpus Ingestion AIA at the new pack. No core platform change required.
