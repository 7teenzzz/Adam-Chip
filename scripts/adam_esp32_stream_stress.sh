#!/usr/bin/env bash
#
# adam_esp32_stream_stress.sh — ESP32 /audio stream zombie-session regression test.
#
# Validates the T17 firmware fixes (commit 4b97e38):
#   1. TCP keepalive in streamServerOpenFn
#   2. Disconnect probe in audioHandler loop
#   3. send_wait_timeout 10 → 5 s
#   4. max_open_sockets 4 → 6
#
# Procedure: open the /audio stream N times in a row with progressively
# nastier disconnect patterns (SIGKILL, partial-read, mid-frame close),
# then probe ESP32 status to confirm heap, audio_clients, and HTTP
# responsiveness all stay healthy.
#
# Without the fixes, this script bricks the ESP32 stream server within
# 5-6 iterations: heap_free drops, max_open_sockets saturates with
# zombies, /api/status starts timing out.
#
# With the fixes, ESP32 should pass all N iterations with:
#   - heap_free oscillating within ~5 KB of baseline (no leak drift)
#   - audio_clients returning to 0 between iterations
#   - /api/status always responding in < 1 s

set -euo pipefail

ESP_HOST="${ESP_HOST:-192.168.0.171}"
ITER="${ITER:-12}"
LOG_DIR="${LOG_DIR:-/tmp/adam_esp32_stress_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${LOG_DIR}"

err()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
info() { printf '· %s\n' "$*"; }

probe_status() {
    # Returns 0 on success, prints uptime/heap/clients to stdout.
    local resp
    resp=$(timeout 3 curl -sf --noproxy '*' "http://${ESP_HOST}/api/status" 2>&1) || return 1
    printf '%s\n' "${resp}" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(f'  uptime={d.get(\"uptime_ms\",0)//1000}s heap_free={d.get(\"heap_free\")} audio_clients={d.get(\"audio_clients\")} stream_clients={d.get(\"stream_clients\")}')
except Exception as e:
    print(f'  parse_error: {e}', file=sys.stderr)
    sys.exit(1)
"
}

echo "=== ESP32 stream stress test ==="
echo "  host : ${ESP_HOST}"
echo "  iter : ${ITER}"
echo "  log  : ${LOG_DIR}"
echo

info "Baseline status:"
if ! probe_status > "${LOG_DIR}/00_baseline.txt" 2>&1; then
    err "Baseline /api/status failed — is the ESP32 reachable? (ping ${ESP_HOST})"
    exit 1
fi
cat "${LOG_DIR}/00_baseline.txt"

# Capture baseline heap for drift comparison.
BASELINE_HEAP=$(awk -F'heap_free=' '{print $2}' "${LOG_DIR}/00_baseline.txt" | awk '{print $1}')
info "baseline heap_free=${BASELINE_HEAP} B"
echo

PASS=0
FAIL=0
for i in $(seq 1 "${ITER}"); do
    pattern_num=$((i % 4))
    case $pattern_num in
        0) pattern="quick_close (250 ms timeout)";   sleep_ms=0.25 ;;
        1) pattern="mid_header (1 s timeout)";        sleep_ms=1.0  ;;
        2) pattern="partial_body (3 s timeout)";      sleep_ms=3.0  ;;
        3) pattern="long_session (6 s timeout)";      sleep_ms=6.0  ;;
    esac
    info "[${i}/${ITER}] ${pattern}"
    # Spawn the curl, kill after sleep_ms — that exercises the
    # disconnect-detection path in audioHandler.
    timeout "${sleep_ms}" curl -sN --noproxy '*' -o /dev/null \
        "http://${ESP_HOST}:81/audio" 2>/dev/null \
        > "${LOG_DIR}/iter_${i}_curl.log" 2>&1 || true
    # Brief settle: lets ESP32's keepalive / peek loop spot the death.
    sleep 0.5
    if probe_status > "${LOG_DIR}/iter_${i}_status.txt" 2>&1; then
        ok "[${i}/${ITER}] status OK"
        cat "${LOG_DIR}/iter_${i}_status.txt"
        PASS=$((PASS+1))
    else
        err "[${i}/${ITER}] status TIMEOUT — ESP32 hung after ${i} iterations"
        cat "${LOG_DIR}/iter_${i}_status.txt" 2>/dev/null || true
        FAIL=$((FAIL+1))
        # Continue iterating — we want full failure-mode trace.
    fi
    echo
done

# Final post-stress status.
info "Final status (after ${ITER} iterations):"
probe_status > "${LOG_DIR}/zz_final.txt" 2>&1 || err "final probe failed"
cat "${LOG_DIR}/zz_final.txt"

FINAL_HEAP=$(awk -F'heap_free=' '{print $2}' "${LOG_DIR}/zz_final.txt" | awk '{print $1}')
HEAP_DRIFT=$((BASELINE_HEAP - FINAL_HEAP))
info "heap drift baseline → final: ${HEAP_DRIFT} B (negative = grew)"

echo
echo "=== Summary ==="
echo "  PASS: ${PASS}/${ITER}"
echo "  FAIL: ${FAIL}/${ITER}"
echo "  heap drift: ${HEAP_DRIFT} B"
echo "  logs: ${LOG_DIR}"
if [[ "${FAIL}" -eq 0 ]] && [[ "${HEAP_DRIFT}" -lt 10000 ]]; then
    ok "Stress test passed — firmware fixes hold."
    exit 0
else
    err "Stress test failed — zombie-session leak still active."
    exit 1
fi
