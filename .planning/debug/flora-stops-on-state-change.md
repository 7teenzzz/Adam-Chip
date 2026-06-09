---
slug: flora-stops-on-state-change
status: fix_applied
trigger: "технофлора перестала работать и не светится — нужно проанализировать конфликты в установлении всех анимаций/состояний технофлоры"
created: 2026-06-07
updated: 2026-06-07
component: technoflora (Phase 29) — ESP32 firmware FloraModule + Jetson FloraController
branch: LuxFlora-modes_V1.1
---

# Debug: technoflora stops lighting during dialogue / state transitions

## Symptoms

- **Expected:** technoflora (light ch 0–10, vibro ch 11–14 on PCA9685) animates across the
  6 pipeline states (покой/breathe → детекция/accent → слушание/attentive → раздумье/think_pulse
  → ответ/RMS → пробуждение/wake_bloom) and stays visibly lit.
- **Actual:** at some point the technoflora stops working and does not light up.
- **Errors:** none reported by the user.
- **Timeline:** worked before, stopped at some point. **Fails during dialogue and state
  transitions** (user-confirmed) — i.e. exactly when channel-write traffic is highest.
- **Reproduction:** occurs during a normal dialogue turn as states transition. ESP power-cycle
  recovery: NOT yet tested (unknown).

## Current Focus

- **hypothesis:** CONFIRMED. No I2C bus mutex. `floraTask` (50 Hz) and the ESP web-server task
  (`/api/pca9685/*` from the Jetson RMS streamer + legacy action-layer scene writes) both call
  into `Pca9685Module` → `Wire` transactions concurrently with no cross-task lock. A preemption
  mid-`Wire.endTransmission()` interleaves two multi-byte I2C transactions → PCA9685 register
  corruption / latch-up → lamps go dark and stay dark. Fires during dialogue state transitions
  (highest write contention). C1/C2/C4 drive the contention; C3 is the mechanism of the blackout.
- **next_action:** apply the firmware I2C mutex (Part A), the firmware external/suspend mode +
  flora.enabled gate (Part B), and the Jetson legacy-action flora guard (Part C); then run the
  hardware verification below (manual flash — PlatformIO).

## Evidence (pre-gathered code analysis + confirmation 2026-06-07)

### Writers into PCA9685 channels (one shared `Wire` bus, NO bus mutex)
- `Subsystem/AdamsServer/src/io/FloraModule.cpp:248` — `floraTask` → `writeAllChannelsRaw(duties)`
  EVERY tick (~50 Hz, `floraTask` while(true)+vTaskDelay). Started `AdamsServer.ino startFloraTask()`.
- `System/adam/flora.py:492` — Jetson RMS streamer `_rms_stream` → `mcu.set_channels` →
  `/api/pca9685/channels` (web-task → `applyPca9685Updates` → `writeAllChannelsRaw`) at ~12.5 Hz.
- `System/Orchestrator.py:2402 mcu.idle()`, `:3222 mcu.set_scene`, `:3224 mcu.set_channel` — LEGACY
  action layer → `/api/pca9685/scene|channel` → web-task → `applyPca9685Scene`/`applyPca9685Update`.
  boot_idle = all-0 (AdamsConfig.h:121) → fights floraTask on channels 0–14.
- Low-level Wire functions all in `Pca9685Module.cpp`: `writeRegister` (:37), `writeRegisters` (:48),
  `readRegister` (:61). `gRuntimeStateMux` (portMUX spinlock) guards ONLY the `gRuntimeState` array
  copy (`:111-113`, `:168-172`) — NOT the `Wire.beginTransmission..endTransmission` block.
- `SensorModule.cpp` calls `Wire.begin/setClock` in init (`:32-33`) but `readSensors()` uses
  `analogRead`/`digitalRead` only — sensorTask does NOT do periodic Wire transactions. So the two
  ACTIVE concurrent Wire writers are floraTask + web-server task.

## Resolution

root_cause: **C3 — concurrent unsynchronised I2C `Wire` access.** The firmware has no I2C bus mutex.
`floraTask` (50 Hz, `writeAllChannelsRaw`) and the HTTP web-server task (`applyPca9685Update(s)` /
`applyPca9685Scene` / `setPca9685Frequency` from `/api/pca9685/*`) both run multi-byte
`Wire.beginTransmission..endTransmission` transactions on the same bus, both pinned to APP_CPU_NUM.
When the web task is preempted mid-transaction by floraTask (or vice-versa) the two I2C transactions
interleave and corrupt the PCA9685 register write — the chip latches up and the lamps go dark and stay
dark. The blackout fires during dialogue state transitions because that is the highest write-contention
window (RMS streamer @12.5 Hz + `set_scene`/`idle` legacy writes + floraTask @50 Hz all active).
C1 (floraTask overwrites external frames within 20 ms) and C2 (attentive-vs-RMS double writer) and
C4 (legacy boot_idle all-0 writes) are the contention drivers; C3 is the mechanism of the blackout.

fix: three parts. **Part A (BLOCKER) — firmware I2C bus mutex.** **Part B (HIGH) — firmware
external/suspend mode + honor flora.enabled.** **Part C (HIGH) — Jetson: stop the legacy action
layer fighting flora channels.** All Config-First; no invariants touched. Exact specs below.

### Part A — I2C bus mutex (Pca9685Module.cpp) [BLOCKER, fixes the dark-out]

Add a dedicated FreeRTOS mutex serializing every complete Wire transaction. Mirror the
`sAudioConfigMutex` pattern (AudioModule.cpp:49-50, 154). Do NOT use `gRuntimeStateMux`
(portMUX) — a spinlock held across a Wire transaction disables interrupts the I2C driver needs.

1. Add includes near the top of `Pca9685Module.cpp`:
   `#include <freertos/FreeRTOS.h>` and `#include <freertos/semphr.h>`
2. In the anonymous namespace add:
   ```cpp
   StaticSemaphore_t sI2cMutexBuffer;
   SemaphoreHandle_t sI2cMutex = nullptr;
   inline void i2cBusLock() {
     if (sI2cMutex == nullptr) sI2cMutex = xSemaphoreCreateMutexStatic(&sI2cMutexBuffer);
     if (sI2cMutex != nullptr) xSemaphoreTake(sI2cMutex, portMAX_DELAY);
   }
   inline void i2cBusUnlock() {
     if (sI2cMutex != nullptr) xSemaphoreGive(sI2cMutex);
   }
   ```
3. Wrap the body of EACH low-level transaction so the lock spans the full
   beginTransmission..endTransmission (including the 3-attempt retry loop):
   - `writeRegister` (:37-46): `i2cBusLock();` at entry, `i2cBusUnlock();` before each `return`.
   - `writeRegisters` (:48-59): same — guard the whole `for(attempt)` loop.
   - `readRegister` (:61-77): same — guard the whole loop (it does begin+requestFrom+read).
   Guard at the LOW level (not the high-level helpers) so it is a single, non-recursive,
   deadlock-free mutex: each call is one complete transaction; sequential calls from
   `setPca9685Frequency`/`initPca9685` simply take/give repeatedly. (Verify there is no path that
   calls a Wire function while already holding the lock — none exists: the three leaf functions
   never call each other.)
   Tip to avoid lock leaks on the multiple `return` paths: refactor each to compute a `bool ok`
   and have a single `i2cBusUnlock(); return ok;` exit, or use a tiny RAII guard struct.

### Part B — firmware external/suspend mode + honor flora.enabled (FloraModule.cpp + AdamsConfig.h) [HIGH, fixes C1/C2/C7]

Goal: when the Jetson is streaming raw frames (RMS "ответ" effect, calibration script) OR when
flora is disabled in Config, floraTask must NOT overwrite those external writes every 20 ms.

1. Add a new preset/flag `FloraPreset::External` (animation-suppressed). When active, `floraTick`
   skips its `writeAllChannelsRaw(duties)` — it lets external `/api/pca9685/*` writes stand.
   (Keep a short watchdog: if no external frame arrives for N ms — config
   `flora.external_timeout_ms` — fall back to `breathe` so the lamps never freeze permanently.)
2. Jetson side: in `flora.py::_on_answer_start` push state `external` (instead of `attentive`)
   right before starting `_rms_stream`, and push `breathe` on `_on_answer_end`. This resolves C2:
   the RMS "ответ" light effect (FLORA-04) actually sticks because floraTask stops fighting it.
3. Honor the `flora.enabled` flag (C7): `startFloraTask()` (or `floraTick`) should early-return /
   not write when flora is disabled. Surface `enabled` to the firmware via the existing
   `/api/flora/state` params (add `enabled` bool) rather than a new endpoint.
   New Config keys (System/Config.json `flora` + Config.schema.json): `external_timeout_ms`
   (default e.g. 500). Do NOT hardcode — Config-First (D-13).

### Part C — stop the legacy action layer fighting flora (Jetson) [HIGH, fixes C4]

The LLM action layer and `/api/agent/stop` still POST `boot_idle` (all-0) / `set_scene` /
`set_channel` to the SAME PCA9685 channels 0–14 that flora owns.
- In `System/Orchestrator.py`: `mcu.idle()` at `:2402` (`/api/agent/stop`) and `_execute_action`
  at `:3221-3224` must NOT write flora-owned channels 0–14 while flora is enabled. Either gate these
  behind `flora.enabled == false`, or restrict the action layer to non-flora channel 15 only.
- This keeps flora the single owner of 0–14 during exhibition; the legacy scene API remains for
  maintenance when `flora.enabled=false`.

### Secondary / cosmetic (apply after A–C verified on hardware)
- **C5 (MED) — double gamma.** Jetson sends perceptual % → linear duty (`flora.py:294
  base_duty = value_max*pct/100`); firmware applies gamma AGAIN (`FloraModule.cpp:79 gammaApply`).
  71% → ~47% actual. Decide ONE gamma owner (recommend firmware-only; send linear from Jetson, or
  send true % and let firmware gamma — but not both). Also reconcile with user intent "70% = raw PWM".
- **C6 (MED) — looks off at rest.** With no transitions firmware sits in `idle`
  (base 120/peak 900 → post-gamma ~0–3.5%). Boot scene `kPca9685BootScene="test_all"` (2907/ch) is
  fine; the dim look is the `idle` preset trough. Raise idle base or settle to `breathe`.

verification: HARDWARE-GATED (real ESP32 + PCA9685). Manual flash required (PlatformIO — agent
cannot flash). After applying Part A and reflashing:
  1. Build firmware: `cd Subsystem/AdamsServer && pio run`  (PASS = compiles clean).
  2. Flash manually (USB COM7): `powershell -ExecutionPolicy Bypass -File tools/flash_com7.ps1`
     or OTA: `tools/flash_ota.ps1 -Host 192.168.0.171`.
  3. I2C-contention stress (this is the direct repro of the dark-out). From the Jetson, hammer
     `/api/pca9685/channels` while floraTask runs, e.g.:
     `for i in $(seq 1 300); do curl --noproxy '*' -s -m 1 -X POST \
        http://10.10.10.171/api/pca9685/channels \
        -H 'Content-Type: application/json' \
        -d '{"updates":[{"channel":0,"value":2000},{"channel":5,"value":2000},{"channel":10,"value":2000}]}' \
        >/dev/null; done`
     PASS = lamps keep animating/responding throughout and do NOT freeze dark; the PCA9685 keeps
     ACKing (no permanent blackout). FAIL = lamps go dark and stay dark (pre-fix behavior).
     (autonomous:false — user runs on hardware.)
  4. Full dialogue turn with `flora.enabled=true`: trigger a normal turn (wake word → reply) and
     watch the 6 states animate; confirm the RMS "ответ" effect is visible (Part B) and there is no
     blackout across transitions. PASS = continuous animation, no dark-out. (autonomous:false.)
  5. journalctl/serial: monitor COM6 (`tools` serial) for repeated `pca9685 ... endTransmission`
     failures — none expected after the mutex. (autonomous:false.)

files_changed (APPLIED 2026-06-07 — Python + JSON validated; firmware NOT yet compiled/flashed):
  - Subsystem/AdamsServer/src/io/Pca9685Module.cpp  (Part A: sI2cMutex + i2cBusLock/Unlock wrapping
       writeRegister/writeRegisters/readRegister; + lastExternalPcaWriteMs timestamp in
       applyPca9685Update/Updates for the External watchdog)
  - Subsystem/AdamsServer/src/core/RuntimeState.h    (new field volatile uint32_t lastExternalPcaWriteMs)
  - Subsystem/AdamsServer/src/io/FloraModule.cpp     (Part B: FloraPreset::External + kPresetDefaults row;
       sFloraEnabled; floraTick early-returns for !enabled and External + watchdog->breathe; setFloraState
       honors params.enabled + resets watchdog on External; computeLightLevel External case)
  - Subsystem/AdamsServer/src/io/FloraModule.h        (Part B: FloraParams.enabled tri-state field)
  - Subsystem/AdamsServer/config/AdamsConfig.h        (Part B: kFloraExternalTimeoutMs = 500)
  - Subsystem/AdamsServer/src/web/WebServerModule.cpp (Part B: floraStateHandler parses "enabled" bool)
  - System/adam/flora.py                              (Part B: _on_answer_start pushes 'external' not
       'attentive'; push_preset known-set adds 'external')
  - System/Orchestrator.py                            (Part C: /api/agent/stop skips mcu.idle() and
       _execute_action suppresses scene/channel writes while flora.enabled)
  - System/Config.json + System/Config.schema.json    (Part B: flora.external_timeout_ms = 500)

VERIFICATION STATUS: code applied + Python/JSON validated. PENDING on hardware (user):
  `cd Subsystem/AdamsServer && pio run` → flash (COM7/OTA) → run the I2C-contention stress repro
  + a full dialogue turn (steps 1-5 above). Firmware was NOT compiled in this environment.

## Confirmed conflicts
- **C1 (BLOCKER):** floraTask overwrites any external channel write within ≤20 ms — no external
  mode. FloraModule.cpp:248. → fixed by Part B.
- **C2 (HIGH):** flora.py:202 `_on_answer_start` sets `attentive` (firmware fast waves @50 Hz) while
  `_rms_stream` (flora.py:492) writes RMS @12.5 Hz → firmware wins 4:1, RMS effect dead. → Part B.
- **C3 (BLOCKER — root cause of "goes dark"):** NO I2C mutex; concurrent Wire access from floraTask +
  web task. Pca9685Module.cpp:39/50/63 + :155. → fixed by Part A.
- **C4 (HIGH):** legacy action layer (mcu.idle boot_idle all-0, set_scene, set_channel) fights
  floraTask. Orchestrator.py:2402/3222/3224 → device.py /api/pca9685/{scene,channel}. → Part C.
- **C5 (MED):** double gamma — flora.py:294 (linear %→duty) + FloraModule.cpp:79 gammaApply. → secondary.
- **C6 (MED):** idle preset trough looks "off" (FloraModule.cpp:50-58). → secondary.
- **C7 (LOW):** floraTask ignores flora.enabled; firmware preset defaults hardcoded. → Part B.

## Eliminated
- **sensorTask as a third concurrent Wire writer:** ELIMINATED. SensorModule.cpp `readSensors()`
  uses analogRead/digitalRead (GPIO ADC), not I2C, despite `Wire.begin()` in `initSensors()`.
  Only floraTask + web-server task are active Wire writers.
- **`/api/flora/state` as a direct Wire writer:** ELIMINATED. `floraStateHandler` (WebServerModule.cpp:2733)
  → `setFloraState` only updates the mux-guarded `sTarget` POD; it does NOT touch Wire. Safe.
