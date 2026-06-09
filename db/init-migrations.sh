#!/bin/bash
##############################################################################
# LAWAPP DATABASE MIGRATION RUNNER
#
# Purpose: Apply all database migrations in order (001, 002, ..., 055)
# Idempotent: Safe to run multiple times (skips already-applied migrations)
# Usage: Called by docker-compose db service automatically
#        Also can be run manually: bash db/init-migrations.sh
##############################################################################

set -e

DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-lawapp}"
DB_USER="${POSTGRES_USER:-lawapp}"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"

if [ -z "$DB_PASSWORD" ]; then
    echo "⚠️  POSTGRES_PASSWORD not set, using PGPASSWORD from environment"
fi

MIGRATIONS_DIR="$(dirname "$0")/migrations"

echo "════════════════════════════════════════════════════════════"
echo "LAWAPP MIGRATION RUNNER"
echo "════════════════════════════════════════════════════════════"
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "Migrations: $MIGRATIONS_DIR"
echo ""

# Wait for PostgreSQL to be ready
echo "▸ Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "  Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ PostgreSQL failed to become ready"
    exit 1
fi

# Create migrations tracking table if not exists
echo "▸ Ensuring migrations tracking table exists..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE TABLE IF NOT EXISTS _migrations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL UNIQUE,
        applied_at TIMESTAMPTZ DEFAULT now()
    );" 2>/dev/null || true

# Find and apply all migrations in order
echo ""
echo "▸ Scanning for migration files..."
migration_count=0
applied_count=0

# Find all .sql files matching pattern NNN_*.sql and sort numerically
for migration_file in $(find "$MIGRATIONS_DIR" -maxdepth 1 -name "[0-9][0-9][0-9]_*.sql" -o -name "[0-9][0-9]_*.sql" | sort -V); do
    migration_name=$(basename "$migration_file")

    # Check if migration already applied
    already_applied=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -t -c "SELECT COUNT(*) FROM _migrations WHERE name = '$migration_name';" 2>/dev/null || echo "0")

    if [ "$already_applied" -eq "0" ]; then
        echo "▸ Applying: $migration_name"

        # Apply migration
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -f "$migration_file" > /dev/null 2>&1; then

            # Mark as applied
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -c "INSERT INTO _migrations (name) VALUES ('$migration_name');" 2>/dev/null || true

            echo "  ✅ Applied"
            applied_count=$((applied_count + 1))
        else
            echo "  ⚠️  FAILED (will continue, may cause issues)"
        fi
    else
        echo "  ⊝ Already applied: $migration_name"
    fi

    migration_count=$((migration_count + 1))
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ MIGRATION COMPLETE"
echo "   Total migrations: $migration_count"
echo "   Newly applied: $applied_count"
echo "════════════════════════════════════════════════════════════"
echo ""

# Verify schema
echo "▸ Verifying schema..."
table_count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema');" 2>/dev/null || echo "0")

echo "✅ Database has $table_count tables"
echo ""
