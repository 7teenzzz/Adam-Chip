# Phase 29: Technoflora Reactions - Research

**Researched:** 2026-06-04
**Domain:** ESP32-S3 firmware animation engine (FreeRTOS + PCA9685 PWM) + Jetson asyncio event layer + RMS audio→light streaming
**Confidence:** HIGH (all symbols verified against actual code; no external library decisions needed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Светофлора — кластер без пространственного порядка. Направленные эффекты (волна / бегущий огонь / цветение 0→10) исключены. Только коллективные и случайно-групповые приёмы: коллективное дыхание, блуждающие вспышки (случайные подмножества каналов), случайное прорастание, коллективный «вдох» к голосу.
- **D-02:** Каналы: свет = 0–10 (11 шт), вибро = 11–14 (4 шт), канал 15 свободен. Маски каналов — в Config.
- **D-03:** Гибрид с уточнением. Фоновые состояния (покой / детекция / слушание / раздумье / пробуждение) — автономные анимации в прошивке ESP по `id + параметры`. Состояние ответа (RMS, состояние 4) — Jetson-driven.
- **D-04:** Технофлора — реактивный слой по событиям пайплайна, подписан на EventBus. Не пересекается с `action.py`.
- **D-05:** Новый эндпоинт прошивки `POST /api/flora/state {state, params}`. Пресеты: `breathe` (покой), `accent` (детекция), `attentive` (слушание), `think_pulse` (раздумье), `wake_bloom` (пробуждение).
- **D-06:** Все 6 состояний сразу в одной фазе, включая RMS-синхронизацию и пробуждение. Не разбиваем на волны.
- **D-07:** Jetson стримит кадры в реальном времени. RMS-огибающая из TTS WAV, аудио (jetson_hdmi) + кадры яркости каналов 0–10 по HTTP батч в такт плейбэку. Потолок ~15 fps. Sync тривиален (один таймер от старта плейбэка); латентность-офсет HDMI-буфера — параметр в Config.
- **D-08:** База яркости речи ~25%, пики ~90%, плюс редкие случайные «искры» на пиках.
- **D-09:** Короткий crossfade ~150–250 мс на переходах. Barge-in мгновенный (свет сразу в слушание).
- **D-10:** НЕ переиспользуем тайминги `scene_director` (sustain/cooldown/hysteresis).
- **D-11:** Вибро — тонкое присутствие, ритмически связана со светом. Молчит в состоянии слушания (моторы наводят вибрацию в INMP441).
- **D-12:** Интенсивность вибро — параметр в Config (по умолчанию сдержанная).
- **D-13:** Все числа — в `System/Config.json` + `Config.schema.json`. Новая секция `flora`.

### Claude's Discretion
- Внутренняя параметризация прошивочного движка (сколько knob'ов наружу vs фиксированные пресеты).
- Точные кривые яркости, периоды, gamma-значения — стартовые дефолты, далее калибруются на железе.
- Формат payload `/api/flora/state` и схема RMS-кадров.

### Deferred Ideas (OUT OF SCOPE)
- RMS через POST массива на ESP (ESP проигрывает по таймеру) — отвергнут в пользу live-стрима с Jetson.
- Связь технофлоры с AIIM/mood — будущая фаза поверх Phase 27.
- Пробуждение по выходу из долгого idle — отдельным триггером позже.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FLORA-01 | ESP animation engine | §ESP Animation Engine — FreeRTOS task `xTaskCreateStaticPinnedToCore` (SensorModule pattern), `writeAllChannelsRaw` per frame, preset state machine, gamma LUT |
| FLORA-02 | POST /api/flora/state endpoint | §Firmware HTTP Endpoint — hand-rolled JSON parse (`extractJsonString`/`extractJsonInt`), register in `WebServerModule.cpp` alongside `/api/pca9685/*` |
| FLORA-03 | Jetson event layer | §Jetson Event Layer — `event_log.subscribe()` → asyncio.Queue consumer task, new `System/adam/flora.py`, lifespan start/stop. REAL event names verified (≠ CONTEXT assumptions) |
| FLORA-04 | RMS speech sync | §RMS Speech Sync — `wave`+`audioop` stdlib envelope, timer parallel to blocking `_play_wav_bytes_local_sync`, `set_channels` batch, HDMI offset |
| FLORA-05 | Config-First params | §Config-First — new top-level `flora` section, `settings.section("flora")`, NOT pydantic tuning |
| FLORA-06 | Vibro policy | §Vibro Policy — channels 11–14 on same PCA9685, mute in listening, NOT subject to `safety.motor_*` |
</phase_requirements>

## Summary

This phase has **zero new external dependencies**. Everything is built on existing in-repo primitives: the ESP32 PCA9685 driver (`writeAllChannelsRaw` — atomic 16-channel I2C burst), the FreeRTOS static-task pattern already used by `SensorModule`/`AudioModule`, the Jetson `MCUClient.set_channels` batch call (already routes through `_NO_PROXY_OPENER`), the `EventLog` pub-sub (`subscribe()` → `asyncio.Queue`), and Python stdlib `wave`+`audioop` (already imported in `inference.py`) for RMS computation. No version research, no library selection.

**The single most important correction to the CONTEXT assumptions:** the event names listed in CONTEXT/ROADMAP (`oww_detected`, `asr_start`, `llm_start`, `tts_start`, `tts_end`) **do not exist in the code.** The real events are `wake_word_detected`, `voice_state_change` (from→to with states `boot_warmup|standby|listening|reply`), `llm_thinking_started`, `tts_started`, `tts_finished`, and `adam_reply`. The flora event layer MUST subscribe to the real names. There is also no distinct "answer" FSM state — TTS playback happens inside `dialogue_turn` while `_voice_state` is still `listening`/`reply`; the `tts_started`/`tts_finished` events are the answer-state boundary, not a voice_state.

**The single biggest technical risk:** the ESP32 `loop()` runs at **4 Hz** (`delay(250)` in `AdamsServer.ino`). A smooth breathing/crossfade animation cannot live there. The animation engine MUST be a dedicated FreeRTOS task ticking at ~30–50 Hz, exactly like `sensorTask`. That task and the existing sensor task both touch the shared `Wire` (I2C) bus — bus contention must be handled (the existing `writeRegisters` already retries 3× on NACK, which softens this, but a tick rate that floods I2C will starve sensor reads).

**Primary recommendation:** Build (1) a firmware `FloraModule` with a static FreeRTOS task running a preset state machine that writes frames via `writeAllChannelsRaw`, plus a `/api/flora/state` handler that swaps the active preset; (2) a Jetson `System/adam/flora.py` `FloraController` that subscribes to `event_log`, maps real events → preset POSTs, and owns the RMS frame streamer for the speech state; (3) a new top-level `flora` config section (plain `settings.section("flora")`, NOT pydantic tuning).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ambient animations (breathe/accent/attentive/think_pulse/wake_bloom) | ESP firmware (FreeRTOS task) | — | D-03: autonomous on ESP by id+params; survives Jetson HTTP jitter; smooth 30–50Hz local tick |
| State transition trigger (which preset is active) | Jetson event layer | ESP endpoint | D-04: Jetson owns pipeline-state knowledge; ESP is a dumb preset player |
| RMS speech brightness (state 4) | Jetson (live frame stream) | ESP raw-channel write | D-07: Jetson owns both audio and light → trivial sync; ESP just writes the duties it receives |
| Crossfade between presets | ESP firmware | — | D-09: ESP interpolates from current duties to new preset over crossfade_ms; lamps inertial anyway |
| Gamma correction | ESP firmware | — | Applied at frame-write time on 12-bit duty; same LUT for autonomous and RMS frames |
| Vibro policy (mute in listening) | Jetson event layer | ESP preset params | D-11: Jetson knows the listening state; passes vibro on/off as preset param |
| Barge-in interrupt | Jetson event layer | — | `tts.interrupt_playback()` exists; flora reacts to the same barge-in by jumping to attentive preset |

## Standard Stack

**No new packages.** Everything is in-repo or stdlib.

### Core (existing primitives reused)
| Symbol | Location | Purpose | Verified |
|--------|----------|---------|----------|
| `writeAllChannelsRaw(const uint16_t* duties)` | `Pca9685Module.cpp:117` | Atomic 16-channel I2C burst — one frame | `[VERIFIED: code]` |
| `applyPca9685Scene(const char*)` | `Pca9685Module.cpp:311` | Existing static-scene apply (engine is a new layer over raw write) | `[VERIFIED: code]` |
| `xTaskCreateStaticPinnedToCore` + `StaticTask_t`/`StackType_t[4096]` | `SensorModule.cpp:10,44` | Template for the flora animation task | `[VERIFIED: code]` |
| `extractJsonString/extractJsonInt/extractJsonBool` | `WebServerModule.cpp:1078,~1020,1053` | Hand-rolled JSON parse used by ALL handlers (NOT ArduinoJson) | `[VERIFIED: code]` |
| `readRequestBody(req, body, maxBytes=4096)` | `WebServerModule.cpp:982` | Read POST body for a handler | `[VERIFIED: code]` |
| `MCUClient.set_channels(updates)` | `device.py:69` | Jetson batch POST to `/api/pca9685/channels` via `_NO_PROXY_OPENER` | `[VERIFIED: code]` |
| `_NO_PROXY_OPENER` | `device.py:14` | Mandatory proxy-bypass opener for ESP HTTP | `[VERIFIED: code]` |
| `event_log.subscribe()` → `asyncio.Queue` | `events.py:80` | Pub-sub for pipeline events (NOT a callback EventBus) | `[VERIFIED: code]` |
| `tts._get_wav_bytes_sync(text)` | `inference.py:264` | Raw WAV bytes (no playback) — RMS source | `[VERIFIED: code]` |
| `tts._play_wav_bytes_local_sync(wav)` | `inference.py:280` | BLOCKING aplay/paplay playback (run via `asyncio.to_thread`) | `[VERIFIED: code]` |
| `tts.interrupt_playback()` | `inference.py:406` | Barge-in kill of aplay Popen | `[VERIFIED: code]` |
| `wave`, `audioop` (stdlib) | imported in `inference.py:4,11` | RMS envelope from WAV — no numpy needed | `[VERIFIED: code]` |
| `settings.section("flora")` | `config.py:302` | Read the new config section | `[VERIFIED: code]` |

### Supporting
| Symbol | Location | Purpose |
|--------|----------|---------|
| `Settings.load()` + `_deep_merge` | `config.py:281` | Config loaded from `DEFAULT_CONFIG` deep-merged with `Config.json` — new section must also be added to `DEFAULT_CONFIG` in config.py if a code default is wanted |
| lifespan `await x.start()` / `await x.stop()` | `Orchestrator.py:1776` | Where `flora_controller` is started/stopped (analog to `mic_reader`, `scene_worker`) |
| `event_log.append(type, payload, turn_id=)` | `events.py:32` | If flora needs to emit diagnostic events |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dedicated FreeRTOS animation task | Tick inside `loop()` | REJECTED — `loop()` runs at 4 Hz (`delay(250)`); unusable for smooth animation |
| stdlib `wave`+`audioop` for RMS | numpy | numpy works but is heavier and `audioop.rms` is already the project idiom (`mic_reader.py:500`, `inference.py`). Stdlib wins. |
| Plain `flora` config section | pydantic `tuning.flora` | Plain section is correct — flora params are infra/calibration, not persona tuning. `tuning.py` is for persona behavior. See §Config-First. |
| Live RMS stream from Jetson | POST RMS array to ESP | REJECTED in CONTEXT (D-07, deferred). Do not implement ESP-side RMS. |

## Architecture Patterns

### System Architecture Diagram

```
  VOICE PIPELINE EVENTS (Orchestrator.py, real names)
  ┌─────────────────────────────────────────────────────────────┐
  │ wake_word_detected → voice_state_change(standby→listening)   │
  │ asr_request / asr_result / asr_final                         │
  │ llm_thinking_started                                          │
  │ tts_started ──────────────────► (answer state begins)        │
  │ tts_finished ─────────────────► (answer state ends)          │
  │ voice_state_change(*→standby)                                │
  └───────────────┬─────────────────────────────────────────────┘
                  │ event_log.subscribe() → asyncio.Queue
                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ System/adam/flora.py  :  FloraController (asyncio task)      │
  │  - consumes event queue, maps event → flora state            │
  │  - debounces / applies state precedence (barge-in immediate) │
  │  ┌──────────────────────────┐   ┌────────────────────────┐  │
  │  │ ambient state path        │   │ SPEECH state path       │ │
  │  │ POST /api/flora/state     │   │ RMS frame streamer      │ │
  │  │ {state, params}           │   │ wave+audioop → envelope │ │
  │  │ (one POST per transition) │   │ timer ∥ blocking aplay  │ │
  │  └────────────┬─────────────┘   └───────────┬────────────┘  │
  └───────────────┼──────────────────────────────┼──────────────┘
                  │ MCUClient (_NO_PROXY_OPENER)  │ set_channels batch
                  │ POST /api/flora/state          │ ~10–15 fps, ch 0–10
                  ▼                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ ESP32-S3 firmware (HTTP server task, port 80)               │
  │  floraStateHandler → parse → set active preset + params      │
  │  pcaChannelsHandler (existing) → applyPca9685Updates         │
  └───────────────┬─────────────────────────────────────────────┘
                  │ shared gRuntimeState + Wire (I2C) bus
                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ FloraModule animation task (NEW, xTaskCreateStaticPinned)   │
  │  ~30–50 Hz tick:                                             │
  │   state machine: breathe/accent/attentive/think_pulse/      │
  │                  wake_bloom/idle                             │
  │   crossfade interpolation (current → target duties)          │
  │   gamma LUT → writeAllChannelsRaw(duties[16])                │
  │   light = ch 0–10, vibro = ch 11–14 (masks from POST params) │
  └─────────────────────────────────────────────────────────────┘
            ▲ I2C bus shared with sensorTask (contention risk)
            └── PCA9685 @ 0x40, 1000 Hz, 12-bit (0–4095)
```

### Pattern 1: ESP Animation Engine as a FreeRTOS Task
**What:** A static FreeRTOS task pinned to `APP_CPU_NUM`, ticking at a fixed rate, running a preset state machine, writing one frame per tick via `writeAllChannelsRaw`.
**When to use:** Required for all autonomous states (D-03).
**Template (verified pattern from `SensorModule.cpp`):**
```cpp
// Source: SensorModule.cpp:10,18-24,43-54 (VERIFIED)
namespace {
  StaticTask_t sFloraTaskBuffer;
  StackType_t  sFloraTaskStack[4096];

  void floraTask(void *parameter) {
    (void)parameter;
    const TickType_t period = pdMS_TO_TICKS(20);  // ~50 Hz; flora.tick_ms in Config
    while (true) {
      floraTick(millis());                 // compute + writeAllChannelsRaw
      vTaskDelay(period);
    }
  }
}

void startFloraTask() {
  xTaskCreateStaticPinnedToCore(
    floraTask, "flora_task",
    sizeof(sFloraTaskStack) / sizeof(StackType_t),
    nullptr, 1,                            // priority 1, same as sensorTask
    sFloraTaskStack, &sFloraTaskBuffer, APP_CPU_NUM);
}
```
Call `startFloraTask()` from `setup()` in `AdamsServer.ino` right after `initPca9685()` succeeds.

### Pattern 2: Preset + crossfade state held in a mutex-guarded struct
**What:** The HTTP handler writes the target preset/params; the animation task reads it and interpolates. Use `gRuntimeStateMux` (the existing `portMUX_TYPE`) or a dedicated mux. `gRuntimeState.pca9685Channels[16]` already holds last-written duties — the crossfade start point.
**Example shape (Claude's discretion on exact fields):**
```cpp
struct FloraState {
  char     preset[16];       // "breathe" | "accent" | "attentive" | ...
  uint16_t base_duty;        // per-state, 0–4095
  uint16_t peak_duty;
  uint32_t period_ms;        // breathing period
  uint32_t crossfade_ms;     // D-09: 150–250
  bool     vibro_enabled;    // D-11: false in listening
  uint16_t vibro_duty;       // D-12
  uint8_t  light_mask_lo, light_mask_hi;  // 0–10
  uint8_t  vibro_mask_lo, vibro_mask_hi;  // 11–14
};
```

### Pattern 3: Gamma correction via a precomputed 256→4095 LUT
**What:** Edison lamps + human perception are non-linear. Map a 0..255 animation level through `duty = round(4095 * (level/255)^gamma)` with gamma≈2.2 (D-13). Precompute a `static const uint16_t kGammaLut[256]` at build time (or fill once at init) to avoid `pow()` per frame.
**Why a LUT:** at 50 Hz × 16 channels = 800 `pow()` calls/sec is wasteful on the ESP; a LUT is O(1).

### Pattern 4: Jetson event consumer (the real EventBus pattern)
**What:** `events.py` is NOT a callback bus. It is `EventLog` with `subscribe()` returning an `asyncio.Queue`. The canonical consumer is in `api_runtime.py:521-547` (SSE generator). FloraController copies this loop.
**Example:**
```python
# Source: api_runtime.py:521-540 (VERIFIED pattern)
class FloraController:
    async def start(self):
        self._queue = event_log.subscribe()
        self._task = asyncio.create_task(self._consume(), name="flora_consumer")

    async def _consume(self):
        try:
            while True:
                event = await self._queue.get()
                await self._handle(event)
        finally:
            event_log.unsubscribe(self._queue)

    async def _handle(self, event: dict):
        etype = event.get("type")
        if etype == "wake_word_detected":
            await self._set_state("accent")          # детекция
        elif etype == "voice_state_change":
            payload = event.get("payload", {})
            if payload.get("from") == "boot_warmup":
                await self._set_state("wake_bloom")  # пробуждение (boot-exit, Open Q1 RESOLVED)
            else:
                to = payload.get("to")
                if to == "listening":
                    await self._set_state("attentive")   # вибро OFF (D-11)
                elif to == "standby":
                    await self._set_state("breathe")     # покой
        elif etype == "llm_thinking_started":
            await self._set_state("think_pulse")     # раздумье
        elif etype == "tts_started":
            await self._on_answer_start(event)       # ответ (state 4); plan 04 RMS via feed_speech_wav
        elif etype == "tts_finished":
            await self._stop_rms_stream()
```
Start/stop in `lifespan` next to `mic_reader` (`Orchestrator.py:1788` / `1807`).

### Recommended Project Structure
```
System/adam/
  flora.py              # NEW: FloraController (event consumer + RMS streamer)
Subsystem/AdamsServer/src/io/
  FloraModule.cpp       # NEW: animation task + state machine + gamma LUT
  FloraModule.h         # NEW: startFloraTask(), setFloraState(...)
Subsystem/AdamsServer/src/web/
  WebServerModule.cpp   # EDIT: floraStateHandler + register /api/flora/state
System/
  Config.json           # EDIT: add "flora" section
  Config.schema.json    # EDIT: document "flora" section
```

### Anti-Patterns to Avoid
- **Putting animation in `loop()`:** 4 Hz tick (`AdamsServer.ino:146 delay(250)`) — far too coarse. Use a FreeRTOS task.
- **Using ArduinoJson in the new handler:** the codebase parses JSON by hand (`extractJsonString` etc.). `kPcaJsonCapacity` exists but is unused for parsing. Match the existing style for consistency.
- **Bypassing `_NO_PROXY_OPENER`:** any `urllib`/`httpx` call to the ESP that goes through the v2ray proxy leaks sockets and exhausts the ESP:81 4-slot pool (CLAUDE.md gotcha). `MCUClient` already handles this — use it, don't roll a new HTTP client.
- **Driving RMS frames from a separate process clock:** the playback thread is the clock. Start the RMS frame timer at the same instant `to_thread(_play_wav_bytes_local_sync)` is dispatched (D-07: "один таймер от старта плейбэка").
- **Applying `safety.motor_*` clamps to vibro:** those are for `action.py` motor commands (duration/cooldown). Vibro here is continuous PWM presence, not a timed actuation. See §Vibro Policy.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP to ESP | New requests/httpx client | `MCUClient.set_channels` / new method on `MCUClient` | `_NO_PROXY_OPENER` + channel clamping already correct; new client would re-leak sockets |
| Event subscription | Polling `event_log.tail()` | `event_log.subscribe()` queue | Push-based, no missed events, matches `api_runtime.py` |
| WAV→RMS envelope | Manual byte unpacking | `wave.open()` + `audioop.rms(frame, width)` | stdlib, already the project idiom (`mic_reader.py:500`) |
| Atomic multi-channel write (firmware) | 16× `writeChannelRaw` | `writeAllChannelsRaw(duties)` | One I2C burst (64 bytes), no partial-frame tearing |
| FreeRTOS task boilerplate | `new`/dynamic task | `xTaskCreateStaticPinnedToCore` + static buffers | Project standard (Sensor/Audio/Camera); no heap fragmentation |
| Resample for ESP speaker | (N/A here) | already handled in `_prepare_wav_for_esp32_speaker` | flora targets jetson_hdmi for audio; light is separate |

**Key insight:** This phase is almost entirely **wiring existing primitives together**. The temptation is to write new HTTP/event/audio machinery; every one of those already exists and has subtle correctness baked in (proxy bypass, socket limits, atomic I2C). New code = animation math + state mapping only.

## RMS Speech Sync (FLORA-04) — detailed design

The playback path is **blocking** (`_play_wav_bytes_local_sync` → `subprocess.Popen(...).wait()`), already wrapped in `asyncio.to_thread` by the consumer (`Orchestrator.py:2854,2878,2903,2931`). The RMS streamer runs as a **parallel asyncio task** on the same event loop.

**Recommended approach (precompute envelope, drive by wall clock):**
1. On `tts_started`, the FloraController already has (or fetches) the WAV bytes. Note: in the streaming consumer, WAV is synthesized per-chunk via `_get_wav_bytes_sync` (`Orchestrator.py:2888`). The cleanest hook is to compute the RMS envelope **from the same WAV bytes** that get played, at the moment of playback dispatch.
2. Compute a downsampled envelope offline: `wave.open(BytesIO(wav))`, read frames in windows of e.g. `frame_interval_ms` (≈66 ms → ~15 fps), `audioop.rms(window, sampwidth)` per window → list of levels. Normalize to 0..1, map to `base_duty(25%)..peak_duty(90%)` (D-08).
3. Start a wall-clock timer `t0 = perf_counter()` at the instant playback is dispatched. Add `flora.hdmi_latency_offset_ms` (D-07 Config param) so light leads/lags to match what the listener hears (HDMI/ALSA buffer drains after the subprocess returns control).
4. Frame loop: for each envelope sample at time `t`, `await asyncio.sleep` until `t0 + t + offset`, then `MCUClient.set_channels([{channel, value} for ch 0..10])` with the duty, plus occasional random "sparks" on peaks (D-08) — boost a random subset to ~peak for one frame.
5. On `tts_finished` or barge-in, cancel the streamer task immediately and hand back to `attentive`/`breathe`.

**Feasibility of 15 fps over HTTP:** `set_channels` is one POST → `applyPca9685Updates` → one `writeAllChannelsRaw` (single 64-byte I2C burst at 100 kHz ≈ 5–6 ms on the bus). The bottleneck is HTTP round-trip over the W5500 crossover link, not I2C. 10–15 fps (66–100 ms/frame) is realistic; the lamps' thermal inertia (CONTEXT) smooths the visible result, so dropping the occasional frame is invisible. **Recommend default `frame_interval_ms ≈ 80` (12.5 fps)** with the planner free to tune. Use a single persistent... note: `MCUClient._request` opens a fresh connection per call (`_NO_PROXY_OPENER.open`); at 12 fps that is 12 connects/sec to ESP:80 (the control server, NOT the 4-slot :81 audio pool — different server, see `WebServerModule.cpp:2861-2865` register on the control server). This is acceptable but the planner should confirm the ESP control server handles ~12 short-lived connections/sec without exhausting `LWIP` sockets (project memory: `CONFIG_LWIP_MAX_SOCKETS=16`).

**Barge-in path (D-09):** `tts.interrupt_playback()` (`inference.py:406`) kills aplay. Whatever cancels the turn (CancelledError in `_stream_llm_and_speak`, `Orchestrator.py:2953`) is the same signal flora needs — subscribe to the `voice_state_change → listening` that follows, OR have the controller cancel its RMS task on any non-tts event arriving mid-stream. Recommend: RMS streamer is cancelled the moment a `voice_state_change` to `listening`/`standby` or a new `wake_word_detected` arrives.

## Common Pitfalls

### Pitfall 1: Wrong event names (CONTEXT/ROADMAP are aspirational, not actual)
**What goes wrong:** Subscribing to `oww_detected`/`asr_start`/`llm_start`/`tts_start`/`tts_end` — none exist; flora never reacts.
**Why:** CONTEXT D-04 and ROADMAP §29 list intended/abstract names; the code uses different ones.
**How to avoid:** Use the VERIFIED real names: `wake_word_detected`, `voice_state_change`(payload `from`/`to`), `llm_thinking_started`, `tts_started`, `tts_finished`, `adam_reply`.
**Warning signs:** Flora stuck in one state; no `set_state` POSTs in logs.

### Pitfall 2: Animation in the 4 Hz main loop
**What goes wrong:** Breathing looks like a 4-step staircase; crossfades jump.
**Why:** `AdamsServer.ino:146` `delay(250)`.
**How to avoid:** Dedicated FreeRTOS task at 20–30 ms tick.

### Pitfall 3: I2C bus contention between flora task and sensor task
**What goes wrong:** Sensor reads NACK, or flora frames stutter, under high tick rate.
**Why:** Both `sensorTask` (reads light/motion, `kSensorPollMs=100`) and the flora task share the single `Wire` bus. `writeRegisters` retries 3× with 2 ms delays on NACK (`Pca9685Module.cpp:48-58`) — a collision adds up to 6 ms latency.
**How to avoid:** Keep flora tick ≤ 50 Hz; consider a lightweight bus mutex if stutter appears, or pin flora and sensor to the same core so they cooperatively schedule. Sensor poll is only 10 Hz, so headroom exists. Flag for hardware calibration.
**Warning signs:** `sensorsReady` flapping; PWM glitches.

### Pitfall 4: Vibro coupling into the microphone during listening
**What goes wrong:** Motors on ch 11–14 vibrate the chassis → INMP441 picks it up → corrupts ASR.
**Why:** Physical coupling (D-11).
**How to avoid:** `attentive` preset MUST set `vibro_enabled=false`. The Jetson controller passes this; the ESP must honor it (zero ch 11–14). Belt-and-suspenders: also zero vibro on the ESP whenever preset==attentive regardless of param.
**Warning signs:** ASR accuracy drops when lamps/vibro active.

### Pitfall 5: HDMI latency makes light lead the audio
**What goes wrong:** Light pulses ~200–300 ms before the sound is heard (ALSA/HDMI buffer drains after subprocess returns).
**Why:** `aplay` buffers; `_play_wav_bytes_local_sync` returns when the process exits, but on HDMI HDA there's residual buffer latency.
**How to avoid:** `flora.hdmi_latency_offset_ms` Config param (D-07). Start with ~150 ms and calibrate on hardware.
**Warning signs:** Subjective desync; calibrate by eye/ear.

### Pitfall 6: Config section placed in `tuning` (pydantic) by mistake
**What goes wrong:** Validation errors, or flora params coupled to persona hot-reload semantics.
**Why:** `tuning.py` `Tuning` root model has fixed fields; adding `flora` there requires a new pydantic model and touches persona machinery.
**How to avoid:** Add a **plain top-level `flora` section**, read via `settings.section("flora")`. See §Config-First.

## Config-First (FLORA-05)

**Decision: new top-level `flora` section, plain dict, NOT pydantic tuning.** Rationale: `tuning.py`'s `Tuning` model (`tuning.py:166`) is exclusively persona/behavior (memory, echoes, voice, prompt). Flora params are infrastructure/hardware calibration — same tier as `services`, `mcu`, `safety`. Read with `settings.section("flora")` (`config.py:302`), matching how `MCUClient` reads `mcu`.

**Hot-reload note:** Plain sections are read at construction/start. If live re-tuning during calibration is wanted, FloraController can re-call `settings.section("flora")` per transition (cheap) or subscribe to config changes. `Settings.load()` deep-merges `Config.json` over `DEFAULT_CONFIG` (`config.py:286-289`), so to give a code-level default also add `flora` to `DEFAULT_CONFIG` in `config.py`.

**Proposed `flora` section shape (planner refines exact numbers — Claude's discretion per D-13):**
```jsonc
"flora": {
  "enabled": true,
  "light_channels": [0,1,2,3,4,5,6,7,8,9,10],   // D-02
  "vibro_channels": [11,12,13,14],              // D-02
  "gamma": 2.2,                                  // D-13
  "tick_ms": 20,                                 // ESP animation task period (informational; lives in firmware Config too)
  "crossfade_ms": 200,                           // D-09 (150–250)
  "speech": {
    "frame_interval_ms": 80,                     // ~12.5 fps (D-07)
    "hdmi_latency_offset_ms": 150,               // D-07
    "base_duty_pct": 25,                          // D-08
    "peak_duty_pct": 90,                          // D-08
    "spark_probability": 0.15                     // D-08 random sparks on peaks
  },
  "vibro": {
    "intensity_pct": 30,                          // D-12 restrained default
    "silent_states": ["attentive"]                // D-11
  },
  "states": {
    "breathe":     { "base_pct": 8,  "peak_pct": 30, "period_ms": 7000, "vibro": false },
    "accent":      { "peak_pct": 75, "attack_ms": 250, "vibro": true,  "vibro_pulse_ms": 120 },
    "attentive":   { "plateau_pct": 40, "vibro": false },
    "think_pulse": { "base_pct": 20, "flash_count": "random_subset", "flash_ms": 1750, "vibro": "double_pulse" },
    "wake_bloom":  { "from_dark": true, "bloom_ms": "random", "settle_to": "breathe", "vibro": true }
  }
}
```
Note: ESP firmware also needs its own copy of structural defaults (channel masks, gamma LUT) in `AdamsConfig.h` since the firmware boots independently. The Config.json `flora` section is the Jetson-side source of truth that gets pushed to the ESP via `/api/flora/state` params. Keep them consistent; document the duplication.

## Firmware HTTP Endpoint (FLORA-02)

Register exactly like the PCA handlers (`WebServerModule.cpp:2861-2865, 2903-2907`):
```cpp
// In startWebServer(), alongside pca routes:
httpd_uri_t floraStateUri = makeHttpUri("/api/flora/state", HTTP_POST, floraStateHandler);
httpd_register_uri_handler(server, &floraStateUri);
```
Handler skeleton (mirrors `pcaSceneHandler`, `WebServerModule.cpp:2660`):
```cpp
esp_err_t floraStateHandler(httpd_req_t *req) {
  // (optional) gate on gRuntimeState.pca9685Ready like pca handlers
  String body;
  if (!readRequestBody(req, body)) return sendError(req, "400 Bad Request", "{\"error\":\"invalid_request_body\"}");
  String state;
  if (!extractJsonString(body, "state", state)) return sendError(req, "400 Bad Request", "{\"error\":\"missing_state\"}");
  // extract optional params via extractJsonInt/extractJsonBool: base_duty, peak_duty, period_ms, crossfade_ms, vibro_enabled, vibro_duty
  if (!setFloraState(state.c_str(), /*parsed params*/)) return sendError(req, "400 Bad Request", "{\"error\":\"invalid_flora_state\"}");
  return sendJson(req, "{\"ok\":true}");
}
```
`setFloraState` (in FloraModule) writes the target into the mutex-guarded `FloraState`; the animation task picks it up next tick and crossfades. **JSON parse style: hand-rolled `extractJson*` helpers** (do NOT introduce ArduinoJson). Body cap is 4096 bytes (`readRequestBody` default) — flora payloads are tiny, fine.

**Payload schema (Claude's discretion, D-05):**
```json
{ "state": "think_pulse",
  "params": { "base_duty": 800, "peak_duty": 3000, "period_ms": 1750,
              "crossfade_ms": 200, "vibro_enabled": true, "vibro_duty": 1200 } }
```
Note the hand-rolled parser is flat-key (`extractJsonInt(body, "base_duty", ...)` scans the whole body for the first `"base_duty"`), so nesting under `"params"` works but the parser ignores object boundaries — keep keys unique. Simplest: flatten to top-level keys, or rely on uniqueness. Planner decides.

## Vibro Policy (FLORA-06)

- Channels **11–14** are vibration motors on the **same PCA9685** as the lights — same `writeAllChannelsRaw` burst, same duty range 0–4095, same gamma considerations (though gamma for motors is about perceived amplitude, may want a separate/linear curve — flag for calibration).
- `safety.motor_default_duration_ms` / `motor_max_duration_ms` / `motor_cooldown_ms` (`Config.json safety`) are enforced by **`action.py`** for LLM-issued motor commands. Technoflora does NOT route through `action.py` (D-04) and is **not subject to those clamps** — vibro here is low-amplitude continuous "presence," not a timed actuation. Confirmed by CONTEXT line 134 ("технофлора не использует motor safety напрямую"). Recommend a separate `flora.vibro.intensity_pct` ceiling instead.
- **Silent in listening (D-11):** mandatory. `attentive` preset → ch 11–14 = 0. Enforce on BOTH tiers (Jetson sends `vibro_enabled=false`; ESP zeroes vibro when preset==attentive). This protects ASR from motor→mic coupling.
- Vibro rhythm "follows the light" (D-11): drive vibro from the same animation phase as the light breathing (e.g., vibro pulse at each breath peak), computed in the same firmware tick.

## Runtime State Inventory

> This is primarily new-feature work, but it adds firmware behavior and an ESP boot scene change.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — flora has no persisted state. ESP NVS stores `pca9685` freq/scene (`Pca9685Module.cpp:14-30`); flora preset is runtime-only (not persisted) unless planner chooses to. | None (recommend NOT persisting flora preset — it's driven by live pipeline state) |
| Live service config | ESP boot scene `test_all` (71% all-on, `AdamsConfig.h:115`) is diagnostic. CONTEXT specifies `wake_bloom` replaces it for exhibition. | Decide boot behavior: keep `test_all` for diagnostics OR have firmware boot into flora idle/`breathe`. Flag for planner. |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | Firmware is rebuilt+flashed (PlatformIO, `pio run` + `flash_com7.ps1`/`flash_ota.ps1`). New `FloraModule.cpp` must be in the build. | Add file; PlatformIO globs `src/` automatically — verify. Flash via OTA to 192.168.0.171 (Wi-Fi) or COM7 (USB). |

**Note:** Firmware change requires a flash. The ESP control IP for OTA is `192.168.0.171` (Wi-Fi setup net); the runtime Ethernet IP is `10.10.10.171` (`AdamsConfig.h:49`, used by `mcu.base_url` in Config.json = `http://10.10.10.171`). Jetson talks flora over the Ethernet IP at runtime.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PlatformIO | Firmware build/flash | Assumed (dev machine) | — | — (must have to flash ESP) |
| `wave`, `audioop` | RMS envelope | ✓ (stdlib, imported in inference.py) | py3 stdlib | — |
| ESP32 control HTTP @ 10.10.10.171:80 | flora state POST + RMS frames | ✓ at runtime (W5500 crossover) | — | flora degrades silently if ESP down (MCUClient returns ok=False) |
| aplay/paplay (Jetson HDMI) | Audio playback (already used) | ✓ (production) | — | — |

**Note on `audioop`:** deprecated in Python 3.11, slated for removal in 3.13 (PEP 594). The project already depends on it heavily (`inference.py`, `mic_reader.py`, `api_runtime.py`), so this introduces no NEW risk, but if the Jetson ever moves to py3.13 the whole audio stack needs migration — out of scope here. `[VERIFIED: code uses audioop in 4 modules]` `[CITED: PEP 594]`

## Validation Architecture

> `.planning/config.json` not checked for `nyquist_validation`; including by default. Firmware has no host test framework (PlatformIO native tests not present in repo) — most validation is on-hardware + Jetson-side unit tests.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Jetson Python side); firmware = on-hardware manual + curl |
| Config file | check `tests/` dir + `pytest.ini`/`pyproject.toml` (Wave 0: confirm) |
| Quick run command | `pytest tests/ -x` (confirm path) |
| Firmware check | `curl --noproxy '*' -X POST http://10.10.10.171/api/flora/state -d '{"state":"breathe"}'` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLORA-02 | `/api/flora/state` accepts valid state, rejects invalid | integration (on-HW) | `curl ... /api/flora/state` → 200/400 | ❌ Wave 0 (manual) |
| FLORA-03 | event→state mapping (incl. wake_bloom on boot-exit) | unit | `pytest tests/test_flora.py::test_event_mapping tests/test_flora.py::test_wake_bloom_on_boot_exit` | ❌ Wave 0 |
| FLORA-04 | WAV→RMS envelope shape + per-chunk feed | unit | `pytest tests/test_flora.py::test_rms_envelope` (feed known WAV, assert level count/range) | ❌ Wave 0 |
| FLORA-05 | config section parses, defaults present | unit | `pytest tests/test_flora.py::test_flora_config` | ❌ Wave 0 |
| FLORA-06 | vibro muted in attentive | unit | `pytest tests/test_flora.py::test_vibro_silent_listening` | ❌ Wave 0 |
| FLORA-01 | animation smoothness, crossfade | manual (on-HW) | visual inspection + scope on a channel | N/A manual |

### Sampling Rate
- **Per task commit:** `pytest tests/test_flora.py -x`
- **Per wave merge:** full `pytest tests/`
- **Phase gate:** Jetson tests green + on-hardware visual sign-off (6 states observed) before verify.

### Wave 0 Gaps
- [ ] `tests/test_flora.py` — covers FLORA-03/04/05/06 (event mapping, wake_bloom boot-exit, RMS envelope, config, vibro policy)
- [ ] Test fixture: a small known WAV for RMS envelope assertions (or synthesize via `wave` in-test)
- [ ] Confirm pytest config/location in repo (Wave 0 discovery)
- [ ] Firmware: no host unit framework — FLORA-01/02 validated on-hardware via curl + visual

## Security Domain

> `security_enforcement` not set in config; treating as low-risk LAN-internal feature.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | ESP handler validates `state` against known presets, clamps duties 0–4095 (existing `constrain`, `min<uint16_t>(4095, ...)`); reject unknown states with 400 |
| V2 Authentication | no | LAN-isolated crossover link (10.10.10.0/24), no L3 routing (`AdamsConfig.h:46`); ESP API is unauthenticated by design (same as existing `/api/pca9685/*`) |
| V6 Cryptography | no | No secrets in flora path |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed flora payload crashes handler | DoS | `readRequestBody` 4096-byte cap; bounds-check channel/duty; reject unknown state (mirror existing pca handlers) |
| Vibro driven to max → mechanical/acoustic harm | Tampering | `flora.vibro.intensity_pct` ceiling clamp in firmware regardless of requested duty |
| ESP socket exhaustion from RMS frame rate | DoS (self-inflicted) | Frame rate ≤ ~15 fps on control server :80; `LWIP_MAX_SOCKETS=16` headroom; short-lived connections close promptly |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ESP control server (:80) handles ~12 short-lived connections/sec for RMS frames without LWIP socket exhaustion | RMS Speech Sync | If wrong, frames drop or ESP wedges; mitigation = lower fps or keep-alive. Calibrate on HW. |
| A2 | HDMI/ALSA buffer latency ≈150 ms (starting offset) | Pitfall 5 / Config | Pure starting guess; D-07 says calibrate on hardware. Wrong value = visible desync only, not a failure. |
| A3 | A 50 Hz flora task + 10 Hz sensor task coexist on the I2C bus without harmful contention | Pitfall 3 | If wrong, sensor flapping / PWM glitches; mitigation = bus mutex or lower tick. On-HW verify. |
| A4 | PlatformIO auto-globs `src/**` so new FloraModule.cpp is compiled without manifest edit | Runtime State Inventory | If wrong, link error at build — caught immediately, trivial fix. |
| A5 | Linear duty for vibro motors (vs gamma for lights) is acceptable | Vibro Policy | Perceived amplitude curve for motors differs from light; calibrate. Low risk (subjective). |
| A6 | pytest is the Jetson test framework and `tests/` exists | Validation | Wave 0 must confirm; if absent, FLORA-03..06 tests need framework bootstrap. |

## Open Questions

1. **ESP boot behavior for flora** — **(RESOLVED)**
   - What we know: current boot scene is diagnostic `test_all` (71% all-on); CONTEXT says `wake_bloom` replaces it for exhibition.
   - What was unclear: should firmware boot directly into `breathe`/idle, or wait for Jetson to POST the first state? Boot before network = no Jetson commands yet. And where does the `wake_bloom` preset get triggered from the Jetson side (checker WARNING 3)?
   - **Decision:** SPLIT across the two tiers. (a) Firmware (plan 01 Task 2) boots into a quiet `idle`/`breathe` autonomous preset — never dark or `test_all`-glaring before Jetson connects; `test_all` stays reachable for diagnostics. (b) The Jetson `FloraController` (plan 03 Task 2) maps `wake_bloom` to the FIRST `voice_state_change` whose `from == "boot_warmup"` — i.e. the moment the pipeline leaves boot and "comes alive". A one-shot `_booted` flag ensures it fires once on boot-exit, then normal mapping resumes; subsequent standby transitions → `breathe`. This makes `wake_bloom` both a real firmware preset AND a Jetson-triggered cinematic state (not firmware-boot-only), satisfying D-05/D-06. Long-idle re-bloom remains deferred (CONTEXT Deferred Ideas).

2. **Where exactly to compute the RMS envelope in the streaming TTS path** — **(RESOLVED)**
   - What we know: streaming consumer synthesizes WAV per-chunk (`Orchestrator.py:2888`); non-streaming `_speak` uses `tts.speak` (Silero plays internally, WAV not exposed). The `tts_started` event payload is `{"text":"(streaming)"}` — it NEVER carries WAV bytes, so a controller on the event queue cannot see the audio (checker BLOCKER 1).
   - What was unclear: how the FloraController gets the played WAV bytes for a precise RMS envelope.
   - **Decision:** per-chunk push, not event payload. `_consumer` (`Orchestrator.py` ~2878/2903/2931) calls `flora_controller.feed_speech_wav(wav)` at the SAME instant it dispatches `await asyncio.to_thread(tts._play_wav_bytes_sync, wav)`, for each of the three playback-dispatch sites (plan 04 Task 3). This makes the WAV a GUARANTEED RMS input matching the existing chunked playback and keeps D-07 single-timer-per-chunk sync (a per-reply single envelope would desync from chunked playback — rejected). The feed is best-effort/guarded so a flora error never breaks TTS (Action-failure-≠-silence invariant). The `/speak` non-streaming path exposes no WAV (Silero plays through its own ALSA) — it degrades to a generic `attentive`-style pulse with no precise sync, and that is the ONLY degraded path. RMS speech-light requires `output_target=jetson_hdmi` AND the streaming consumer path (the production path with `generate_streaming`).

3. **One persistent HTTP connection vs per-frame connect for RMS stream**
   - What we know: `MCUClient._request` opens a fresh `_NO_PROXY_OPENER.open` per call.
   - What's unclear: whether a keep-alive/session to ESP:80 is worth adding for the frame burst.
   - Recommendation: start with per-frame (simplest, proven); if HW shows socket pressure (A1), add a keep-alive flora method on `MCUClient`. Don't optimize pre-emptively.
