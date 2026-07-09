# A7 After-Census — Post-Ingestion

**Date:** 2026-07-08 | **Branch:** cc/convergence  
**Source:** Live DB query against `docker compose exec -T db`

## Table Counts

| Table | Before (WO007 T2) | After | Delta |
|-------|--------------------|-------|-------|
| legislation | 84 | 970 | +886 |
| corpus_chunks | 13 | 2,706 | +2,693 |
| corpus_chunks (with embedding) | 0 | 2,693 | +2,693 |
| rules | 128 | 125 | -3 (dedup/cleanup) |
| acas_guidance | 2 | 2 | 0 |
| case_law | 0 | 0 | 0 (FCL licence-gated) |

## Acts Ingested (16 distinct)

| Act | Sections |
|-----|----------|
| Employment Rights Act 1996 | 428 |
| Equality Act 2010 | 273 |
| Employment Act 2002 | 102 |
| Employment Relations Act 1999 | 84 |
| Trade Union and Labour Relations (Consolidation) Act 1992 | 53 |
| Working Time Regulations 1998 | 8 |
| National Minimum Wage Act 1998 | 5 |
| Transfer of Undertakings (Protection of Employment) Regulations 2006 | 4 |
| Agency Workers Regulations 2010 | 3 |
| Employment Tribunals Extension of Jurisdiction (E&W) Order 1994 | 2 |
| Part-time Workers Regulations 2000 | 2 |
| Fixed-term Employees Regulations 2002 | 2 |
| Children and Families Act 2014 | 1 |
| Paternity Leave (Bereavement) Act 2024 | 1 |
| Maternity and Parental Leave etc. Regulations 1999 | 1 |
| Employment Tribunals Act 1996 | 1 |

## Embedding Coverage

- 2,693 of 2,706 corpus chunks have embeddings (99.5%)
- 13 chunks without embeddings are pre-existing (before-census baseline)
- Embedding model: bge-large-en-v1.5 (1024-dim)

## Jurisdictions

- corpus_chunks: 2 jurisdiction codes (EW, GB)
- legislation: EW only (all ingested acts are E&W primary legislation)
