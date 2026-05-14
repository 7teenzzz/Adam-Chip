#!/usr/bin/env bash
# Verify that the WhisperX ASR container is running on CUDA (not CPU).
# Exit 0 = CUDA OK, Exit 1 = not CUDA or service unreachable.
set -euo pipefail

ASR_URL="${ADAM_ASR_URL:-http://127.0.0.1:8095}"

if ! HEALTH=$(curl --noproxy '*' -fsS "${ASR_URL}/health" 2>&1); then
    echo "❌ ASR service unreachable at ${ASR_URL}/health" >&2
    echo "   Is the container running?  docker ps | grep adam-asr-whisperx" >&2
    exit 1
fi

DEVICE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('device','UNKNOWN'))")
DEVICE_REQ=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('device_requested','UNKNOWN'))")
MODEL=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('model','?'))")
COMPUTE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('compute_type','?'))")

echo "WhisperX health:"
echo "  device_requested : ${DEVICE_REQ}"
echo "  device           : ${DEVICE}"
echo "  model            : ${MODEL}"
echo "  compute_type     : ${COMPUTE}"

if [ "$DEVICE" != "cuda" ]; then
    echo ""
    echo "❌ WhisperX is running on ${DEVICE} instead of CUDA." >&2
    echo "   Possible causes:" >&2
    echo "   1. ctranslate2 wheel has no CUDA support — rebuild image:" >&2
    echo "      docker compose build adam-asr-whisperx && docker compose up -d adam-asr-whisperx" >&2
    echo "   2. nvidia-container-toolkit not installed or docker runtime not set:" >&2
    echo "      docker info | grep -i runtime" >&2
    echo "   3. Container missing 'runtime: nvidia' in compose.yaml" >&2
    exit 1
fi

echo ""
echo "✅ WhisperX CUDA OK"
