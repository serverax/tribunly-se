#!/bin/bash
curl -s -X POST http://localhost:8000/api/brain/trace \
  -H "Content-Type: application/json" \
  -d '{"message":"right not to be unfairly dismissed","facts":{"edt":"2026-05-10","service_years":3,"reason":"performance","appeal_done":false}}' | jq '{status: .assessment.status, rules: .trace.rules_applied, sources: .trace.sources_retrieved}'
