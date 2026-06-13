---
phase: 41-audio-pipeline-latency-fix
plan: 01
status: resolved (cross-branch, see addendum)
subsystem: audio/pipewire
tags: [wireplumber, pipewire, oww, audio-cadence, usb]
key-files:
  created:
    - "~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua"
metrics:
  before_oww_hz: 1.5
  after_oww_hz: 3.5
  after_usb_fix_oww_hz: 12.64
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

### Self-Check: PARTIAL (at time of writing — see addendum below)

- Override file present with correct content ✓
- WirePlumber restarted, services active ✓
- node.latency=512/48000 applied to WebCamera node ✓
- oww_score cadence improved (1.5→3.5 Hz) but BELOW 8.3 Hz threshold ✗
- Acceptance criteria NOT fully met (42/12s vs ≥100 required)

---

## Addendum (2026-06-13, cross-branch finding from `audio-pipeline-restoration`)

**The remaining 3.5→12.5 Hz gap was NOT a PipeWire/WirePlumber problem — it was a
physical USB Full-Speed vs High-Speed negotiation issue on the WebCamera's hub
port, one layer below everything diagnosed in this plan.**

A parallel branch (`audio-pipeline-restoration`, diverged from `main@37830af`,
independent capture architecture via `_run_local`/`arecord` instead of
`LocalMicReader`) ran the same root-cause chase and found:

- `node.max-latency=48000/48000` confirmed stuck (matches this plan's finding) —
  but even with `api.alsa.period-size=512` applied (Attempt 3, same override as
  here), raw `arecord -D pulse` throughput stayed at **~8.3%** of nominal at
  16kHz, 16kHz+`PULSE_LATENCY_MSEC=20`, AND native 48kHz — ruling out resampling,
  WirePlumber config, and `PULSE_LATENCY_MSEC` (option 2 above) as fixes.
- `sudo usbreset` on the device → identical re-enumeration, same port, same 8.3%
  — ruled out stuck-USB-state.
- **Empirical fix (today)**: `/proc/asound/card0/stream0` showed `full speed`
  (12 Mbps) on port `1-2.2` — the WebCamera was on a USB hub port negotiating
  Full-Speed instead of High-Speed (480 Mbps), capping real throughput at ~8%
  regardless of OS/driver/PipeWire configuration. User moved the physical cable
  to port `1-2.4`. Device re-enumerated `usb 1-2.4: new HIGH-SPEED USB device
  number 6`. `/proc/asound/card0/stream0` now shows `high speed`,
  `Data packet interval: 1000 us`. Throughput jumped to **91.7% (48kHz) / 95.8%
  (16kHz)**. Live `oww_score` cadence: **12.64 Hz** (target ~12.5 Hz, met).
- **Caveat**: the user reports having tried other USB ports in past sessions
  without this fixing the issue. The kernel journal only retains the current
  boot (today, from 18:05) — no record of those earlier attempts to compare
  against. So "any High-Speed port permanently fixes this" is NOT confirmed as
  a general rule; what IS confirmed is that the CURRENT live system, on port
  `1-2.4` with the Attempt-3 WirePlumber override, measures 91.7-95.8%
  throughput / 12.64 Hz right now, reproducibly. If cadence regresses again,
  check `/proc/asound/card0/stream0` for `full speed` vs `high speed` as a fast
  triage before re-diagnosing PipeWire.

### Verified against THIS branch's exact `LocalMicReader._start_process()`

To confirm this fix carries over to SmartFlora's architecture (not just
`_run_local`), the exact `_find_pulse_source("webcamera")` + `_start_process()`
invocation from `local_mic_reader.py` (dynamic PULSE_SOURCE resolution via
`pactl list short sources`, plus `PULSE_LATENCY_MSEC=20`) was replicated on the
current (post-USB-fix) hardware:

- `_find_pulse_source("webcamera")` → resolves
  `alsa_input.usb-WebCamera_WebCamera_202509021958-02.capture.0.0`
  (the renamed node from the period-size override — substring match on
  "webcamera" still works, no code change needed)
- `arecord -D pulse -f S16_LE -r 16000 -c 1 -t raw` with that `PULSE_SOURCE` +
  `PULSE_LATENCY_MSEC=20` → **95.2% throughput, stable 128ms chunk cadence**
  (identical to the `_run_local` measurement above)

### Conclusion

Plan 41-01's acceptance criteria (≥8.3 Hz / target 12.5 Hz) are now met **with no
further code or WirePlumber changes** — the blocker was hardware (USB port
speed), fixed by the user moving the cable. The existing
`51-webcamera-latency.lua` override (period-size=512) stays in place, untouched
— it's a real (if secondary) improvement and the renamed `.capture.0.0` node is
already handled correctly by `_find_pulse_source`'s substring match.

**Plan 41-02's hardcoded `PULSE_SOURCE=...mono-fallback` in
`adam-orchestrator.service`** is dead config (overridden by
`LocalMicReader._start_process()`'s dynamic resolution) — harmless, but could be
removed/updated for clarity in a future cleanup.

**Plans 41-03 (OWW threshold recalibration) and 41-04 (full e2e voice-loop
verification) are now unblocked** — cadence precondition is met. As a data
point: on `audio-pipeline-restoration`, the full wake→listen→reply cycle was
confirmed working live with the CURRENT (unrecalibrated) `wake_word.threshold=0.01`,
`debounce_hits=2` — Plan 41-03's recalibration may still be worth doing for
false-positive safety at the new (correct) cadence, but is not blocking.

Full details: `BRANCH.md` (item 9-10) and
`.planning/phases/36-audio-pipeline-restoration/36-CONTEXT.md` on
`audio-pipeline-restoration`.
