#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${ADAM_ORCHESTRATOR_URL:-http://127.0.0.1:8080}"

echo "Power:"
nvpmodel -q || true

echo
echo "Orchestrator:"
curl -fsS "${BASE_URL}/api/agent/status" | python3 -m json.tool
