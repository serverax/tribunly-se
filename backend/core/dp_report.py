"""
Data-protection status report  -  Phase 5A.

Generates a plain-English report of the current data-protection posture.
This is a status check, NOT a compliance certification.
lawapp does not claim GDPR compliance from this report.

The report is honest about gaps and production-readiness status.
Each item is marked: IMPLEMENTED | PARTIAL | NOT_IMPLEMENTED
Each item also has production_ready: True | False

IMPORTANT: Several items are NOT production-ready in Phase 5A.
A full DPIA is required before production deployment.
"""

from __future__ import annotations

from datetime import date

# Phase 5A assessed status
_TODAY = "2026-06-01"


def generate_dp_report() -> dict:
    """
    Generate the data-protection status report.

    Returns a structured dict covering all required areas.
    Does NOT claim GDPR compliance  -  reports current state honestly.
    """
    return {
        "report_date":   _TODAY,
        "report_version": "phase5a",
        "overall_status": "NOT_PRODUCTION_READY",
        "disclaimer": (
            "This report describes the current implementation state. "
            "It is NOT a GDPR compliance certification. "
            "A formal DPIA and legal review are required before production deployment."
        ),

        # ── 1. Raw upload storage ──────────────────────────────────────────────
        "upload_storage": {
            "status":              "NOT_PRODUCTION_READY",
            "implementation":      "PARTIAL",
            "location":            "/tmp/lawapp_uploads/{case_id}/{upload_id}",
            "encryption_at_rest":  "NOT_IMPLEMENTED",
            "access_control":      "Container filesystem only  -  no ACL",
            "retention_policy":    "NOT_IMPLEMENTED",
            "note": (
                "Phase 4A: local filesystem, container ephemeral storage. "
                "Phase 5B+: replace with AES-256-GCM encrypted object storage "
                "(S3/GCS with server-side encryption and RBAC)."
            ),
        },

        # ── 2. Logs ────────────────────────────────────────────────────────────
        "logs": {
            "status":             "PARTIAL",
            "file_bytes_in_logs": "GUARDRAILED  -  upload endpoint logs metadata only",
            "pii_in_logs":        "UNKNOWN  -  log scanner covers test fixtures only",
            "log_level":          "INFO (production should be WARN+)",
            "log_retention":      "NOT_IMPLEMENTED",
            "structured_logging": "NOT_IMPLEMENTED",
            "note": (
                "Upload handler explicitly avoids logging file_bytes. "
                "Deidentify.py strips PII before model boundary. "
                "Log scanning for PII values is partial  -  not production guarantee."
            ),
        },

        # ── 3. Third-party model boundary ──────────────────────────────────────
        "third_party_model_boundary": {
            "status":                     "IMPLEMENTED",
            "implementation":             "COMPLETE",
            "de_identification_module":   "backend.core.deidentify",
            "pii_field_types_stripped":   14,
            "fields_stripped": [
                "claimant_name", "employer_name", "email", "home_address",
                "phone", "date_of_birth", "national_insurance", "ip_address",
                "device_id", "session_token", "bank_account", "nhs_number",
                "passport_number", "driving_licence",
            ],
            "boundary_log_in_every_response": True,
            "proof":                      "test_phase5a_hardening.py::test_deidentify_boundary_strips_pii",
            "production_ready":           True,
        },

        # ── 4. Encryption at rest ──────────────────────────────────────────────
        "encryption_at_rest": {
            "status":             "NOT_IMPLEMENTED",
            "cases_assessment":   "Stored in PostgreSQL plaintext jsonb",
            "cases_facts":        "facts_encrypted column is NULL  -  encryption not yet applied",
            "uploaded_documents": "Local filesystem, no encryption",
            "handoff_leads":      "Name+email in plaintext DB column",
            "note": (
                "Phase 5B: implement AES-256-GCM for cases.facts_encrypted, "
                "encrypted object storage for uploads, and encrypt handoff_leads PII."
            ),
        },

        # ── 5. Facts persistence ───────────────────────────────────────────────
        "facts_persistence": {
            "status":                "PARTIAL",
            "raw_user_facts":        "NOT stored  -  only structured assessment output persisted",
            "assessment_jsonb":      "De-identified pipeline output  -  no intake PII",
            "key_dates":             "Stores dates only (not names/employers)",
            "extracted_facts_table": "documents.extracted_facts may contain PII from confirmed OCR",
            "note": (
                "Confirmed PII extracted facts (employer_name, employee_name) are "
                "currently excluded from apply-confirmed (Phase 5B). "
                "If user corrects OCR to include a name, it could enter extracted_facts."
            ),
        },

        # ── 6. Retention and deletion ──────────────────────────────────────────
        "retention_deletion": {
            "status":           "NOT_IMPLEMENTED",
            "retention_policy": "None defined",
            "deletion_endpoint": "None  -  no DELETE /cases/{id} or data erasure",
            "right_to_erasure":  "Not implemented (Art.17 UK GDPR)",
            "note": (
                "Phase 5B+: implement case deletion, upload deletion, "
                "audit log retention limits, and automated deletion schedules."
            ),
        },

        # ── 7. PII handling ────────────────────────────────────────────────────
        "pii_handling": {
            "status": "PARTIAL",
            "intake_form": {
                "handling": "De-identified by deidentify.py before any model call",
                "fields_stripped": 14,
                "production_ready": True,
            },
            "uploaded_documents": {
                "handling": "Mock extraction only  -  placeholders returned, no real OCR",
                "real_ocr_pii_risk": "Phase 5B: real OCR will extract real PII  -  needs encryption pipeline",
                "production_ready": False,
            },
            "handoff_leads": {
                "handling": "Name+email stored in plaintext in handoff_leads table",
                "consent_required": True,
                "encryption": "NOT_IMPLEMENTED",
                "production_ready": False,
            },
            "case_timeline_events": {
                "handling": "User-entered text  -  may contain PII",
                "encryption": "NOT_IMPLEMENTED",
                "production_ready": False,
            },
        },

        # ── 8. Article 9 risk ──────────────────────────────────────────────────
        "article_9_risk": {
            "status": "PARTIAL_ASSESSMENT",
            "health_data": {
                "intake_collects": False,
                "case_summary_risk": "handoff_leads.case_summary may contain health data if user includes it",
            },
            "trade_union_membership": {
                "intake_collects": False,
            },
            "race_ethnicity": {
                "intake_collects": False,
            },
            "dpia_required": True,
            "dpia_status":   "NOT_COMPLETED",
            "note": (
                "Phase 5A: no Art.9 data explicitly collected in intake. "
                "Risk: case_summary in handoff_leads may contain sensitive details. "
                "A full DPIA covering Art.9 is required before production. "
                "Consider adding a warning to handoff form about sensitive data."
            ),
        },

        # ── Priority categorisation (Phase 5C) ───────────────────────────────
        # launch_blocker:         must fix before ANY real users (closed beta)
        # production_blocker:     must fix before production (can run closed beta)
        # post_launch_enhancement: can fix after launch
        # implemented:            already in place
        "priority_breakdown": {
            "launch_blockers": [
                "DPIA not completed  -  required before any real user data is processed",
                "No documented legal basis for data processing (GDPR Art.6/Art.9)",
                "No privacy notice / transparency information for users",
            ],
            "production_blockers": [
                "No encryption at rest for uploaded documents (AES-256-GCM required)",
                "No encryption for cases.facts_encrypted column (NULL  -  unfilled)",
                "No encryption for handoff_leads PII (name, email in plaintext)",
                "No data retention or deletion policy (Art.17 UK GDPR right to erasure)",
                "User authentication not implemented (user_id=NULL on all case records)",
            ],
            "post_launch_enhancements": [
                "Structured logging with PII audit trail",
                "Automated log scanning for PII values",
                "Full access control and audit log for admin endpoints",
                "Solicitor referral live integration (currently local storage only)",
            ],
            "implemented": [
                "Model boundary de-identification (14 PII field types stripped)",
                "boundary_log in every assess() response",
                "Upload file bytes never logged, never sent to external service",
                "Handoff lead consent required at DB constraint level",
                "Extracted PII facts excluded from apply-confirmed (Phase 5B)",
            ],
        },

        # ── Summary ────────────────────────────────────────────────────────────
        "summary": {
            "production_ready": False,
            "implemented_count": 2,    # model boundary + intake de-id
            "partial_count":     3,
            "not_implemented_count": 3,
            "critical_gaps": [
                "DPIA not completed (launch blocker)",
                "No privacy notice for users (launch blocker)",
                "No encryption at rest for uploaded documents (production blocker)",
                "No encryption for cases.facts_encrypted (production blocker)",
                "No data retention/deletion policy  -  Art.17 UK GDPR (production blocker)",
                "User authentication not implemented (production blocker)",
            ],
            "ready_for_limited_beta": False,
            "ready_for_production": False,
        },
    }
