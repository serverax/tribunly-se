#!/bin/bash
##############################################################################
# LAWAPP BACKEND ENTRYPOINT
#
# Purpose: Run database migrations, then start the backend server
# This ensures database is ready before backend initializes
##############################################################################

set -e

echo "════════════════════════════════════════════════════════════"
echo "LAWAPP BACKEND STARTUP"
echo "════════════════════════════════════════════════════════════"

# Run migrations
echo ""
echo "▸ Running database migrations..."
bash /app/db/init-migrations.sh

# Verify backend dependencies
echo ""
echo "▸ Verifying backend dependencies..."

if ! python -c "import fastapi; import psycopg2; import redis" 2>/dev/null; then
    echo "❌ Missing dependencies - install with: pip install -r requirements.txt"
    exit 1
fi

echo "✅ All dependencies available"

# Start backend
echo ""
echo "▸ Starting backend server..."
echo "════════════════════════════════════════════════════════════"
echo ""

exec uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
