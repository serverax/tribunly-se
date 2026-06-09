# Full Pytest Suite — Result

- Timestamp: 2026-06-05T14:41:28Z
- Command: `docker compose run --rm ingestion python -m pytest tests/ -q`
- Image: Dockerfile.ingestion (deps baked in — no ad-hoc pip)
- Exit code: 1

```
21 failed, 1255 passed, 42 skipped, 2 warnings in 782.67s (0:13:02)
```

## Tail of run
```

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_api_smoke.py::test_assess_ud_returns_correct_shape
FAILED tests/integration/test_phase3e_mvp_close.py::test_full_mvp_journey - a...
FAILED tests/integration/test_phase4b_bundle.py::test_preview_content_is_truncated
FAILED tests/integration/test_phase4b_bundle.py::test_full_bundle_with_premium_token_returns_full_content
FAILED tests/integration/test_phase4b_bundle.py::test_witness_statement_contains_employment_dates
FAILED tests/integration/test_phase4b_bundle.py::test_evidence_checklist_contains_expected_categories
FAILED tests/integration/test_phase4b_bundle.py::test_et1_support_notes_generated
FAILED tests/integration/test_phase4b_bundle.py::test_bundle_uses_confirmed_corrected_facts
FAILED tests/integration/test_phase4b_bundle.py::test_bundle_does_not_use_rejected_facts
FAILED tests/integration/test_phase4b_bundle.py::test_bundle_metadata_saved_after_premium_generate
FAILED tests/integration/test_phase4b_bundle.py::test_bundle_status_lists_all_components
FAILED tests/integration/test_phase4c_timeline.py::test_timeline_includes_generated_document_event
FAILED tests/integration/test_phase4c_timeline.py::test_timeline_excludes_rejected_extracted_facts
FAILED tests/integration/test_phase4c_timeline.py::test_phase4b_bundle_regression
FAILED tests/integration/test_phase5b_unpaid_wages.py::test_letter_before_action_includes_amount
FAILED tests/integration/test_phase6a_deployment.py::test_payment_stripe_live_fails_safely_without_key
FAILED tests/integration/test_phase6a_deployment.py::test_payment_stripe_test_fails_safely
FAILED tests/integration/test_phase7b_kms.py::test_legal_accuracy_gate_regression
FAILED tests/integration/test_phase7b_kms.py::test_rules_verification_gate_regression
FAILED tests/integration/test_phase7c_aws_kms.py::test_legal_accuracy_gate_regression
FAILED tests/test_xss_protection.py::test_no_unsafe_inner_html - AssertionErr...
21 failed, 1255 passed, 42 skipped, 2 warnings in 782.67s (0:13:02)
```
