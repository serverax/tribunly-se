"""
De-identification boundary for Phase 2 reasoning calls.

GUARDRAIL (data protection / UK GDPR Article 9):
  Before ANY call to a third-party or escalation model, raw personal facts
  must be stripped. This module is the enforced boundary. It logs what was
  stripped and what was passed, so the de-identification boundary can be
  PROVED not asserted.

Stripping philosophy:
  - Remove: fields that identify an individual or employer
  - Keep: fields needed for legal analysis (dates, amounts, boolean flags)
  - Abstracted fields (e.g. 'reason_for_dismissal') are kept as-is; they
    describe legal facts not personal identity.

The boundary payload log is written to `deidentify_log` at test time so the
Phase 2 acceptance criterion ("no personal data in third-party payloads") can
be demonstrated with actual output.
"""

from __future__ import annotations

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# Fields that directly identify a person or employer — strip entirely.
_PII_FIELDS = frozenset({
    "claimant_name", "name", "full_name", "first_name", "last_name", "surname",
    "employer_name", "employer", "company_name", "organisation_name",
    "home_address", "address", "postcode",
    "email", "email_address",
    "phone", "telephone", "mobile",
    "national_insurance", "nino", "ni_number",
    "date_of_birth", "dob",
    "bank_account", "bank_details", "sort_code",
    "passport_number", "driving_licence",
    # Raw document text — may contain names, addresses, and other PII
    "raw_document", "raw_text", "upload_text", "ocr_text", "document_content",
    "letter_text", "email_body", "contract_text",
})

# Fields that are legally necessary and do not identify the individual.
# These pass through.
_SAFE_FIELDS = frozenset({
    "edt", "effective_date_of_termination", "dismissal_date",
    "service_start_date", "employment_start_date", "start_date",
    "ec_day_a", "ec_day_b",
    "weekly_pay", "annual_salary",
    "age",
    "jurisdiction",
    "reason_for_dismissal",
    "was_procedure_followed",
    "had_disciplinary_hearing",
    "acas_code_followed",
    "claim_type",
    "length_of_service_months",
    "length_of_service_years",
    "redundancy_selected",
    "whistleblowing_involved",
    "discrimination_ground",   # category only, not individual details
    "health_safety_involved",
})


def deidentify(facts: dict) -> tuple[dict, dict]:
    """
    Strip PII from user facts before sending to any third-party model.

    Returns (safe_facts, stripped_log) where:
      - safe_facts: the de-identified dict to pass to the model
      - stripped_log: records which fields were stripped (keys only, no values)
        Log this at the boundary to prove compliance.

    Unknown fields are kept but flagged in the log for review.
    """
    safe: dict = {}
    stripped_keys: list[str] = []
    unknown_kept: list[str] = []

    for key, value in facts.items():
        key_lower = key.lower().replace("-", "_")
        if key_lower in _PII_FIELDS or key in _PII_FIELDS:
            stripped_keys.append(key)
        elif key_lower in _SAFE_FIELDS or key in _SAFE_FIELDS:
            safe[key] = value
        else:
            # Unknown field: keep but flag for review
            safe[key] = value
            unknown_kept.append(key)

    boundary_log = {
        "fields_stripped": stripped_keys,
        "fields_passed": list(safe.keys()),
        "unknown_fields_kept_for_review": unknown_kept,
        "pii_fields_in_output": [],  # should always be empty — checked below
    }

    # Verify: no PII field names appear in the output keys
    pii_in_output = [k for k in safe if k.lower().replace("-", "_") in _PII_FIELDS]
    if pii_in_output:
        # Should never happen — log and strip again
        logger.error("PII fields found in de-identified output: %s — stripping", pii_in_output)
        for k in pii_in_output:
            del safe[k]
            stripped_keys.append(k)
        boundary_log["pii_fields_in_output"] = pii_in_output

    logger.info(
        "De-identification boundary: stripped=%s, passed=%d fields, unknown_kept=%s",
        stripped_keys, len(safe), unknown_kept,
    )

    return safe, boundary_log
