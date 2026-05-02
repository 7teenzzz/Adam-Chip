#!/usr/bin/env bash
set -euo pipefail

TTS_URL="${ADAM_TTS_URL:-http://127.0.0.1:8090}"
OUTPUT_DEVICE="${ADAM_TTS_OUTPUT_DEVICE:-${ADAM_AUDIO_OUTPUT_DEVICE:-default}}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ADAM_VENV:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${ADAM_PYTHON_BIN:-${VENV}/bin/python}"
FAILED=0

check() {
  local name="$1"
  shift
  if "$@"; then
    printf '[ok] %s\n' "${name}"
  else
    printf '[fail] %s\n' "${name}"
    FAILED=1
  fi
}

check "venv python exists: ${PYTHON_BIN}" test -x "${PYTHON_BIN}"
if [[ -x "${PYTHON_BIN}" ]]; then
  check "python imports: torch" "${PYTHON_BIN}" -c "import torch; print(getattr(torch, '__version__', 'unknown'))"
  check "python imports: silero" "${PYTHON_BIN}" -c "import silero; print(getattr(silero, '__version__', 'unknown'))"
fi
check "aplay is installed" command -v aplay
check "audio output device ${OUTPUT_DEVICE}" bash -c "aplay -L | grep -q -F '${OUTPUT_DEVICE}' || [[ '${OUTPUT_DEVICE}' == default ]]"
check "tts health ${TTS_URL}/health" curl -fsS "${TTS_URL}/health"

if [[ "${FAILED}" -ne 0 ]]; then
  cat <<'EOF'

TTS is not ready.

Install PyTorch into the Adam Chip venv using the NVIDIA Jetson-specific PyTorch
instructions for the active JetPack image, then install Silero without deps:

  ./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"

  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html

Do not install a generic PyPI torch wheel on Jetson unless you intentionally
accept CPU-only or incompatible behavior.
EOF
  exit 1
fi

echo "TTS doctor passed."
