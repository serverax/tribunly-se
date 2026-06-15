"""Prove the live database schema is ready for LawApp's core workflows.

This is intentionally narrower than the full DB integrity proof: it checks the
tables/columns required for auth, case saving, dashboard, payment gating,
documents, admin/audit, RAG/rules, and the 24-module catalogue.
"""

from __future__ import annotations

from pathlib import Path
import sys

from ingestion.db import get_connection


REPORT = Path("reports/proof_schema_readiness.txt")

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "users": {
        "id",
        "email",
        "password_hash",
        "created_at",
        "subscription_status",
    },
    "auth_sessions": {
        "id",
        "user_id",
        "refresh_token_hash",
        "expires_at",
        "revoked_at",
    },
    "auth_tokens": {
        "id",
        "user_id",
        "token_hash",
        "purpose",
        "expires_at",
        "consumed_at",
    },
    "cases": {
        "id",
        "user_id",
        "claim_type",
        "jurisdiction",
        "assessment",
        "key_dates",
        "status",
        "payment_status",
        "facts_encrypted",
        "encryption_version",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "documents": {
        "id",
        "case_id",
        "user_id",
        "doc_type",
        "document_type",
        "storage_ref",
        "is_user_upload",
        "extraction_status",
        "created_at",
    },
    "payment_sessions": {
        "case_id",
        "user_id",
        "stripe_session_id",
        "status",
        "package_id",
        "amount_pence",
        "created_at",
        "completed_at",
    },
    "payment_events": {
        "case_id",
        "user_id",
        "session_id",
        "payment_status",
        "received_at",
    },
    "audit_events": {
        "user_id",
        "action",
        "resource_type",
        "resource_id",
        "result",
        "created_at",
    },
    "rules": {
        "rule_key",
        "claim_type",
        "jurisdiction",
        "value_numeric",
        "authority_ref",
        "authority_url",
        "effective_from",
        "verification_status",
    },
    "employment_modules": {
        "module_key",
        "label",
        "status",
        "db_backed_required",
    },
}


def _write(lines: list[str]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print(text, end="")


def main() -> int:
    lines = ["LAWAPP SCHEMA READINESS PROOF", ""]
    failures: list[str] = []
    try:
        conn = get_connection()
    except Exception as exc:
        lines.append(f"FAIL: cannot connect to database: {type(exc).__name__}: {exc}")
        _write(lines)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            columns: dict[str, set[str]] = {}
            for table_name, column_name in cur.fetchall():
                columns.setdefault(table_name, set()).add(column_name)

            for table_name, required in sorted(REQUIRED_COLUMNS.items()):
                actual = columns.get(table_name, set())
                if not actual:
                    failures.append(f"missing table: {table_name}")
                    lines.append(f"FAIL: missing table {table_name}")
                    continue
                missing = sorted(required - actual)
                if missing:
                    failures.append(f"{table_name} missing columns: {', '.join(missing)}")
                    lines.append(f"FAIL: {table_name} missing columns: {', '.join(missing)}")
                else:
                    lines.append(f"PASS: {table_name} required columns present")

            if "employment_modules" in columns:
                cur.execute("SELECT count(*) FROM employment_modules")
                module_count = int(cur.fetchone()[0])
                if module_count != 24:
                    failures.append(f"employment_modules row count is {module_count}, expected 24")
                    lines.append(f"FAIL: employment_modules row count {module_count} != 24")
                else:
                    lines.append("PASS: employment_modules has 24 rows")
            else:
                failures.append("employment_modules cannot be counted because table is missing")

            cur.execute("SELECT to_regclass('public._migrations')")
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM _migrations")
                lines.append(f"INFO: _migrations rows: {int(cur.fetchone()[0])}")
            else:
                failures.append("missing migration tracking table: _migrations")
                lines.append("FAIL: missing migration tracking table _migrations")
    finally:
        conn.close()

    lines.append("")
    if failures:
        lines.append("SCHEMA READINESS: FAIL")
        for failure in failures:
            lines.append(f"- {failure}")
        _write(lines)
        return 1

    lines.append("SCHEMA READINESS: PASS")
    _write(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
