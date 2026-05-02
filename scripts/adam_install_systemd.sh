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
ESP_BASE_URL=http://192.168.0.171
ADAM_LLM_PROVIDER=ollama
ADAM_LLM_BASE_URL=http://127.0.0.1:11434
ADAM_LLM_MODEL=gemma3:4b
ADAM_TTS_BASE_URL=http://127.0.0.1:8090
ADAM_ASR_HOST=127.0.0.1
ADAM_ASR_PORT=50051
ADAM_VLM_BASE_URL=http://127.0.0.1:8050
ADAM_VLM_MODEL=Efficient-Large-Model/VILA1.5-3b
ADAM_TTS_PORT=8090
ADAM_TTS_OUTPUT_DEVICE=default
ADAM_VIDEO_DEVICE=/dev/video0
ADAM_AUDIO_INPUT_DEVICE=hw:0,0
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
  if ! grep -q "^${key}=" "${ENV_FILE}"; then
    printf '%s=%s\n' "${key}" "${value}" >>"${ENV_FILE}"
  fi
}

ensure_env_line "ADAM_VENV" "${VENV}"
ensure_env_line "ADAM_ASR_HOST" "127.0.0.1"
ensure_env_line "ADAM_ASR_PORT" "50051"
ensure_env_line "ADAM_VLM_BASE_URL" "http://127.0.0.1:8050"
ensure_env_line "ADAM_VLM_MODEL" "Efficient-Large-Model/VILA1.5-3b"

install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-orchestrator.service" /etc/systemd/system/adam-orchestrator.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-tts-silero.service" /etc/systemd/system/adam-tts-silero.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/adam-exhibition.target" /etc/systemd/system/adam-exhibition.target

systemctl daemon-reload
systemctl enable adam-orchestrator.service adam-tts-silero.service adam-exhibition.target

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
  sudo systemctl start adam-tts-silero.service
  sudo systemctl start adam-orchestrator.service
  ${ROOT_DIR}/scripts/adam_service_status.sh
  ${ROOT_DIR}/scripts/adam_set_mode.sh exhibition

Full target:
  sudo systemctl start adam-exhibition.target

Logs:
  ${ROOT_DIR}/scripts/adam_service_logs.sh adam-orchestrator.service
  ${ROOT_DIR}/scripts/adam_service_logs.sh adam-tts-silero.service
EOF
