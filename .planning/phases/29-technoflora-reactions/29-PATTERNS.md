# Phase 29: Technoflora Reactions - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 6 (3 new, 3 modified) + 1 test file
**Analogs found:** 6 / 6 (all exact or strong role+flow matches)

> All analogs are in-repo. This phase is wiring existing primitives — no new
> external deps. Event names are the VERIFIED real ones from RESEARCH §Summary
> (`wake_word_detected`, `voice_state_change`, `llm_thinking_started`,
> `tts_started`, `tts_finished`), NOT the aspirational CONTEXT names.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Subsystem/AdamsServer/src/io/FloraModule.cpp` (NEW) | firmware module (FreeRTOS task) | event-driven / streaming (per-tick frame write) | `src/io/SensorModule.cpp` (task) + `src/io/Pca9685Module.cpp` (frame write) | exact |
| `Subsystem/AdamsServer/src/io/FloraModule.h` (NEW) | firmware header | — | `src/io/SensorModule.h` / `Pca9685Module.h` | exact |
| `Subsystem/AdamsServer/src/web/WebServerModule.cpp` (EDIT) | HTTP route handler | request-response | `pcaSceneHandler` + `/api/pca9685/*` registration (same file) | exact |
| `System/adam/flora.py` (NEW) | controller / service (event consumer + frame streamer) | event-driven + streaming | `api_runtime.py:521` subscribe loop + `mic_reader.py` start/stop + `device.py` MCUClient | exact (composed) |
| `System/Orchestrator.py` (EDIT) | lifespan wiring | — | `mic_reader.start()/stop()` block (lines 1788/1807) | exact |
| `System/Config.json` + `Config.schema.json` (EDIT) | config section | — | `mcu` / `media.audio` plain sections | exact |
| `tests/test_flora.py` (NEW) | test | — | (Wave 0 — confirm `tests/` framework; no direct flora analog) | no-analog |

---

## Pattern Assignments

### `Subsystem/AdamsServer/src/io/FloraModule.cpp` (firmware module, FreeRTOS task)

**Analogs:** `src/io/SensorModule.cpp` (task lifecycle), `src/io/Pca9685Module.cpp` (atomic frame write + mux pattern)

**FreeRTOS static-task pattern** — copy from `SensorModule.cpp:8-54`:
```cpp
namespace {
StaticTask_t sSensorTaskBuffer;
StackType_t sSensorTaskStack[4096];

void sensorTask(void *parameter) {
  (void)parameter;
  while (true) {
    readSensors();
    vTaskDelay(pdMS_TO_TICKS(kSensorPollMs));
  }
}
}  // namespace

void startSensorTask() {
  xTaskCreateStaticPinnedToCore(
    sensorTask,
    "sensor_task",
    sizeof(sSensorTaskStack) / sizeof(StackType_t),
    nullptr,
    1,                       // priority 1 — match for flora (RESEARCH Pattern 1)
    sSensorTaskStack,
    &sSensorTaskBuffer,
    APP_CPU_NUM
  );
}
```
For flora: rename buffers (`sFloraTaskBuffer`/`sFloraTaskStack[4096]`), tick at
`pdMS_TO_TICKS(flora.tick_ms)` ≈ 20 ms (50 Hz), call `floraTick(millis())`
inside the loop. Call `startFloraTask()` from `setup()` in `AdamsServer.ino`
right after `initPca9685()` succeeds.

**Atomic 16-channel frame write** — call this every tick (`Pca9685Module.cpp:117-136`):
```cpp
bool writeAllChannelsRaw(const uint16_t *duties) {
  if (duties == nullptr) return false;
  uint8_t payload[16 * 4] = {};
  for (uint8_t channel = 0; channel < 16; ++channel) {
    fillChannelPayload(duties[channel], payload + (channel * 4));
  }
  if (!writeRegisters(kLed0OnLowReg, payload, sizeof(payload))) return false;  // one I2C burst
  portENTER_CRITICAL(&gRuntimeStateMux);
  for (uint8_t channel = 0; channel < 16; ++channel) {
    gRuntimeState.pca9685Channels[channel] = duties[channel];
  }
  portEXIT_CRITICAL(&gRuntimeStateMux);
  return true;
}
```
Note `gRuntimeState.pca9685Channels[16]` holds last-written duties — use it as
the **crossfade start point** (RESEARCH Pattern 2). Light = ch 0–10, vibro =
ch 11–14 (masks from POST params / `AdamsConfig.h` defaults).

**Mutex-guarded shared state** — the target preset/params struct that the HTTP
handler writes and the task reads. Reuse the existing `gRuntimeStateMux`
(`portMUX_TYPE`) pattern seen throughout `Pca9685Module.cpp`:
```cpp
portENTER_CRITICAL(&gRuntimeStateMux);
// read/write FloraState fields
portEXIT_CRITICAL(&gRuntimeStateMux);
```

**Gamma LUT** (RESEARCH Pattern 3): precompute `static const uint16_t kGammaLut[256]`
at init (`duty = round(4095 * (level/255)^gamma)`, gamma≈2.2) to avoid `pow()`
per frame. No analog — new animation math.

---

### `Subsystem/AdamsServer/src/web/WebServerModule.cpp` (HTTP handler, request-response) — EDIT

**Analog:** `pcaSceneHandler` (same file, lines 2660-2681) — closest by role+flow
(POST + hand-rolled JSON parse + apply + status response).

**Handler skeleton** — mirror `pcaSceneHandler` (`WebServerModule.cpp:2660-2681`):
```cpp
esp_err_t pcaSceneHandler(httpd_req_t *req) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  const bool ready = gRuntimeState.pca9685Ready;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  if (!ready) {
    return sendError(req, "503 Service Unavailable", "{\"error\":\"pca9685_not_ready\"}");
  }

  String body;
  if (!readRequestBody(req, body)) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  }

  String scene;
  if (!extractJsonString(body, "scene", scene) || !applyPca9685Scene(scene.c_str())) {
    return sendError(req, "400 Bad Request", "{\"error\":\"invalid_scene\"}");
  }

  String json;
  buildPcaStatusJson(json);
  return sendJson(req, json);
}
```
For `floraStateHandler`: read `state` via `extractJsonString`, optional params
via `extractJsonInt`/`extractJsonBool`, call `setFloraState(...)`, respond
`sendJson(req, "{\"ok\":true}")`.

**Hand-rolled JSON parse helpers** (`WebServerModule.cpp`) — USE THESE, NOT ArduinoJson:
- `extractJsonString(body, "state", state)` — lines 1078-1098 (scans whole body for first `"state"`)
- `extractJsonInt(body, "base_duty", value)` — lines 1002-1025
- `extractJsonBool(body, "vibro_enabled", flag)` — lines 1053-1076
- `extractJsonFloat(body, "gamma", f)` — lines 1027-1051
- `readRequestBody(req, body)` — line 982, 4096-byte cap (flora payloads tiny)

⚠ Parser is **flat-key** (ignores object boundaries) — keep param keys unique
across the payload; nesting under `"params"` works but the parser won't scope to
it (RESEARCH §Firmware HTTP Endpoint).

**Route registration** — add alongside the PCA routes:
- Declare URIs at `WebServerModule.cpp:2861-2865`:
```cpp
httpd_uri_t pcaSceneUri = makeHttpUri("/api/pca9685/scene", HTTP_POST, pcaSceneHandler);
// add:
httpd_uri_t floraStateUri = makeHttpUri("/api/flora/state", HTTP_POST, floraStateHandler);
```
- Register at `WebServerModule.cpp:2903-2907`:
```cpp
httpd_register_uri_handler(server, &pcaSceneUri);
// add:
httpd_register_uri_handler(server, &floraStateUri);
```
Registers on the **control server (:80)**, same as PCA — not the :81 4-slot pool.

---

### `System/adam/flora.py` (controller: event consumer + RMS streamer) — NEW

**Analogs (composed):**
- `api_runtime.py:521-540` — the canonical `subscribe()`→queue consume loop
- `mic_reader.py:199-243` — long-lived task `start()`/`stop()` lifecycle
- `device.py` MCUClient — ESP HTTP via `_NO_PROXY_OPENER`
- `inference.py` — `wave`/`audioop` for RMS, `_get_wav_bytes_sync`, `_play_wav_bytes_local_sync`

**Event subscribe + consume loop** — copy structure from `api_runtime.py:521-540`:
```python
queue = deps.event_log.subscribe()
async def generator():
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
            # ... handle event ...
    finally:
        deps.event_log.unsubscribe(queue)
```
`EventLog` is a **pub-sub queue, NOT a callback bus** (`events.py:80-89`:
`subscribe()` returns `asyncio.Queue`, `unsubscribe(queue)`). FloraController’s
`_consume()` loops `event = await self._queue.get()`, dispatches on
`event.get("type")`, and always `event_log.unsubscribe(self._queue)` in `finally`.

**Real event → flora-state mapping** (RESEARCH §Pattern 4 — VERIFIED names):
```python
etype = event.get("type")
if etype == "wake_word_detected":            # детекция
    await self._set_state("accent")
elif etype == "voice_state_change":
    to = event.get("payload", {}).get("to")  # payload keys: from / to / reason
    if to == "listening":
        await self._set_state("attentive")   # вибро OFF (D-11)
    elif to == "standby":
        await self._set_state("breathe")     # покой
elif etype == "llm_thinking_started":        # раздумье
    await self._set_state("think_pulse")
elif etype == "tts_started":                 # ответ (state 4) → RMS stream
    await self._start_rms_stream(event)
elif etype == "tts_finished":
    await self._stop_rms_stream()
```
`voice_state_change` payload shape is confirmed at `Orchestrator.py:561-563`:
`{"from": ..., "to": ..., "reason": ...}`. There is no distinct "answer"
voice_state — `tts_started`/`tts_finished` ARE the answer-state boundary.

**Long-lived task lifecycle** — copy from `mic_reader.py:199-243`:
```python
async def start(self) -> None:
    if self._task is not None and not self._task.done():
        return
    self._running = True
    self._task = asyncio.create_task(self._run(), name="adam_mic_reader")
    # ... emit started event ...

async def stop(self) -> None:
    self._running = False
    task = self._task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```
FloraController: `start()` does `self._queue = event_log.subscribe()` +
`create_task(self._consume(), name="flora_consumer")`; `stop()` cancels the
consumer (and any live RMS streamer task) and unsubscribes.

**ESP HTTP via MCUClient** — `device.py:69-78` `set_channels` (batch, already
clamps + routes through `_NO_PROXY_OPENER`):
```python
async def set_channels(self, updates: list[dict[str, Any]]) -> DeviceResult:
    normalized = []
    for item in updates:
        channel = max(self.channel_min, min(self.channel_max, int(item.get("channel", 0))))
        mode = str(item.get("mode", "pwm")).strip() or "pwm"
        value = max(self.value_min, min(self.value_max, int(item.get("value", 0))))
        normalized.append({"channel": channel, "mode": mode, "value": value})
    if not normalized:
        return DeviceResult(False, 400, {}, "updates_required")
    return await asyncio.to_thread(self._request, "POST", "/api/pca9685/channels", {"updates": normalized})
```
RMS frames use `set_channels(...)` for ch 0–10. For `/api/flora/state` POSTs,
add a thin `set_flora_state(state, params)` method on `MCUClient` reusing the
same `self._request("POST", "/api/flora/state", payload)` path — do NOT roll a
new HTTP client (`_NO_PROXY_OPENER` mandatory per CLAUDE.md gotcha).

**RMS envelope from WAV** — `wave` + `audioop` are already imported in
`inference.py` (lines 4, 11; `wave.open` used at line 500). Idiom:
`audioop.rms(window_bytes, sampwidth)` per `frame_interval_ms` window over the
WAV → normalize 0..1 → map to `base_duty_pct(25)..peak_duty_pct(90)` (D-08). No
numpy. WAV source is `tts._get_wav_bytes_sync(text)` (`inference.py:264-272`).

**RMS frame timer** (RESEARCH §RMS Speech Sync): start `t0 = perf_counter()` at
the instant playback is dispatched (`asyncio.to_thread(_play_wav_bytes_local_sync)`),
add `flora.speech.hdmi_latency_offset_ms`, `await asyncio.sleep` per envelope
sample. Cancel the streamer on `tts_finished` / barge-in / any
`voice_state_change→listening|standby`.

---

### `System/Orchestrator.py` (lifespan wiring) — EDIT

**Analog:** the `mic_reader.start()/stop()` block (`Orchestrator.py:1788`, `1807`).

**Start** — add next to `mic_reader.start()` at line ~1788:
```python
await mic_reader.start()
# add:
await flora_controller.start()
```
**Stop** — add in the `finally:` block near line ~1807 (stop before mic_reader
or after — flora only consumes events, ordering is not load-bearing, but stop it
before the session commit):
```python
await mic_reader.stop()
# add:
await flora_controller.stop()
```
Construct `flora_controller` alongside the other singletons (`mic_reader`,
`scene_worker`) with `settings.section("flora")` + the shared `mcu_client` and
`event_log`. No new events need emitting — flora only consumes existing ones
(optionally `event_log.append("flora_state_change", {...})` for diagnostics,
signature at `events.py:32`).

---

### `System/Config.json` + `Config.schema.json` (config section) — EDIT

**Analog:** existing top-level plain sections `mcu` and `media.audio`. Read via
`settings.section("flora")` (`config.py:302`) — the SAME way `MCUClient` reads
`mcu`. **NOT pydantic `tuning`** (RESEARCH §Config-First / Pitfall 6 — `tuning.py`
`Tuning` model is persona-only).

**Pattern reference** — `mcu` section in `Config.json` (plain dict, includes a
`channels` sub-object with min/max clamps) + its documented entry in
`Config.schema.json`. New `flora` section follows the same plain-dict + schema-doc
shape. Proposed shape (planner refines numbers per D-13, RESEARCH §Config-First):
```jsonc
"flora": {
  "enabled": true,
  "light_channels": [0,1,2,3,4,5,6,7,8,9,10],
  "vibro_channels": [11,12,13,14],
  "gamma": 2.2,
  "tick_ms": 20,
  "crossfade_ms": 200,
  "speech": { "frame_interval_ms": 80, "hdmi_latency_offset_ms": 150,
              "base_duty_pct": 25, "peak_duty_pct": 90, "spark_probability": 0.15 },
  "vibro": { "intensity_pct": 30, "silent_states": ["attentive"] },
  "states": { "breathe": {...}, "accent": {...}, "attentive": {...},
              "think_pulse": {...}, "wake_bloom": {...} }
}
```
To give a code-level default, also add `flora` to `DEFAULT_CONFIG` in
`config.py` (`Settings.load()` deep-merges `Config.json` over `DEFAULT_CONFIG`,
`config.py:281-289`). Every numeric value documented in `Config.schema.json`
(English descriptions — matches existing schema convention).

---

## Shared Patterns

### `_NO_PROXY_OPENER` (mandatory for all ESP HTTP)
**Source:** `device.py:14`
**Apply to:** `flora.py` ESP calls — ALWAYS via `MCUClient`, never a fresh client.
```python
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))
# used inside MCUClient._request: _NO_PROXY_OPENER.open(req, timeout=self.timeout)
```
CLAUDE.md gotcha: v2ray (port 10808) leaks sockets → exhausts ESP:81 4-slot
pool. `MCUClient` already bypasses it correctly; reuse it.

### Config-First
**Source:** `config.py:302` `settings.section(name)`
**Apply to:** every flora number (channel masks, gamma, periods, duties, frame
interval, HDMI offset, crossfade, vibro intensity). No hardcoded numerics in
`flora.py` or new firmware logic — firmware structural defaults live in
`AdamsConfig.h`, Jetson-side source of truth in `Config.json flora`.

### Mutex-guarded shared state (firmware)
**Source:** `gRuntimeStateMux` (`portMUX_TYPE`) used in `Pca9685Module.cpp` /
`SensorModule.cpp` throughout.
**Apply to:** the FloraState struct (HTTP handler writes target, task reads).
```cpp
portENTER_CRITICAL(&gRuntimeStateMux); /* touch shared */ portEXIT_CRITICAL(&gRuntimeStateMux);
```

### Atomic multi-channel write (firmware)
**Source:** `Pca9685Module.cpp:117` `writeAllChannelsRaw(duties)` — one 64-byte
I2C burst, no partial-frame tearing.
**Apply to:** every flora animation frame AND the RMS frames (via the existing
`applyPca9685Updates` path the channels handler already uses).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_flora.py` | test | — | No existing flora test; Wave 0 must confirm `tests/` + pytest config exist (RESEARCH §Validation A6). Covers FLORA-03/04/05/06: event→state mapping, WAV→RMS envelope shape, config parse, vibro-muted-in-attentive. Use `wave` in-test to synthesize a known WAV fixture. |
| Gamma LUT math (in `FloraModule.cpp`) | new logic | — | Animation math is net-new (no analog); the LUT *mechanism* is standard but the curves are calibration work. |

---

## Metadata

**Analog search scope:** `Subsystem/AdamsServer/src/{io,web}/`, `System/adam/`,
`System/Orchestrator.py`, `System/Config.json` + `Config.schema.json`
**Files scanned (read):** `SensorModule.cpp`, `Pca9685Module.cpp`,
`WebServerModule.cpp` (handler + parse-helper ranges), `device.py`, `events.py`,
`api_runtime.py` (subscribe loop), `inference.py` (WAV/RMS/playback ranges),
`Orchestrator.py` (lifespan + event emission ranges), `mic_reader.py` (start/stop)
**Pattern extraction date:** 2026-06-04
**Key correction carried forward:** real event names
(`wake_word_detected`/`voice_state_change`/`llm_thinking_started`/`tts_started`/
`tts_finished`) — the CONTEXT names (`oww_detected`/`asr_start`/`llm_start`/
`tts_start`/`tts_end`) DO NOT EXIST in code.
