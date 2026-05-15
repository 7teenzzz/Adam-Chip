#!/usr/bin/env bash
# Adam Chip — llama-server launcher that reads model+flags from System/Config.json.
#
# This script is the single source of truth for which LLM model adam-llm.service
# loads. Config.json `services.llm` controls:
#   - model_path        — GGUF file (absolute, or relative to repo root)
#   - num_ctx           — context size (--ctx-size)
#   - speculative.type  — optional, sets --spec-type
#   - speculative.ngram_mod_n_match / n_min / n_max — optional ngram-mod params
#
# Environment variables remain as low-priority fallbacks (used only when
# Config.json doesn't define the field). The /etc/adam-chip/adam.env override
# layer is still honored for non-model settings (port, GPU layers).
#
# Edit Config.json → systemctl restart adam-llm.service → new model loads.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${ADAM_CONFIG:-${ROOT_DIR}/System/Config.json}"
LLAMACPP_DIR="${ADAM_LLM_LLAMACPP_DIR:-${ROOT_DIR}/Subsystem/llama.cpp}"
LLAMA_BIN="${LLAMACPP_DIR}/build/bin/llama-server"
PORT="${ADAM_LLM_PORT:-8081}"
GPU_LAYERS="${ADAM_LLM_GPU_LAYERS:-99}"

if [[ ! -f "${CONFIG}" ]]; then
  echo "ERROR: Config.json not found at ${CONFIG}" >&2
  exit 2
fi
if [[ ! -x "${LLAMA_BIN}" ]]; then
  echo "ERROR: llama-server binary missing at ${LLAMA_BIN}" >&2
  exit 2
fi

# Parse Config.json → space-separated key=value pairs
read_config() {
  python3 - "$@" <<'PY'
import json, os, sys
config_path = sys.argv[1]
root_dir = sys.argv[2]
with open(config_path) as f:
    cfg = json.load(f)
llm = (cfg.get("services") or {}).get("llm") or {}

# Model path: prefer Config.json model_path; fallback to env var; relative paths resolved to root.
mp = llm.get("model_path") or os.environ.get("ADAM_LLM_GGUF_PATH", "")
if not mp:
    sys.exit("ERROR: services.llm.model_path missing in Config.json and ADAM_LLM_GGUF_PATH unset")
if not os.path.isabs(mp):
    mp = os.path.join(root_dir, mp)
if not os.path.isfile(mp):
    sys.exit(f"ERROR: model file not found: {mp}")

# Context size from Config.json, fallback to env, then 8192.
ctx = int(llm.get("num_ctx") or os.environ.get("ADAM_LLM_CTX") or 8192)

# Speculative decoding (optional). Default to ngram-mod which works without a draft model.
spec = llm.get("speculative") or {}
spec_type = spec.get("type", "")
ngram_match = int(spec.get("ngram_mod_n_match") or 24)
ngram_min = int(spec.get("ngram_mod_n_min") or 48)
ngram_max = int(spec.get("ngram_mod_n_max") or 64)

print(f"MODEL_PATH={mp}")
print(f"CTX={ctx}")
print(f"SPEC_TYPE={spec_type}")
print(f"NGRAM_MATCH={ngram_match}")
print(f"NGRAM_MIN={ngram_min}")
print(f"NGRAM_MAX={ngram_max}")
PY
}

# shellcheck disable=SC2046
eval "$(read_config "${CONFIG}" "${ROOT_DIR}")"

echo "▶ adam-llm launcher" >&2
echo "  config:     ${CONFIG}" >&2
echo "  model:      ${MODEL_PATH}" >&2
echo "  ctx:        ${CTX}" >&2
echo "  port:       ${PORT}" >&2
echo "  gpu_layers: ${GPU_LAYERS}" >&2
echo "  spec_type:  ${SPEC_TYPE:-(none)}" >&2

ARGS=(
  --model "${MODEL_PATH}"
  --host 127.0.0.1
  --port "${PORT}"
  --n-gpu-layers "${GPU_LAYERS}"
  --ctx-size "${CTX}"
  --parallel 1
  --reasoning off
  --flash-attn on
  --cache-type-k q8_0
  --cache-type-v q8_0
)

if [[ -n "${SPEC_TYPE}" ]]; then
  ARGS+=(--spec-type "${SPEC_TYPE}")
  if [[ "${SPEC_TYPE}" == ngram-mod ]]; then
    ARGS+=(
      --spec-ngram-mod-n-match "${NGRAM_MATCH}"
      --spec-ngram-mod-n-min "${NGRAM_MIN}"
      --spec-ngram-mod-n-max "${NGRAM_MAX}"
    )
  fi
fi

exec "${LLAMA_BIN}" "${ARGS[@]}"
