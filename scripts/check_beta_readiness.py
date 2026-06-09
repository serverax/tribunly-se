#!/usr/bin/env python3
"""
Controlled-beta readiness check — Phase 6E.

Checks all pre-beta conditions without requiring a running server or DB.
Reports ordered next steps. Always exits 0 (reporting only).

Usage:
    python scripts/check_beta_readiness.py

Works in both dev and production environments.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    print("=" * 70)
    print("LAWAPP — CONTROLLED-BETA READINESS CHECK")
    print("=" * 70)

    blockers: list[str] = []
    ok_items: list[str] = []
    next_steps: list[dict] = []

    # ── 1. Compliance / human reviews ─────────────────────────────────────────
    from backend.domains.employment.compliance import load_signoff, check_controlled_beta
    signoff = load_signoff()
    cb = check_controlled_beta(signoff)

    dpia_ok = (signoff.get("dpia", {}).get("reviewed_by_dpo", False)
               or signoff.get("dpia", {}).get("approved", False))
    dpia_evidence = (signoff.get("dpia", {}).get("reviewer_name")
                     and signoff.get("dpia", {}).get("review_date"))
    pn_ok = signoff.get("privacy_notice", {}).get("legally_reviewed", False)
    pn_evidence = (signoff.get("privacy_notice", {}).get("reviewer_name")
                   and signoff.get("privacy_notice", {}).get("review_date"))

    if not (dpia_ok and dpia_evidence):
        blockers.append("DPIA not reviewed by DPO with evidence")
        next_steps.append({
            "priority": 1,
            "type": "human_review_required",
            "action": "DPIA DPO review",
            "detail": "See docs/dpia-review-checklist.md → update docs/compliance-signoff.json",
        })
    else:
        ok_items.append("DPIA reviewed by DPO with evidence")

    if not (pn_ok and pn_evidence):
        blockers.append("Privacy notice not legally reviewed with evidence")
        next_steps.append({
            "priority": 2,
            "type": "human_review_required",
            "action": "Privacy notice legal review",
            "detail": "See docs/privacy-review-checklist.md → update docs/compliance-signoff.json",
        })
    else:
        ok_items.append("Privacy notice legally reviewed with evidence")

    # ── 2. Environment configuration ──────────────────────────────────────────
    required_config = {
        "ADMIN_API_KEY":    "Admin endpoint protection",
        "ENCRYPTION_KEY":   "PII encryption at rest",
        "APP_BASE_URL":     "Application base URL for CORS",
    }
    for var, desc in required_config.items():
        if not os.getenv(var):
            blockers.append(f"{var} not set ({desc})")
            next_steps.append({
                "priority": 3,
                "type": "configuration",
                "action": f"Set {var}",
                "detail": f"See docs/env-production.template — {desc}",
            })
        else:
            ok_items.append(f"{var} configured")

    # ── 3. Auth mode ───────────────────────────────────────────────────────────
    auth_mode = os.getenv("LAWAPP_AUTH_MODE", "none")
    if auth_mode not in ("jwt", "mock"):
        blockers.append(f"LAWAPP_AUTH_MODE='{auth_mode}' — set to 'jwt' for beta")
        next_steps.append({
            "priority": 4,
            "type": "configuration",
            "action": "Set LAWAPP_AUTH_MODE=jwt with JWT_SECRET + JWT_ISSUER + JWT_AUDIENCE",
            "detail": "See docs/env-production.template for JWT configuration",
        })
    else:
        ok_items.append(f"Auth mode: {auth_mode}")

    # ── 4. Operational files ───────────────────────────────────────────────────
    docs_root = Path(__file__).resolve().parent.parent / "docs"
    required_docs = {
        "dpia-artefact.md":            "DPIA artefact",
        "privacy-notice-draft.md":     "Privacy notice",
        "dpia-review-checklist.md":    "DPO review checklist",
        "privacy-review-checklist.md": "Legal review checklist",
        "compliance-signoff.json":     "Compliance sign-off",
        "pre-beta-runbook.md":         "Pre-beta runbook",
        "env-production.template":     "Production env template",
    }
    for fname, label in required_docs.items():
        if (docs_root / fname).exists():
            ok_items.append(f"docs/{fname} exists")
        else:
            blockers.append(f"docs/{fname} missing ({label})")

    # ── 5. CI scripts ──────────────────────────────────────────────────────────
    scripts_root = Path(__file__).resolve().parent
    for script in ["run_legal_accuracy.py", "check_rules_verification.py"]:
        if (scripts_root / script).exists():
            ok_items.append(f"scripts/{script} exists")
        else:
            blockers.append(f"scripts/{script} missing")

    # ── Report ─────────────────────────────────────────────────────────────────
    print(f"\n{'✓ OK'} items ({len(ok_items)}):")
    for item in ok_items:
        print(f"  ✓  {item}")

    if blockers:
        print(f"\n{'✗ BLOCKERS'} ({len(blockers)}):")
        for b in blockers:
            print(f"  ✗  {b}")

    if next_steps:
        print(f"\nOrdered next steps to reach controlled beta:")
        for step in sorted(next_steps, key=lambda s: s["priority"]):
            tag = "[HUMAN REVIEW]" if step["type"] == "human_review_required" else "[CONFIG]"
            print(f"  {step['priority']}. {tag} {step['action']}")
            print(f"       {step['detail']}")

    print()
    beta_ready = len(blockers) == 0
    status = "CONTROLLED BETA READY" if beta_ready else "NOT BETA READY"
    print(f"Result: {status}")
    print()
    print("Note: This check is configuration-based only.")
    print("For full report, use GET /admin/production-readiness with X-Admin-Key.")
    print("=" * 70)
    return 0   # always exits 0 — reporting only


if __name__ == "__main__":
    sys.exit(main())
