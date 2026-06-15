from pathlib import Path

import scripts.proof.prove_schema_readiness as schema_readiness


def test_schema_readiness_covers_workflow_critical_tables():
    required = schema_readiness.REQUIRED_COLUMNS

    for table in (
        "users",
        "auth_sessions",
        "cases",
        "documents",
        "payment_sessions",
        "payment_events",
        "audit_events",
        "rules",
        "employment_modules",
    ):
        assert table in required

    assert {"id", "user_id", "payment_status", "assessment", "key_dates"} <= required["cases"]
    assert {"module_key", "status", "db_backed_required"} <= required["employment_modules"]


def test_migration_runner_fails_hard_on_failed_migration():
    script = Path("db/init-migrations.sh").read_text(encoding="utf-8")

    assert "Migration failure is a hard release blocker." in script
    assert "exit 1" in script
    assert "FAILED (will continue" not in script


def test_docker_db_init_uses_canonical_migration_runner():
    script = Path("scripts/docker-init-db.sh").read_text(encoding="utf-8")

    assert "/app/db/init-migrations.sh" in script
    assert "backend/schema/legal_database_schema.sql" not in script
    assert "public schema" in script


def test_database_integrity_proof_runs_schema_readiness_first():
    script = Path("scripts/proof/prove_database_integrity.sh").read_text(encoding="utf-8")

    assert "## schema readiness" in script
    assert "prove_schema_readiness.py" in script
    assert "import psycopg2" in script
