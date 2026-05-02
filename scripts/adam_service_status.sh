#!/usr/bin/env bash
set -euo pipefail

systemctl --no-pager status adam-orchestrator.service adam-tts-silero.service adam-exhibition.target || true
echo
curl -fsS "${ADAM_ORCHESTRATOR_URL:-http://127.0.0.1:8080}/api/agent/status" | python3 -m json.tool || true
