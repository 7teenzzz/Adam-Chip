#!/usr/bin/env bash
# Adam Chip — restart one or more services.
#
# Usage:
#   ./scripts/adam_service_restart.sh                  # restart all
#   ./scripts/adam_service_restart.sh --llm            # только LLM
#   ./scripts/adam_service_restart.sh --tts --asr      # только TTS + ASR
#   ./scripts/adam_service_restart.sh --orchestrator   # только оркестратор
#
# Flags: --llm, --tts, --asr, --orchestrator  (default: all)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${ROOT_DIR}/data/adam/orchestrator.pid"
LOG_FILE="${ROOT_DIR}/data/adam/orchestrator.log"
PORT="${ADAM_ORCHESTRATOR_PORT:-8080}"
MODE="${ADAM_MODE:-maintenance}"

DO_LLM=false
DO_TTS=false
DO_ASR=false
DO_ORCH=false
EXPLICIT=false

for arg in "$@"; do
  case "${arg}" in
    --llm)          DO_LLM=true;  EXPLICIT=true ;;
    --tts)          DO_TTS=true;  EXPLICIT=true ;;
    --asr)          DO_ASR=true;  EXPLICIT=true ;;
    --orchestrator) DO_ORCH=true; EXPLICIT=true ;;
    *)
      echo "Неизвестный аргумент: ${arg}" >&2
      echo "Использование: $0 [--llm] [--tts] [--asr] [--orchestrator]" >&2
      exit 1 ;;
  esac
done

if ! ${EXPLICIT}; then
  DO_LLM=true; DO_TTS=true; DO_ASR=true; DO_ORCH=true
fi

echo "▶ Adam Chip — restart"
echo

# --------- Systemd services --------------------------------------------------
SYSD_SERVICES=()
${DO_LLM} && SYSD_SERVICES+=(adam-llm.service)
${DO_TTS} && SYSD_SERVICES+=(adam-tts-silero.service)
${DO_ASR} && SYSD_SERVICES+=(adam-asr-whisper.service)

if [[ ${#SYSD_SERVICES[@]} -gt 0 ]]; then
  # Kill stray llama-server before LLM restart to avoid port 8051 conflict.
  if ${DO_LLM}; then
    strays="$(pgrep -f 'llama-server' || true)"
    if [[ -n "${strays}" ]]; then
      echo "  · Убиваю stray llama-server: ${strays}"
      kill ${strays} 2>/dev/null || true
      sleep 1
    fi
  fi

  echo "⏵ Перезапуск сервисов (sudo):"
  if [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl restart "${SYSD_SERVICES[@]}" || true
  else
    systemctl restart "${SYSD_SERVICES[@]}" || true
  fi

  sleep 2
  for s in "${SYSD_SERVICES[@]}"; do
    if systemctl is-active --quiet "${s}" 2>/dev/null; then
      echo "  ✓ ${s}"
    else
      echo "  ✗ ${s} (см. journalctl -u ${s} -n 30)"
    fi
  done
fi

# --------- Orchestrator (PID-process) ----------------------------------------
if ${DO_ORCH}; then
  [[ ${#SYSD_SERVICES[@]} -gt 0 ]] && echo
  existing_pids="$(pgrep -f 'System/Orchestrator\.py' || true)"
  if [[ -n "${existing_pids}" ]]; then
    echo "⏵ Останавливаю orchestrator: ${existing_pids}"
    kill ${existing_pids} 2>/dev/null || true
    sleep 1
    remaining="$(pgrep -f 'System/Orchestrator\.py' || true)"
    [[ -n "${remaining}" ]] && kill -9 ${remaining} 2>/dev/null || true
    rm -f "${PID_FILE}"
  fi

  VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
  MODELS_DIR="${ADAM_MODELS_DIR:-${ROOT_DIR}/Subsystem/Models}"
  echo "⏵ Запуск orchestrator…"
  cd "${ROOT_DIR}"
  PYTHONPATH="${ROOT_DIR}/System" \
    ADAM_MODE="${MODE}" \
    ADAM_ORCHESTRATOR_PORT="${PORT}" \
    ADAM_MODELS_DIR="${MODELS_DIR}" \
    HF_HOME="${MODELS_DIR}/hf" \
    HF_HUB_CACHE="${MODELS_DIR}/hf/hub" \
    nohup "${VENV_PYTHON}" "${ROOT_DIR}/System/Orchestrator.py" >>"${LOG_FILE}" 2>&1 &
  ORCH_PID=$!
  echo "${ORCH_PID}" > "${PID_FILE}"
  disown "${ORCH_PID}" 2>/dev/null || true

  for i in $(seq 1 40); do
    if curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}/api/agent/status" >/dev/null 2>&1; then
      break
    fi
    sleep 0.3
  done

  if kill -0 "${ORCH_PID}" 2>/dev/null; then
    echo "  ✓ orchestrator (PID=${ORCH_PID})"
  else
    echo "  ✗ orchestrator упал:" >&2
    tail -n 20 "${LOG_FILE}" >&2 || true
  fi
fi

echo
echo "▶ Готово."
