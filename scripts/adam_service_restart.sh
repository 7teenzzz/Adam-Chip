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

# --------- Systemd services (LLM + TTS) --------------------------------------
# ASR is NOT here: native adam-asr-whisperx.service is masked (CPU-only, deprecated).
# ASR runs exclusively via the Docker CUDA container — handled in its own block below.
# Restarts are issued PER-UNIT (not multi-arg) because the NOPASSWD sudoers rules whitelist
# only single-unit `systemctl restart adam-<name>.service` — a multi-arg `restart A B`
# would not match and would prompt for a password.
SYSD_SERVICES=()
${DO_LLM} && SYSD_SERVICES+=(adam-llm.service)
${DO_TTS} && SYSD_SERVICES+=(adam-tts-silero.service)

if [[ ${#SYSD_SERVICES[@]} -gt 0 ]]; then
  # Kill stray llama-server before LLM restart to avoid port 8081 conflict.
  if ${DO_LLM}; then
    strays="$(pgrep -f 'llama-server' || true)"
    if [[ -n "${strays}" ]]; then
      echo "  · Убиваю stray llama-server: ${strays}"
      kill ${strays} 2>/dev/null || true
      sleep 1
    fi
  fi

  echo "⏵ Перезапуск сервисов (sudo, по одному):"
  for s in "${SYSD_SERVICES[@]}"; do
    if [[ "${EUID}" -ne 0 ]]; then
      sudo systemctl restart "${s}" || true
    else
      systemctl restart "${s}" || true
    fi
  done

  sleep 2
  for s in "${SYSD_SERVICES[@]}"; do
    if systemctl is-active --quiet "${s}" 2>/dev/null; then
      echo "  ✓ ${s}"
    else
      echo "  ✗ ${s} (см. journalctl -u ${s} -n 30)"
    fi
  done
fi

# --------- ASR (WhisperX — Docker CUDA, canonical) ---------------------------
if ${DO_ASR}; then
  echo "⏵ Перезапуск ASR (WhisperX Docker, CUDA):"
  if ! command -v docker >/dev/null 2>&1; then
    echo "  ! docker не найден — ASR не перезапущен"
  elif (cd "${ROOT_DIR}" && docker compose restart adam-asr-whisperx >/dev/null 2>&1); then
    # Wait for CUDA model load + verify device.
    for _ in $(seq 1 40); do
      d="$(curl --noproxy '*' -fsS http://127.0.0.1:8095/health 2>/dev/null || true)"
      echo "${d}" | grep -q '"model_loaded":true' && break
      sleep 2
    done
    if echo "${d}" | grep -q '"device":"cuda"'; then
      echo "  ✓ adam-asr-whisperx (Docker, :8095, device=cuda)"
    elif echo "${d}" | grep -q '"model_loaded":true'; then
      echo "  ⚠ adam-asr-whisperx работает, но device≠cuda — проверь docker logs adam-asr-whisperx"
    else
      echo "  ✗ adam-asr-whisperx не ответил на /health — docker logs adam-asr-whisperx"
    fi
  else
    echo "  ✗ docker compose restart adam-asr-whisperx failed"
  fi
fi

# --------- Orchestrator (systemd — единый владелец, Phase 30 Option A) --------
# Раньше скрипт запускал bare-python и делал pkill — это дралось с systemd-юнитом
# (тот рестартил убитый инстанс) и плодило дубликаты. Теперь — только systemd.
# flock-singleton в Orchestrator.py гарантирует один инстанс (defence-in-depth).
if ${DO_ORCH}; then
  [[ ${#SYSD_SERVICES[@]} -gt 0 ]] && echo
  echo "⏵ orchestrator → systemd restart (единый владелец)…"
  if [[ "${EUID}" -ne 0 ]]; then sudo systemctl stop adam-orchestrator.service 2>/dev/null || true
  else systemctl stop adam-orchestrator.service 2>/dev/null || true; fi
  # Подчистить legacy bare-инстансы (до миграции на systemd-only).
  strays="$(pgrep -f 'System/Orchestrator\.py' || true)"
  if [[ -n "${strays}" ]]; then kill ${strays} 2>/dev/null || true; sleep 1; kill -9 ${strays} 2>/dev/null || true; fi
  rm -f "${PID_FILE}"
  if [[ "${EUID}" -ne 0 ]]; then sudo systemctl start adam-orchestrator.service
  else systemctl start adam-orchestrator.service; fi

  for i in $(seq 1 60); do
    if curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}/api/agent/status" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if systemctl is-active --quiet adam-orchestrator.service 2>/dev/null; then
    echo "  ✓ orchestrator (systemd)"
  else
    echo "  ✗ orchestrator (см. journalctl -u adam-orchestrator.service -n 30)" >&2
  fi
fi

echo
echo "▶ Готово."
