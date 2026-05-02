#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E "$0" "$@"
fi

nvpmodel -m 0
jetson_clocks --fan

echo "nvpmodel:"
nvpmodel -q

echo
echo "jetson_clocks:"
jetson_clocks --show || true
