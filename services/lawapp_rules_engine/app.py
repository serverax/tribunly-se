"""lawapp-rules-engine — deterministic legal rules from the DB (no LLM).

Wraps backend.core.retrieve.retrieve_rules and the employment deadline/value
math. Returns a REAL rule count from the `rules` table; fails closed (503) if the
DB is unavailable — never a fabricated count. X-Trace-ID via the shared factory.
"""
from __future__ import annotations

import time
from datetime import date

from fastapi import HTTPException
from pydantic import BaseModel

from services._common import create_service
from services.lawapp_rules_engine.cache import (
    cache_stats, cached_retrieve_rules, memoized_limitation_date)

app = create_service("lawapp-rules-engine", needs_db=True)


class RulesRequest(BaseModel):
    claim_type: str = "unfair_dismissal"
    jurisdiction: str = "EW"
    relevant_date: str | None = None
    # ACAS Early Conciliation stop-clock dates (s.207B). Optional; dates only, no PII.
    ec_day_a: str | None = None
    ec_day_b: str | None = None
    facts: dict | None = None


def _edt(req: RulesRequest) -> date:
    if req.relevant_date:
        return date.fromisoformat(req.relevant_date)
    return date.today()


def _opt_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _time_limit_months(rules: list[dict]) -> tuple[int, str, str]:
    """Pull the statutory time-limit (months) + authority from the rules rows.

    The deadline is ALWAYS computed from the rules table — never guessed. If no
    time_limit_months rule exists for this claim/jurisdiction/date, fall back to
    the ERA 1996 s.111(2) statutory default of 3 months (documented, not invented).
    """
    rule = next((r for r in rules if "time_limit_months" in r.get("rule_key", "")), None)
    if not rule:
        return 3, "ERA 1996 s.111(2)", ""
    return (
        int(rule["value_numeric"]),
        rule.get("authority_ref") or "ERA 1996 s.111(2)",
        rule.get("authority_url") or "",
    )


@app.post("/v1/rules/evaluate")
def evaluate(req: RulesRequest):
    """Rule evaluation on the hot path. Rules are served from a read-through TTL
    cache — a cache hit does ZERO database work, so steady-state latency is the
    cache lookup (microseconds), not a Postgres round trip. Single-flight on miss
    means a cold key hit by N concurrent requests triggers exactly one DB read."""
    t0 = time.perf_counter()
    try:
        rules, hit = cached_retrieve_rules(req.claim_type, req.jurisdiction, _edt(req))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"rules_db_unavailable: {e}")
    return {
        "service": "lawapp-rules-engine",
        "llm_called": False,
        "source": "rules_table",
        "count": len(rules),
        "rules": rules,
        "cache": "hit" if hit else "miss",
        "compute_ms": round((time.perf_counter() - t0) * 1000, 3),
    }


@app.post("/v1/deadline/calculate")
def deadline(req: RulesRequest):
    """Deterministic ET limitation date. The statutory time limit is read from the
    cached rules; the date arithmetic is memoized (pure function of edt + months +
    EC dates). Steady state touches neither the DB nor recomputes. Fails closed:
    503 if the rules DB is unavailable on a cold key, 422 on invalid input."""
    edt = _edt(req)
    try:
        rules, rules_hit = cached_retrieve_rules(req.claim_type, req.jurisdiction, edt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"rules_db_unavailable: {e}")
    t0 = time.perf_counter()
    try:
        tl_months, authority, authority_url = _time_limit_months(rules)
        ec_a = _opt_date(req.ec_day_a)
        ec_b = _opt_date(req.ec_day_b)
        result = memoized_limitation_date(edt, tl_months, ec_a, ec_b)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"deadline_fail_closed: {e}")
    return {
        "service": "lawapp-rules-engine",
        "source": "rules_table",
        "llm_called": False,
        "claim_type": req.claim_type,
        "jurisdiction": req.jurisdiction,
        "edt": edt.isoformat(),
        "time_limit_months": tl_months,
        "authority": authority,
        "authority_url": authority_url,
        "result": result,
        "cache": "hit" if rules_hit else "miss",
        "compute_ms": round((time.perf_counter() - t0) * 1000, 3),
    }


@app.post("/v1/compensation/calculate")
def compensation(req: RulesRequest):
    """Statutory value range computed from cached rules-table values + confirmed
    facts only. Fails closed: 503 if the rules DB is unavailable on a cold key,
    422 on invalid facts."""
    from backend.domains.employment.assess_logic import compute_value_range
    try:
        rules, hit = cached_retrieve_rules(req.claim_type, req.jurisdiction, _edt(req))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"rules_db_unavailable: {e}")
    try:
        result = compute_value_range(rules, req.facts or {})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"compensation_fail_closed: {e}")
    return {"service": "lawapp-rules-engine", "source": "rules_table", "llm_called": False,
            "result": result, "cache": "hit" if hit else "miss"}


@app.get("/v1/cache/stats")
def cache_stats_route():
    """Cache observability: hit/miss counts, hit rate, sizes. Proves the DB is off
    the hot path under load and lets ops watch the steady-state hit rate per pod."""
    return {"service": "lawapp-rules-engine", **cache_stats()}
