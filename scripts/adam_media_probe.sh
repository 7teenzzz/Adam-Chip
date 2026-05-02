#!/usr/bin/env bash
set -euo pipefail

echo "Video devices:"
ls -l /dev/video* 2>/dev/null || true

echo
echo "V4L2 capabilities:"
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices || true
  v4l2-ctl --device="${ADAM_VIDEO_DEVICE:-/dev/video0}" --all || true
else
  echo "v4l2-ctl is not installed"
fi

echo
echo "Audio capture devices:"
arecord -l || true

echo
echo "Audio playback devices:"
aplay -l || true
