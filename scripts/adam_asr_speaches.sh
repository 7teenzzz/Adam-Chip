#!/usr/bin/env bash
# Adam Chip — ASR Service (speaches: faster-whisper + CUDA via Docker).
#
# speaches — OpenAI-compatible speech API.
# ASR: POST http://127.0.0.1:8083/v1/audio/transcriptions
#       -F file=@audio.wav -F model=Systran/faster-whisper-medium -F language=ru
#
# Использование:
#   scripts/adam_asr_speaches.sh          # foreground
#   scripts/adam_asr_speaches.sh bg       # detached (фон)
#   scripts/adam_asr_speaches.sh stop     # остановить контейнер
#
# ENV overrides:
#   ADAM_ASR_IMAGE    dustynv/speaches:r36.4.0-cu128-24.04
#   ADAM_ASR_MODEL    Systran/faster-whisper-medium
#   ADAM_ASR_PORT     8083

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="adam-asr-speaches"
IMAGE="${ADAM_ASR_IMAGE:-dustynv/speaches:r36.4.0-cu128-24.04}"
MODEL="${ADAM_ASR_MODEL:-Systran/faster-whisper-small}"
PORT="${ADAM_ASR_PORT:-8083}"
HF_CACHE="${ROOT_DIR}/Subsystem/Models/hf"

# --------- stop --------------------------------------------------------------
if [[ "${1:-}" == "stop" ]]; then
  docker stop "${CONTAINER_NAME}" 2>/dev/null || true
  docker rm   "${CONTAINER_NAME}" 2>/dev/null || true
  echo "▶ ${CONTAINER_NAME} остановлен."
  exit 0
fi

# --------- preflight ---------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker не установлен" >&2
  exit 1
fi

# Stop any previous instance.
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "${CONTAINER_NAME}"; then
  echo "⏵ Останавливаю предыдущий контейнер ${CONTAINER_NAME}…"
  docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  docker rm   "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

# Pull if not present.
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "▶ Загружаю образ ${IMAGE} (~6 GB, первый раз)…"
  docker pull "${IMAGE}"
fi

IP="$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^192\.168\./){print $i; exit}}')"
[[ -z "${IP}" ]] && IP="127.0.0.1"

MODE="${1:-fg}"

cat <<EOF
▶ ASR speaches (Adam Chip)
  container:  ${CONTAINER_NAME}   (${MODE})
  image:      ${IMAGE}
  model:      ${MODEL}
  api:        http://${IP}:${PORT}/v1/audio/transcriptions
  models:     http://${IP}:${PORT}/v1/models

  Первый старт: модель загружается из кэша (~5-10 сек).
  Запрос: curl -s http://127.0.0.1:${PORT}/v1/models | python3 -m json.tool

EOF

COMMON_ARGS=(
  --runtime nvidia
  --env NVIDIA_DRIVER_CAPABILITIES=compute,utility
  --network host
  --name "${CONTAINER_NAME}"
  --workdir /opt/speaches
  --rm
  -e PORT="${PORT}"
  -e WHISPER__INFERENCE_DEVICE=cuda
  -e WHISPER__COMPUTE_TYPE=float16
  -e WHISPER__TTL=-1
  -e WHISPER__VAD_FILTER=false
  -e HF_HUB_OFFLINE=1
  -e TRANSFORMERS_OFFLINE=1
  -e HF_HOME=/hf_cache
  -e HF_HUB_CACHE=/hf_cache/hub
  -v "${HF_CACHE}:/hf_cache"
  -v /etc/localtime:/etc/localtime:ro
)
[[ -e /etc/nv_tegra_release ]] && COMMON_ARGS+=(-v /etc/nv_tegra_release:/etc/nv_tegra_release)

case "${MODE}" in
  bg|detached|d)
    docker run -d "${COMMON_ARGS[@]}" "${IMAGE}"
    echo "▶ Detached. Логи: docker logs -f ${CONTAINER_NAME}"
    echo "  Стоп:         docker stop ${CONTAINER_NAME}"
    echo "  Health:       curl -s http://127.0.0.1:${PORT}/v1/models"
    ;;
  fg|foreground|*)
    exec docker run "${COMMON_ARGS[@]}" "${IMAGE}"
    ;;
esac
