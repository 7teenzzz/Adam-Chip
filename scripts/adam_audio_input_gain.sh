#!/usr/bin/env bash
# Adam Chip — re-assert microphone input gain at every start (durable across reboot).
#
# WHY: USB capture cards do NOT persist their ALSA capture gain across a cold boot
# unless alsa-restore is configured. The WebCamera 'Mic' control resets from its
# tuned +24 dB (100%) back to the driver default, which silently cripples wake-word
# (OWW) sensitivity after an unattended reboot. This script reads the desired levels
# from System/Config.json (Config-First) and applies BOTH:
#   - ALSA card capture gain (the hardware boost that actually resets), and
#   - PulseAudio source volume (soft gain; usually persists, set for completeness).
#
# It is idempotent, never fails the caller (all best-effort), and is wired as an
# ExecStartPre of adam-orchestrator.service so it runs on boot autostart, plus from
# adam_start.sh for manual starts.
#
# Usage: adam_audio_input_gain.sh   (reads Config.json; no args)
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${ADAM_CONFIG:-${ROOT_DIR}/System/Config.json}"

# --- read desired values from Config.json (media.audio.input_gain) -----------
read_cfg() {
  python3 - "$CONFIG" "$1" "$2" <<'PY' 2>/dev/null
import json, sys
cfg, key, default = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    g = json.load(open(cfg)).get("media", {}).get("audio", {}).get("input_gain", {})
    v = g.get(key, default)
    print(v if v is not None else default)
except Exception:
    print(default)
PY
}

CARD="$(read_cfg card_name WebCamera)"
CONTROL="$(read_cfg alsa_control Mic)"
ALSA_PCT="$(read_cfg alsa_capture_percent 100)"
PULSE_PCT="$(read_cfg pulse_source_percent 100)"

log() { printf '[adam-input-gain] %s\n' "$*" >&2; }

# --- 1. ALSA card capture gain (the part that resets on reboot) --------------
if command -v amixer >/dev/null 2>&1; then
  # Resolve card: prefer the configured name; amixer accepts a name directly. If the
  # name is gone (mic unplugged / renamed), skip rather than error.
  if amixer -c "${CARD}" sget "${CONTROL}" >/dev/null 2>&1; then
    if amixer -c "${CARD}" sset "${CONTROL}" "${ALSA_PCT}%" cap >/dev/null 2>&1; then
      now="$(amixer -c "${CARD}" sget "${CONTROL}" 2>/dev/null | grep -oE '\[[0-9]+%\] \[[-0-9.]+dB\]' | head -1)"
      log "ALSA ${CARD}/${CONTROL} → ${ALSA_PCT}%  ${now}"
    else
      log "WARN: failed to set ALSA ${CARD}/${CONTROL}"
    fi
  else
    log "WARN: ALSA control ${CARD}/${CONTROL} not found — skipping (mic absent?)"
  fi
else
  log "WARN: amixer not available — skipping ALSA gain"
fi

# --- 2. PulseAudio source volume (best-effort; needs a running pulse) ---------
if command -v pactl >/dev/null 2>&1; then
  # Prefer the pinned source from the env (PULSE_SOURCE), else the first source whose
  # name contains the card name.
  src="${PULSE_SOURCE:-}"
  if [[ -z "${src}" ]]; then
    src="$(pactl list short sources 2>/dev/null | awk -v c="${CARD}" 'tolower($2) ~ tolower(c){print $2; exit}')"
  fi
  if [[ -n "${src}" ]] && pactl get-source-volume "${src}" >/dev/null 2>&1; then
    if pactl set-source-volume "${src}" "${PULSE_PCT}%" >/dev/null 2>&1; then
      pactl set-source-mute "${src}" 0 >/dev/null 2>&1 || true
      pactl set-default-source "${src}" >/dev/null 2>&1 || true
      log "PULSE ${src} → ${PULSE_PCT}% (default)"
    else
      log "WARN: failed to set pulse volume on ${src}"
    fi
  else
    log "INFO: no matching pulse source for '${CARD}' (pulse down or device absent)"
  fi
fi

exit 0
