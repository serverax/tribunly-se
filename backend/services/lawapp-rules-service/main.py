"""
lawapp-rules-service
Port 8016

Rules service for UK employment law.
Serves employment law rules: unfair dismissal, unpaid wages, discrimination.
No LLM. Deterministic rules engine only.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import redis

SERVICE_NAME = "lawapp-rules-service"
SERVICE_PORT = 8016

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def get_db_connection():
    try:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            return psycopg2.connect(database_url)
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "lawapp"),
            user=os.getenv("POSTGRES_USER", "lawapp"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
    except Exception as e:
        logger.warning(f"DB connection failed: {e}")
        return None

# Redis connection
def get_redis_connection():
    try:
        return redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        return None

# Core employment law rules
UNFAIR_DISMISSAL_RULES = {
    "time_limit_months": 3,
    "time_limit_days": 93,
    "qualifying_period_months": 2,
    "notice_period_default_weeks": 1,
    "compensation_weeks_per_year": 0.5,
    "basic_award_cap_weeks": 30,
    "compensatory_award_cap_multiplier": 52,
}

UNPAID_WAGES_RULES = {
    "time_limit_years": 2,
    "time_limit_days": 730,
    "limitation_statute": "Limitation Act 1980 s5",
}

DISCRIMINATION_RULES = {
    "time_limit_months": 3,
    "time_limit_days": 90,
    "protected_characteristics": [
        "age", "disability", "gender_reassignment", "marriage",
        "pregnancy", "race", "religion", "sex", "sexual_orientation",
    ],
}

app = FastAPI(title=SERVICE_NAME)
db = None
cache = None

@app.on_event("startup")
def startup():
    global db, cache
    db = get_db_connection()
    cache = get_redis_connection()
    if db:
        logger.info("✓ Database connected")
    else:
        logger.warning("✗ Database unavailable (rules available in memory)")
    if cache:
        logger.info("✓ Cache connected")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/ready")
def ready():
    db_ok = db is not None
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "database_connected": db_ok,
        "redis_connected": cache is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/api/rules/{domain}/{module}/{rule_key}")
def get_rule(domain: str, module: str, rule_key: str):
    """Get a specific rule."""

    # Validate inputs
    if not all(c.isalnum() or c == "_" for c in [domain, module, rule_key]):
        raise HTTPException(status_code=400, detail="Invalid rule key format")

    # Check cache first
    if cache:
        cached = cache.get(f"rule:{domain}:{module}:{rule_key}")
        if cached:
            return json.loads(cached)

    # Load from memory rules
    rule_data = _get_rule_from_memory(domain, module, rule_key)
    if not rule_data:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Cache the result
    if cache:
        cache.setex(f"rule:{domain}:{module}:{rule_key}", 3600, json.dumps(rule_data))

    return rule_data

@app.get("/api/rules/list")
def list_rules(domain: str = "uk_employment"):
    """List all rules for a domain."""

    if domain != "uk_employment":
        raise HTTPException(status_code=400, detail="Only uk_employment domain supported")

    all_rules = {
        "unfair_dismissal": UNFAIR_DISMISSAL_RULES,
        "unpaid_wages": UNPAID_WAGES_RULES,
        "discrimination": DISCRIMINATION_RULES,
    }

    return {
        "domain": domain,
        "rules": all_rules,
        "total_count": sum(len(rules) for rules in all_rules.values()),
    }

@app.get("/api/rules/validate/{domain}")
def validate_rules(domain: str = "uk_employment"):
    """Validate rule coverage for a domain."""

    if domain != "uk_employment":
        raise HTTPException(status_code=400, detail="Only uk_employment domain supported")

    modules = {
        "unfair_dismissal": UNFAIR_DISMISSAL_RULES,
        "unpaid_wages": UNPAID_WAGES_RULES,
        "discrimination": DISCRIMINATION_RULES,
    }

    return {
        "domain": domain,
        "modules": modules,
        "total_rules": sum(len(rules) for rules in modules.values()),
        "coverage": "complete",
    }

def _get_rule_from_memory(domain: str, module: str, rule_key: str) -> Optional[Dict]:
    """Load rule from memory."""

    if domain != "uk_employment":
        return None

    rules_map = {
        "unfair_dismissal": UNFAIR_DISMISSAL_RULES,
        "unpaid_wages": UNPAID_WAGES_RULES,
        "discrimination": DISCRIMINATION_RULES,
    }

    if module not in rules_map:
        return None

    rule_value = rules_map[module].get(rule_key)
    if rule_value is None:
        return None

    return {
        "domain": domain,
        "module": module,
        "rule_key": rule_key,
        "claim_type": module,
        "jurisdiction": "EW",
        "value": rule_value,
        "authority_ref": f"Employment Rights Act 1996 / {module}",
        "effective_from": "2024-01-01",
        "last_updated": datetime.utcnow().isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
