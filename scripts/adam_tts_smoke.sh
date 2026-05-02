#!/usr/bin/env bash
set -euo pipefail

TTS_URL="${ADAM_TTS_URL:-http://127.0.0.1:8090}"
TEXT="${1:-Проверка голоса Adam Chip.}"
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

HTTP_STATUS="$(curl -sS "${TTS_URL}/speak" \
  -H "Content-Type: application/json" \
  -d "$(ADAM_TTS_SMOKE_TEXT="${TEXT}" python3 - <<'PY'
import os
import json
print(json.dumps({"text": os.environ["ADAM_TTS_SMOKE_TEXT"]}, ensure_ascii=False))
PY
)" \
  -o "${TMP}" \
  -w "%{http_code}")"

python3 - "${TMP}" "${HTTP_STATUS}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
http_status = int(sys.argv[2])
print(json.dumps(payload, ensure_ascii=False, indent=2))

if http_status >= 400:
    raise SystemExit(f"TTS smoke failed: HTTP {http_status}")

playback = payload.get("playback") if isinstance(payload.get("playback"), dict) else {}
playback_enabled = playback.get("enabled", True)
playback_ok = playback.get("ok", True) if playback_enabled else True

if not payload.get("ok", False):
    raise SystemExit("TTS smoke failed: /speak returned ok=false")
if not playback_ok:
    raise SystemExit("TTS smoke failed: playback failed")
PY
