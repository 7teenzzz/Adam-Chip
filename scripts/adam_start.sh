#!/usr/bin/env bash
# Adam Chip — start the agent stack.
#
# Usage:
#   ./scripts/adam_start.sh                  # запустить всё
#   ./scripts/adam_start.sh --llm --tts      # только LLM + TTS
#   ./scripts/adam_start.sh --empty          # только UI/оркестратор, без моделей
#
# Флаги (можно комбинировать): --llm --tts --asr --vlm     
#   --empty   только оркестратор (UI, настройки) — ни одна модель не стартует
#
# Если флаги не переданы — запускается вся система (режим "всё").
# Idempotent. Safe to re-run. Uses sudo only when systemd action is required.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
LOG_DIR="${ROOT_DIR}/data/adam"
LOG_FILE="${LOG_DIR}/orchestrator.log"
PID_FILE="${LOG_DIR}/orchestrator.pid"
PORT="${ADAM_ORCHESTRATOR_PORT:-8080}"
MODE="${ADAM_MODE:-maintenance}"
MODELS_DIR="${ADAM_MODELS_DIR:-${ROOT_DIR}/Subsystem/Models}"

LIVE_VLM_CONTAINER="adam-live-vlm"
LIVE_VLM_CAMERA="${ADAM_VLM_CAMERA:-/dev/video0}"
LLAMACPP_DIR="${ADAM_LLM_LLAMACPP_DIR:-${ROOT_DIR}/Subsystem/llama.cpp}"
LLM_PORT="${ADAM_LLM_PORT:-8081}"

# --------- argument parsing --------------------------------------------------
EXPLICIT_NODES=false
START_LLM=false
START_TTS=false
START_ASR=false
START_VLM=false
EMPTY_MODE=false

for arg in "$@"; do
  case "${arg}" in
    --llm)   START_LLM=true;  EXPLICIT_NODES=true ;;
    --tts)   START_TTS=true;  EXPLICIT_NODES=true ;;
    --asr)   START_ASR=true;  EXPLICIT_NODES=true ;;
    --vlm)   START_VLM=true;  EXPLICIT_NODES=true ;;
    --empty) EMPTY_MODE=true ;;
    *)
      echo "Неизвестный аргумент: ${arg}" >&2
      echo "Использование: $0 [--llm] [--tts] [--asr] [--vlm] [--empty]" >&2
      exit 1
      ;;
  esac
done

# No explicit nodes + no --empty → start everything
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE}; then
  START_LLM=true
  START_TTS=true
  START_ASR=true   # ASR включится ниже только если есть микрофон
  START_VLM=auto   # VLM включится если есть камера + Docker-образ
else
  # --vlm без --asr при полном запуске handled above; при --vlm explicit:
  [[ "${START_VLM}" == "false" ]] && START_VLM=false
fi

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

# Auto-skip ASR if no mic (only in full-start mode)
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE}; then
  if [[ "${MIC_OK}" != "1" ]] && [[ "${ADAM_FORCE_ASR:-0}" != "1" ]]; then
    START_ASR=false
  fi
fi

# Build speech services list
SPEECH_SERVICES=()
${START_TTS} && SPEECH_SERVICES+=(adam-tts-silero.service)
${START_ASR} && SPEECH_SERVICES+=(adam-asr-speaches.service)

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
  [[ "${START_VLM}" == "true" ]] && NODES_LIST+=" vlm"
  echo "  nodes:  ${NODES_LIST:-none}"
else
  echo "  nodes:   all"
fi
printf "  hw:      USB-cam=%s  ESP-cam=%s  mic=%s\n" \
  "$([[ ${USB_CAM} == 1 ]] && echo ✓ || echo ✗)" \
  "$([[ ${ESP_CAM} == 1 ]] && echo ✓ || echo ✗)" \
  "$([[ ${MIC_OK} == 1 ]] && echo ✓ || echo ✗)"
if ! ${EXPLICIT_NODES} && ! ${EMPTY_MODE}; then
  [[ "${MIC_OK}" != "1" ]] && echo "  · ASR пропущен (нет микрофона). Принудительно: ADAM_FORCE_ASR=1"
fi
echo

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
      # Kill stray llama-server that might hold port 8051 from a previous session.
      strays="$(pgrep -f 'llama-server' || true)"
      if [[ -n "${strays}" ]]; then
        echo "  · Убиваю stray llama-server: ${strays}"
        kill ${strays} 2>/dev/null || true
        sleep 1
      fi
      sudo systemctl start adam-llm >/dev/null 2>&1 || true
      sleep 3
    fi
    if systemctl is-active --quiet adam-llm 2>/dev/null; then
      echo "  ✓ adam-llm.service (llama-server :${LLM_PORT})"
      echo "    модель: $(basename "${ADAM_LLM_GGUF_PATH:-unknown}")"
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
      sleep 2
    fi

    for s in "${SERVICES_AVAILABLE[@]}"; do
      systemctl is-active --quiet "${s}" 2>/dev/null \
        && echo "  ✓ ${s}" \
        || echo "  ✗ ${s} (см. journalctl -u ${s} -n 30)"
    done
  fi
fi

# --------- resolve VLM & expected services before orchestrator ---------------
should_start_vlm=false
case "${START_VLM}" in
  true)  should_start_vlm=true ;;
  false) should_start_vlm=false ;;
  auto)
    if { [[ "${USB_CAM}" == "1" ]] || [[ "${ESP_CAM}" == "1" ]]; } \
       && command -v docker >/dev/null 2>&1 \
       && docker image inspect dustynv/nano_llm:r36.4.0 >/dev/null 2>&1; then
      should_start_vlm=true
    fi
    ;;
esac

# Comma-separated list of AI services the orchestrator should wait for before playing the startup sound.
# Empty string = --empty mode, no services expected, no sound.
EXPECTED_SERVICES=""
if ! ${EMPTY_MODE}; then
  ${START_LLM}        && EXPECTED_SERVICES+="llm,"
  ${START_TTS}        && EXPECTED_SERVICES+="tts,"
  ${START_ASR}        && EXPECTED_SERVICES+="asr,"
  ${should_start_vlm} && EXPECTED_SERVICES+="vlm,"
  EXPECTED_SERVICES="${EXPECTED_SERVICES%,}"
fi

# --------- 3. Orchestrator ---------------------------------------------------
existing_pids="$(pgrep -f 'System/Orchestrator\.py' || true)"
if [[ -n "${existing_pids}" ]]; then
  echo
  echo "⏵ Останавливаю предыдущий orchestrator: ${existing_pids}"
  kill ${existing_pids} 2>/dev/null || true
  sleep 1
  remaining="$(pgrep -f 'System/Orchestrator\.py' || true)"
  if [[ -n "${remaining}" ]]; then
    kill -9 ${remaining} 2>/dev/null || true
  fi
fi

echo
echo "⏵ Запуск orchestrator…"
cd "${ROOT_DIR}"
PYTHONPATH="${ROOT_DIR}/System" \
  ADAM_MODE="${MODE}" \
  ADAM_ORCHESTRATOR_PORT="${PORT}" \
  ADAM_MODELS_DIR="${MODELS_DIR}" \
  ADAM_EXPECTED_SERVICES="${EXPECTED_SERVICES}" \
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

if ! kill -0 "${ORCH_PID}" 2>/dev/null; then
  echo "✗ Orchestrator упал. Последние строки лога:" >&2
  tail -n 30 "${LOG_FILE}" >&2 || true
  exit 1
fi

# --------- 4. Live VLM (optional) --------------------------------------------
if ${should_start_vlm}; then
  echo
  echo "⏵ Запуск Live VLM (Docker, detached)…"
  if docker ps --format '{{.Names}}' | grep -qx "${LIVE_VLM_CONTAINER}"; then
    echo "  · ${LIVE_VLM_CONTAINER} уже работает"
  else
    if ! "${ROOT_DIR}/scripts/adam_live_vlm.sh" bg >/dev/null 2>&1; then
      echo "  ✗ Live VLM не стартовал — посмотри: ${ROOT_DIR}/scripts/adam_live_vlm.sh bg"
    else
      sleep 2
      if docker ps --format '{{.Names}}' | grep -qx "${LIVE_VLM_CONTAINER}"; then
        echo "  ✓ ${LIVE_VLM_CONTAINER} (логи: docker logs -f ${LIVE_VLM_CONTAINER})"
      else
        echo "  ✗ контейнер не появился — docker logs ${LIVE_VLM_CONTAINER}"
      fi
    fi
  fi
elif [[ "${START_VLM}" == "auto" ]] && [[ ! -e "${LIVE_VLM_CAMERA}" ]]; then
  echo
  echo "  · Live VLM пропущен (нет ${LIVE_VLM_CAMERA}). Запусти руками: scripts/adam_live_vlm.sh"
fi

# --------- summary -----------------------------------------------------------
IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^192\.168\./){print $i; exit}}')"
[[ -z "${IP}" ]] && IP="127.0.0.1"

vlm_url=""
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${LIVE_VLM_CONTAINER}"; then
  vlm_url="http://${IP}:8084/"
fi

cat <<EOF

▶ Готово.
  PID:       ${ORCH_PID}   (saved to ${PID_FILE})
  Log:       ${LOG_FILE}
  Local UI:  http://127.0.0.1:${PORT}/
  LAN UI:    http://${IP}:${PORT}/${vlm_url:+
  Live VLM:  ${vlm_url}}

Проверить:    curl -s http://127.0.0.1:${PORT}/api/agent/status | python3 -m json.tool
Логи:         tail -f ${LOG_FILE}
LLM логи:     journalctl -u adam-llm -f
VLM логи:     docker logs -f ${LIVE_VLM_CONTAINER}
Остановить:   ${ROOT_DIR}/scripts/adam_stop.sh
EOF
