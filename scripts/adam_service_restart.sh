#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E "$0" "$@"
fi

systemctl restart adam-tts-silero.service adam-orchestrator.service
systemctl --no-pager status adam-orchestrator.service adam-tts-silero.service || true
