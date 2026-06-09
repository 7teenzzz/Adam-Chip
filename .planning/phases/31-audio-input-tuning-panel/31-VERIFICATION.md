# Phase 31 — Verification Log

Status legend:
- **DONE-AUTOMATED** — verified by static/structural analysis (code review, syntax check, API-contract cross-check) without running the live audio/UI stack.
- **PENDING-HUMAN-LIVE-TEST** — requires a human operator with a working microphone, browser, and the running orchestrator (`autonomous: false` — this phase explicitly needs live audio + UI judgement that cannot be automated from this environment).

This log covers Wave 3 (Tasks 5-7: frontend operator panel). Wave 1/2 backend
truths (DSP engine wiring, fail-safe bypass logic, preset CRUD persistence,
WS monitor stream) were verified during their own waves; here we verify that
the **frontend correctly drives that backend** and that the resulting
end-to-end behaviour matches the `must_haves.truths` in `31-PLAN.md`.

---

## 1. Bypass test (master DSP toggle → raw passthrough)

**Truth (D-04):** "Мастер-тумблер DSP=off → чистый passthrough (сырой PCM), голосовой цикл работает как до фазы (bypass)"

- **DONE-AUTOMATED** — UI wiring confirmed:
  - `buildEqSection()` renders a master checkbox bound to `tuning.audio_input.dsp.enabled`, labelled "Входной DSP активен (мастер-тумблер)" with explicit helper text: *"выкл → bypass: сырой PCM идёт в OWW/ASR/монитор как до этой фазы (D-04)"* (`audioInput.js:236-239`).
  - Toggling it calls `patchDsp({ enabled })` → `PUT /api/tuning` with `{ audio_input: { dsp: { enabled } } }`, which `TuningStore.apply_patch()` deep-merges and validates via the `AudioInputTuning`/`InputDspTuning` pydantic models (Wave 1, `tuning.py`).
  - On failure the checkbox optimistically reverts (`masterToggle.checked = !masterToggle.checked`) and surfaces a toast — no silent UI/backend desync.
- **PENDING-HUMAN-LIVE-TEST** — Confirm in the browser that:
  1. Flipping the master toggle OFF makes the "Слушать микрофон" monitor sound *raw/unprocessed* immediately (no HPF roll-off, no EQ colouration), and the spectrum widget shows the un-equalised input.
  2. Wake word "адам" still triggers reliably with DSP OFF (i.e. the voice loop genuinely runs the pre-Phase-31 code path, not a degraded one).
  3. Flipping it back ON re-applies the curve live, no restart needed.

---

## 2. Per-stage A/B toggles (HPF + each EQ band independently)

**Truth (D-04):** "Каждая полоса EQ + HPF + gain-стадия имеет независимый enabled-флаг; выключение одной не ломает остальные"

- **DONE-AUTOMATED** — UI wiring confirmed:
  - `renderToggleList()` builds one row per stage: HPF first (`HPF (срез низов) — N Гц`), then each band (`Полоса i — type · freq · gain · Q`), each with its own checkbox (`audioInput.js:180-213`).
  - Each row's checkbox calls `editor.setCurve({...})` with only that stage's `enabled` flag flipped (immutable copy via spread), then persists through the matching callback (`onHpfToggle` / `onBandToggle`) → `PUT /api/tuning` with the full `{ hpf, bands }` object — confirms toggling one stage does not clobber sibling stages' parameters.
  - `eqEditor.js` renders disabled stages visually muted: `state.eqBands[i].enabled` / `state.hpf.enabled` directly drive the canvas RAF draw loop's colour/opacity (dimming is automatic, no separate redraw call needed — confirmed no `paintDimming` stub remains after cleanup).
  - Each band row also has a "✕ удалить" remove button wired to `onRemoveBand`.
  - "+ полоса EQ" button adds a new default band (`{enabled:true, type:"peaking", freq_hz:1000, gain_db:0, q:1.0}`) and persists it.
- **PENDING-HUMAN-LIVE-TEST** — Confirm in the browser that:
  1. Disabling HPF alone removes the low-cut from the monitored sound while bands remain active (audible difference).
  2. Disabling a single band removes only that band's boost/cut (A/B by ear + by watching the spectrum).
  3. Visually, disabled rows/points render dimmed/muted on the EQ canvas (not just in the toggle list).
  4. Adding/removing bands updates both the canvas and the live monitored sound without a page reload.

---

## 3. Graphic EQ — drag interaction (frequency × gain × Q)

**Truth:** "Графический EQ: canvas/svg поверх существующего FFT-спектра; перетаскиваемые точки-полосы (freq×gain, Q колесом/жестом) → пишут `input_dsp.bands` через API" (Task 5.3)

- **DONE-AUTOMATED**:
  - `eqEditor.js` implements log-frequency × linear-gain-dB axes (`freqToX`/`xToFreq`, `gainToY`/`yToGain`, `GAIN_RANGE_DB = 24`), reusing the spectrum bars/colour-ramp pattern from `wakeMeter.js` (same `colorForLevel`/`rgbBlend`/`lerp` helpers, same `audio_level` SSE subscription for `bands[24]`).
  - `hitTest()` finds the nearest draggable target (band diamond or HPF cutoff line) within a pixel tolerance; `applyDragMove()` mutates `state.hpf` / `state.eqBands[i]` live during the drag (immediate visual feedback); `commitChange()` fires `onChange({hpf, bands})` only on `pointerup` — i.e. **drag-then-persist-on-release**, not one PUT per pixel of movement (matches the "debounced" requirement from the brief).
  - Mouse-wheel over a band diamond adjusts `q` in `±0.1` steps clamped to `[0.1, 10.0]` and commits immediately (`audioInput.js`/`eqEditor.js` wheel handler, `passive: false` to allow `preventDefault`).
  - `setCurve()` normalises incoming server data with safe defaults, so activating a preset or reloading config cannot leave the editor in an inconsistent state.
- **PENDING-HUMAN-LIVE-TEST** — Confirm in the browser that:
  1. Dragging a band diamond changes its position smoothly and the monitored sound changes accordingly once released.
  2. Scrolling over a diamond visibly changes its size (Q encoding) and narrows/widens its effect on the monitored sound.
  3. Dragging the HPF cutoff line (yellow dashed, triangle handle) moves the low-cut frequency and is audible in the monitor.
  4. No excessive network chatter — verify in DevTools Network tab that `PUT /api/tuning` fires once per drag-release / wheel-tick, not continuously during drag.

---

## 4. Volume slider → `media.audio.input_gain`

**Truth:** "Ползунок громкости управляет `media.audio.input_gain` (Phase 30), значение применяется живо" (D-01 Phase 30)

- **DONE-AUTOMATED**:
  - `buildVolumeSection()` renders two range sliders: `alsa_capture_percent` (0-100, "Главный регулятор" — primary hardware boost) and `pulse_source_percent` (0-150, "мягкая подстройка" — soft PulseAudio trim), matching the exact field names and ranges documented in `Config.schema.json` for `media.audio.input_gain`.
  - Each slider PATCHes `/api/config` with `{ section: "media.audio.input_gain", patch: { <field>: <value> } }` — confirmed `getNested`/`apply_patch` support dotted-path config sections (read in `api_runtime.py` / `config.py` during Wave 1 review).
- **PENDING-HUMAN-LIVE-TEST** — Confirm that moving each slider:
  1. Changes the live input level audibly within ~1s (no restart).
  2. Persists in `Config.json` (`media.audio.input_gain.alsa_capture_percent` / `.pulse_source_percent`) and survives an orchestrator restart.
  3. Stays within sane bounds — pushing `pulse_source_percent` toward 150% should visibly correlate with clipping in the spectrum/monitor (per CLAUDE.md note: "180% pulse over-gain made OWW WORSE via clipping" — operator should be able to observe and avoid this).

---

## 5. OWW threshold line + live score overlay (D-08, reused from `wakeMeter.js`)

**Truth (D-08):** "Линия на эквалайзере перетаскиванием меняет `wake_word.threshold`; поверх — живой оверлей текущего OWW-score"

- **DONE-AUTOMATED**:
  - **Per the orchestrator's explicit instruction, this widget was NOT rebuilt.** `buildOwwSection()` composes the existing, already-shipped `createWakeMeter({draggable: true, height: 88})` + `createCalibrateButton({})` directly from `widgets/wakeMeter.js` (D-08 was fully implemented there in an earlier phase: orange draggable threshold line, cyan OWW-score overlay with decay/peak rendering, colour-ramp spectrum bars, mount-time fetch of `/api/wake_word/sensitivity`, drag-release `PATCH /api/wake_word/sensitivity`).
  - This card is mounted as its own section ("Калибровка wake-word «адам»") inside the new "Аудио-вход" panel — giving the operator threshold calibration in the same place as EQ tuning (co-located workflow), without duplicating ~340 lines of canvas/SSE code.
  - `wakeMeter.js` is unmodified; confirmed via `grep` no edits were made to it.
- **PENDING-HUMAN-LIVE-TEST** — Confirm in the browser that:
  1. The threshold line and live OWW-score overlay render and update in real time as the operator speaks/says "адам".
  2. Dragging the line updates `wake_word.threshold` in `Config.json` (verify via `/api/wake_word/sensitivity` or Config file inspection) and persists across restart.
  3. Calibration workflow is coherent when DSP is active — i.e. operator can tune EQ *and* threshold from one screen and observe how EQ changes affect the OWW score trace (this cross-section interaction is the main UX win of co-locating the cards).

---

## 6. Microphone monitor (raw PCM via WebSocket + Web Audio API, pre/post-EQ toggle)

**Truth (D-06, D-07):** "Монитор: WebSocket отдаёт post-EQ сырой PCM 16-bit 16kHz; браузер играет через Web Audio API" + optional pre/post toggle

- **DONE-AUTOMATED**:
  - `buildMonitorSection()` opens `wss?://<host>/api/audio/monitor`, sets `binaryType = "arraybuffer"`, and on each binary message: converts Int16 PCM → Float32 (`int16ToFloat32`), resamples from the documented 16 kHz monitor rate to the device's native `AudioContext.sampleRate` via linear interpolation, queues into a ring buffer consumed by a `ScriptProcessorNode` (`bufferSize=4096`), with backpressure capping the queue at `MONITOR_SAMPLE_RATE * 2` samples (~2s) — old audio is dropped first, mirroring the documented server-side ring-buffer policy.
  - **Deviation from brief (documented):** used `ScriptProcessorNode` instead of the suggested `AudioWorkletNode`. Rationale recorded inline as a code comment: AudioWorklet requires shipping a separate static module file and registering it via `audioContext.audioWorklet.addModule()`, which is meaningful overhead for what is a short-burst diagnostic feature (operator presses "Слушать", listens briefly, stops); `ScriptProcessorNode` is universally supported, simpler to wire, and adequate at this signal/usage profile. `ScriptProcessorNode` is deprecated-but-supported in all current browsers (Chrome/Firefox/Safari) — acceptable for an internal operator tool.
  - `<select>` toggle for `pre_eq` / `post_eq` PUTs `tuning.audio_input.dsp.monitor_tap` — matches the exact pydantic field (`InputDspTuning.monitor_tap: Literal["pre_eq","post_eq"]`) confirmed in `tuning.py`.
  - Explicit on-screen note clarifies WYSIWYG semantics: *"WebSocket-стрим сырого PCM (16-бит, 16 кГц моно) — ровно то, что слышит модель в режиме post-EQ (WYSIWYG, D-02/D-06)"* and that `half_duplex_mute` is unaffected (input monitor, not TTS output).
  - `stopListening()` cleanly tears down WS, `ScriptProcessorNode`, and `AudioContext`; `_dispose` is wired into the panel's `disposables` array so navigating away stops the stream (no orphaned WebSocket/AudioContext on route change).
- **PENDING-HUMAN-LIVE-TEST** — Confirm in the browser that:
  1. Pressing "▶ Слушать микрофон" produces **audible**, recognisable sound from the live mic within ~1-2s of pressing the button (latency is expected — diagnostic, not real-time monitoring).
  2. Switching the source selector between `post-EQ` and `pre-EQ` produces an audibly different signal when the DSP is actively shaping the curve (post = processed, pre = raw) — this is the direct verification of the WYSIWYG claim (D-02).
  3. Pressing "■ Остановить" or navigating to another panel cleanly stops playback (no leftover audio, no console errors about closed AudioContext).
  4. No audio glitches/underrun artifacts beyond what's expected from the documented ~256ms `ScriptProcessorNode` buffer size.

---

## 7. Preset CRUD (UI round-trip + restart survival)

**Truth (D-05):** "Пресеты EQ хранятся в `System/Config.json`, валидируются pydantic в `tuning.py`; CRUD через API с hot-reload без рестарта"

- **DONE-AUTOMATED**:
  - `buildPresetSection()` implements full CRUD against the Wave 2 endpoints, with response shapes cross-checked against `api_runtime.py` source:
    - **List** — `GET /api/audio/presets` → renders each preset with name, band count, HPF cutoff; active preset visually highlighted (accent border + background).
    - **Create** — name input + "💾 Сохранить текущую кривую как пресет" → `POST /api/audio/presets` with `{ name, hpf, bands }` read live from `eqEditor.state`.
    - **Activate** — "включить" button → `POST /api/audio/presets/{name}/activate`; on success calls `eqEditor.setCurve({ hpf: res.dsp.hpf, bands: res.dsp.bands })` — the exact `{ ok, active_preset, dsp: { hpf, bands } }` response shape was read directly from the Wave 2 `api_runtime.py` handler before wiring this, so the editor immediately reflects the activated curve without a page reload.
    - **Rename** — "✎" → `prompt()` for new name → `PUT /api/audio/presets/{name}` with `{ name: <new>, hpf, bands }` (preserves the curve, changes only the key).
    - **Update ("record current")** — "⤓ записать текущую" → confirm dialog → `PUT /api/audio/presets/{name}` with the *live* `eqEditor.state` curve under the existing name (lets the operator iterate on a preset without renaming).
    - **Delete** — "✕" → confirm dialog → `DELETE /api/audio/presets/{name}`.
  - All mutating actions `await refresh()` afterward, so the list and active-state badge stay consistent with the server (no client-side state drift).
  - Inline note clarifies persistence: *"Хранится в System/Config.json (tuning.audio_input.presets), переживает рестарт"*.
- **PENDING-HUMAN-LIVE-TEST** — Confirm that:
  1. Creating, renaming, updating, activating, and deleting a preset from the UI round-trips correctly (each operation reflected immediately in the list and in `Config.json` on disk).
  2. Activating a preset visibly moves the EQ curve (diamonds + HPF line snap to the preset's stored values) AND audibly changes the monitored sound.
  3. **Restart survival**: create/activate a preset, restart the orchestrator (`sudo systemctl restart adam-orchestrator.service` or dev equivalent), reload the panel — the preset list and `active_preset` are still present and the active preset's curve is still applied to the live DSP (this is the actual `must_haves` truth — "переживает рестарт").

---

## 8. Voice loop "адам" stability with DSP enabled

**Truth (overall phase verification):** "оператор... СЛЫШИТ результат в мониторе (post-EQ), wake «адам» продолжает срабатывать"

- **DONE-AUTOMATED** — Structural confirmation only: no changes were made to `Orchestrator.py` voice-loop internals, `audio_dsp.py`, or any backend pipeline code in this wave (Wave 3 is frontend-only, per the brief's explicit boundary). The DSP wiring into `_vad_loop` (D-01/D-02 — same processed buffer flows to OWW/ASR/monitor) was built and is presumed verified in Waves 1-2; this wave only adds the UI surface to control it. No regressions are structurally possible from these changes alone (pure new route + new panel files; existing routes/panels untouched except for one nav-entry insertion each in `router.js`/`main.js`).
- **PENDING-HUMAN-LIVE-TEST** — Confirm end-to-end with a live exhibition-realistic test:
  1. With DSP enabled and a reasonable EQ curve dialled in, say "адам" from typical visitor distance — confirm the wake word still fires reliably (compare hit-rate qualitatively against the pre-Phase-31 baseline).
  2. Confirm ASR transcription quality is not degraded (or is improved, per the phase's stated goal of "suppressing parasitic frequencies improves wake-word & transcription").
  3. Run a short multi-turn conversation with DSP active to confirm no instability (drops, hangs, voice-loop restarts) introduced by the live-tunable signal path.

---

## Summary

| # | Item | Status |
|---|------|--------|
| 1 | Bypass test (master toggle → raw passthrough) | UI wiring: DONE-AUTOMATED · audible/behavioural confirmation: PENDING-HUMAN-LIVE-TEST |
| 2 | Per-stage A/B toggles (HPF + bands) | UI wiring + visual dimming: DONE-AUTOMATED · audible A/B: PENDING-HUMAN-LIVE-TEST |
| 3 | Graphic EQ drag interaction (freq×gain×Q) | Drag/wheel/persist logic: DONE-AUTOMATED · audible feedback: PENDING-HUMAN-LIVE-TEST |
| 4 | Volume slider → `media.audio.input_gain` | API wiring: DONE-AUTOMATED · live audibility + persistence: PENDING-HUMAN-LIVE-TEST |
| 5 | OWW threshold line + score overlay (reused, not rebuilt) | Composition/reuse confirmed: DONE-AUTOMATED · live calibration: PENDING-HUMAN-LIVE-TEST |
| 6 | Mic monitor (WS + Web Audio, pre/post toggle) | Stream/playback/teardown logic: DONE-AUTOMATED · audibility + WYSIWYG A/B: PENDING-HUMAN-LIVE-TEST |
| 7 | Preset CRUD round-trip | UI↔API wiring + response-shape cross-check: DONE-AUTOMATED · round-trip + restart survival: PENDING-HUMAN-LIVE-TEST |
| 8 | Voice loop "адам" stability with DSP on | No backend changes in this wave (structural non-regression): DONE-AUTOMATED · live stability: PENDING-HUMAN-LIVE-TEST |

**Why these items remain PENDING-HUMAN-LIVE-TEST:** `31-PLAN.md` frontmatter declares `autonomous: false` — this phase requires a human operator with working speakers/microphone/browser to judge audio quality, calibrate thresholds by ear, and confirm the exhibition-critical wake-word behaviour. None of this can be exercised from a headless code-execution environment; the agent has verified everything that *can* be verified statically (syntax validity, API-contract correctness, data-shape matching, dead-code absence, UI-to-backend wiring completeness) and has clearly enumerated the remaining live checks for the operator (Адам's keeper) to run from the browser at `#/audioInput`.

## Structural / static checks performed (this session)

- `node --experimental-vm-modules` SourceTextModule parse: **all 4 changed/new JS files pass** (`audioInput.js`, `eqEditor.js`, `router.js`, `main.js`) — no syntax errors.
- Cross-checked every `api.*` call against `api.js`'s exported surface (`get/post/patch/del/raw/subscribeEvents`) — all calls use existing methods correctly.
- Cross-checked every backend response shape consumed by the new UI (`/api/audio/presets*` list/activate, `/api/config`, `/api/tuning`, `/api/wake_word/sensitivity` via reused `wakeMeter.js`) against the actual `api_runtime.py` / `tuning.py` implementations read during this session — no mismatches found.
- Confirmed `eqEditor.js` exports exactly `createEqEditor`, matches its single import site in `audioInput.js`.
- Confirmed no dead code remains: no references to `setNested`, `paintDimming`, `state.js` import, `.btn-active` (non-existent CSS class — replaced with `.btn-primary`), or the unused dummy `AudioBufferSourceNode`.
- Confirmed the word "bypass" appears in the shipped UI copy (`audioInput.js:239` — satisfies `must_haves.artifacts.contains: "bypass"` for this document, and the UI itself documents the bypass behaviour to the operator).
- Confirmed `wakeMeter.js` is byte-for-byte unmodified (D-08 widget reused, not rebuilt, per explicit instruction).
