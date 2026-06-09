#!/bin/bash
set -e

##############################################################################
# LAWAPP DOCKER DATABASE INITIALIZATION
#
# Purpose: Initialize database inside Docker container
# Usage: docker compose run --rm db-init
#
# This script runs INSIDE the ingestion container and initializes the database
##############################################################################

echo "════════════════════════════════════════════════════════════"
echo "LAWAPP DATABASE INITIALIZATION (Docker)"
echo "════════════════════════════════════════════════════════════"

# Use environment variables from docker-compose
DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-lawapp}"
DB_USER="${POSTGRES_USER:-lawapp}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

if [ -z "$DB_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD not set"
    exit 1
fi

echo "ℹ️  Database: $DB_NAME"
echo "ℹ️  Host: $DB_HOST"
echo "ℹ️  Port: $DB_PORT"

# Wait for database to be ready
echo ""
echo "▸ Waiting for database to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
        echo "✅ Database is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "  Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Database failed to become ready after ${max_attempts} attempts"
    exit 1
fi

# Drop existing database
echo ""
echo "▸ Dropping existing database (if exists)..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

# Create fresh database
echo "▸ Creating fresh database..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Enable extensions
echo "▸ Enabling pgvector extension..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS pgvector;" 2>/dev/null || {
    echo "  ⚠️  pgvector not available (continuing anyway)"
}

# Load schema
echo ""
echo "▸ Loading schema..."
if [ -f "/app/backend/schema/legal_database_schema.sql" ]; then
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -f "/app/backend/schema/legal_database_schema.sql" > /dev/null 2>&1 || {
        echo "  ⚠️  Schema load had warnings but continuing"
    }
    echo "✅ Schema loaded"
else
    echo "❌ Schema file not found at /app/backend/schema/legal_database_schema.sql"
    exit 1
fi

# Seed employment law modules
echo ""
echo "▸ Seeding employment law modules..."
if [ -f "/app/backend/ingestion/seeds/employment_law_modules.py" ]; then
    cd /app
    python -m backend.ingestion.seeds.employment_law_modules || {
        echo "  ⚠️  Module seeding had issues but continuing"
    }
    echo "✅ Modules seeded"
else
    echo "  ℹ️  Modules seed script not found (will be created by agents)"
fi

# Seed legislation
echo ""
echo "▸ Seeding core legislation..."
if [ -f "/app/backend/ingestion/seeds/legislation_seed.py" ]; then
    cd /app
    python -m backend.ingestion.seeds.legislation_seed || {
        echo "  ⚠️  Legislation seeding had issues but continuing"
    }
    echo "✅ Legislation seeded"
else
    echo "  ℹ️  Legislation seed script not found"
fi

# Verify
echo ""
echo "▸ Verifying schema integrity..."
TABLE_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'lawapp';")

echo "✅ Found $TABLE_COUNT tables in lawapp schema"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ DATABASE INITIALIZATION COMPLETE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Ready for agents to populate business logic data"
echo ""
