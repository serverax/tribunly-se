#!/usr/bin/env python3
"""
Production readiness check for CI  -  no running server or DB required.

Generates the readiness report from config/files only (no DB rules query).
Always exits 0  -  this is a reporting script, not a hard gate.
CI will see the output in the job log.

Usage:
    python scripts/check_production_readiness_ci.py

The script checks:
  - Deployment config env vars
  - Auth mode config
  - KMS/key management mode
  - Compliance sign-off state (docs/compliance-signoff.json)
  - CI scripts exist
  - Does NOT check DB-dependent rules (that is the rules-verification-gate job)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from backend.core.config_validation import validate_startup_config
    from backend.domains.employment.compliance import get_compliance_status
    from backend.core.kms import get_kms_status
    from backend.core.user_auth import is_auth_controlled_beta_ready, is_auth_production_ready

    print("=" * 70)
    print("LAWAPP  -  CI PRODUCTION READINESS CHECK (no DB required)")
    print("=" * 70)

    # Config validation (dev mode  -  never fail_fast in CI without full env)
    config = validate_startup_config(fail_fast=False)
    print(f"\nDeployment mode:   {config['deployment_mode']}")
    print(f"Auth mode:         {config['auth_mode']}")
    print(f"Payment mode:      {config['payment_mode']}")
    print(f"KMS mode:          {config['kms_mode']}")
    if config["missing_required"]:
        print(f"Missing vars:      {config['missing_required']}")

    # KMS status
    kms = get_kms_status()
    print(f"\nKey management:    {kms['mode']}  -  production-grade: {kms['production_grade']}")

    # Auth status
    auth_cb = is_auth_controlled_beta_ready()
    print(f"Auth (beta ready): {auth_cb['ready']}")
    if auth_cb["blockers"]:
        for b in auth_cb["blockers"]:
            print(f"  Blocker: {b}")

    # Compliance
    comp = get_compliance_status()
    print(f"\nCompliance:")
    print(f"  Controlled beta ready: {comp['controlled_beta_ready']}")
    if comp["controlled_beta_blockers"]:
        for b in comp["controlled_beta_blockers"]:
            print(f"  Blocker: {b}")
    print(f"  Production ready:      {comp['production_compliance_ready']}")

    # Check scripts exist
    scripts = [
        "scripts/run_legal_accuracy.py",
        "scripts/check_rules_verification.py",
        "scripts/safe_push.sh",
        "scripts/run_full_regression.sh",
    ]
    all_scripts_ok = True
    print("\nCI scripts:")
    for s in scripts:
        exists = os.path.exists(s)
        print(f"  {'OK' if exists else 'MISSING'}  {s}")
        if not exists:
            all_scripts_ok = False

    print()
    print("=" * 70)
    print("NOTE: This is a REPORTING check  -  exits 0 always.")
    print("NOT_PRODUCTION_READY is expected. Use production-readiness endpoint")
    print("for full status (requires running server with ADMIN_API_KEY).")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
