#!/bin/bash
set -e

echo "Starting lawapp demo environment..."

if [ ! -f .env ]; then
    echo "Warning: .env not found. Copying .env.example to .env..."
    cp .env.example .env
fi

echo "Ensuring virtual environment and dependencies..."
source .venv/bin/activate
pip install -r requirements.txt || echo "requirements.txt missing, assuming dependencies are managed via pyproject.toml"
pip install -e .

echo "Checking database connectivity..."
python scripts/check_rules_verification.py || echo "Warning: rules verification check failed."

echo "Starting backend server..."
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
