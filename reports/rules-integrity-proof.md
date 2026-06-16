# Rules Integrity  -  Proof Report

- **Timestamp:** 2026-06-05  **Branch:** main  **Commit:** a0968b0
- **Command:** `bash scripts/prove_rules_integrity.sh` + `pytest tests/test_rules_integrity.py`
- **Final status:** **PASS** (10/10 required keys; 31 spine tests incl. rules pass)

## Required GB unfair-dismissal rule keys (all PRESENT, jurisdiction_code=GB)
time_limit_months, early_conciliation_required, qualifying_period,
compensatory_cap_amount, compensatory_cap_weeks_pay, weeks_pay_cap_amount,
basic_award_formula, basic_award_min_automatic, acas_code_adjustment_percent (TULRCA s.207A, 25%),
not_reasonably_practicable_extension (ERA 1996 s.111(2)(b)).

## Integrity
- All **current** rules carry authority_ref, authority_url, effective_from, last_verified_at, jurisdiction_code.
- verification_status ∈ {unverified, verified, mismatch, blocked} (normalised).
- Cap rules tied to official **UKSI** Increase-of-Limits Orders (authority_url → legislation.gov.uk/uksi/...).
- Week's-pay / compensatory caps effective-dated 2021–2026 (backdated-case support).
- No hardcoded deterministic legal values found in deadline/value code (grep check passed).

## rules count by key + jurisdiction
34 rule rows, all jurisdiction_code=GB. Cap keys carry 6 effective-dated rows each
(2021–2026). Prospective: ERA 2025 s.25 compensatory-cap removal (is_prospective=true).

## verification status
Rules cited to legislation.gov.uk are `verified`. No rule has an invalid status.
