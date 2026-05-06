#!/usr/bin/env bash
# Adam Chip — Live VLM (real-time video captioning) via nano_llm + VILA.
#
# Запускает Docker-контейнер dustynv/nano_llm с агентом video_query.
# Stream WebRTC overlay с captions виден на https://<JETSON_IP>:8050.
#
# Stop: scripts/adam_stop.sh (выключит контейнер adam-live-vlm).
#
# ENV overrides:
#   ADAM_VLM_CAMERA       /dev/video0
#   ADAM_VLM_MODEL        Efficient-Large-Model/VILA1.5-3b
#   ADAM_VLM_PROMPT       "Опиши коротко что ты видишь."
#   ADAM_VLM_WEBRTC_PORT  8050     (browser viewer)
#   ADAM_VLM_STREAM_PORT  8554     (WebRTC media)
#   ADAM_VLM_MAX_TOKENS   32
#   ADAM_VLM_MAX_CTX      256

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JC="${JETSON_CONTAINERS_DIR:-/home/i17jet/Agents/jetson-containers}"
CONTAINER_NAME="adam-live-vlm"

CAMERA="${ADAM_VLM_CAMERA:-/dev/video0}"
MODEL="${ADAM_VLM_MODEL:-Efficient-Large-Model/VILA1.5-3b}"
PROMPT="${ADAM_VLM_PROMPT:-Опиши коротко что ты видишь.}"
WEBRTC_PORT="${ADAM_VLM_WEBRTC_PORT:-8050}"
STREAM_PORT="${ADAM_VLM_STREAM_PORT:-8554}"
MAX_TOKENS="${ADAM_VLM_MAX_TOKENS:-32}"
MAX_CTX="${ADAM_VLM_MAX_CTX:-256}"

# --------- preflight ---------------------------------------------------------
if [[ ! -d "${JC}" ]]; then
  echo "ERROR: jetson-containers не найден в ${JC}" >&2
  echo "Установи: git clone https://github.com/dusty-nv/jetson-containers ${JC} && bash ${JC}/install.sh" >&2
  exit 1
fi

if [[ ! -e "${CAMERA}" ]]; then
  echo "ERROR: ${CAMERA} не существует. Подключи USB веб-камеру и проверь:" >&2
  echo "  ls /dev/video*"  >&2
  echo "  v4l2-ctl --list-devices  (sudo apt install v4l-utils)" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker не установлен" >&2
  exit 1
fi

# Stop any previous instance with the same name.
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "${CONTAINER_NAME}"; then
  echo "⏵ Останавливаю предыдущий контейнер ${CONTAINER_NAME}…"
  docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker rm   "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^192\.168\./){print $i; exit}}')"
[[ -z "${IP}" ]] && IP="127.0.0.1"

# Resolve container tag via autotag. autotag needs `requests` python module —
# venv has it but system python may not, so prepend venv to PATH.
TAG="${ADAM_VLM_IMAGE:-}"
if [[ -z "${TAG}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    TAG="$(PATH="${ROOT_DIR}/.venv/bin:${PATH}" "${JC}/autotag" nano_llm 2>/dev/null | tail -1)"
  fi
  # Fallback: use a known image if autotag failed and the image is already pulled.
  if [[ -z "${TAG}" ]] && docker image inspect dustynv/nano_llm:r36.4.0 >/dev/null 2>&1; then
    TAG="dustynv/nano_llm:r36.4.0"
  fi
fi
if [[ -z "${TAG}" ]]; then
  echo "ERROR: не удалось определить container tag для nano_llm." >&2
  echo "Попробуй: ADAM_VLM_IMAGE=dustynv/nano_llm:r36.4.0 ${BASH_SOURCE[0]}" >&2
  exit 1
fi

# Mode: "fg" runs interactive (so -it works); "bg" runs detached for adam_start.sh.
MODE="${1:-fg}"

cat <<EOF
▶ Live VLM (Adam Chip)
  container:  ${CONTAINER_NAME}   (${MODE})
  image:      ${TAG}
  camera:     ${CAMERA}
  model:      ${MODEL}
  prompt:     ${PROMPT}
  ports:      ${WEBRTC_PORT} (viewer)  /  ${STREAM_PORT} (WebRTC media)
  Откроется:  https://${IP}:${WEBRTC_PORT}

EOF

# --------- docker args (mirrors jetson-containers/run.sh defaults) -----------
# We bypass run.sh because it hardcodes -it; we need -d for adam_start.sh.
COMMON_ARGS=(
  --runtime nvidia
  --env NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
  --network host
  --shm-size=8g
  --name "${CONTAINER_NAME}"
  --rm
  -e DISPLAY="${DISPLAY:-:0}"
  -v /tmp/.X11-unix:/tmp/.X11-unix
  --device "${CAMERA}"
  -p "${WEBRTC_PORT}:${WEBRTC_PORT}"
  -p "${STREAM_PORT}:${STREAM_PORT}"
  -v "${ROOT_DIR}/data/adam:/data/adam"
  -v "${JC}/data:/data"
  -v /etc/localtime:/etc/localtime:ro
)
[[ -e /tmp/argus_socket ]]                       && COMMON_ARGS+=(-v /tmp/argus_socket:/tmp/argus_socket)
[[ -e /etc/nv_tegra_release ]]                   && COMMON_ARGS+=(-v /etc/nv_tegra_release:/etc/nv_tegra_release)
[[ -e /run/jtop.sock ]]                          && COMMON_ARGS+=(-v /run/jtop.sock:/run/jtop.sock)
[[ -e /var/run/dbus ]]                           && COMMON_ARGS+=(-v /var/run/dbus:/var/run/dbus)

CMD_ARGS=(
  python3 -m nano_llm.agents.video_query --api=mlc
    --model "${MODEL}"
    --max-context-len "${MAX_CTX}"
    --max-new-tokens "${MAX_TOKENS}"
    --video-input "${CAMERA}"
    --video-output "webrtc://@:${STREAM_PORT}/output"
    --prompt "${PROMPT}"
)

case "${MODE}" in
  bg|detached|d)
    docker run -d "${COMMON_ARGS[@]}" "${TAG}" "${CMD_ARGS[@]}"
    echo
    echo "▶ Detached. Логи: docker logs -f ${CONTAINER_NAME}"
    echo "  Стоп:        docker stop ${CONTAINER_NAME}   (или scripts/adam_stop.sh)"
    ;;
  fg|foreground|*)
    exec docker run -it "${COMMON_ARGS[@]}" "${TAG}" "${CMD_ARGS[@]}"
    ;;
esac
