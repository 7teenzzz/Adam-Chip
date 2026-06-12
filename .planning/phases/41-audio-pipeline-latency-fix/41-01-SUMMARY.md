---
phase: 41-audio-pipeline-latency-fix
plan: 01
status: partial
subsystem: audio/pipewire
tags: [wireplumber, pipewire, oww, audio-cadence]
key-files:
  created:
    - "~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua"
metrics:
  before_oww_hz: 1.5
  after_oww_hz: 3.5
  target_oww_hz: 12.5
---

## Plan 41-01: WirePlumber latency override activation — Partial

### BEFORE baseline (2026-06-12, pre-override)

From 41-CONTEXT.md diagnostics:
- `node.max-latency = 48000/48000` (1 second)
- oww_score events: ~18/12s = ~1.5 Hz (severely bursty, 7× below target)
- audio_level events: ~7/12s

### Status of the override

**Override file confirmed** (`~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua`):
- Match rule: `alsa_input.usb-WebCamera_*` ✓
- `["node.latency"] = "512/48000"` ✓
- `["api.alsa.period-size"] = 512` ✓
- `["api.alsa.headroom"] = 0` ✓
- `["session.suspend-timeout-seconds"] = 0` ✓

**WirePlumber restarted**: `2026-06-12 22:39:56 MSK` (system auto-restart or manual; occurred between the debugging session and this execution phase)

**Node state after restart** (pw-dump, 2026-06-13):
- `node.latency = 512/48000` ✓ (was 48000/48000 or unset)
- `api.alsa.period-size = 512` ✓ (override applied)
- `session.suspend-timeout-seconds = 0` ✓ (override applied)
- `node.max-latency = 48000/48000` — still 1 second (hardware constraint, NOT overridable via apply_properties)
- node state: `running`

All PipeWire/WirePlumber services: `active` ✓

### AFTER measurement (2026-06-13)

12-second live measurement with orchestrator in standby (voice_loop active):
- oww_score events: **42/12s = 3.5 Hz** (was 1.5 Hz → 2.3× improvement)
- audio_level events: **17/12s = 1.4 Hz** (was 0.58 Hz → 2.4× improvement)
- oww scores: still 0.001 (cadence too low for model to see coherent utterance)

**Target NOT met**: ≥100 oww_score/12s required (= ~8.3 Hz); observed 3.5 Hz.

### Root cause of partial fix

`node.max-latency = 48000/48000` is a hardware-reported property from the ALSA USB audio driver. PipeWire uses it to determine the maximum scheduling quantum for this node. Our override sets `node.latency = 512/48000` (the requested rate), but PipeWire's graph scheduler may still round up to the driver's reported max-latency when choosing the actual quantum.

WirePlumber's `apply_properties` cannot override `node.max-latency` because it is driver-provided metadata, not a node configuration property.

### LocalMicReader reconnect confirmed

The LocalMicReader's `_open_drain_reconnect_loop` (sleep 2.0s) automatically restarts arecord when the audio stack is interrupted. After WirePlumber's restart at 22:39 MSK, arecord would have reconnected within ~2-4s. The current 3.5 Hz cadence reflects this post-reconnect state.

### Next steps for full resolution (unblocked)

The wave cadence improvement (1.5 → 3.5 Hz) is meaningful — Wave 2 OWW calibration should proceed with this partial fix as baseline. After Wave 2, options for further improvement:

1. **Add `node.max-latency` to the WirePlumber override** (may or may not be respected by the driver):
   ```lua
   ["node.max-latency"] = "1024/48000",
   ```
   Restart wireplumber, re-measure.

2. **Set `PULSE_LATENCY_MSEC=20` in arecord subprocess** (LocalMicReader._start_process):
   Requests a 20ms PulseAudio stream latency from the PipeWire-PulseAudio bridge.
   Previously tested via CLI with no change, but that was before node.latency override was applied.

3. **Restart the orchestrator** (fresh arecord → new PulseAudio stream negotiation):
   The current arecord connection may have negotiated its stream latency before the PipeWire fix was fully in effect. A fresh connection might pick up smaller buffer parameters.

### Self-Check: PARTIAL

- Override file present with correct content ✓
- WirePlumber restarted, services active ✓
- node.latency=512/48000 applied to WebCamera node ✓
- oww_score cadence improved (1.5→3.5 Hz) but BELOW 8.3 Hz threshold ✗
- Acceptance criteria NOT fully met (42/12s vs ≥100 required)
