"""
Production-readiness report — Phase 5C.

Honest, comprehensive status of the system's readiness for production deployment.
This report is NOT a compliance certification.

The report must remain NOT_PRODUCTION_READY until:
  - Encryption at rest is implemented (Phase 5B+)
  - DPIA is completed and legal basis documented
  - User authentication is implemented (Phase 4+)
  - Live payment integration is configured (Phase 4)
  - Legal accuracy gate passes for all claim types

Can be retrieved via GET /admin/production-readiness.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_CLAIM_TYPES = ["unfair_dismissal", "unpaid_wages"]


def _check_rules_verification(rules: list[dict]) -> dict:
    """Check verification status for all non-prospective rules."""
    from scripts.check_rules_verification import check_verification
    return check_verification(rules)


def generate_production_readiness_report(
    rules: list[dict],
    run_kms_health_check: bool = False,
) -> dict:
    """
    Generate the full production-readiness report.

    Args:
        rules: list of rule dicts from the rules table
               (must include verification_status if migration 011 applied)

    Returns a comprehensive status dict. The overall_status will be
    NOT_PRODUCTION_READY unless all blockers are resolved.
    """
    from backend.core.dp_report import generate_dp_report
    dp = generate_dp_report()

    # ── Legal rules verification ───────────────────────────────────────────────
    from scripts.check_rules_verification import check_verification
    ver_result = check_verification(rules)
    ver_summary = ver_result["summary"]

    rules_by_claim: dict[str, dict] = {}
    for ct in _CLAIM_TYPES:
        ct_rules = [r for r in rules if r.get("claim_type") == ct and not r.get("is_prospective")]
        ct_result = check_verification(ct_rules)
        rules_by_claim[ct] = {
            "total_production_rules": len(ct_rules),
            "verified":              ct_result["summary"]["verified"],
            "case_law_verified":     ct_result["summary"]["case_law_verified"],
            "verification_required": ct_result["summary"]["verification_required"],
            "failed":                ct_result["summary"]["failed"],
            "rules_gate_passed":     ct_result["passed"],
            "status": (
                "VERIFIED" if ct_result["passed"] and ct_result["summary"]["verification_required"] == 0
                else "VERIFICATION_LIMITED"
            ),
        }

    # ── Claim-type production readiness ───────────────────────────────────────
    claim_readiness: dict[str, dict] = {}
    for ct in _CLAIM_TYPES:
        rd = rules_by_claim.get(ct, {})
        rules_ok = rd.get("rules_gate_passed", False)
        blockers = []
        if not rules_ok:
            blockers.append("Legal rules not fully verified")
        # DP blockers apply to all claim types
        blockers.extend([
            "Encryption at rest not implemented",
            "DPIA not completed",
            "User authentication not implemented",
        ])
        claim_readiness[ct] = {
            "status":            "VERIFICATION_LIMITED" if rules_ok else "BLOCKED",
            "rules_verified":    rules_ok,
            "blocking_issues":   blockers,
            "production_ready":  False,   # blocked by DP/auth regardless
        }

    import os
    from pathlib import Path as _PPath

    # ── Phase 6: check new controls ───────────────────────────────────────────
    enc_key_set   = bool(os.getenv("ENCRYPTION_KEY", ""))
    admin_key_set = bool(os.getenv("ADMIN_API_KEY", ""))
    docs_root     = _PPath(__file__).resolve().parent.parent.parent / "docs"
    privacy_ok    = (docs_root / "privacy-notice-draft.md").exists()
    dpia_ok       = (docs_root / "dpia-artefact.md").exists()

    # ── Overall blockers (Phase 6 update) ─────────────────────────────────────
    overall_blockers = []
    if not enc_key_set:
        overall_blockers.append("ENCRYPTION_KEY not set — PII stored in plaintext")
    overall_blockers.extend([
        "HSM/KMS key management not implemented — env var key not suitable for production",
        "DPIA not legally reviewed or completed",
        "Privacy notice not legally reviewed or published",
        "User authentication (OAuth/JWT) not implemented — admin key only covers admin routes",
        "Live payment not configured (PAYMENT_ENABLED=false — mock mode only)",
    ])

    # ── Model boundary ─────────────────────────────────────────────────────────
    model_boundary = {
        "status":                         "IMPLEMENTED",
        "pii_fields_stripped":            14,
        "boundary_log_in_every_response": True,
        "upload_bytes_never_logged":      True,
        "upload_bytes_never_sent_externally": True,
    }

    # ── Payment mode ───────────────────────────────────────────────────────────
    payment_enabled = os.getenv("PAYMENT_ENABLED", "false").lower() == "true"
    payment_status = {
        "live_payment":     "ENABLED" if payment_enabled else "MOCK_ONLY",
        "production_ready": payment_enabled,
        "note":             "PAYMENT_ENABLED=false — mock mode. Stripe integration required.",
    }

    # ── Legal accuracy gate ────────────────────────────────────────────────────
    legal_accuracy = {
        "status":       "CONFIGURED",
        "suite":        "tests/legal_accuracy/test_legal_accuracy.py",
        "claim_types":  _CLAIM_TYPES,
        "gate_script":  "scripts/run_legal_accuracy.py",
        "note":         "Run scripts/run_legal_accuracy.py to verify.",
    }

    return {
        "report_date":     "2026-06-01",
        "report_version":  "phase6",
        "overall_status":  "NOT_PRODUCTION_READY",
        "overall_blockers": overall_blockers,
        "disclaimer": (
            "This report describes the current implementation state. "
            "It is NOT a GDPR compliance certification or legal advice. "
            "A formal DPIA and legal review are required before production deployment. "
            "lawapp is not a law firm and does not provide regulated legal advice."
        ),

        # ── Phase 6 controls ────────────────────────────────────────────────
        "admin_authentication": {
            "status": "IMPLEMENTED" if admin_key_set else "NOT_CONFIGURED",
            "mechanism": "X-Admin-Key header on all /admin/* endpoints",
            "note": "Set ADMIN_API_KEY env var to enable. Not user-facing OAuth.",
        },
        "encryption_at_rest": {
            "status":         "PARTIAL" if enc_key_set else "NOT_CONFIGURED",
            "fields_covered": ["handoff_leads name/email/phone", "uploaded files"] if enc_key_set else [],
            "algorithm":      "Fernet (AES-128-CBC + HMAC-SHA256)",
            "key_provider":   __import__('backend.core.kms', fromlist=['get_key_provider']).get_key_provider().provider_name(),
            "envelope_encryption_supported": (
                __import__('backend.core.kms', fromlist=['get_key_provider'])
                .get_key_provider().supports_envelope_encryption()
            ),
            "ciphertext_blob_persistence_supported": (
                __import__('backend.core.kms', fromlist=['get_key_management_mode'])
                .get_key_management_mode() == "aws_kms"
                and bool(os.getenv("AWS_KMS_KEY_ARN"))
            ),
            "production_ready": False,
            "note": (
                "Phase 7D: envelope encryption (GenerateDataKey/Decrypt) implemented. "
                "Full key rotation lifecycle is Phase 7E+."
            ),
        },
        "deletion_policy": {
            "status":    "IMPLEMENTED",
            "endpoints": ["DELETE /cases/{id}", "DELETE /handoff/leads/{id}"],
            "script":    "scripts/run_retention.py",
        },
        "privacy_notice": {
            "artefact_exists":  privacy_ok,
            "legally_reviewed": False,
            "status":           "ARTEFACT_IN_PROGRESS" if privacy_ok else "NOT_STARTED",
        },
        "dpia": {
            "artefact_exists":  dpia_ok,
            "legally_reviewed": False,
            "status":           "ARTEFACT_IN_PROGRESS" if dpia_ok else "NOT_STARTED",
        },

        # ── Phase 8B: algorithm brain / reasoning model status ──────────────────
        # ── Reasoning model status: LOCAL OLLAMA ONLY (no external LLM) ──────────
        "reasoning_model": (lambda: {
            "backend":              "ollama_local",
            "provider":             os.getenv("LAWAPP_LLM_PROVIDER", "ollama_local"),
            "ollama_base_url":      os.getenv("LAWAPP_OLLAMA_BASE_URL", ""),
            "ollama_model":         os.getenv("LAWAPP_OLLAMA_MODEL", "qwen2.5:3b-instruct-q6_K"),
            "external_llm_allowed": False,
            "anthropic_configured": False,
            "deterministic_upgrade":"IMPLEMENTED (assess_logic.py — runs before any model call)",
            "production_grade": (
                os.getenv("LAWAPP_LLM_PROVIDER", "") == "ollama_local"
                and bool(os.getenv("LAWAPP_OLLAMA_BASE_URL", "").strip())
                and bool(os.getenv("LAWAPP_OLLAMA_MODEL", "").strip())
            ),
            "note": (
                "Local Ollama only. No external LLM (OpenAI/Anthropic/OpenRouter). "
                "Order: RULES -> GRAPHRAG -> local Ollama (last resort) -> CitationGuard. "
                "If Ollama is unavailable, legal inference fails closed (INFERENCE_UNAVAILABLE)."
            ),
        })(),

        "claim_type_readiness": claim_readiness,
        "legal_rules_verification": {
            "gate_passed": ver_result["passed"],
            "summary":     ver_summary,
            "failures":    ver_result["failures"],
            "by_claim_type": rules_by_claim,
        },
        "legal_accuracy_gate":   legal_accuracy,
        "model_boundary":        model_boundary,
        "data_protection":       dp["summary"],
        "dp_priority_breakdown": dp.get("priority_breakdown", {}),
        "payment_mode":          payment_status,
        "live_solicitor_referral": {
            "status": "NOT_IMPLEMENTED",
            "note":   "Handoff leads stored locally. Phase 7.",
        },
        "user_authentication": {
            "admin_key_status":  "IMPLEMENTED" if admin_key_set else "NOT_CONFIGURED",
            "end_user_auth_mode": os.getenv("LAWAPP_AUTH_MODE", "none"),
            "jwt_hs256_verification": (
                "IMPLEMENTED" if (os.getenv("LAWAPP_AUTH_MODE") == "jwt"
                                   and os.getenv("JWT_SECRET"))
                else "NOT_CONFIGURED"
            ),
            "jwt_rs256_jwks_verification": (
                "IMPLEMENTED" if (os.getenv("LAWAPP_AUTH_MODE") == "jwt"
                                   and os.getenv("JWT_JWKS_URL"))
                else "NOT_CONFIGURED"
            ),
            "jwt_production_grade": bool(
                os.getenv("LAWAPP_AUTH_MODE") == "jwt"
                and os.getenv("JWT_JWKS_URL")
                and os.getenv("JWT_ISSUER")
                and os.getenv("JWT_AUDIENCE")
            ),
            "overall_status": (
                "IMPLEMENTED_PRODUCTION_GRADE"
                if (os.getenv("LAWAPP_AUTH_MODE") == "jwt"
                    and os.getenv("JWT_JWKS_URL")
                    and os.getenv("JWT_ISSUER")
                    and os.getenv("JWT_AUDIENCE"))
                else (
                    "IMPLEMENTED_DEV_QUALITY"
                    if (os.getenv("LAWAPP_AUTH_MODE") == "jwt"
                        and os.getenv("JWT_SECRET"))
                    else "PARTIAL"
                )
            ),
            "note": (
                "RS256+JWKS implemented (Phase 7A) — production-grade when JWT_JWKS_URL set. "
                "HS256 (JWT_SECRET) implemented (Phase 6C) — dev/test quality only. "
                "Mock auth (X-User-ID) for dev/test only."
            ),
        },
        "payment": {
            "mode":        os.getenv("PAYMENT_MODE", "mock"),
            "live_ready":  (os.getenv("PAYMENT_MODE", "mock") == "stripe_live"
                            and bool(os.getenv("STRIPE_SECRET_KEY"))),
            "stripe_key":  "SET" if os.getenv("STRIPE_SECRET_KEY") else "NOT_SET",
            "note":        "mock mode for tests; stripe_live requires STRIPE_SECRET_KEY + Phase 7.",
        },
        "deployment_config": {
            "mode":                  os.getenv("DEPLOYMENT_MODE", "development"),
            "startup_validation":    "IMPLEMENTED",
            "required_vars_present": all(os.getenv(v) for v in ["POSTGRES_PASSWORD","ADMIN_API_KEY","ENCRYPTION_KEY"]),
            "missing_required":      [v for v in ["POSTGRES_PASSWORD","ADMIN_API_KEY","ENCRYPTION_KEY"] if not os.getenv(v)],
        },
        "upload_storage": {
            "status":    "LOCAL_FILESYSTEM_ONLY",
            "encrypted": enc_key_set,
            "phase":     "Phase 7: encrypted object storage required for production.",
        },

        # ── Phase 6B/7E: KMS + envelope encryption + key rotation ──────────────
        "key_management": __import__(
            'backend.core.kms', fromlist=['get_kms_status']
        ).get_kms_status(run_health_check=run_kms_health_check),

        "key_rotation": {
            "status":               "FOUNDATION_READY",
            "encryption_version":   "7D",
            "provider_key_id_tracked": True,
            "envelope_encrypt_str_available": True,
            "envelope_decrypt_str_available": True,
            "rotation_api":         "NOT_IMPLEMENTED — Phase 7F",
            "db_schema_ready":      True,   # encryption_key_metadata jsonb (migration 013)
            "note": (
                "Phase 7E: envelope encryption integrated into handoff-leads PII path. "
                "Key rotation lifecycle (re-encrypt + update bundle) is Phase 7F."
            ),
        },

        "compliance": __import__(
            'backend.domains.employment.compliance', fromlist=['get_compliance_status']
        ).get_compliance_status(),
        # Phase 6D: required_evidence is now embedded inside get_compliance_status()
        # under key "required_evidence" — no separate top-level field needed.

        # ── Phase 6B: controlled-beta vs production readiness ─────────────────
        **_compute_beta_production_readiness(
            ver_result=ver_result,
            enc_key_set=enc_key_set,
            admin_key_set=admin_key_set,
        ),
    }


def _compute_beta_production_readiness(
    ver_result:    dict,
    enc_key_set:   bool,
    admin_key_set: bool,
) -> dict:
    """Compute controlled_beta_ready and production_ready with explicit blockers."""
    from backend.domains.employment.compliance import get_compliance_status
    from backend.core.user_auth import is_auth_controlled_beta_ready, is_auth_production_ready
    from backend.core.kms import is_production_grade_key_management

    compliance  = get_compliance_status()
    auth_cb     = is_auth_controlled_beta_ready()
    auth_prod   = is_auth_production_ready()
    kms_ok      = is_production_grade_key_management()

    # ── Controlled-beta blockers ───────────────────────────────────────────────
    cb_blockers: list[str] = []
    if not ver_result.get("passed", False):
        cb_blockers.append("Rules verification gate not passing")
    if not enc_key_set:
        cb_blockers.append("ENCRYPTION_KEY not set")
    if not admin_key_set:
        cb_blockers.append("ADMIN_API_KEY not set")
    cb_blockers.extend(auth_cb.get("blockers", []))
    cb_blockers.extend(compliance.get("controlled_beta_blockers", []))

    # ── Production blockers ────────────────────────────────────────────────────
    prod_blockers: list[str] = list(cb_blockers)  # starts from CB blockers
    prod_blockers.extend(auth_prod.get("blockers", []))
    prod_blockers.extend(compliance.get("production_compliance_blockers", []))
    if not kms_ok:
        prod_blockers.append(
            "KEY_MANAGEMENT_MODE=env is not production-grade — use kms_stub or real KMS (Phase 7)."
        )
    prod_blockers.append("No live deployment environment (Phase 7)")

    cb_ready   = len(cb_blockers) == 0
    prod_ready = False   # always False until all prod blockers resolved

    # Phase 6E: generate ordered next steps for reaching controlled beta
    next_steps = _controlled_beta_next_steps(cb_blockers, compliance)

    return {
        "controlled_beta_ready":     cb_ready,
        "controlled_beta_blockers":  cb_blockers,
        "controlled_beta_next_steps": next_steps,
        "production_ready":          prod_ready,
        "production_blockers":       prod_blockers,
        "ready_for_limited_beta":    cb_ready,   # alias
        "ready_for_production":      prod_ready,
        "runbook":                   "docs/pre-beta-runbook.md",
        "beta_readiness_script":     "scripts/check_beta_readiness.py",
    }


def _controlled_beta_next_steps(cb_blockers: list[str], compliance: dict) -> list[dict]:
    """
    Generate ordered, prioritised next steps for reaching controlled beta.
    Human-review items are listed first (critical path).
    Configuration items listed next.
    Phase 7 items are excluded (out of scope for beta preparation).
    """
    steps: list[dict] = []
    priority = 1

    def _add(action: str, step_type: str, detail: str, reference: str = "") -> None:
        nonlocal priority
        steps.append({
            "priority":  priority,
            "type":      step_type,
            "action":    action,
            "detail":    detail,
            "reference": reference,
        })
        priority += 1

    # ── Human review items (critical path — cannot be automated) ───────────────
    dpia_comp = compliance.get("signoff", {}).get("dpia", {})
    dpia_reviewed = dpia_comp.get("reviewed_by_dpo", False) or dpia_comp.get("approved", False)
    dpia_evidence = dpia_comp.get("reviewer_name") and dpia_comp.get("review_date")

    if not (dpia_reviewed and dpia_evidence):
        _add(
            "DPIA DPO review",
            "human_review_required",
            "Complete docs/dpia-review-checklist.md; update docs/compliance-signoff.json with reviewer_name + review_date.",
            "docs/dpia-review-checklist.md",
        )

    pn_comp = compliance.get("signoff", {}).get("privacy_notice", {})
    pn_reviewed = pn_comp.get("legally_reviewed", False)
    pn_evidence = pn_comp.get("reviewer_name") and pn_comp.get("review_date")

    if not (pn_reviewed and pn_evidence):
        _add(
            "Privacy notice legal review",
            "human_review_required",
            "Complete docs/privacy-review-checklist.md; update docs/compliance-signoff.json with reviewer_name + review_date.",
            "docs/privacy-review-checklist.md",
        )

    # ── Configuration items ─────────────────────────────────────────────────────
    import os as _os
    if any("ENCRYPTION_KEY" in b for b in cb_blockers):
        _add(
            "Set ENCRYPTION_KEY environment variable",
            "configuration",
            'Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
            "docs/env-production.template",
        )
    if any("ADMIN_API_KEY" in b for b in cb_blockers):
        _add(
            "Set ADMIN_API_KEY environment variable",
            "configuration",
            "Set to a strong random string. See docs/env-production.template.",
            "docs/env-production.template",
        )
    if any("auth" in b.lower() or "LAWAPP_AUTH_MODE" in b for b in cb_blockers):
        _add(
            "Configure LAWAPP_AUTH_MODE=jwt + JWT_SECRET + JWT_ISSUER + JWT_AUDIENCE",
            "configuration",
            "HS256 JWT verification is implemented (Phase 6C). See docs/env-production.template.",
            "docs/env-production.template",
        )

    # ── Verification step (after all blockers resolved) ─────────────────────────
    _add(
        "Verify controlled_beta_ready=true",
        "verification",
        "Run: python scripts/check_beta_readiness.py; then GET /admin/production-readiness",
        "scripts/check_beta_readiness.py",
    )

    return steps
