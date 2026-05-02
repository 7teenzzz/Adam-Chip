#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-adam-orchestrator.service}"
journalctl -u "${SERVICE}" -n "${ADAM_LOG_LINES:-120}" -f
