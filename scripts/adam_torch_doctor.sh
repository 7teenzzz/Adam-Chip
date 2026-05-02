#!/usr/bin/env bash
set -euo pipefail

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

echo "Jetson:"
if [[ -r /etc/nv_tegra_release ]]; then
  sed -n '1,2p' /etc/nv_tegra_release
else
  echo "  /etc/nv_tegra_release not found"
fi
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query --show nvidia-l4t-core 2>/dev/null || true
fi
echo

check "venv python exists: ${PYTHON_BIN}" test -x "${PYTHON_BIN}"

if [[ -x "${PYTHON_BIN}" ]]; then
  check "python version is 3.10.x" "${PYTHON_BIN}" - <<'PY'
import sys
print(sys.version.split()[0])
raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)
PY

  check "torch import" "${PYTHON_BIN}" - <<'PY'
import torch
print(torch.__version__)
PY

  check "torch cuda available" "${PYTHON_BIN}" - <<'PY'
import torch
print(f"cuda_available={torch.cuda.is_available()} cuda={getattr(torch.version, 'cuda', None)}")
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY

  check "silero import" "${PYTHON_BIN}" - <<'PY'
import silero
print(getattr(silero, "__version__", "unknown"))
PY
fi

if [[ "${FAILED}" -ne 0 ]]; then
  cat <<EOF

Torch/Silero runtime is not ready.

Use the NVIDIA Jetson-compatible PyTorch instructions for the active JetPack
image. For this Jetson line, target JetPack 6.2 compatibility unless your
installed JetPack differs.

Install policy:
  1. Install NVIDIA's Jetson PyTorch wheel or an explicitly selected local
     Jetson-compatible wheel into:
       ${VENV}
  2. Do not let pip resolve and install generic torch from PyPI.
  3. After torch imports and CUDA is available, install Silero without deps:
       ${PYTHON_BIN} -m pip install --no-deps "silero>=0.5.0"

Docs:
  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html
  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform-release-notes/pytorch-jetson-rel.html
EOF
  exit 1
fi

echo "Torch/Silero doctor passed."
