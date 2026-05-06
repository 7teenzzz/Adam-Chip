#!/usr/bin/env bash
# Convenience launcher for the Adam Chip orchestrator on Jetson.
# - Stops any previous manually-started orchestrator process.
# - Ensures TTS + ASR systemd services are active (best-effort, no sudo prompt).
# - Starts the orchestrator in the background, logs to data/adam/orchestrator.log
# - Prints the URL to open in the operator browser.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
LOG_DIR="${ROOT_DIR}/data/adam"
LOG_FILE="${LOG_DIR}/orchestrator.log"
PID_FILE="${LOG_DIR}/orchestrator.pid"
PORT="${ADAM_ORCHESTRATOR_PORT:-8080}"
MODE="${ADAM_MODE:-maintenance}"
MODELS_DIR="${ADAM_MODELS_DIR:-${ROOT_DIR}/Subsystem/Models}"

mkdir -p "${LOG_DIR}" "${MODELS_DIR}/silero" "${MODELS_DIR}/whisper" "${MODELS_DIR}/vlm" "${MODELS_DIR}/hf/hub"

export ADAM_MODELS_DIR="${MODELS_DIR}"
export HF_HOME="${MODELS_DIR}/hf"
export HF_HUB_CACHE="${MODELS_DIR}/hf/hub"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "ERROR: ${VENV_PYTHON} not found. Run scripts/adam_bootstrap_venv.sh first." >&2
  exit 1
fi

stop_existing() {
  local pids
  pids="$(pgrep -f 'System/Orchestrator\.py' || true)"
  if [[ -n "${pids}" ]]; then
    echo "Stopping previous orchestrator: ${pids}"
    kill ${pids} 2>/dev/null || true
    sleep 1
    pids="$(pgrep -f 'System/Orchestrator\.py' || true)"
    if [[ -n "${pids}" ]]; then
      echo "Force-killing: ${pids}"
      kill -9 ${pids} 2>/dev/null || true
    fi
  fi
}

probe_service() {
  local unit="$1"
  if systemctl is-active --quiet "${unit}"; then
    echo "  ${unit}: active"
  else
    echo "  ${unit}: NOT active (try: sudo systemctl start ${unit})"
  fi
}

primary_ip() {
  hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^192\.168\./){print $i; exit}}'
}

stop_existing

echo "Speech services:"
probe_service adam-tts-silero.service
probe_service adam-asr-whisper.service

echo "Models dir: ${MODELS_DIR}"
echo "Starting orchestrator (mode=${MODE}, port=${PORT})…"
cd "${ROOT_DIR}"
PYTHONPATH="${ROOT_DIR}/System" \
  ADAM_MODE="${MODE}" \
  ADAM_ORCHESTRATOR_PORT="${PORT}" \
  ADAM_MODELS_DIR="${MODELS_DIR}" \
  HF_HOME="${MODELS_DIR}/hf" \
  HF_HUB_CACHE="${MODELS_DIR}/hf/hub" \
  nohup "${VENV_PYTHON}" "${ROOT_DIR}/System/Orchestrator.py" >>"${LOG_FILE}" 2>&1 &
ORCH_PID=$!
echo "${ORCH_PID}" > "${PID_FILE}"
disown "${ORCH_PID}" 2>/dev/null || true

# Wait briefly for the server to come up.
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/agent/status" >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

if ! kill -0 "${ORCH_PID}" 2>/dev/null; then
  echo "ERROR: orchestrator exited. Last log lines:" >&2
  tail -n 30 "${LOG_FILE}" >&2 || true
  exit 1
fi

IP="$(primary_ip || true)"
[[ -z "${IP}" ]] && IP="127.0.0.1"

cat <<EOF

  PID:       ${ORCH_PID}   (saved to ${PID_FILE})
  Log:       ${LOG_FILE}
  Local UI:  http://127.0.0.1:${PORT}/
  LAN UI:    http://${IP}:${PORT}/

Helpful commands:
  tail -f ${LOG_FILE}
  curl -s http://127.0.0.1:${PORT}/api/agent/status | python3 -m json.tool
  kill \$(cat ${PID_FILE})

EOF
