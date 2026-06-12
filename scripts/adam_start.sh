#!/usr/bin/env bash
# Adam Chip — start the agent stack.
#
# Usage:
#   ./scripts/adam_start.sh                          # запустить всё
#   ./scripts/adam_start.sh --llm --tts              # только LLM + TTS (+ оркестратор)
#   ./scripts/adam_start.sh --asr --no-orch          # перезапустить только ASR
#   ./scripts/adam_start.sh --empty                  # только UI/оркестратор, без моделей
#   ./scripts/adam_start.sh --mode exhibition        # запустить в exhibition-режиме
#
# Флаги (можно комбинировать):
#   --llm        Запустить LLM (adam-llm.service, llama-server)
#   --tts        Запустить TTS (adam-tts-silero.service, Silero)
#   --asr        Запустить ASR (adam-asr-whisperx.service, WhisperX Docker)
#   --empty      Только оркестратор (UI, настройки) — ни одна модель не стартует
#   --no-orch    Не (пере)запускать оркестратор — только AI-сервисы
#                Полезно когда оркестратор уже работает и надо перестартовать TTS/ASR
#   --mode <m>   Задать ADAM_MODE (maintenance|exhibition). По умолчанию: maintenance
#
# Wake Word (OWW) — встроен в оркестратор, отдельного флага не требует.
# OWW запускается автоматически вместе с оркестратором.
#
# Если флаги не переданы — запускается вся система (режим "всё").
# Idempotent. Safe to re-run. Uses sudo only when systemd action is required.

set -euo pipefail

# ─── Proxy hard-clear ───────────────────────────────────────────────────────
# Adam НИКОГДА не должен идти через v2ray/xray — ESP подключён напрямую через
# crossover (eno1, 10.10.10.0/24). NO_PROXY="*" гарантирует что любой
# urllib/httpx/requests вызов идёт direct, даже если что-то забыло trust_env=False.
unset http_proxy https_proxy ftp_proxy all_proxy socks_proxy
unset HTTP_PROXY HTTPS_PROXY FTP_PROXY ALL_PROXY SOCKS_PROXY
export NO_PROXY="*"
export no_proxy="*"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
LOG_DIR="${ROOT_DIR}/data/adam"
LOG_FILE="${LOG_DIR}/orchestrator.log"
PID_FILE="${LOG_DIR}/orchestrator.pid"
PORT="${ADAM_ORCHESTRATOR_PORT:-8080}"
MODE="${ADAM_MODE:-maintenance}"
MODELS_DIR="${ADAM_MODELS_DIR:-${ROOT_DIR}/Subsystem/Models}"

LLAMACPP_DIR="${ADAM_LLM_LLAMACPP_DIR:-${ROOT_DIR}/Subsystem/llama.cpp}"
LLM_PORT="${ADAM_LLM_PORT:-8081}"
# Resolve model path: Config.json → env var → default
_cfg_model_path=$(python3 -c "
import json, pathlib, sys
try:
    d = json.load(open('${ROOT_DIR}/System/Config.json'))
    mp = d.get('services',{}).get('llm',{}).get('model_path','')
    if mp and not mp.startswith('/'):
        mp = str(pathlib.Path('${ROOT_DIR}') / mp)
    print(mp)
except Exception:
    print('')
" 2>/dev/null)
LLM_GGUF_PATH="${_cfg_model_path:-${ADAM_LLM_GGUF_PATH:-${ROOT_DIR}/Subsystem/Models/gguf/gemma-4-E4B-it-UD-Q4_K_XL.gguf}}"

# --------- argument parsing --------------------------------------------------
EXPLICIT_NODES=false
START_LLM=false
START_TTS=false
START_ASR=false
EMPTY_MODE=false
START_ORCH=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --llm)    START_LLM=true;  EXPLICIT_NODES=true ;;
    --tts)    START_TTS=true;  EXPLICIT_NODES=true ;;
    --asr)    START_ASR=true;  EXPLICIT_NODES=true ;;
    --empty)  EMPTY_MODE=true ;;
    --no-orch) START_ORCH=false ;;
    --mode)
      shift
      if [[ $# -eq 0 ]]; then
        echo "Ошибка: --mode требует значение (maintenance|exhibition)" >&2
        exit 1
      fi
      if [[ "$1" != "maintenance" && "$1" != "exhibition" ]]; then
        echo "Ошибка: --mode допускает только maintenance|exhibition, получено: $1" >&2
        exit 1
      fi
      MODE="$1"
      ;;
    *)
      echo "Неизвестный аргумент: $1" >&2
      echo "Использование: $0 [--llm] [--tts] [--asr] [--empty] [--no-orch] [--mode maintenance|exhibition]" >&2
      exit 1
      ;;
  esac
  shift
done

# No explicit nodes + no --empty → start everything
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE}; then
  START_LLM=true
  START_TTS=true
  START_ASR=true   # ASR включится ниже только если есть микрофон
fi

# --------- port helpers ------------------------------------------------------
# Wait until a TCP port is free (no listener). Returns 0 when free, 1 on timeout.
wait_port_free() {
  local port=$1 tries=${2:-20}
  for _ in $(seq 1 "${tries}"); do
    ss -tlnp 2>/dev/null | grep -q ":${port} " || return 0
    sleep 0.3
  done
  echo "  ! порт ${port} всё ещё занят после ожидания" >&2
  return 1
}

# Poll a URL until it responds (200-level). Returns 0 when healthy, 1 on timeout.
wait_port_ready() {
  local url=$1 tries=${2:-30} label=${3:-"${url}"}
  for _ in $(seq 1 "${tries}"); do
    curl --noproxy '*' -fsS -m1 "${url}" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "  ! ${label} не ответил за $(echo "${tries} * 0.5" | bc)с" >&2
  return 1
}

# --------- preflight checks --------------------------------------------------
has_usb_camera() {
  for d in /dev/video0 /dev/video1 /dev/video2; do [[ -e "$d" ]] && return 0; done
  return 1
}

has_esp_camera() {
  local url
  url="$(python3 -c "import json; print(json.load(open('${ROOT_DIR}/System/Config.json'))['mcu']['base_url'])" 2>/dev/null || echo "")"
  [[ -z "${url}" ]] && return 1
  curl -fsS --max-time 2 "${url}/api/status" >/dev/null 2>&1
}

has_microphone() {
  command -v arecord >/dev/null 2>&1 || return 1
  local dev
  dev="${ADAM_AUDIO_INPUT_DEVICE:-$(python3 -c "import json; print(json.load(open('${ROOT_DIR}/System/Config.json'))['media']['audio']['input_device'])" 2>/dev/null || echo "hw:0,0")}"
  local out
  out="$( (timeout 1 arecord -D "${dev}" --dump-hw-params 2>&1 || true) | tr -d '\000')"
  [[ "${out}" == *"ACCESS:"* ]]
}

USB_CAM=$(has_usb_camera && echo 1 || echo 0)
ESP_CAM=$(has_esp_camera && echo 1 || echo 0)
MIC_OK=$(has_microphone && echo 1 || echo 0)
MIC_SOURCE="$(python3 -c "import json; print(json.load(open('${ROOT_DIR}/System/Config.json'))['media']['audio'].get('mic_source','local'))" 2>/dev/null || echo local)"

# Auto-skip ASR if no mic (only in full-start mode).
# ВАЖНО: при mic_source=esp32 микрофон — это ESP (INMP441), а НЕ локальное
# ALSA-устройство, поэтому has_microphone()/arecord его не видит. В этом случае
# НЕ пропускаем ASR — наличие микрофона определяется доступностью ESP.
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE}; then
  if [[ "${MIC_SOURCE}" == "esp32" ]]; then
    if [[ "${ESP_CAM}" != "1" ]] && [[ "${ADAM_FORCE_ASR:-0}" != "1" ]]; then
      # mic_source=esp32, но ESP недоступен — микрофона по факту нет
      START_ASR=false
    fi
  elif [[ "${MIC_OK}" != "1" ]] && [[ "${ADAM_FORCE_ASR:-0}" != "1" ]]; then
    START_ASR=false
  fi
fi

# Build speech services list — TTS via systemd; ASR via Docker (see section 2b below)
SPEECH_SERVICES=()
${START_TTS} && SPEECH_SERVICES+=(adam-tts-silero.service)

mkdir -p "${LOG_DIR}" \
  "${MODELS_DIR}/silero" "${MODELS_DIR}/whisper" "${MODELS_DIR}/vlm" "${MODELS_DIR}/hf/hub"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "ERROR: ${VENV_PYTHON} not found. Run scripts/adam_bootstrap_venv.sh first." >&2
  exit 1
fi

# --------- header ------------------------------------------------------------
echo "▶ Adam Chip — start"
echo "  root:    ${ROOT_DIR}"
echo "  mode:    ${MODE}"
echo "  port:    ${PORT}"
if ${EMPTY_MODE}; then
  echo "  nodes:   --empty (только UI)"
elif ${EXPLICIT_NODES}; then
  NODES_LIST=""
  ${START_LLM} && NODES_LIST+=" llm"
  ${START_TTS} && NODES_LIST+=" tts"
  ${START_ASR} && NODES_LIST+=" asr"
  echo "  nodes:  ${NODES_LIST:-none}"
else
  echo "  nodes:   all"
fi
${START_ORCH} || echo "  orch:    --no-orch (оркестратор не (пере)запускается)"
printf "  hw:      USB-cam=%s  ESP-cam=%s  mic=%s\n" \
  "$([[ ${USB_CAM} == 1 ]] && echo ✓ || echo ✗)" \
  "$([[ ${ESP_CAM} == 1 ]] && echo ✓ || echo ✗)" \
  "$([[ ${MIC_OK} == 1 ]] && echo ✓ || echo ✗)"
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE} && ! ${START_ASR}; then
  echo "  · ASR пропущен (нет микрофона: source=${MIC_SOURCE}). Принудительно: ADAM_FORCE_ASR=1"
fi
echo

# --------- 0a. Mic input gain (durable across reboot, Config-driven) ---------
# Mirrors the orchestrator unit's ExecStartPre for manual starts: re-asserts the
# WebCamera ALSA capture boost + pulse source volume from Config.json so OWW keeps
# its sensitivity. Best-effort — never blocks the start.
if [[ -x "${ROOT_DIR}/scripts/adam_audio_input_gain.sh" ]]; then
  "${ROOT_DIR}/scripts/adam_audio_input_gain.sh" 2>&1 | sed 's/^/  /' || true
fi

# --------- 0. Log Viewer (always-on, independent of AI services) -------------
if systemctl cat adam-logviewer.service >/dev/null 2>&1; then
  if ! systemctl is-active --quiet adam-logviewer.service 2>/dev/null; then
    # .service суффикс обязателен — NOPASSWD-правило задано как `adam-*.service`;
    # без суффикса sudo запросит пароль.
    sudo systemctl start adam-logviewer.service >/dev/null 2>&1 || true
  fi
  systemctl is-active --quiet adam-logviewer.service 2>/dev/null \
    && echo "  ✓ adam-logviewer.service (:${ADAM_LOG_VIEWER_PORT:-8083})" \
    || echo "  ! adam-logviewer.service не стартовал"
fi

# --------- 1. LLM (llama-server) ---------------------------------------------
if ${START_LLM}; then
  LLAMA_BIN="${LLAMACPP_DIR}/build/bin/llama-server"
  if [[ ! -x "${LLAMA_BIN}" ]]; then
    echo "  ✗ llama-server не найден: ${LLAMA_BIN}"
    echo "    Собери: ${ROOT_DIR}/scripts/adam_build_llamacpp.sh"
  elif ! systemctl cat adam-llm.service >/dev/null 2>&1; then
    echo "  ! adam-llm.service не установлен. Сначала: scripts/adam_install_systemd.sh"
  else
    if ! systemctl is-active --quiet adam-llm; then
      echo "⏵ Запуск adam-llm.service:"
      # Kill stray llama-server that might hold port 8081 from a previous session.
      strays="$(pgrep -f 'llama-server' || true)"
      if [[ -n "${strays}" ]]; then
        echo "  · Убиваю stray llama-server: ${strays}"
        kill ${strays} 2>/dev/null || true
        wait_port_free "${LLM_PORT}" 10 || true
      fi
      sudo systemctl start adam-llm >/dev/null 2>&1 || true
      wait_port_ready "http://127.0.0.1:${LLM_PORT}/health" 40 "llama-server :${LLM_PORT}" || true
    fi
    if systemctl is-active --quiet adam-llm 2>/dev/null; then
      echo "  ✓ adam-llm.service (llama-server :${LLM_PORT})"
      echo "    модель: $(basename "${LLM_GGUF_PATH:-unknown}")"
    else
      echo "  ✗ adam-llm.service (см. journalctl -u adam-llm -n 30)"
    fi
  fi
fi

# --------- 2. Speech services (TTS / ASR) ------------------------------------
if [[ ${#SPEECH_SERVICES[@]} -gt 0 ]]; then
  SERVICES_AVAILABLE=()
  for s in "${SPEECH_SERVICES[@]}"; do
    if ! systemctl cat "${s}" >/dev/null 2>&1; then
      echo "  ! ${s} не установлен. Сначала: scripts/adam_install_systemd.sh"
    else
      SERVICES_AVAILABLE+=("${s}")
    fi
  done

  if [[ ${#SERVICES_AVAILABLE[@]} -gt 0 ]]; then
    need_systemd=false
    for s in "${SERVICES_AVAILABLE[@]}"; do
      if ! systemctl is-active --quiet "${s}"; then need_systemd=true; fi
    done

    if ${need_systemd}; then
      echo "⏵ Запуск speech-сервисов:"
      sudo systemctl start "${SERVICES_AVAILABLE[@]}" >/dev/null 2>&1 || true
      # Wait for TTS port instead of fixed sleep
      TTS_PORT="$(python3 -c "import json; print(json.load(open('${ROOT_DIR}/System/Config.json'))['services']['tts']['base_url'].split(':')[-1].rstrip('/'))" 2>/dev/null || echo 8082)"
      wait_port_ready "http://127.0.0.1:${TTS_PORT}/health" 30 "TTS :${TTS_PORT}" || true
    fi

    for s in "${SERVICES_AVAILABLE[@]}"; do
      systemctl is-active --quiet "${s}" 2>/dev/null \
        && echo "  ✓ ${s}" \
        || echo "  ✗ ${s} (см. journalctl -u ${s} -n 30)"
    done
  fi
fi

# --------- 2b. ASR (WhisperX — Docker CUDA, canonical sole owner of :8095) ----
# The native adam-asr-whisperx.service is masked (CPU-only, deprecated). Verification
# is health-based, NOT `docker ps` name: a container can be "running" while its uvicorn
# server has shut down after failing to bind 8095 (e.g. a stray process squatting the
# port) — so we poll /health and confirm device=cuda before declaring success.
asr_verify_health() {  # echoes the /health body; returns 0 if model loaded
  local d
  for _ in $(seq 1 40); do
    d="$(curl --noproxy '*' -fsS http://127.0.0.1:8095/health 2>/dev/null || true)"
    if echo "${d}" | grep -q '"model_loaded":true'; then echo "${d}"; return 0; fi
    sleep 2
  done
  echo "${d}"; return 1
}
asr_report() {  # arg: /health body
  if echo "$1" | grep -q '"device":"cuda"'; then
    echo "  ✓ adam-asr-whisperx (Docker, :8095, device=cuda)"
  elif echo "$1" | grep -q '"model_loaded":true'; then
    echo "  ⚠ adam-asr-whisperx работает, но device≠cuda — docker logs adam-asr-whisperx"
  else
    echo "  ✗ adam-asr-whisperx не ответил на /health — docker logs adam-asr-whisperx"
  fi
}
if ${START_ASR}; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "  ! docker не найден — ASR не запущен"
  else
    # Guard: if :8095 is held by a non-container process (masked native somehow alive),
    # the container will never bind. Surface it instead of failing silently.
    if ss -ltn 2>/dev/null | grep -q ':8095 ' && \
       ! docker ps --format '{{.Names}}' | grep -qx "adam-asr-whisperx"; then
      echo "  ! порт 8095 занят НЕ контейнером — останавливаю native ASR (deprecated)…"
      sudo systemctl stop adam-asr-whisperx.service 2>/dev/null || true
      sleep 1
    fi
    if docker ps --format '{{.Names}}' | grep -qx "adam-asr-whisperx"; then
      body="$(asr_verify_health)"; asr_report "${body}"
    else
      echo "⏵ Запуск ASR (WhisperX Docker, CUDA):"
      if (cd "${ROOT_DIR}" && docker compose up -d adam-asr-whisperx >/dev/null 2>&1); then
        body="$(asr_verify_health)"; asr_report "${body}"
      else
        echo "  ✗ docker compose up adam-asr-whisperx failed"
        echo "    Пересборка: cd ${ROOT_DIR} && docker compose build adam-asr-whisperx"
      fi
    fi
  fi
fi

# --------- 3. Orchestrator (systemd — единый владелец, Phase 30 Option A) -----
# Раньше bare-nohup + pkill дрались с systemd-юнитом → дубликаты. Теперь — только
# systemd (flock-singleton в Orchestrator.py страхует). Динамический
# ADAM_EXPECTED_SERVICES опущен: юнит берёт env из /etc/adam-chip/adam.env,
# стартовый звук работает по дефолту (минорно; вынести в файл — отдельный TODO).
if ${START_ORCH}; then
  echo
  echo "⏵ orchestrator → systemd (единый владелец)…"
  if [[ "${EUID}" -ne 0 ]]; then sudo systemctl stop adam-orchestrator.service 2>/dev/null || true
  else systemctl stop adam-orchestrator.service 2>/dev/null || true; fi
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

  if ! systemctl is-active --quiet adam-orchestrator.service 2>/dev/null; then
    echo "✗ Orchestrator не поднялся (systemd). journalctl -u adam-orchestrator.service -n 30:" >&2
    journalctl -u adam-orchestrator.service -n 30 --no-pager >&2 2>/dev/null || true
    exit 1
  fi
else
  ORCH_PID="$(pgrep -f 'System/Orchestrator\.py' | head -1 || true)"
  if [[ -n "${ORCH_PID}" ]]; then
    echo
    echo "  · Оркестратор уже запущен (PID ${ORCH_PID}), --no-orch: пропускаю перезапуск"
  else
    echo
    echo "  ! Оркестратор не запущен. Запусти без --no-orch или через adam_start.sh --empty"
  fi
fi

# --------- summary -----------------------------------------------------------
IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^192\.168\./){print $i; exit}}')"
[[ -z "${IP}" ]] && IP="127.0.0.1"

ORCH_PID="${ORCH_PID:-$(pgrep -f 'System/Orchestrator\.py' | head -1 || echo '?')}"

cat <<EOF

▶ Готово.
  PID:       ${ORCH_PID}   (saved to ${PID_FILE})
  Log:       ${LOG_FILE}
  Local UI:  http://127.0.0.1:${PORT}/
  LAN UI:    http://${IP}:${PORT}/
  Log Viewer: http://${IP}:${ADAM_LOG_VIEWER_PORT:-8083}/

Проверить:    curl --noproxy '*' -s http://127.0.0.1:${PORT}/api/agent/status | python3 -m json.tool
Логи:         tail -f ${LOG_FILE}
LLM логи:     journalctl -u adam-llm -f
Остановить:   ${ROOT_DIR}/scripts/adam_stop.sh
EOF
