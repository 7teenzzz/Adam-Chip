#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="/etc/adam-chip"
ENV_FILE="${ENV_DIR}/adam.env"
VENV="${ROOT_DIR}/.venv"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E "$0" "$@"
fi

install -d -m 0755 "${ENV_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  cat >"${ENV_FILE}" <<EOF
ADAM_MODE=maintenance
ADAM_VENV=${VENV}
ADAM_CONFIG=${ROOT_DIR}/System/Config.json
ADAM_DATA_DIR=${ROOT_DIR}/data/adam
ADAM_ORCHESTRATOR_HOST=0.0.0.0
ADAM_ORCHESTRATOR_PORT=8080
ESP_BASE_URL=http://10.10.10.171
ADAM_LLM_PROVIDER=openai
ADAM_LLM_BASE_URL=http://127.0.0.1:8081/v1
ADAM_LLM_MODEL=gemma-4-E4B-it-UD-Q4_K_XL
ADAM_LLM_LLAMACPP_DIR=${ROOT_DIR}/Subsystem/llama.cpp
ADAM_LLM_GGUF_PATH=${ROOT_DIR}/Subsystem/Models/gguf/gemma-4-E4B-it-UD-Q4_K_XL.gguf
ADAM_LLM_PORT=8081
ADAM_LLM_GPU_LAYERS=99
ADAM_LLM_CTX=8192
ADAM_TTS_BASE_URL=http://127.0.0.1:8082
ADAM_TTS_PORT=8082
ADAM_TTS_OUTPUT_DEVICE=plughw:1,3
ADAM_ASR_HOST=127.0.0.1
ADAM_ASR_PORT=8095
ADAM_ASR_WHISPERX_BASE_URL=http://127.0.0.1:8095
ADAM_ASR_WHISPERX_MODEL=medium
ADAM_ASR_LANGUAGE=ru
ADAM_ASR_DEVICE=cuda
ADAM_VLM_BASE_URL=http://127.0.0.1:8051
ADAM_VLM_MODEL=Cosmos-Reason2-2B-Q8_0
ADAM_VLM_LLAMACPP_DIR=${ROOT_DIR}/Subsystem/llama.cpp
ADAM_VLM_GGUF_PATH=${ROOT_DIR}/Subsystem/Models/gguf/Cosmos-Reason2-2B-Q8_0.gguf
ADAM_VLM_MMPROJ_PATH=${ROOT_DIR}/Subsystem/Models/gguf/mmproj-Cosmos-Reason2-2B-F16.gguf
ADAM_VLM_PORT=8051
ADAM_VLM_CTX=4096
ADAM_VLM_GPU_LAYERS=99
ADAM_VIDEO_DEVICE=/dev/video0
ADAM_AUDIO_INPUT_DEVICE=pulse
ADAM_AUDIO_OUTPUT_DEVICE=default
EOF
fi

if ! grep -q "^ADAM_CONFIG=" "${ENV_FILE}"; then
  echo "ERROR: ${ENV_FILE} exists but does not look like an Adam Chip environment file." >&2
  exit 1
fi

ensure_env_line() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${ENV_FILE}"
  fi
}

ensure_env_line "ADAM_VENV" "${VENV}"
ensure_env_line "ADAM_LLM_BASE_URL" "http://127.0.0.1:8081/v1"
ensure_env_line "ADAM_LLM_PORT" "8081"
ensure_env_line "ADAM_LLM_GPU_LAYERS" "99"
ensure_env_line "ADAM_LLM_CTX" "8192"
ensure_env_line "ADAM_LLM_LLAMACPP_DIR" "${ROOT_DIR}/Subsystem/llama.cpp"
ensure_env_line "ADAM_LLM_GGUF_PATH" "${ROOT_DIR}/Subsystem/Models/gguf/gemma-4-E4B-it-UD-Q4_K_XL.gguf"
ensure_env_line "ADAM_TTS_BASE_URL" "http://127.0.0.1:8082"
ensure_env_line "ADAM_TTS_PORT" "8082"
ensure_env_line "ADAM_TTS_OUTPUT_DEVICE" "plughw:1,3"
ensure_env_line "ADAM_ASR_HOST" "127.0.0.1"
ensure_env_line "ADAM_ASR_PORT" "8095"
ensure_env_line "ADAM_ASR_WHISPERX_BASE_URL" "http://127.0.0.1:8095"
ensure_env_line "ADAM_ASR_WHISPERX_MODEL" "small"
ensure_env_line "ADAM_ASR_LANGUAGE" "ru"
ensure_env_line "ADAM_ASR_DEVICE" "cuda"
ensure_env_line "ADAM_VLM_BASE_URL" "http://127.0.0.1:8051"
ensure_env_line "ADAM_VLM_MODEL" "Cosmos-Reason2-2B-Q8_0"
ensure_env_line "ADAM_VLM_LLAMACPP_DIR" "${ROOT_DIR}/Subsystem/llama.cpp"
ensure_env_line "ADAM_VLM_GGUF_PATH" "${ROOT_DIR}/Subsystem/Models/gguf/Cosmos-Reason2-2B-Q8_0.gguf"
ensure_env_line "ADAM_VLM_MMPROJ_PATH" "${ROOT_DIR}/Subsystem/Models/gguf/mmproj-Cosmos-Reason2-2B-F16.gguf"
ensure_env_line "ADAM_VLM_PORT" "8051"
ensure_env_line "ADAM_VLM_CTX" "4096"
ensure_env_line "ADAM_VLM_GPU_LAYERS" "99"
ensure_env_line "ADAM_AUDIO_INPUT_DEVICE" "pulse"
ensure_env_line "ADAM_AUDIO_OUTPUT_DEVICE" "default"

# Prune deprecated ASR env keys: ADAM_ASR_WHISPER_* (singular, no X) were superseded
# by ADAM_ASR_WHISPERX_*. The stale ADAM_ASR_WHISPER_BASE_URL even pointed at :8083
# (the logviewer port). The regex matches WHISPER_ but NOT WHISPERX_ (X follows WHISPER).
sed -i '/^ADAM_ASR_WHISPER_/d' "${ENV_FILE}"

install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-orchestrator.service" /etc/systemd/system/adam-orchestrator.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-tts-silero.service" /etc/systemd/system/adam-tts-silero.service
# NOTE: adam-asr-whisperx.service (native) is NOT installed — ASR runs via Docker.
# The native unit uses pip ctranslate2 (CPU-only on aarch64) and blocks port 8095,
# preventing the Docker container (dustynv/faster-whisper, CUDA ctranslate2) from binding.
# Canonical start: docker compose up -d adam-asr-whisperx
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-llm.service" /etc/systemd/system/adam-llm.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-vlm.service" /etc/systemd/system/adam-vlm.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-logviewer.service" /etc/systemd/system/adam-logviewer.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-exhibition.target" /etc/systemd/system/adam-exhibition.target

ensure_env_line "ADAM_LOG_VIEWER_PORT" "8083"

systemctl daemon-reload
# adam-vlm НЕ авто-стартует по умолчанию (Phase 30 durability caution). С Phase 33
# (Cosmos-Reason2-2B via llama.cpp, :8051) бюджет много меньше старого VILA Docker
# (~5.6 GB) — Cosmos Q8_0 + mmproj F16 ~3 GB, должен сосуществовать с Gemma 4 E4B
# (:8081, ~8 GB) на 16 GB Jetson. Включить вручную после проверки:
# sudo systemctl enable --now adam-vlm.service
systemctl enable adam-orchestrator.service adam-tts-silero.service adam-llm.service adam-logviewer.service adam-exhibition.target
systemctl disable adam-vlm.service 2>/dev/null || true

# Native adam-asr-whisperx.service is DEPRECATED — it uses pip ctranslate2 which is
# CPU-only on aarch64, so it transcribes on CPU (~9.8s/utterance) AND squats on port
# 8095, blocking the canonical Docker container (dustynv faster-whisper, CUDA ctranslate2)
# from binding → "address already in use" → ASR silently falls back to CPU.
# We STOP it, REMOVE the orphan unit file (this installer never (re)installs it — there is
# no `install` line for it above), daemon-reload, then MASK so any `systemctl start
# adam-asr-whisperx.service` (NOPASSWD wildcard lets any script call it) hard-fails.
# `mask` can only overlay a unit with no real file in /etc/systemd/system — hence the rm
# first. After this, Docker is the single ASR owner of 8095, always on CUDA.
# To revert on a non-Docker host: sudo systemctl unmask adam-asr-whisperx.service &&
#   sudo install -m0644 deploy/systemd/adam-asr-whisperx.service /etc/systemd/system/
systemctl stop adam-asr-whisperx.service 2>/dev/null || true
rm -f /etc/systemd/system/adam-asr-whisperx.service
systemctl daemon-reload
systemctl mask adam-asr-whisperx.service 2>/dev/null || true

echo "Installed Adam Chip systemd units."
echo "Edit ${ENV_FILE} for device/service overrides."

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "WARNING: ${VENV}/bin/python is missing. Run: ${ROOT_DIR}/scripts/adam_bootstrap_venv.sh" >&2
else
  if ! "${VENV}/bin/python" -c "import torch, silero" >/dev/null 2>&1; then
    echo "WARNING: torch/silero are not ready in ${VENV}. Run: ${ROOT_DIR}/scripts/adam_torch_doctor.sh" >&2
  fi
fi

cat <<EOF

Next commands:
  ${ROOT_DIR}/scripts/adam_bootstrap_venv.sh
  ${ROOT_DIR}/scripts/adam_torch_doctor.sh

  # Build llama.cpp (first time, ~15 min):
  ${ROOT_DIR}/scripts/adam_build_llamacpp.sh

  # Download primary model (~6 GB):
  ${ROOT_DIR}/scripts/adam_download_model.sh unsloth/gemma-4-E4B-it-GGUF '*UD-Q4_K_XL*'

  # Start services:
  sudo systemctl start adam-llm.service
  docker compose up -d adam-asr-whisperx   # ASR via Docker (CUDA ctranslate2)
  sudo systemctl start adam-tts-silero.service
  sudo systemctl start adam-orchestrator.service
  ${ROOT_DIR}/scripts/adam_service_status.sh
  ${ROOT_DIR}/scripts/adam_set_mode.sh exhibition

Full target:
  sudo systemctl start adam-exhibition.target

Logs:
  ${ROOT_DIR}/scripts/adam_service_logs.sh adam-llm.service
  ${ROOT_DIR}/scripts/adam_service_logs.sh adam-orchestrator.service
  ${ROOT_DIR}/scripts/adam_service_logs.sh adam-tts-silero.service
  docker logs adam-asr-whisperx

Switch model without restart:
  sudo systemctl edit adam-llm
  # Add: Environment=ADAM_LLM_GGUF_PATH=/path/to/other-model.gguf
  sudo systemctl restart adam-llm
EOF
