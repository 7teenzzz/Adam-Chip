#!/usr/bin/env bash
# Adam Chip — restart the orchestrator ONLY (LLM/TTS/ASR/VLM stay running).
#
# Usage:
#   ./scripts/adam_restart.sh                      # быстрый рестарт оркестратора
#   ./scripts/adam_restart.sh --mode exhibition    # с режимом
#   ./scripts/adam_restart.sh --all                # полный рестарт стека (stop+start)
#
# Оркестратор-only — быстро (не перезагружает модели). Перезапуск через systemd
# (Phase 30 Option A — единый владелец); flock-singleton в Orchestrator.py не даёт
# второго инстанса. ADAM_MODE / ожидаемые сервисы берутся из env-файла юнита.
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

# ─── 2. Запуск оркестратора через systemd (Phase 30 Option A — единый владелец) ─
# Раньше тут был bare-nohup, который дрался с systemd-юнитом → дубликаты на
# ребуте. Теперь — только systemd; flock-singleton в Orchestrator.py страхует от
# любого второго инстанса. ADAM_MODE / EXPECTED_SERVICES берутся из env-файла
# юнита (/etc/adam-chip/adam.env). Для смены режима: scripts/adam_set_mode.sh.
rm -f "${PID_FILE}"
if [[ "${EUID}" -ne 0 ]]; then sudo systemctl start adam-orchestrator.service
else systemctl start adam-orchestrator.service; fi

for _ in $(seq 1 60); do
  curl --noproxy '*' -fsS "http://127.0.0.1:${PORT}/api/agent/status" >/dev/null 2>&1 && break
  sleep 0.5
done
if systemctl is-active --quiet adam-orchestrator.service 2>/dev/null; then
  echo "  ✓ оркестратор перезапущен (systemd, :${PORT})"
else
  echo "✗ Оркестратор не поднялся (systemd). journalctl -u adam-orchestrator.service -n 25:" >&2
  journalctl -u adam-orchestrator.service -n 25 --no-pager >&2 2>/dev/null || true
  exit 1
fi
