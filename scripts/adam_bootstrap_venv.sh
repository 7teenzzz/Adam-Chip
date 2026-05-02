#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ADAM_VENV:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${ADAM_PYTHON:-python3}"

safe_remove_venv() {
  case "${VENV}" in
    "${ROOT_DIR}/.venv"|"${ROOT_DIR}"/.venv) rm -rf "${VENV}" ;;
    *) echo "ERROR: refusing to remove non-standard venv path: ${VENV}" >&2; exit 1 ;;
  esac
}

create_venv() {
  if "${PYTHON_BIN}" -m venv "${VENV}"; then
    return 0
  fi

  echo "python3 venv failed; trying virtualenv fallback." >&2
  if "${PYTHON_BIN}" -m virtualenv --version >/dev/null 2>&1; then
    safe_remove_venv
    "${PYTHON_BIN}" -m virtualenv -p "${PYTHON_BIN}" "${VENV}"
    return 0
  fi

  echo "ERROR: failed to create ${VENV}. Install python3-venv or virtualenv for the active Python." >&2
  exit 1
}

PY_VERSION="$("${PYTHON_BIN}" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
if sys.version_info[:2] != (3, 10):
    raise SystemExit(1)
PY
)" || {
  echo "ERROR: Adam Chip runtime expects Python 3.10.x. Current ${PYTHON_BIN}: ${PY_VERSION:-unknown}" >&2
  exit 1
}

if [[ ! -x "${VENV}/bin/python" ]] || ! "${VENV}/bin/python" -m pip --version >/dev/null 2>&1; then
  safe_remove_venv
  create_venv
fi

"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/python" -m pip install -r "${ROOT_DIR}/System/requirements.txt"

cat <<EOF
Adam Chip venv is ready.

Venv:
  ${VENV}

Python:
  ${PY_VERSION}

Next:
  Install NVIDIA Jetson-compatible PyTorch for the active JetPack image.
  Then install Silero without allowing pip to replace torch:

    ${VENV}/bin/python -m pip install --no-deps "silero>=0.5.0"
    ${ROOT_DIR}/scripts/adam_torch_doctor.sh

Docs:
  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html
  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform-release-notes/pytorch-jetson-rel.html
EOF
