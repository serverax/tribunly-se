#!/bin/bash
set -e

DIR="/mnt/f/lawapp/reports/v3_evidence"
mkdir -p "$DIR"
cd /mnt/f/lawapp

echo "--- F. HOSTILE SECURITY TESTS ---" > "$DIR/f_security_audit.txt"
timeout 120 python -m pytest tests/security/ -q >> "$DIR/f_security_audit.txt" 2>&1 || echo "SECURITY PYTEST TIMED OUT OR FAILED" >> "$DIR/f_security_audit.txt"
timeout 120 python -m pytest tests/user_isolation/ -q >> "$DIR/f_security_audit.txt" 2>&1 || echo "ISOLATION PYTEST TIMED OUT OR FAILED" >> "$DIR/f_security_audit.txt"
timeout 120 python -m pytest tests/rate_limiting/ -q >> "$DIR/f_security_audit.txt" 2>&1 || echo "RATE LIMIT PYTEST TIMED OUT OR FAILED" >> "$DIR/f_security_audit.txt"

echo "--- M. ADDITIONAL TESTS ---" >> "$DIR/m_test_audit.txt"
timeout 120 python -m pytest tests/payment/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/documents/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/deadlines/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/brain/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/rag/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/legal_accuracy/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true
timeout 120 python -m pytest tests/ingestion/ -q >> "$DIR/m_test_audit.txt" 2>&1 || true

echo "Additional tests complete."
