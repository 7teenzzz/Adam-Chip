#!/usr/bin/env bash
# Adam Chip — restart the orchestrator ONLY (LLM/TTS/ASR/VLM stay running).
#
# Usage:
#   ./scripts/adam_restart.sh                      # быстрый рестарт оркестратора
#   ./scripts/adam_restart.sh --mode exhibition    # с режимом
#   ./scripts/adam_restart.sh --all                # полный рестарт стека (stop+start)
#
# Оркестратор-only — быстро (не перезагружает модели). Сервисы, которые сейчас
# подняты (по health-портам), передаются в ADAM_EXPECTED_SERVICES, чтобы
# оркестратор их ожидал. Запускается тем же nohup-способом, что и adam_start.sh.
set -euo pipefail

# ─── Proxy hard-clear (ESP — direct, без v2ray) ─────────────────────────────
unset http_proxy https_proxy ftp_proxy all_proxy socks_proxy
unset HTTP_PROXY HTTPS_PROXY FTP_PROXY ALL_PROXY SOCKS_PROXY
export NO_PROXY="*" no_proxy="*"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
LOG_DIR="${ROOT_DIR}/data/adam"
LOG_FILE="${LOG_DIR}/orchestrator.log"
PID_FILE="${LOG_DIR}/orchestrator.pid"
PORT="${ADAM_ORCHESTRATOR_PORT:-8080}"
MODE="${ADAM_MODE:-maintenance}"
MODELS_DIR="${ADAM_MODELS_DIR:-${ROOT_DIR}/Subsystem/Models}"

# ─── args ────────────────────────────────────────────────────────────────────
FULL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) FULL=true ;;
    --mode)
      shift
      [[ $# -eq 0 || ( "$1" != "maintenance" && "$1" != "exhibition" ) ]] && {
        echo "Ошибка: --mode требует maintenance|exhibition" >&2; exit 1; }
      MODE="$1" ;;
    *) echo "Неизвестный аргумент: $1" >&2
       echo "Использование: $0 [--mode maintenance|exhibition] [--all]" >&2; exit 1 ;;
  esac
  shift
done

# ─── --all: полный рестарт стека через stop+start ───────────────────────────
if ${FULL}; then
  echo "▶ Полный рестарт стека (stop + start)…"
  "${ROOT_DIR}/scripts/adam_stop.sh"
  exec "${ROOT_DIR}/scripts/adam_start.sh" --mode "${MODE}"
fi

echo "▶ Adam Chip — restart orchestrator (mode=${MODE})"

# ─── 1. Стоп текущего оркестратора (systemd + PID + strays) ──────────────────
if systemctl is-active --quiet adam-orchestrator.service 2>/dev/null; then
  echo "⏵ stop adam-orchestrator.service (systemd)…"
  sudo systemctl stop adam-orchestrator.service || true
fi
if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true
    for _ in $(seq 1 15); do kill -0 "${PID}" 2>/dev/null || break; sleep 0.3; done
    kill -0 "${PID}" 2>/dev/null && kill -9 "${PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi
strays="$(pgrep -f 'System/Orchestrator\.py' || true)"
if [[ -n "${strays}" ]]; then
  kill ${strays} 2>/dev/null || true
  sleep 1
  remaining="$(pgrep -f 'System/Orchestrator\.py' || true)"
  [[ -n "${remaining}" ]] && kill -9 ${remaining} 2>/dev/null || true
fi
echo "  ✓ старый оркестратор остановлен"

# Wait for port to be free before binding uvicorn — race condition on rapid restart.
_wait_port_free() {
  local port=$1 tries=${2:-20}
  for _ in $(seq 1 "${tries}"); do
    ss -tlnp 2>/dev/null | grep -q ":${port} " || return 0
    sleep 0.3
  done
  echo "  ! порт ${port} всё ещё занят после ожидания" >&2
  return 1
}
_wait_port_free "${PORT}" 20 || {
  echo "  · принудительное освобождение порта ${PORT}…"
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  sleep 1
}

# ─── 2. Какие сервисы сейчас живы → ADAM_EXPECTED_SERVICES ───────────────────
# Read ports from Config.json to avoid hardcoded values.
_cfg() { python3 -c "import json; d=json.load(open('${ROOT_DIR}/System/Config.json')); print($1)" 2>/dev/null || echo "$2"; }
LLM_HEALTH_PORT="$(_cfg "d['services']['llm']['base_url'].split(':')[-1].rstrip('/')" 8081)"
TTS_HEALTH_PORT="$(_cfg "d['services']['tts']['base_url'].split(':')[-1].rstrip('/')" 8082)"
ASR_HEALTH_PORT="$(_cfg "d['services']['asr']['base_url'].split(':')[-1].rstrip('/')" 8095)"
VLM_HEALTH_PORT="$(_cfg "d['services']['vlm']['base_url'].split(':')[-1].rstrip('/')" 8084)"

EXPECTED=""
curl --noproxy '*' -fsS -m2 "http://127.0.0.1:${LLM_HEALTH_PORT}/health" >/dev/null 2>&1 && EXPECTED+="llm,"
curl --noproxy '*' -fsS -m2 "http://127.0.0.1:${TTS_HEALTH_PORT}/health" >/dev/null 2>&1 && EXPECTED+="tts,"
curl --noproxy '*' -fsS -m2 "http://127.0.0.1:${ASR_HEALTH_PORT}/health" >/dev/null 2>&1 && EXPECTED+="asr,"
curl --noproxy '*' -fsS -m2 "http://127.0.0.1:${VLM_HEALTH_PORT}/"        >/dev/null 2>&1 && EXPECTED+="vlm,"
EXPECTED="${EXPECTED%,}"
echo "  ожидаемые сервисы: ${EXPECTED:-none}"

# ─── 3. Запуск оркестратора (nohup, как в adam_start.sh) ─────────────────────
mkdir -p "${LOG_DIR}"
[[ -x "${VENV_PYTHON}" ]] || { echo "ERROR: ${VENV_PYTHON} нет — adam_bootstrap_venv.sh" >&2; exit 1; }

cd "${ROOT_DIR}"
PYTHONPATH="${ROOT_DIR}/System" \
  ADAM_MODE="${MODE}" \
  ADAM_ORCHESTRATOR_PORT="${PORT}" \
  ADAM_MODELS_DIR="${MODELS_DIR}" \
  ADAM_EXPECTED_SERVICES="${EXPECTED}" \
  HF_HOME="${MODELS_DIR}/hf" \
  HF_HUB_CACHE="${MODELS_DIR}/hf/hub" \
  NO_PROXY="*" no_proxy="*" \
  http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" \
  nohup "${VENV_PYTHON}" "${ROOT_DIR}/System/Orchestrator.py" >>"${LOG_FILE}" 2>&1 &
ORCH_PID=$!
echo "${ORCH_PID}" > "${PID_FILE}"
disown "${ORCH_PID}" 2>/dev/null || true

for _ in $(seq 1 40); do
  curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}/api/agent/status" >/dev/null 2>&1 && break
  sleep 0.3
done
if kill -0 "${ORCH_PID}" 2>/dev/null; then
  echo "  ✓ оркестратор перезапущен (PID ${ORCH_PID}, :${PORT})"
else
  echo "✗ Оркестратор упал. Хвост лога:" >&2
  tail -n 25 "${LOG_FILE}" >&2 || true
  exit 1
fi
