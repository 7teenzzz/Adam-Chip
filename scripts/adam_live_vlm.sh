#!/usr/bin/env bash
# Adam Chip — VLM HTTP Service (VILA1.5-3b via nano_llm, MLC backend).
#
# Запускает Docker-контейнер dustynv/nano_llm с FastAPI HTTP-сервисом VLM.py.
# Сервис принимает кадры в OpenAI vision формате и возвращает описание сцены.
# Совместим с VLMClient оркестратора: http://127.0.0.1:8084/v1/chat/completions
#
# Использование:
#   scripts/adam_live_vlm.sh          # foreground (Ctrl-C для остановки)
#   scripts/adam_live_vlm.sh bg       # detached (фон)
#   scripts/adam_live_vlm.sh fg       # то же что без аргументов
#
# Stop: scripts/adam_stop.sh (выключит контейнер adam-live-vlm).
#
# ENV overrides:
#   ADAM_VLM_MODEL        Efficient-Large-Model/VILA1.5-3b
#   ADAM_VLM_HTTP_PORT    8084          (HTTP REST API порт)
#   ADAM_VLM_MAX_TOKENS   48
#   ADAM_VLM_IMAGE        dustynv/nano_llm:r36.4.0  (override image tag)
#   JETSON_CONTAINERS_DIR /home/i17jet/Agents/jetson-containers

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JC="${JETSON_CONTAINERS_DIR:-/home/i17jet/Agents/jetson-containers}"
CONTAINER_NAME="adam-live-vlm"

MODEL="${ADAM_VLM_MODEL:-Efficient-Large-Model/VILA1.5-3b}"
HTTP_PORT="${ADAM_VLM_HTTP_PORT:-8084}"
MAX_TOKENS="${ADAM_VLM_MAX_TOKENS:-48}"

VLM_PY="${ROOT_DIR}/System/Speech/VLM.py"

# --------- preflight ---------------------------------------------------------
if [[ ! -f "${VLM_PY}" ]]; then
  echo "ERROR: ${VLM_PY} не найден — убедись что файл существует" >&2
  exit 1
fi

if [[ ! -d "${JC}" ]]; then
  echo "ERROR: jetson-containers не найден в ${JC}" >&2
  echo "Установи: git clone https://github.com/dusty-nv/jetson-containers ${JC} && bash ${JC}/install.sh" >&2
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

# Resolve container tag via autotag (needs requests module — use venv python if available).
TAG="${ADAM_VLM_IMAGE:-}"
if [[ -z "${TAG}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    TAG="$(PATH="${ROOT_DIR}/.venv/bin:${PATH}" "${JC}/autotag" nano_llm 2>/dev/null | tail -1)" || TAG=""
  fi
  # Fallback: use known image if already pulled.
  if [[ -z "${TAG}" ]] && docker image inspect dustynv/nano_llm:r36.4.0 >/dev/null 2>&1; then
    TAG="dustynv/nano_llm:r36.4.0"
  fi
fi
if [[ -z "${TAG}" ]]; then
  echo "ERROR: не удалось определить container tag для nano_llm." >&2
  echo "Попробуй: ADAM_VLM_IMAGE=dustynv/nano_llm:r36.4.0 ${BASH_SOURCE[0]}" >&2
  exit 1
fi

MODE="${1:-fg}"

cat <<EOF
▶ VLM HTTP Service (Adam Chip)
  container:  ${CONTAINER_NAME}   (${MODE})
  image:      ${TAG}
  model:      ${MODEL}
  api:        http://${IP}:${HTTP_PORT}/v1/chat/completions
  health:     http://${IP}:${HTTP_PORT}/health
  max_tokens: ${MAX_TOKENS}

  Загрузка модели занимает ~60-120 сек — ожидай {"ok": true} на /health.

EOF

# --------- docker args -------------------------------------------------------
COMMON_ARGS=(
  --runtime nvidia
  --env NVIDIA_DRIVER_CAPABILITIES=compute,utility
  --network host
  --shm-size=8g
  --name "${CONTAINER_NAME}"
  --rm
  -e ADAM_VLM_HOST=0.0.0.0
  -e ADAM_VLM_PORT="${HTTP_PORT}"
  -e ADAM_VLM_MODEL="${MODEL}"
  -e ADAM_VLM_MAX_TOKENS="${MAX_TOKENS}"
  -e HF_HOME=/data/models/huggingface
  -p "${HTTP_PORT}:${HTTP_PORT}"
  -v "${VLM_PY}:/app/VLM.py:ro"
  -v "${JC}/data:/data"
  -v /etc/localtime:/etc/localtime:ro
)
[[ -e /etc/nv_tegra_release ]] && COMMON_ARGS+=(-v /etc/nv_tegra_release:/etc/nv_tegra_release)
[[ -e /run/jtop.sock ]]        && COMMON_ARGS+=(-v /run/jtop.sock:/run/jtop.sock)

CMD_ARGS=(
  python3 /app/VLM.py
)

case "${MODE}" in
  bg|detached|d)
    docker run -d "${COMMON_ARGS[@]}" "${TAG}" "${CMD_ARGS[@]}"
    echo
    echo "▶ Detached. Логи: docker logs -f ${CONTAINER_NAME}"
    echo "  Стоп:        docker stop ${CONTAINER_NAME}   (или scripts/adam_stop.sh)"
    echo "  Health:      curl -s http://127.0.0.1:${HTTP_PORT}/health | python3 -m json.tool"
    ;;
  fg|foreground|*)
    # No -it: works both in terminal and under systemd.
    exec docker run "${COMMON_ARGS[@]}" "${TAG}" "${CMD_ARGS[@]}"
    ;;
esac
