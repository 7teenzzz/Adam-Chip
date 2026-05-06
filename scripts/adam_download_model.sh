#!/usr/bin/env bash
# Download a GGUF model from HuggingFace Hub into Subsystem/Models/gguf/.
#
# Usage:
#   adam_download_model.sh <hf_repo> <filename_pattern> [output_dir]
#
# Examples:
#   # Gemma 4 E4B UD-Q4_K_XL (primary, ~6 GB)
#   ./scripts/adam_download_model.sh unsloth/gemma-4-E4B-it-GGUF '*UD-Q4_K_XL*'
#
#   # Gemma 3n E4B UD-Q4_K_XL (~3 GB, 32K ctx)
#   ./scripts/adam_download_model.sh unsloth/gemma-3n-E4B-it-GGUF '*UD-Q4_K_XL*'
#
#   # Gemma 4 E2B Q8_0 (5–8 GB, fallback)
#   ./scripts/adam_download_model.sh unsloth/gemma-4-E2B-it-GGUF '*Q8_0*'
#
#   # Gemma 3n E2B UD-Q4_K_XL (~1.5 GB, fastest)
#   ./scripts/adam_download_model.sh unsloth/gemma-3n-E2B-it-GGUF '*UD-Q4_K_XL*'
#
# Proxy: v2ray SOCKS5 on 127.0.0.1:10808.
#   httpx (used by huggingface_hub) only understands socks5://, not socks://.
#   This script cleans conflicting system proxy vars inside Python before the call.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"

REPO="${1:?Usage: $0 <hf_repo> <filename_pattern> [output_dir]}"
PATTERN="${2:?Usage: $0 <hf_repo> <filename_pattern> [output_dir]}"
OUT_DIR="${3:-${ROOT_DIR}/Subsystem/Models/gguf}"

mkdir -p "${OUT_DIR}"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "ERROR: ${VENV_PYTHON} не найден. Сначала: scripts/adam_bootstrap_venv.sh" >&2
  exit 1
fi

# Ensure huggingface_hub and httpx[socks] are installed
"${VENV_PYTHON}" -m pip install -q huggingface_hub 'httpx[socks]'

# Detect SOCKS5 proxy (v2ray :10808). Pass as env var to Python — don't export
# to the shell environment to avoid confusing httpx before we clean it there.
ADAM_SOCKS5_PROXY=""
if curl -fsS --max-time 2 --socks5 "127.0.0.1:10808" "https://huggingface.co" >/dev/null 2>&1; then
  ADAM_SOCKS5_PROXY="socks5://127.0.0.1:10808"
  echo "  · hfproxy обнаружен: ${ADAM_SOCKS5_PROXY}"
else
  echo "  · прокси не обнаружен, прямое подключение"
fi

echo "▶ Скачиваю модель"
echo "  repo:    ${REPO}"
echo "  pattern: ${PATTERN}"
echo "  dest:    ${OUT_DIR}"
[[ -n "${ADAM_SOCKS5_PROXY}" ]] && echo "  proxy:   ${ADAM_SOCKS5_PROXY}"
echo

# Pass all args as env vars. Quoted heredoc ('PYEOF') prevents bash expansion
# inside Python — values come through os.environ instead.
_HF_REPO="${REPO}" \
_HF_PATTERN="${PATTERN}" \
_HF_OUT_DIR="${OUT_DIR}" \
ADAM_SOCKS5_PROXY="${ADAM_SOCKS5_PROXY}" \
"${VENV_PYTHON}" - <<'PYEOF'
import os, sys, pathlib

# Remove all proxy env vars — system may have all_proxy=socks:// (no "5")
# which httpx rejects. We apply only the correctly-formed socks5:// below.
for _k in [k for k in list(os.environ)
           if k.lower() in ('http_proxy', 'https_proxy', 'all_proxy',
                            'socks_proxy', 'ftp_proxy', 'no_proxy')]:
    del os.environ[_k]

_proxy = os.environ.pop("ADAM_SOCKS5_PROXY", "").strip()
if _proxy:
    os.environ["ALL_PROXY"] = _proxy

from huggingface_hub import snapshot_download

repo    = os.environ["_HF_REPO"]
pattern = os.environ["_HF_PATTERN"]
out_dir = os.environ["_HF_OUT_DIR"]

snapshot_download(
    repo_id=repo,
    allow_patterns=[pattern],
    local_dir=out_dir,
)

files = sorted(pathlib.Path(out_dir).glob("**/*.gguf"))
if not files:
    files = sorted(pathlib.Path(out_dir).glob("**/*"))
for f in files:
    print(f"  {f.name}  ({f.stat().st_size / 1e9:.1f} GB)")

print(f"\nГотово: {out_dir}")
PYEOF

echo
echo "Следующий шаг — запустить llama-server и проверить:"
echo "  sudo systemctl start adam-llm"
echo "  curl -s http://127.0.0.1:8051/v1/models | python3 -m json.tool"
