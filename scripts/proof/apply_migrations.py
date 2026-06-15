"""Apply LawApp SQL migrations to the DB used by the Python app.

This runner exists because shell/WSL environment propagation can point psql at
the wrong database. It uses ingestion.config.settings.database_url directly, the
same source the application uses.
"""

from __future__ import annotations

from pathlib import Path
import sys

from ingestion.config import settings
from ingestion.db import get_connection


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "db" / "migrations"
REPORT = ROOT / "reports" / "migration_run_latest.txt"


def _log(lines: list[str], message: str = "") -> None:
    lines.append(message)
    print(message)


def _migration_files() -> list[Path]:
    return sorted(
        [
            path
            for path in MIGRATIONS_DIR.glob("*.sql")
            if path.name[:2].isdigit()
        ],
        key=lambda p: p.name,
    )


def main() -> int:
    lines: list[str] = []
    _log(lines, "LAWAPP PYTHON MIGRATION RUNNER")
    _log(lines, f"Database URL source: ingestion.config.settings.database_url")
    safe_url = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
    _log(lines, f"Database target: {safe_url}")
    _log(lines, f"Migrations: {MIGRATIONS_DIR}")
    _log(lines)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port()")
            _log(lines, f"Connected: {cur.fetchone()}")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS _migrations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        conn.commit()

        total = 0
        applied = 0
        skipped = 0
        for path in _migration_files():
            total += 1
            name = path.name
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM _migrations WHERE name = %s", (name,))
                if cur.fetchone():
                    skipped += 1
                    _log(lines, f"SKIP: {name}")
                    continue

            sql = path.read_text(encoding="utf-8")
            _log(lines, f"APPLY: {name}")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute("INSERT INTO _migrations (name) VALUES (%s)", (name,))
                conn.commit()
                applied += 1
                _log(lines, f"PASS: {name}")
            except Exception as exc:
                conn.rollback()
                _log(lines, f"FAIL: {name}")
                _log(lines, f"{type(exc).__name__}: {exc}")
                REPORT.parent.mkdir(parents=True, exist_ok=True)
                REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return 1

        _log(lines)
        _log(lines, f"MIGRATIONS COMPLETE: total={total} applied={applied} skipped={skipped}")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
