#!/usr/bin/env python3
"""
Live smoke gate for lawapp.

Validates:
  - /health returns DB-connected
  - /assess returns a grounded unfair-dismissal assessment for a definitive case
  - /assess refuses an out-of-scope claim
"""

from __future__ import annotations

import json
import os
import sys

import requests


BASE_URL = os.getenv("LAWAPP_SMOKE_BASE_URL", "http://lawapp-backend.lawapp-api.svc.cluster.local")


def fail(msg: str) -> int:
    print(f"✗ SMOKE GATE: FAILED  -  {msg}")
    return 1


def main() -> int:
    print("=" * 70)
    print("LAWAPP  -  LIVE SMOKE GATE")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")

    health = requests.get(f"{BASE_URL}/health", timeout=20)
    print("Health:", health.status_code, health.text[:300])
    if health.status_code != 200:
        return fail(f"/health returned {health.status_code}")
    if health.json().get("db") != "connected":
        return fail(f"/health db state was {health.json()}")

    grounded_payload = {
        "query": "I was dismissed after 14 months with no procedure",
        "facts": {
            "edt": "2026-03-15",
            "service_start_date": "2025-01-01",
            "reason_for_dismissal": "conduct",
            "was_procedure_followed": False,
            "weekly_pay": 450,
            "jurisdiction": "EW",
        },
        "jurisdiction": "EW",
        "use_model": False,
    }
    grounded = requests.post(f"{BASE_URL}/assess", json=grounded_payload, timeout=60)
    grounded_json = grounded.json()
    print("Grounded assessment:")
    print(json.dumps({
        "status": grounded_json.get("status"),
        "claim_type": grounded_json.get("claim_type"),
        "citations": len(grounded_json.get("citations") or []),
        "grounding_score": grounded_json.get("grounding_score"),
        "confidence_score": grounded_json.get("confidence_score"),
        "deadline_info": grounded_json.get("deadline_info"),
        "recommended_next_step": grounded_json.get("recommended_next_step"),
    }, ensure_ascii=False, indent=2))
    if grounded.status_code != 200:
        return fail(f"grounded assessment HTTP {grounded.status_code}")
    if grounded_json.get("status") != "ok":
        return fail(f"grounded assessment status {grounded_json.get('status')}")
    if grounded_json.get("claim_type") != "unfair_dismissal":
        return fail("grounded assessment claim_type mismatch")
    if not grounded_json.get("citations"):
        return fail("grounded assessment had no citations")
    if float(grounded_json.get("grounding_score") or 0) <= 0:
        return fail("grounded assessment grounding_score not positive")

    refusal_payload = {
        "query": "I want to sue my landlord for deposit",
        "facts": {},
        "jurisdiction": "EW",
        "use_model": False,
    }
    refusal = requests.post(f"{BASE_URL}/assess", json=refusal_payload, timeout=60)
    refusal_json = refusal.json()
    print("Refusal assessment:")
    print(json.dumps({
        "status": refusal_json.get("status"),
        "matter_type": refusal_json.get("matter_type"),
        "message": refusal_json.get("message"),
    }, ensure_ascii=False, indent=2))
    if refusal.status_code != 200:
        return fail(f"refusal assessment HTTP {refusal.status_code}")
    if refusal_json.get("status") != "not_supported":
        return fail(f"refusal status {refusal_json.get('status')}")

    print("✓ SMOKE GATE: PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
