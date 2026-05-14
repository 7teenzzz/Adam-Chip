#!/usr/bin/env bash
# Adam Chip — stop the full agent stack:
#   - orchestrator (kill PID from data/adam/orchestrator.pid)
#   - LLM (adam-llm.service) + speech systemd services (TTS + ASR)
#   - any leftover live-vlm container (best effort)
#
# Idempotent. Safe to run when nothing is up.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/data/adam"
PID_FILE="${LOG_DIR}/orchestrator.pid"

SYSTEMD_SERVICES=(adam-orchestrator.service adam-llm.service adam-tts-silero.service)
LIVE_VLM_CONTAINER="adam-live-vlm"

STOP_ALL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) STOP_ALL=true ;;
    *) echo "Неизвестный аргумент: $1" >&2; echo "Использование: $0 [--all]" >&2; exit 1 ;;
  esac
  shift
done

echo "▶ Adam Chip — stop${STOP_ALL:+ (--all)}"
echo

# --------- 0. Disarm systemd orchestrator first (prevents Restart=on-failure) -
if systemctl is-active --quiet adam-orchestrator.service 2>/dev/null; then
  echo "⏵ Останавливаю adam-orchestrator.service (systemd)…"
  sudo systemctl stop adam-orchestrator.service || true
  echo "  ✓ adam-orchestrator.service остановлен"
fi

# --------- 1. Orchestrator ---------------------------------------------------
killed=false
if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    echo "⏵ Останавливаю orchestrator PID=${PID}…"
    kill "${PID}" 2>/dev/null || true
    for i in $(seq 1 15); do
      if ! kill -0 "${PID}" 2>/dev/null; then break; fi
      sleep 0.3
    done
    if kill -0 "${PID}" 2>/dev/null; then
      echo "  ! force kill"
      kill -9 "${PID}" 2>/dev/null || true
    fi
    killed=true
  fi
  rm -f "${PID_FILE}"
fi

# Sweep stragglers (manually started instances that don't have a PID file).
strays="$(pgrep -f 'System/Orchestrator\.py' || true)"
if [[ -n "${strays}" ]]; then
  echo "⏵ Останавливаю забытые orchestrator: ${strays}"
  kill ${strays} 2>/dev/null || true
  sleep 1
  remaining="$(pgrep -f 'System/Orchestrator\.py' || true)"
  if [[ -n "${remaining}" ]]; then
    kill -9 ${remaining} 2>/dev/null || true
  fi
  killed=true
fi

if ${killed}; then
  echo "  ✓ orchestrator остановлен"
else
  echo "  · orchestrator не был запущен"
fi

# --------- 2. Live VLM container (best effort) -------------------------------
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${LIVE_VLM_CONTAINER}"; then
    echo
    echo "⏵ Останавливаю live VLM container…"
    docker stop "${LIVE_VLM_CONTAINER}" >/dev/null 2>&1 || true
    docker rm   "${LIVE_VLM_CONTAINER}" >/dev/null 2>&1 || true
    echo "  ✓ ${LIVE_VLM_CONTAINER} остановлен"
  fi
fi

# --------- 2b. ASR (WhisperX — Docker) --------------------------------------
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "adam-asr-whisperx"; then
    echo
    echo "⏵ Останавливаю ASR (WhisperX Docker)…"
    (cd "${ROOT_DIR}" && docker compose stop adam-asr-whisperx >/dev/null 2>&1) || true
    echo "  ✓ adam-asr-whisperx остановлен"
  else
    echo "  · adam-asr-whisperx не был запущен"
  fi
fi

# --------- 3. Systemd services (LLM + TTS) -----------------------------------
need_systemd=false
for s in "${SYSTEMD_SERVICES[@]}"; do
  if systemctl is-active --quiet "${s}" 2>/dev/null; then
    need_systemd=true
  fi
done

if ${need_systemd}; then
  echo
  echo "⏵ Остановка сервисов (sudo):"
  sudo systemctl stop "${SYSTEMD_SERVICES[@]}" || true
fi

for s in "${SYSTEMD_SERVICES[@]}"; do
  if systemctl is-active --quiet "${s}" 2>/dev/null; then
    echo "  ✗ ${s} всё ещё активен"
  else
    echo "  ✓ ${s} остановлен"
  fi
done

# --------- 4. Log Viewer (only with --all) -----------------------------------
if ${STOP_ALL}; then
  if systemctl is-active --quiet adam-logviewer.service 2>/dev/null; then
    echo
    echo "⏵ Останавливаю adam-logviewer.service (--all)…"
    sudo systemctl stop adam-logviewer.service || true
    echo "  ✓ adam-logviewer.service остановлен"
  fi
fi

echo
echo "▶ Готово."
