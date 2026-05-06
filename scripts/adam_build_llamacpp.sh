#!/usr/bin/env bash
# Build llama.cpp with CUDA for Jetson Orin (SM 87, Ampere GA10B).
# Output: Subsystem/llama.cpp/build/bin/llama-server
#         Subsystem/llama.cpp/build/bin/llama-cli
#
# Re-runnable: skips git clone if already present, does a full cmake rebuild.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLAMA_DIR="${ROOT_DIR}/Subsystem/llama.cpp"
BUILD_DIR="${LLAMA_DIR}/build"
JOBS="${JOBS:-$(nproc)}"

# Jetson Orin NX/AGX = Ampere SM 87.
# Override via env: CUDA_ARCH=89 for Orin NX 16 GB (if mis-detected).
CUDA_ARCH="${CUDA_ARCH:-87}"

echo "▶ llama.cpp build"
echo "  source: ${LLAMA_DIR}"
echo "  build:  ${BUILD_DIR}"
echo "  CUDA arch: sm_${CUDA_ARCH}"
echo "  jobs:  ${JOBS}"
echo

# --------- 1. Clone if absent -------------------------------------------
if [[ ! -d "${LLAMA_DIR}/.git" ]]; then
  echo "⏵ Клонирование llama.cpp (depth=1)…"
  mkdir -p "${ROOT_DIR}/Subsystem"
  git clone --depth=1 https://github.com/ggerganov/llama.cpp "${LLAMA_DIR}"
  echo "  ✓ клонировано"
else
  echo "  · исходники уже есть: ${LLAMA_DIR}"
  echo "  · для обновления вручную: cd ${LLAMA_DIR} && git pull"
fi
echo

# --------- 2. Verify CUDA -----------------------------------------------
if ! command -v nvcc >/dev/null 2>&1; then
  echo "ERROR: nvcc не найден. Установи CUDA Toolkit (JetPack):" >&2
  echo "  sudo apt install cuda-toolkit-12-6   # или нужную версию" >&2
  exit 1
fi
CUDA_VERSION="$(nvcc --version | grep -oP 'release \K[0-9]+\.[0-9]+')"
echo "  ✓ nvcc ${CUDA_VERSION}"

# --------- 3. cmake configure -------------------------------------------
echo "⏵ cmake configure…"
cmake -B "${BUILD_DIR}" "${LLAMA_DIR}" \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF \
  2>&1 | tail -5
echo

# --------- 4. cmake build -----------------------------------------------
echo "⏵ cmake build (${JOBS} ядер) — может занять 10–20 мин…"
cmake --build "${BUILD_DIR}" --config Release -j"${JOBS}" \
  --target llama-server llama-cli
echo

# --------- 5. Verify ----------------------------------------------------
SERVER_BIN="${BUILD_DIR}/bin/llama-server"
CLI_BIN="${BUILD_DIR}/bin/llama-cli"

if [[ ! -x "${SERVER_BIN}" ]]; then
  echo "ERROR: ${SERVER_BIN} не найден после сборки." >&2
  exit 1
fi

echo "▶ Готово."
echo "  llama-server: ${SERVER_BIN}"
echo "  llama-cli:    ${CLI_BIN}"
echo
echo "Следующий шаг — скачать модель:"
echo "  ${ROOT_DIR}/scripts/adam_download_model.sh unsloth/gemma-4-E4B-it-GGUF '*UD-Q4_K_XL*'"
echo "  или Gemma 3n: ./scripts/adam_download_model.sh unsloth/gemma-3n-E4B-it-GGUF '*UD-Q4_K_XL*'"
