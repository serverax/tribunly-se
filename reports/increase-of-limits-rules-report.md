# Increase of Limits Orders — Statutory Caps Report

**Date:** 2026-06-05  **Domain:** employment_uk  **Status:** DONE AND PROVEN

UK statutory employment limits are revised annually by **The Employment Rights
(Increase of Limits) Order {year}** (a UKSI). lawapp ingests these as official,
historical, cited and effective-dated data — **no cap value is hardcoded in
application logic**; all live in the cited `rules` table and resolve to the
official Order.

## Source (official, licence: OGL)
SI numbers confirmed live via legislation.gov.uk title resolution (2026-06-05):

| Year | SI | URL | commences |
|---|---|---|---|
| 2021 | SI 2021/208 | https://www.legislation.gov.uk/uksi/2021/208 | 6 Apr 2021 |
| 2022 | SI 2022/182 | https://www.legislation.gov.uk/uksi/2022/182 | 6 Apr 2022 |
| 2023 | SI 2023/318 | https://www.legislation.gov.uk/uksi/2023/318 | 6 Apr 2023 |
| 2024 | SI 2024/213 | https://www.legislation.gov.uk/uksi/2024/213 | 6 Apr 2024 |
| 2025 | SI 2025/348 | https://www.legislation.gov.uk/uksi/2025/348 | 6 Apr 2025 |
| 2026 | SI 2026/310 | https://www.legislation.gov.uk/uksi/2026/310 | 6 Apr 2026 (current) |

Each Order's text is stored in `legislation` (`leg_type='uksi'`, 6 rows, 6/6
content_hash) so the source is captured, hashed and citation-resolvable.

## Rules produced (effective-dated, tied to official source)
Ingested by `ingestion/rules/seed_limits_orders.py`. Each rule row carries
`authority_ref` (ERA anchor + SI citation), `authority_url` (the Order URL),
`effective_from`, `effective_to`, `value_numeric`, `unit=GBP`, `last_verified_at`,
`verification_status='verified_against_official_source'`.

**Week's pay cap** (`unfair_dismissal.weeks_pay_cap_amount`, ERA 1996 s.227):
£544 (2021) → £571 (2022) → £643 (2023) → £700 (2024) → £719 (2025) → £751 (2026, current).

**Max compensatory award** (`unfair_dismissal.compensatory_cap_amount`, ERA 1996 s.124):
£89,493 → £93,878 → £105,707 → £115,115 → £118,223 → £123,543 (2026, current).

**Min basic award, certain automatically-unfair dismissals**
(`unfair_dismissal.basic_award_min_automatic`, ERA 1996 s.120):
£6,634 → £6,959 → £7,836 → £8,533 → £8,533 → £9,157 (2026, current).

Effective windows are contiguous and non-overlapping; the 2026 Order is open-ended
(current). A separate **prospective** row records ERA 2025 s.25 (removal of the
compensatory cap) — marked prospective, not treated as current until commenced.

## Backdated-case support
Because each cap is effective-dated to its Order, a Schedule of Loss for a dismissal
in any year 2021–2026 selects the correct statutory limit by date — supporting
backdated claims without hardcoding.

## Proof
`scripts/prove_uk_legal_dataset.sh` §4e fails if: UKSI source rows absent, any cap
rule not tied to a `legislation.gov.uk/uksi/...` authority_url, caps not
effective-dated, or historical depth < 3 years.

## Gaps / next
- Extend history before 2021 (2019/2020 Orders) for older backdated claims — NOT STARTED.
- Automated annual refresh: detect the next Increase of Limits Order at each April
  and append a new effective-dated row — currently the order list is updated on ingest.
- Auto-extract figures from the Order XML (currently figures are published statutory
  values tied to the official Order URL; source text is stored for verification).
