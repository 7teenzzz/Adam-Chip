#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-maintenance}"
BASE_URL="${ADAM_ORCHESTRATOR_URL:-http://127.0.0.1:8080}"

curl -fsS "${BASE_URL}/api/agent/mode" \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"${MODE}\"}" | python3 -m json.tool
