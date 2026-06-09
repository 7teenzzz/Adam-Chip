# Phase 35 Wave 4 — Debug Log

**Date:** 2026-06-09 | **Branch:** ultimate-integration

---

## Defect D-01: Flora goes dark during dialogue turns (I2C mutex missing)

**Source:** Wave 3 Session 1 — `pca9685.ready=False` after first voice turn

**Symptom:**
PCA9685 channels go to 0 (dark) during active flora state transitions.
GET /api/status showed `pca9685.ready=False` (SDA stuck low from interrupted I2C transaction).

**Root cause (C3):**
`Pca9685Module.cpp` had no FreeRTOS mutex protecting `Wire1` calls.
`floraTask` writes at 50Hz and the HTTP web task also writes on state-change POSTs → concurrent
`Wire1.beginTransmission/write/endTransmission` from two FreeRTOS tasks → PCA9685 register
corruption → I2C bus NACK → `pca9685.ready=False`.

**Fix:**
`Subsystem/AdamsServer/src/io/Pca9685Module.cpp` — added `sI2cMutex` FreeRTOS semaphore
wrapping `writeRegister`, `writeRegisters`, `readRegister`.
Compiled with arduino-cli (esp32:esp32 3.3.9, fqbn FlashMode=qio FlashSize=16M PartitionScheme=custom
PSRAM=opi CDCOnBoot=cdc) and flashed via USB /dev/ttyACM0.

**Verification:** `flora_state_change` events with no `mcu_error` field throughout full voice turn.
PCA9685 channels show correct values per preset, breathe animation cycles continuously.

**Status:** FIXED ✓

---

## Defect D-02: Accent flash invisible (accent timing race condition)

**Source:** Wave 3 Session 3 — accent preset not visible despite correct API response

**Symptom:**
`flora_state_change: accent` fires but no visible brightness change. Lamps stay at breathe level.

**Root cause:**
`FloraController._handle()` calls `_set_state("accent")` then immediately `_set_state("attentive")`.
Both HTTP POSTs arrive at firmware before the first `floraTask` tick (20ms).
Firmware's `sTarget` holds only ONE preset at a time → attentive overwrites accent before any
tick runs. With default `crossfade_ms=200`, only ~10% of brightness delta applied at T=20ms
(imperceptible). With `breathe.peak_pct=71` and `accent.peak_pct=71`, delta was zero anyway.

**Fix (two-part):**
1. `System/Config.json`:
   - `flora.accent_hold_ms: 220` — new param holding flora in accent state before attentive
   - `flora.states.accent.crossfade_ms: 10` — instant snap (tick=20ms > crossfadeMs=10)
   - `flora.states.breathe.peak_pct: 40` — creates +31% visible delta vs accent 71%
2. `System/adam/flora.py`:
   After `_set_state("accent")`, added `asyncio.sleep(accent_hold_ms / 1000)` so attentive
   stays in the event queue until the 220ms hold expires.

**Verification:**
Unit test confirmed: accent fires at T=0ms (crossfade=10ms, instant), attentive at T=221ms.
Operator confirmed: "засветилось, погасло, проиграл звук" (flash, dark, sound).
Events trace: 14:09 voice turn showed accent → attentive (221ms gap) → chain complete.

**Status:** FIXED ✓

---

## Defect D-03: breathe.peak_pct=71% made accent delta zero

**Source:** Investigation of D-02

**Symptom:**
Even after accent_hold fix, flash was imperceptible because breathe peak = accent peak = 71%.
When breathe was at its crest (71%), accent transition produced zero brightness delta.

**Fix:**
`System/Config.json`: `flora.states.breathe.peak_pct` 71 → 40.
Breathe now cycles 7%→40%, leaving +31% headroom for accent (71%).

**Status:** FIXED ✓

---

## Summary

| Defect | Root cause | Fix | Status |
|--------|-----------|-----|--------|
| D-01 flora dark (I2C) | No FreeRTOS mutex on Wire1 | Firmware mutex, COM flash | FIXED |
| D-02 accent invisible (timing) | accent+attentive race, crossfade | accent_hold + crossfade=10 | FIXED |
| D-03 breathe=accent brightness | breathe.peak_pct=71=accent | breathe.peak_pct→40 | FIXED |

All defects resolved. No open defects from Waves 1–3.
