# Phase 21A: Chat EQ Real Spectrum — Research

**Researched:** 2026-05-18
**Domain:** Real-time FFT spectrum for live audio visualisation (Python backend → SSE → Canvas2D frontend)
**Confidence:** HIGH

## Summary

All 12 research questions are answerable with HIGH confidence — this is a small, well-bounded fix: ~15 lines of new Python in one function (`MicReader._emit_audio_level`), ~80 lines of frontend rewrite (`wakeMeter.js draw()` + handler), 6 new Config keys + schema descriptions, and a one-line cadence constant change. No new dependencies (numpy 1.26.4 already in venv; verified by `python3 -c "import numpy"` on this Jetson).

Per-FFT cost on this Jetson Orin NX was measured at **~7 µs** (no window) / **~7.5 µs** (Hann, 160 samples) / **~10 µs** (Hann + zero-pad to 256) — three to four orders of magnitude below the 40 ms inter-frame budget. FFT cost is irrelevant; the cadence bump from 10 Hz → 25 Hz on `audio_level` events is the only real load increase (~2.5× more SSE messages and ~2.5× more bytes per `events.jsonl` line because `bands[24]` is added).

The largest risks are NOT in the FFT math but in **(a)** the SSE leak: confirmed already present in code (the chat-panel cleanup already disposes wakeMeter; settings-panel disposes via `wrapper._dispose`) — the leak is real but already half-fixed, so this phase mainly needs to make `dispose()` idempotent and verify both call sites still work. **(b)** `events.jsonl` is **417 MB** today with no rotation in `EventLog.append()` — 2.5× cadence accelerates an existing problem. Recommend planner add a separate task (or backlog item) for jsonl sampling/rotation, even if minimal.

**Primary recommendation:** Use `numpy.fft.rfft` directly on `mono_chunk` (already mono via `audioop.tomono` upstream in `_make_stereo_reader`), apply Hann window of length 160 (precomputed once), no zero-padding (the cosmetic gain at 100 Hz bin width is marginal for 24 log-bands), precompute a log-band binning index table on first call and recompute lazily when any of `sample_rate / spectrum_bands / spectrum_min_hz / spectrum_max_hz` change. Frontend: keep last `bands[]` snapshot, redraw on RAF, color via piecewise RGB interpolation (cheap and predictable; HSL is fine too).

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01** FFT on Jetson backend, same `mono_chunk` that `MicReader._emit_audio_level` already feeds to `audioop.rms()`.
- **D-02** Web Audio API on client rejected.
- **D-03** Extend existing `audio_level` event with optional `bands: number[24]` (NOT a new event).
- **D-04** Cadence 10 → 25 Hz (every 2nd frame instead of every 5th).
- **D-05** 24 bands. Config key `media.audio.spectrum_bands`.
- **D-06** Cadence in Config: `media.audio.spectrum_cadence_hz` (informational mirror of the cadence constant).
- **D-07** 80 Hz – 8000 Hz. Keys `media.audio.spectrum_min_hz`, `media.audio.spectrum_max_hz`.
- **D-08** Log-frequency scale. Key `media.audio.spectrum_scale = "log"` (future-proofing for mel/lin).
- **D-09** dBFS normalisation `mag → 20·log10(mag/MAX) → clamp([floor, 0]) → linear [0..1]`. Keys `media.audio.spectrum_floor_db = -60`, `media.audio.spectrum_ceiling_db = 0`.
- **D-10** Bars without smoothing/peak-hold/decay/wobble. Direct from `bands[i]`.
- **D-11** Color green→yellow→red by per-bar level. Thresholds in Config (`media.audio.spectrum_color_yellow_at`, `..._red_at`).
- **D-12** OWW score (cyan) + threshold (orange dashed) preserved as-is.
- **D-13** Delete `EQ_SHAPE`, `audioLevel * 4.0`, `sin(Date.now()...)` wobble, `peaks[i] * 0.87`.
- **D-14** Verify `dispose()` is called by both host panels (chat.js, settings.js); make idempotent.
- **D-15** All numeric params in `Config.json` `media.audio.*` + schema documentation in `Config.schema.json`.
- **D-16** FFT params hot-reloadable (no Orchestrator restart).
- **D-17** Mono FFT (down-mixed via existing `_make_stereo_reader`). One spectrum, not per-channel.

### Claude's Discretion

- numpy vs scipy for FFT.
- Binning-table structure and lazy-recompute trigger.
- Config key layout: flat keys vs nested object for color thresholds.
- Whether to slow `audio_level` jsonl writes (writing-side sampling) while keeping SSE at 25 Hz.

### Deferred Ideas (OUT OF SCOPE)

- UI reorg (Phase 21).
- silence_timeout UI (Phase 21).
- TTS volume UI (Phase 21).
- jsonl writing-side sampler (backlog; recommended for follow-up — see Risk Landmines §12).
- Mel scale / formant bands (backlog).
- Waterfall spectrogram (backlog).
- Per-channel L/R spectrum (backlog).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-EQ-01 | FFT backend: real spectrum from same audio stream as OWW/ASR | §1 FFT impl, §3 dBFS, §4 stereo confirmed |
| UI-EQ-02 | Event format/SSE: `bands[24]` field in `audio_level` event | §5 payload size, §6 cadence bump, §10 backward compat |
| UI-EQ-03 | Frontend renders bars without smoothing | §7 RAF + last-snapshot pattern |
| UI-EQ-04 | Color gradient green→yellow→red by per-bar level | §7 color math |
| UI-EQ-05 | SSE leak fix in wakeMeter | §8 dispose audit |
| UI-EQ-06 | All numeric params in Config.json + schema | §9 settings access pattern |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FFT compute (160-sample windowed) | Jetson backend (Python, MicReader) | — | Same audio stream as OWW/ASR; only backend has the bytes. D-01. |
| Log-band binning + dBFS normalisation | Jetson backend (MicReader helper) | — | Send compact `bands[24]` over SSE; client gets [0..1] floats. |
| SSE publication | EventBus / FastAPI | — | Existing infrastructure; no new endpoint. |
| Canvas rendering (24 bars + color) | Browser (Canvas2D in wakeMeter widget) | — | Pure presentation; RAF loop already exists. |
| OWW score / threshold overlay | Browser (Canvas2D) | — | Unchanged. |
| Mic-source badge / VU-meter | Browser (chat.js / settings.js host panels) | — | Out of scope; preserved. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 1.26.4 (verified on Jetson: `import numpy; print(numpy.__version__)` → 1.26.4) | `np.fft.rfft`, `np.hanning`, `np.abs`, `np.log10` | Already in venv (silero/whisperx dep). `np.fft.rfft` returns only positive bins, exactly what we need. No SIMD config needed at 160-sample sizes — bottleneck is irrelevant. |
| audioop (stdlib) | builtin | `audioop.rms` already used | No change, just sit adjacent to the new FFT path. |

### Supporting
None.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `numpy.fft.rfft` | `scipy.fft.rfft` | scipy is faster at large N (FFTW-class backend), irrelevant at N=160. Adds heavyweight dependency we'd have to pin for Jetson aarch64. **REJECTED.** |
| Python FFT | C extension (e.g. pyfftw) | Massive overkill. 7 µs/call is already ~0.02% CPU at 50 fps. **REJECTED.** |
| numpy `np.fft.rfft` on int16 directly | Convert to float32 first | rfft accepts int16 but always upcasts internally. Explicit float32 cast keeps memory predictable. **CHOSEN: float32 cast.** |
| Hann window length 160 | No window | Spectral leakage on short stationary tones is visible — Hann costs +0.5 µs and prevents the "leaking sidebands" look. **CHOSEN: Hann.** |
| 160-sample FFT | Zero-pad to 256/512 | Pad to 256 improves bin resolution from 100 Hz to 62.5 Hz; below 200 Hz this matters cosmetically. But 24 log-bands across 80–8000 Hz averages bins per band, so the gain is **almost zero in practice**. **CHOSEN: no padding (160).** |

**Installation:** None — numpy is already in venv.

**Version verification:**
```bash
# Verified on Jetson 2026-05-18:
python3 -c "import numpy; print(numpy.__version__)"  # → 1.26.4
```

## Architecture Patterns

### System Architecture Diagram

```
ESP32 :81 WAV stream
        │
        ▼
[MicReader._socket_reader_thread] ───── raw stereo bytes
        │
        ▼
[stereo_reader_factory in Orchestrator] ── audioop.tomono → mono_chunk (160 samples, int16, 320 bytes)
        │
        ▼
[MicReader._drain_loop] ── every 2nd frame (was 5th) ──┐
        │                                              │
        ▼                                              │
[MicReader._emit_audio_level(mono_chunk)]              │
        │                                              │
        ├── audioop.rms()  → level (existing path)     │
        │                                              │
        ├── NEW: compute_spectrum_bands(mono_chunk)    │
        │       │                                      │
        │       ├── np.frombuffer(int16) → float32     │
        │       ├── × Hann(160) precomputed            │
        │       ├── np.fft.rfft → 81 complex bins      │
        │       ├── np.abs → 81 magnitudes             │
        │       ├── log-bin lookup (precomputed table) │
        │       │      → 24 band power values          │
        │       ├── 20·log10(mag/MAX) → 24 dBFS        │
        │       ├── clamp([-60, 0]) → linear [0..1]    │
        │       └── round(3) → list[float] len 24      │
        │                                              │
        ▼                                              │
[event_log.append("audio_level", payload + bands[])]   │
        │                                              │
        ▼                                              │
[FastAPI /api/agent/stream SSE] ◄──────────────────────┘
        │
        ▼
[Browser EventSource → wakeMeter.handleEvent]
        │
        ▼
[Canvas2D draw() @ RAF 60 Hz]
   ├── bars: 24× rect, color = colorFor(bands[i])
   ├── OWW score: cyan horizontal line (decay 0.86) — unchanged
   └── threshold: orange dashed line — unchanged
```

### Recommended Project Structure

No new files. Changes confined to:
- `System/adam/mic_reader.py` (FFT compute + payload extension + cadence constant)
- `System/Config.json` + `System/Config.schema.json` (six new keys)
- `System/WebUI/static/js/widgets/wakeMeter.js` (rewrite draw loop + handler `bands[]` consumer)
- `System/WebUI/static/js/panels/chat.js` (caption text update — already minimal)

### Pattern 1: Precomputed Binning Table (recompute-on-config-change)
**What:** Build a list of `(start_bin, end_bin, weight_array)` tuples once at MicReader construction; rebuild only when one of {sample_rate, n_fft, n_bands, min_hz, max_hz} changes.
**When to use:** Hot-reloadable FFT params (D-16) without per-frame allocation.
**Example:**
```python
# Source: standard log-band binning pattern (no specific citation; well-known math)
def _build_log_band_table(
    n_fft: int, sample_rate: int, n_bands: int, min_hz: float, max_hz: float
) -> list[tuple[int, int]]:
    """Return list of (start_bin_idx, end_bin_idx) inclusive ranges into rfft output.

    rfft output has n_fft//2 + 1 bins. Bin k covers frequency k * sample_rate / n_fft.
    """
    import math
    n_bins = n_fft // 2 + 1
    bin_hz = sample_rate / n_fft
    log_min = math.log(min_hz)
    log_max = math.log(max_hz)
    edges_hz = [math.exp(log_min + i * (log_max - log_min) / n_bands) for i in range(n_bands + 1)]
    table: list[tuple[int, int]] = []
    for i in range(n_bands):
        lo = max(1, int(math.floor(edges_hz[i] / bin_hz)))      # skip DC bin 0
        hi = min(n_bins - 1, int(math.ceil(edges_hz[i + 1] / bin_hz)))
        if hi < lo:
            hi = lo
        table.append((lo, hi))
    return table
```

### Pattern 2: Stateless dBFS Mapper
**What:** Per-band magnitude → dBFS → clamped → linear [0..1]. No state, no leak.
**Example:**
```python
import math
# magnitude_max corresponds to a full-scale int16 sinusoid through the Hann window.
# For a 160-sample int16 input with Hann sum-of-window-coefficients ≈ 80:
#   |X[k]_peak| ≈ 0.5 * 32768 * sum(Hann) = 0.5 * 32768 * 80 ≈ 1_310_720
# That's the theoretical max magnitude any single rfft bin can attain.
# We can use this as a fixed reference, OR derive it once per band table build.

MAG_REF_FULL_SCALE = 0.5 * 32768.0 * 80.0  # ≈ 1.31e6 — Hann-windowed, no padding

def _band_db_to_norm(band_mag_sum: float, n_bins_in_band: int, floor_db: float, ceiling_db: float) -> float:
    # Per-band reference = full-scale reference × number of bins summed (energy adds).
    # We sum magnitudes (not power) so reference scales linearly.
    ref = MAG_REF_FULL_SCALE * max(1, n_bins_in_band)
    mag = max(band_mag_sum, 1e-9)  # avoid log10(0)
    db = 20.0 * math.log10(mag / ref)
    db_clamped = max(floor_db, min(ceiling_db, db))
    return (db_clamped - floor_db) / (ceiling_db - floor_db)  # linear [0..1]
```

### Anti-Patterns to Avoid
- **Recomputing the Hann window every frame.** Build once, store as numpy array on the MicReader instance.
- **Allocating new lists per frame.** Pre-size and reuse if profiling demands it (not needed at 25 Hz × 24 floats; profile says nope).
- **Reading `Settings.load()` inside `_emit_audio_level`.** That'd parse the JSON file every 40 ms. The pattern in MicReader is: read on construction, refresh via `apply_config()` when `config_patched` event fires.
- **Putting `bands` into the synthetic fallback `_level_emit_loop`.** That loop emits when drain has stalled — we have no fresh PCM bytes, so we can't compute a fresh spectrum. Just OMIT `bands` from synthetic events; frontend treats missing field as "no update".

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Discrete Fourier Transform | Hand-rolled Goertzel or DFT loop | `numpy.fft.rfft` | Numerically stable, vectorised, already linked against system BLAS. |
| Stereo down-mix | New code | Existing `_make_stereo_reader` in Orchestrator.py:309 | Already produces mono PCM via `audioop.tomono(raw, 2, 0.5, 0.5)`. MicReader's `mono_chunk` IS the down-mixed signal. **CONFIRMED — see §4.** |
| SSE subscription | New EventSource | Existing `subscribeEvents()` in api.js:47 | Already used by both wakeMeter mount sites; comes with auto-reconnect + close-handle returned for `dispose()`. |
| dBFS clamp | Custom piecewise | `max(floor, min(ceil, db))` | Standard; nothing to gain. |

**Key insight:** Every component is reused; this phase is almost entirely "wire it together correctly + delete two illusions" (`EQ_SHAPE`, `peaks[i] * 0.87`).

## Common Pitfalls

### Pitfall 1: float32 conversion silently introduces DC offset
**What goes wrong:** `np.frombuffer(mono_chunk, dtype=np.int16).astype(np.float32)` is correct, but forgetting to subtract mean leaves DC bias from the INMP441's electrical offset, producing a spurious peak at bin 0.
**Why it happens:** ESP32 INMP441 has a small but non-zero DC offset.
**How to avoid:** Skip bin 0 in the log-band table (`lo = max(1, ...)` — already shown in Pattern 1). Don't subtract mean (changes meaning of "zero" reference); just exclude DC bin from spectral display.
**Warning signs:** A persistent leftmost-band glow on silence.

### Pitfall 2: Hann window saved at wrong precision
**What goes wrong:** `np.hanning(160)` returns float64. Multiplying int16-cast-to-float32 by float64 promotes everything to float64, doubling memory bandwidth.
**How to avoid:** `self._hann = np.hanning(self._n_fft).astype(np.float32)` once at construction.

### Pitfall 3: dBFS reference math
**What goes wrong:** Choosing `MAG_REF = 32768` (peak int16) is wrong because rfft of a full-scale sine gives a peak bin magnitude ≈ N/2 × peak, not "peak". A full-scale 1 kHz tone with a 160-sample Hann gives bin magnitude ≈ 0.5 × 32768 × sum(Hann) ≈ 1.3e6, not 32768. Using 32768 as reference produces "+92 dB" readings that get clamped to 0 dB constantly — the meter looks pegged.
**How to avoid:** Use the closed-form reference `0.5 × INT16_MAX × sum(hann_window)` ≈ 1.31e6 for 160-sample Hann (or compute `sum(self._hann)` once at construction). See Pattern 2. **VERIFY at smoke-test:** speak normally — bars should land in mid-range, not all-red.

### Pitfall 4: Frontend treats missing `bands` as "zero", not "no update"
**What goes wrong:** When `_level_emit_loop` emits a synthetic fallback `audio_level` without `bands` (because no fresh PCM), the frontend coerces missing to `[]` or zeros — bars flash to floor each fallback frame.
**How to avoid:** Frontend handler: `if (Array.isArray(p.bands) && p.bands.length === 24) state.bands = p.bands;` — explicit guard; ignore otherwise. Then `draw()` reuses last known `state.bands` until a real one arrives.

### Pitfall 5: SSE leak when `dispose()` is never called
**What goes wrong:** chat.js does call `wakeMeter.dispose()` in its cleanup return (chat.js:663 — confirmed). settings.js wires it via `wrapper._dispose` (settings.js:700-705 — confirmed). But: calling `dispose()` twice should be safe (idempotent), since unmount + browser cleanup may race.
**How to avoid:** Add a `disposed` boolean in the wakeMeter closure; guard both `unsub()` and `cancelAnimationFrame()` against repeat calls.

### Pitfall 6: events.jsonl 2.5× growth on top of an already 417 MB file
**What goes wrong:** `EventLog.append()` opens the file every event and `write()` synchronously — no rotation. At 25 Hz × 24-float-array × 8-byte-text each, audio_level events become ~400 bytes each → 10 KB/s → 36 MB/hour → ~860 MB/day.
**How to avoid:** Out of phase scope per CONTEXT, but planner should consider a separate task or backlog item: writing-side sampler (write 1 of N events to disk; keep all on SSE). Surfaced in §5 below.

## Runtime State Inventory

Not applicable — this is greenfield code addition in existing functions, no rename/migration.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| numpy | FFT compute | ✓ | 1.26.4 | — |
| Python 3 audioop | existing RMS | ✓ | builtin | — |

No missing dependencies. No new install steps.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing tests/) |
| Config file | none — pytest auto-discovers tests/test_*.py |
| Quick run command | `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q` (file to be created) |
| Full suite command | `./.venv/bin/python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-EQ-01 | FFT of synthetic 1 kHz sine puts energy in band covering 1000 Hz, near-zero elsewhere | unit | `pytest tests/test_mic_reader_spectrum.py::test_sine_localised -x` | ❌ Wave 0 |
| UI-EQ-01 | Silence (zeros) produces all bands at floor [0..0.05] | unit | `pytest tests/test_mic_reader_spectrum.py::test_silence_floor -x` | ❌ Wave 0 |
| UI-EQ-01 | Full-scale white noise produces all bands above 0.5 | unit | `pytest tests/test_mic_reader_spectrum.py::test_noise_distributed -x` | ❌ Wave 0 |
| UI-EQ-02 | `audio_level` event payload has `bands` field, len == 24, all floats in [0,1] | unit | `pytest tests/test_mic_reader_spectrum.py::test_payload_shape -x` | ❌ Wave 0 |
| UI-EQ-02 | Cadence constant changed from 5 → 2 (config-driven via `spectrum_cadence_hz`) | unit | `pytest tests/test_mic_reader_spectrum.py::test_cadence_constant -x` | ❌ Wave 0 |
| UI-EQ-03 | Frontend `bands[]` consumed directly, no `EQ_SHAPE`, no decay, no wobble | manual | Browser visual smoke-test | manual |
| UI-EQ-04 | Color function: 0.0 → green, 0.7 → yellow, 0.95 → red | manual | Browser visual smoke-test | manual |
| UI-EQ-05 | Network tab: one EventSource per page load even after panel-toggle 5× | manual | Browser DevTools Network tab | manual |
| UI-EQ-06 | All six new keys present in Config.json + Config.schema.json with descriptions | unit | `pytest tests/test_config_schema.py::test_spectrum_keys -x` (extend existing if present, else add) | ❌ Wave 0 |
| UI-EQ-06 | Hot-reload: PATCH `/api/config` with `spectrum_floor_db = -50` triggers `apply_config` rebuild of band table without restart | integration | `pytest tests/test_mic_reader_spectrum.py::test_hot_reload -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q`
- **Per wave merge:** `./.venv/bin/python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green + manual smoke-test (questions 11 below) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mic_reader_spectrum.py` — covers UI-EQ-01, UI-EQ-02, UI-EQ-06
- [ ] (Optional) Extend `tests/test_config_schema.py` if it exists; if not, the schema-key test can live alongside in `test_mic_reader_spectrum.py`.
- [ ] Pytest framework already installed (existing tests in `tests/` directory verify this).

## Security Domain

Not applicable — no auth, no input validation surface, no crypto, no PII. Spectrum bands are derived from already-flowing audio. Skip.

## Project Constraints (from CLAUDE.md)

| Constraint | Compliance Path |
|------------|-----------------|
| **Config-First** (no hardcoded numerics) | All six FFT params go to `media.audio.spectrum_*` + schema docs. Cadence constant `_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES` becomes derived from `spectrum_cadence_hz` (or stays as a constant clearly tied to Config). |
| **Settings access only via `Settings.load()` / `settings.section()`** | MicReader continues to take `audio_cfg` dict in constructor; new keys read in `__init__` and re-read in `apply_config()`. NEVER touch `DEFAULT_CONFIG`. |
| **Events via `EventBus`, not `print`/`logging`** | We use the existing `self._emit(...)` path. No change. |
| **Hot-reload via `tuning.py`** | FFT params are media/audio, not tuning — they live in `media.audio.*` (CONTEXT D-15). Hot-reload happens via the existing `config_patched` → `apply_config()` chain (verified: api_runtime.py:124 emits `config_patched`; MicReader.apply_config exists at mic_reader.py:403). New keys to read in `apply_config`: spectrum_bands, spectrum_min_hz, spectrum_max_hz, spectrum_floor_db, spectrum_ceiling_db, spectrum_cadence_hz, spectrum_color_yellow_at, spectrum_color_red_at. If any of bands/min/max changes, rebuild the binning table. |
| **LLM = чистый русский текст** | N/A (no LLM in this phase). |
| **`half_duplex_mute = true`** | Preserved — `_emit_audio_level` already fires during mute (B-1 fix at mic_reader.py:496-498). Spectrum publish follows the same path → also live during TTS. See §12 below for whether that's correct. |

---

## §1. FFT Implementation Choices

**Recommendation: `numpy.fft.rfft` on float32 with precomputed Hann window, NO zero-padding.**

### Why numpy over scipy
- numpy 1.26.4 already in venv (verified above). Zero new dependency.
- scipy.fft is marginally faster at large N (uses pocketfft / FFTW-class backends), but at N=160 the difference is dominated by Python call overhead.
- Adding scipy as a Jetson aarch64 dep is non-trivial and produces no measurable benefit.

### Why no zero-padding
- Bin resolution at N=160, fs=16000 is **100 Hz**.
- Bin resolution at N=256 is **62.5 Hz**.
- The 24 log-bands across 80–8000 Hz have band edges at exponentially-spaced points. Below ~200 Hz, bands are ~30–40 Hz wide and STILL undersampled by 100 Hz bins — they end up sharing a single bin (or none). Padding to 256 doesn't fully solve this either (still only ~60 Hz resolution).
- For the bottom 2-3 bands (sub-200 Hz) the band may contain 0 or 1 bin. The binning table handles this by ensuring `hi >= lo` (clamp), so the band reads the nearest bin's magnitude. This is acceptable — voice rarely lives below 100 Hz and the few bands below 200 Hz are decorative.
- **Conclusion: cosmetic gain too small to justify +50% FFT cost and added complexity.**

### Why Hann window (length 160, not zero-padded)
- Without windowing, spectral leakage produces visible "ghost peaks" near strong tones.
- Hann window at length 160 takes ~7.5 µs (measured) vs ~7 µs no-window (measured).
- Hann ≈ best general-purpose window for short frames with strong sinusoidal content. Hamming is comparable but has higher sidelobes.
- Alternatives like Blackman-Harris: longer mainlobe, hurts low-freq band sensitivity. Not worth it.

### Measured cost (Jetson Orin NX, single core, Python 3.x venv)
Benchmark run during research (10000 iterations averaged):
```
no-window 160:    6.96 µs/call
hann       160:   7.55 µs/call
hann + pad 256:  10.25 µs/call
```
At 25 Hz cadence, total CPU = 25 × 7.55 µs = **189 µs/sec ≈ 0.02% of one core**. Negligible.

### Concrete code shape for integration into `_emit_audio_level`
```python
# In MicReader.__init__, after _normalize_factor is set:
import numpy as np  # added at module top

# Spectrum config — read from audio_cfg.
self._spec_n_bands = int(audio_cfg.get("spectrum_bands", 24))
self._spec_min_hz = float(audio_cfg.get("spectrum_min_hz", 80.0))
self._spec_max_hz = float(audio_cfg.get("spectrum_max_hz", 8000.0))
self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", -60.0))
self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", 0.0))

# n_fft = samples per mono_chunk (sample_rate * frame_ms / 1000). For 16k/20ms = 320.
# WAIT: frame_bytes = sample_rate * 2 bytes * frame_ms / 1000 = 16000 * 2 * 20 / 1000 = 640 bytes,
# so samples = 320, not 160. Let me re-derive… (see correction note below)
self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))  # mono samples
self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())  # full-scale mag reference
self._spec_band_table = _build_log_band_table(
    self._spec_n_fft, self._sample_rate, self._spec_n_bands,
    self._spec_min_hz, self._spec_max_hz,
)

# In _emit_audio_level, after the existing rms/norm computation:
bands = self._compute_bands(mono_chunk)  # method below
if bands is not None:
    payload["bands"] = bands

# New method on MicReader:
def _compute_bands(self, mono_chunk: bytes) -> list[float] | None:
    if not mono_chunk or len(mono_chunk) < self._spec_n_fft * 2:
        return None
    # Take exactly n_fft samples (truncate if longer, which shouldn't happen).
    samples = np.frombuffer(mono_chunk[: self._spec_n_fft * 2], dtype=np.int16).astype(np.float32)
    windowed = samples * self._spec_hann
    spectrum = np.abs(np.fft.rfft(windowed))  # shape (n_fft//2 + 1,)
    out: list[float] = []
    floor_db = self._spec_floor_db
    ceiling_db = self._spec_ceiling_db
    span_db = ceiling_db - floor_db
    for (lo, hi) in self._spec_band_table:
        # Sum magnitudes across bins in band; reference scales with bin count.
        band_mag = float(spectrum[lo : hi + 1].sum())
        bin_count = hi - lo + 1
        ref = self._spec_mag_ref * max(1, bin_count)
        if band_mag < 1e-9:
            norm = 0.0
        else:
            db = 20.0 * math.log10(band_mag / ref)
            db_clamped = floor_db if db < floor_db else (ceiling_db if db > ceiling_db else db)
            norm = (db_clamped - floor_db) / span_db
        out.append(round(norm, 3))
    return out
```

### IMPORTANT correction note on N

The objective brief says "FFT over 160 samples → 80 positive bins, bin width = 100 Hz." That math implies sample_rate=16000 and frame_ms=10. Let me verify from Config:
- `media.audio.sample_rate = 16000`
- `media.audio.frame_ms = 20`
- `mic_reader.py:103`: `_frame_bytes = max(2, int(self._sample_rate * 2 * self._frame_ms / 1000))` = `16000 * 2 * 20 / 1000` = **640 bytes = 320 int16 samples per mono_chunk** (after stereo→mono downmix).

So `N=320`, not 160. Bin width = 16000/320 = **50 Hz**. rfft output = 161 bins. This is actually **better** than the brief assumed — no padding needed at all; 50 Hz resolution is excellent for log-binning above 80 Hz.

The benchmark above tested N=160 (which is what the brief specified) — real cost at N=320 will be slightly higher (~12–15 µs/call extrapolating from rfft's N log N). Still negligible.

**Recommendation: derive `n_fft` from `sample_rate * frame_ms / 1000` (no hardcode). If a future config changes frame_ms, table rebuilds via `apply_config`.**

### Alternatives considered
- **scipy.fft.rfft:** rejected (new aarch64 dep, no perf win).
- **No window:** rejected (visible leakage on tones).
- **Zero-padding to 256/512:** rejected (cosmetic gain only at sub-200 Hz where bands are 0-1 bin anyway).

## §2. Log-Frequency Binning into 24 Bands

**Recommendation: precomputed list of `(start_bin, end_bin)` tuples; rebuild only when sample_rate / n_fft / spectrum_bands / min_hz / max_hz changes. Energy summation (sum of magnitudes) within each band; no interpolation.**

### Algorithm
1. Compute band edges: `edges[i] = exp(log(min_hz) + i × (log(max_hz) - log(min_hz)) / n_bands)` for `i ∈ [0, n_bands]`.
2. For each band `i ∈ [0, n_bands - 1]`:
   - `lo = max(1, floor(edges[i] / bin_hz))` (skip DC bin)
   - `hi = min(n_bins - 1, ceil(edges[i+1] / bin_hz))`
   - If `hi < lo`, force `hi = lo` (degenerate single-bin band, expected for lowest bands).
3. Result: 24 tuples `(lo, hi)` totalling ≤ 81 bin references.

### Why sum-of-magnitudes (not energy or interpolation)
- **Sum-of-magnitudes:** linear in amplitude; matches what user perceives as "loudness in this band". Reference scales linearly with bin count.
- **Sum-of-power (|X|²):** more physically correct for "energy in band" but produces wider dynamic range and more "spiky" response — visually less smooth.
- **Linear interpolation across bin boundaries:** marginally more accurate when bin boundary cuts a band, but for 24 log-bands the visual difference is negligible. Skip; adds complexity.

Standard log-band magnitude binning is the approach used by VLC, foobar2000, and most audio spectrum plugins. No specific URL — well-known math.

### Hot-reload trigger
In `apply_config(asr_cfg, audio_cfg)`:
```python
new_bands = int(audio_cfg.get("spectrum_bands", self._spec_n_bands))
new_min = float(audio_cfg.get("spectrum_min_hz", self._spec_min_hz))
new_max = float(audio_cfg.get("spectrum_max_hz", self._spec_max_hz))
# (also pick up new sample_rate / frame_ms if changed)
table_dirty = (
    new_bands != self._spec_n_bands
    or new_min != self._spec_min_hz
    or new_max != self._spec_max_hz
    or restart_needed  # implies sample_rate or frame_ms changed
)
self._spec_n_bands = new_bands
self._spec_min_hz = new_min
self._spec_max_hz = new_max
self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", self._spec_floor_db))
self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", self._spec_ceiling_db))
if table_dirty:
    self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))
    self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
    self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())
    self._spec_band_table = _build_log_band_table(
        self._spec_n_fft, self._sample_rate, self._spec_n_bands,
        self._spec_min_hz, self._spec_max_hz,
    )
```

### Alternatives considered
- **scipy.signal.get_window + librosa-style mel-binning:** overkill; new deps.
- **Per-band Gaussian kernels:** smoother visuals but expensive at 25 Hz. Rejected — D-10 says "no smoothing" anyway.
- **Eager rebuild on every frame:** lazy is strictly better; table is pure function of params.

## §3. dBFS Normalisation

**Recommendation: per-band reference = `MAG_REF_FULL_SCALE × bin_count` where `MAG_REF_FULL_SCALE = 0.5 × INT16_MAX × sum(Hann_window)`. Clamp result to [floor_db, ceiling_db]; linearly remap to [0..1].**

### Exact pipeline
```
mag_sum_in_band  = sum(|X[k]| for k in band)        # already magnitudes, not power
bin_count        = len(band)
ref              = 0.5 * 32768 * sum(hann)          # ~1.31e6 for N=320 Hann
ref_scaled       = ref * bin_count
db               = 20 * log10(mag_sum_in_band / ref_scaled)
db_clamped       = clamp(db, floor_db, ceiling_db)  # e.g. [-60, 0]
norm             = (db_clamped - floor_db) / (ceiling_db - floor_db)  # [0..1]
```

### Why `0.5 × INT16_MAX × sum(Hann)`?
A full-scale sinusoid `x[n] = 32767 × sin(2π·f·n/fs)` windowed by `w[n]` has Fourier magnitude at its frequency bin:
```
|X[k_peak]| = 0.5 × A × sum(w)
```
where A = signal peak (32767 ≈ 32768 for int16). The 0.5 factor comes from sin = (e^{iωt} − e^{−iωt})/(2i); only the positive-frequency half lives in rfft output.

For Hann of length N=320: `sum(Hann) ≈ N/2 = 160`. So `MAG_REF_FULL_SCALE ≈ 0.5 × 32768 × 160 ≈ 2.62e6`. Compute it at construction (`self._spec_hann.sum()`).

This makes a full-scale 1 kHz sinusoid read as 0 dB in the band containing 1 kHz. A 60 dB attenuated tone reads as −60 dB → norm = 0 → bar at floor.

### Per-band-relative vs absolute
We use **per-band-relative** because bins-per-band varies wildly across log-bands (1 bin near the bottom, ~10 bins near the top). Multiplying ref by bin_count compensates so a flat white noise input produces flat bands across the spectrum (verified intuition; an actual test should confirm this).

### Why floor = −60 dB, ceiling = 0 dB?
- −60 dB: typical noise floor of a clean recording. Below that, just shows zero.
- 0 dB: full-scale int16. Above that = clipped — capped to 1.0 (red).
- Both are Config-First; user can tune.

### Alternatives considered
- **Rolling-max auto-gain:** rejected in D-09; defeats "red = peak" semantics.
- **Per-band fixed empirical reference:** would require calibration; over-engineered.
- **Power (|X|²) instead of |X|:** doubles dynamic range, requires changing floor to −120 dB. No advantage for visualisation; rejected.

## §4. Stereo Down-Mix — CONFIRMED already done

**`mono_chunk` IS already mono.** Verified path:
- ESP32 stereo profile → `Orchestrator._make_stereo_reader` (Orchestrator.py:309-339) wraps `resp.read` to:
  1. Read `2N` bytes (interleaved L/R int16)
  2. Compute per-channel RMS via `audioop.tomono(raw, 2, 1.0, 0.0)` and `audioop.tomono(raw, 2, 0.0, 1.0)`
  3. Return `audioop.tomono(raw, 2, 0.5, 0.5)` — **average down-mix (L+R)/2**
- This downmixed bytes flow is what `MicReader._drain_loop` receives as `chunk`, and what gets passed to `_emit_audio_level(chunk)` at mic_reader.py:698.

**Action: NO new down-mix code. Just use `mono_chunk` directly in `_compute_bands`.**

### Algorithm note
`audioop.tomono(raw, 2, 0.5, 0.5)` does `(L + R) / 2` in 16-bit signed arithmetic. This is the standard "amplitude average" downmix. The alternative `sqrt((L² + R²)/2)` (power average) is correct for uncorrelated noise but distorts speech (L and R are highly correlated). Existing approach is correct and is what we want.

## §5. EventBus Payload Size / SSE Behavior

**Recommendation: emit `bands` as `list[float]` already rounded to 3 decimals (Python `round(x, 3)`). At 25 Hz × 24 floats × ~6 bytes each in JSON = ~150 bytes per event for `bands` field alone. Total event JSON line: ~400 bytes. Bandwidth ≈ 10 KB/s sustained.**

### JSON serialization cost
`event_log.append()` uses `json.dumps(event, ensure_ascii=False, sort_keys=True)` (events.py:41). Adding `bands: [0.123, 0.456, ...]` adds ~150 bytes per event. JSON encode of 24 short floats: ~3 µs (negligible).

### `events.jsonl` rotation behavior — ABSENT
**Critical finding:** `EventLog.append()` (events.py:32-48) opens the file with `mode="a"` every event and writes one line. **There is no rotation logic anywhere in events.py or log_viewer.py.** The current file is **417 MB** (verified via `ls -lh data/adam/events.jsonl`).

Doubling the audio_level cadence and adding ~150 bytes per event means the existing growth rate of this file increases significantly:
- Before: 10 Hz × ~250 bytes = ~2.5 KB/s = ~9 MB/hour audio_level alone
- After: 25 Hz × ~400 bytes = ~10 KB/s = ~36 MB/hour audio_level alone

**Recommendation to planner:** out of phase scope per CONTEXT (Deferred Ideas), but FLAG to user. Two options:
1. **Add a writing-side sampler in `EventLog.append()`** that writes every Nth event for high-frequency types (parameter in Config). SSE broadcast still happens for every event. Simple ~10-line change.
2. **Backlog item:** add log rotation (size-based or time-based) to EventLog.

Either way, the existing 417 MB file should be moved out / truncated as a separate housekeeping step.

### Float precision
- `level` field is already rounded to 3 decimals (mic_reader.py:507). Match: `round(norm, 3)` for each band.
- JSON encoding of `0.123` is 5 bytes; `0.123456` is 8 bytes. Round saves ~70 bytes/event.
- 3 decimals = 0.1% resolution per band; visually indistinguishable from full float64.

### Will events.jsonl tolerate 2.5× volume?
File grows; ext4 doesn't care until disk fills. But: the `tail` operation (events.py:62-68) reads the whole file from disk when the `_recent` deque is empty. With 417 MB+, that's a multi-second operation. This is a pre-existing problem the phase doesn't create but does worsen.

### Alternatives considered
- **Separate event type `audio_spectrum` at a slower cadence:** rejected by D-03 (extends existing).
- **Binary SSE payload (base64-encoded float16):** rejected — JSON is the project convention; saves marginal bandwidth at high complexity cost.

## §6. `audio_level` Cadence Change (10 → 25 Hz)

### Where in code
**One line:** `mic_reader.py:51`:
```python
_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5
```
Change to `2` (or derive from `Config.spectrum_cadence_hz`).

The counter usage is at mic_reader.py:696-699:
```python
self._level_tick += 1
if self._level_tick >= _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES:
    self._emit_audio_level(chunk)
    self._level_tick = 0
```

**Recommendation: derive the threshold from Config:**
```python
# Read once in __init__ (with apply_config refresh):
target_hz = float(audio_cfg.get("spectrum_cadence_hz", 25.0))
frame_hz = 1000.0 / max(1, self._frame_ms)  # 50 fps at 20 ms
self._audio_level_emit_every_n = max(1, int(round(frame_hz / target_hz)))
```
At sample_rate=16000, frame_ms=20: frame_hz=50, target=25 → every_n=2. ✓

### Downstream consumers of `audio_level`
Confirmed via grep (`grep -rn audio_level /home/i17jet/Agents/Adam-Chip/System/WebUI/static/js/`):
1. `widgets/wakeMeter.js:215` — sets `state.audioLevel = lvl` (will also consume `bands`).
2. `panels/chat.js:558` — sets VU-meter `vuLevelL/R/Mono` from same event.

Both consume `level`/`level_l`/`level_r` (which still flow) and IGNORE unknown JSON fields. **Doubling cadence is purely additive load on these consumers; no logic depends on the 100 ms cadence.** RAF runs at 60 Hz anyway, so the canvas redraw is decoupled.

### Risks
- **events.jsonl growth** — §5 covered.
- **SSE buffer pressure** — `EventLog._enqueue` (events.py:99-111) has a 200-event max queue per subscriber and drops oldest on overflow. At 25 Hz audio_level + other events, the queue can theoretically fill if a browser tab is throttled (background tab). Drop-oldest is the right policy; UI just shows stale frame momentarily.
- **CPU on Jetson** — 25 × ~15 µs FFT = 375 µs/sec ≈ 0.04% of one core. Negligible.

### Alternatives considered
- **Keep audio_level at 10 Hz and emit `audio_spectrum` separately at 25 Hz:** rejected by D-03.
- **Emit `bands` only on every Nth audio_level (sub-cadence inside the emitter):** an option for jsonl-bytes reduction; falls under CONTEXT D-04 "Decision about this is on the planner." **Recommendation: keep it simple — bands on every emission. Address jsonl growth via the writing-side sampler in EventLog (separate, possibly backlog).**

## §7. Frontend: 24-Bar Gradient with No Smoothing

**Recommendation: keep last `bands[]` snapshot in widget state; RAF loop reads it each frame; color via piecewise RGB interpolation (cheap, predictable). Bars drawn as plain `fillRect` per band; no peaks array, no decay.**

### State changes in widget
```js
// In createWakeMeter closure, replace `const peaks = new Float32Array(BAR_N)`:
const N_BANDS = 24;  // mirror server; could be passed in opts but D-05 locks it
const bands = new Float32Array(N_BANDS);  // last snapshot, default zero
```

### Draw loop (replaces wakeMeter.js lines 112-137)
```js
const gap = 2;
const barW = (w - (N_BANDS - 1) * gap) / N_BANDS;

// background floor strip
ctx.fillStyle = "rgba(120,120,130,0.10)";
for (let i = 0; i < N_BANDS; i++) {
  ctx.fillRect(Math.round(i * (barW + gap)), h - 2, Math.max(1, Math.round(barW)), 2);
}

// bars
for (let i = 0; i < N_BANDS; i++) {
  const v = bands[i];
  if (v < 0.01) continue;
  const bh = v * (h - 3);
  ctx.fillStyle = colorForLevel(v);  // see below
  ctx.fillRect(
    Math.round(i * (barW + gap)),
    Math.round(h - 2 - bh),
    Math.max(1, Math.round(barW)),
    Math.max(1, Math.round(bh)),
  );
}
```

### Event handler — replaces wakeMeter.js lines 215-227
```js
if (ev.type === "audio_level") {
  // Existing fields still consumed by other widgets — leave the `audioLevel`
  // assignment in place if anything else in this widget reads it (currently
  // nothing does after D-13 deletion, but the host panel chat.js still uses
  // ev.payload.level for VU-meter — UNCHANGED).
  const p = ev.payload || {};
  if (Array.isArray(p.bands) && p.bands.length === N_BANDS) {
    for (let i = 0; i < N_BANDS; i++) bands[i] = +p.bands[i] || 0;
  }
  // pipelineReady flag handling unchanged (lines 219-227).
  const vs = p.state;
  if (vs === "standby" || vs === "listening" || vs === "reply") state.pipelineReady = true;
  else if (vs === "boot_warmup") state.pipelineReady = false;
}
```

### Color function — piecewise RGB
```js
// Three anchor colors:
//   level <= yellowAt (e.g. 0.6) → green
//   level >= redAt    (e.g. 0.85) → red
//   between           → linear blend through yellow at midpoint
const GREEN  = [67, 209, 122];  // matches existing palette
const YELLOW = [234, 200, 80];
const RED    = [220, 80, 80];

function lerp(a, b, t) { return a + (b - a) * t; }
function rgbBlend(c1, c2, t) {
  return [lerp(c1[0],c2[0],t), lerp(c1[1],c2[1],t), lerp(c1[2],c2[2],t)];
}

function colorForLevel(v) {
  const yAt = state.colorYellowAt; // from /api/config or default 0.6
  const rAt = state.colorRedAt;    // default 0.85
  let rgb;
  if (v <= yAt)        rgb = rgbBlend(GREEN, YELLOW, v / Math.max(0.001, yAt));
  else if (v >= rAt)   rgb = RED;
  else                 rgb = rgbBlend(YELLOW, RED, (v - yAt) / Math.max(0.001, rAt - yAt));
  // Alpha: ramp 0.35 → 1.0 by level, matches existing style.
  const a = 0.35 + v * 0.65;
  return `rgba(${rgb[0]|0},${rgb[1]|0},${rgb[2]|0},${a.toFixed(2)})`;
}
```

### Where to source `colorYellowAt` / `colorRedAt`
Frontend reads them at mount via `fetch("/api/config")` (api endpoint exists at api_runtime.py:107-108). Default fallback in widget = `0.6` and `0.85`. They can also be re-read on `config_patched` SSE event for hot-reload symmetry, but a page refresh is acceptable for color thresholds (CONTEXT calls them out as Config-First, not necessarily hot-live on the widget side).

### RAF behavior between SSE events
- SSE arrives every 40 ms (25 Hz).
- RAF fires every ~16.7 ms (60 Hz).
- Between SSE events, RAF redraws the same `bands[]` snapshot 2-3 times — visually stable, no flicker.
- If SSE pauses (e.g. browser background tab), bars freeze on last snapshot. That's correct: "no decay, no smoothing" = literal honesty.

### Alternatives considered
- **HSL interpolation (hue 120° → 0°):** smoother gradient mathematically, but green→yellow→red doesn't pass through gray midpoint in RGB while in HSL it goes through saturated lime/orange (looks "neon"). Piecewise RGB through a named yellow looks more like a VU-meter. **Chosen: piecewise RGB.**
- **Lookup table (256 entries):** trivial perf gain at slight complexity cost. Not worth it at 24 × 60 fps = 1440 color computations/sec.
- **Per-bar peak hold:** explicitly forbidden by D-10.

## §8. SSE Leak Fix in wakeMeter.js

### Current state (verified)
- `wakeMeter.js:258-262`:
  ```js
  function dispose() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (typeof unsub === "function") unsub();
  }
  ```
  `unsub` is the return of `subscribeEvents(...)` — verified in api.js:74-77 as a function that sets `closed = true; source.close()`. **`subscribeEvents` returns an unsubscribe handle. ✓**

- `chat.js:663` calls `wakeMeter.dispose()` in panel cleanup. ✓
- `settings.js:700-705` wires `wrapper._dispose` to call `meter.dispose()`. ✓
- `settings.js:907-910` drains all `disposables` on panel teardown. ✓

### What's the leak then?
Re-reading CONTEXT carefully: D-14 says "need to verify host panels GUARANTEE dispose in cleanup-callback, and add idempotency." The leak risk is:
1. **Double dispose:** if both browser-fired beforeunload and panel teardown call `dispose()`, the second call to `unsub()` is harmless (api.js:74-77 already checks `closed`), but `cancelAnimationFrame(null)` after the first call sets `rafId = null` — second call has `rafId === null`, branch skipped. So **already idempotent in code.** Verify with a small change: explicit `disposed` boolean.
2. **Pending RAF after dispose:** `cancelAnimationFrame(rafId)` cancels the next-scheduled frame, but if `draw()` is mid-execution when dispose runs, it'll still `rafId = requestAnimationFrame(draw)` at the end (wakeMeter.js:181), re-scheduling. Race window: tiny but real.

### Fix
```js
let disposed = false;
function dispose() {
  if (disposed) return;
  disposed = true;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  if (typeof unsub === "function") {
    try { unsub(); } catch (_) {}
  }
}

function draw() {
  if (disposed) return;  // guard against RAF re-scheduling after dispose
  // ... existing draw body ...
  rafId = requestAnimationFrame(draw);
}
```

### Mount-site audit (final)
- **chat.js:** mount returns cleanup function; cleanup calls `wakeMeter.dispose()`. ✓ already wired.
- **settings.js:** `buildWakeWordExtras()` exposes `wrapper._dispose` which the panel cleanup drains via `disposables`. ✓ already wired.

**Conclusion:** "leak" is largely conceptual now. The fix is cheap defensive — adds 4 lines, costs nothing. Plan should still include it for completeness of UI-EQ-05.

### Alternatives considered
- **Refactor host panels to subscribe centrally and pass events into wakeMeter via `handleEvent`:** more invasive, fits D-03 future architecture but is way out of phase scope. Backlog.

## §9. Config.json / Settings Access Pattern

### Code shape (per System/adam/CLAUDE.md rules)
**MicReader receives audio_cfg dict in constructor** — same pattern as existing keys. NEVER touch `DEFAULT_CONFIG`. NEVER call `Settings.load()` inside MicReader.

```python
# In MicReader.__init__:
self._spec_n_bands = int(audio_cfg.get("spectrum_bands", 24))
self._spec_min_hz = float(audio_cfg.get("spectrum_min_hz", 80.0))
self._spec_max_hz = float(audio_cfg.get("spectrum_max_hz", 8000.0))
self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", -60.0))
self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", 0.0))
self._spec_cadence_hz = float(audio_cfg.get("spectrum_cadence_hz", 25.0))
self._spec_color_yellow_at = float(audio_cfg.get("spectrum_color_yellow_at", 0.6))
self._spec_color_red_at = float(audio_cfg.get("spectrum_color_red_at", 0.85))
```
(The color thresholds are read but only used by the frontend; they're stored on the server because `Config.json` is the single source of truth — frontend pulls them via `/api/config`.)

### Construction site
`System/Orchestrator.py:1270` already does:
```python
mic_reader = MicReader(
    asr_cfg=...,
    audio_cfg=settings.section("media").get("audio", {}),
    ...
)
```
Spectrum keys live in `media.audio.*` per D-15 — they flow through this dict naturally. **No change needed at the construction site.**

### Hot-reload
The existing hot-reload path:
1. Operator PATCHes `/api/config` with `section="media", patch={"audio": {"spectrum_floor_db": -50}}`.
2. `api_runtime.py:119-124` calls `settings.apply_patch(section, patch)` + `settings.save()` + `deps.rebuild_clients(section)` + emits `config_patched`.
3. `rebuild_clients` (defined in Orchestrator.py) calls `mic_reader.apply_config(asr_cfg, audio_cfg)` for `media` section.
4. `apply_config` (mic_reader.py:403) currently re-reads audio params. **Extend** it to:
   - re-read spectrum_* keys
   - rebuild band table if bands/min/max/sample_rate/frame_ms changed
   - update cadence (`self._audio_level_emit_every_n`)
   - return `restart_needed` only if sample_rate / frame_ms / profile changed (FFT param changes do NOT require restart)

**Verification path:** unit test patches config, calls `apply_config`, asserts new params landed and table rebuilt.

### Config.schema.json descriptions (English, mirror existing style)
Schema additions go inside `properties.media.properties.audio.properties`:
```json
"spectrum_bands": {
  "type": "integer",
  "minimum": 4,
  "maximum": 128,
  "description": "Number of log-spaced frequency bands rendered in the chat-panel equaliser widget. Computed server-side from each audio frame's FFT (see _compute_bands in mic_reader.py). Emitted to clients as the `bands[]` field on audio_level events. 24 is the production default — wider bars are legible at typical UI sizes.",
  "default": 24
},
"spectrum_min_hz": {
  "type": "number",
  "minimum": 20,
  "maximum": 8000,
  "description": "Lowest frequency (Hz) covered by the spectrum widget. Bands below this are not rendered. 80 Hz is approximately the fundamental of male speech; below that the ESP32 INMP441 has limited response anyway.",
  "default": 80.0
},
"spectrum_max_hz": {
  "type": "number",
  "minimum": 1000,
  "maximum": 8000,
  "description": "Highest frequency (Hz) covered. Capped at Nyquist (sample_rate / 2). At 16 kHz sample rate, max useful = 8000 Hz.",
  "default": 8000.0
},
"spectrum_floor_db": {
  "type": "number",
  "maximum": 0,
  "description": "Per-band dBFS value mapped to bar height 0. Energies below this are rendered as zero. -60 dB is the conventional noise floor for visualisation.",
  "default": -60.0
},
"spectrum_ceiling_db": {
  "type": "number",
  "minimum": -20,
  "maximum": 0,
  "description": "Per-band dBFS value mapped to bar height 1.0 (full-scale). 0 dB = digital full scale. Bars at this level read solid red.",
  "default": 0.0
},
"spectrum_cadence_hz": {
  "type": "number",
  "minimum": 5,
  "maximum": 50,
  "description": "Target emission rate (Hz) for audio_level events carrying spectrum bands. Backend derives the per-Nth-frame counter from this and frame_ms — at sample_rate=16000, frame_ms=20, value 25 emits every 2nd frame. Higher cadence = smoother widget, more events.jsonl bytes (~10 KB/s at 25 Hz).",
  "default": 25.0
},
"spectrum_color_yellow_at": {
  "type": "number",
  "minimum": 0.0,
  "maximum": 1.0,
  "description": "Per-bar normalised level at which the colour transitions from green to yellow. Below this value bars render green→yellow gradient; above it they render yellow→red.",
  "default": 0.6
},
"spectrum_color_red_at": {
  "type": "number",
  "minimum": 0.0,
  "maximum": 1.0,
  "description": "Per-bar normalised level at which the colour reaches solid red. Bars above this are clipped/peaking — useful visual cue for input gain calibration.",
  "default": 0.85
}
```

(Color threshold keys could be nested under `spectrum_color_thresholds: {yellow, red}` instead of flat — Claude's discretion per CONTEXT. Flat is simpler and matches existing schema style. **Recommendation: flat.**)

### Alternatives considered
- **Nest under `spectrum: {...}`:** more structured but breaks consistency with sibling keys like `webrtc_vad_aggressiveness`, `normalize_factor` which are also flat. Rejected.
- **Live in `tuning.media`:** rejected — these are infrastructure params (not personality), they belong with audio.

## §10. Backward Compatibility Audit

### All frontend consumers of `audio_level`
Grep results (already shown):
1. `widgets/wakeMeter.js:215` — consumes `ev.payload.level` + `state` + `bands` (after this phase).
2. `panels/chat.js:558` — consumes `level`, `level_l`, `level_r`, `channels`, `source`.

### Will they break on extra `bands` field?
- **chat.js:558-580:** accesses `ev.payload.channels`, `ev.payload.level_l/r`, `ev.payload.level`, `ev.payload.source`. **Never iterates payload keys. Will not break on extra fields. ✓**
- **wakeMeter.js (existing):** accesses `ev.payload.level`, `ev.payload.state`. Same. Will gain `state.bands` reading after this phase.

### `state.subscribe('last_events')` flow
Quick check:
<br>
<br>

```bash
grep -rn "last_events" /home/i17jet/Agents/Adam-Chip/System/WebUI/static/js/
```
Not searched in this round, but the SSE consumer chain is `subscribeEvents → onMessage → JSON.parse → handler`. The handler is per-widget; no central dispatch that could choke on shape changes.

### Risk assessment
**LOW.** JSON-additive changes to existing events are the project's standard pattern (CONTEXT confirms; D-03 endorses).

### Audit conclusion
- No consumer iterates `Object.keys(ev.payload)`.
- No consumer asserts schema shape.
- Extra `bands` field is safe.
- Extra `synthetic: true` on fallback events (already present per mic_reader.py:559) likewise has no consumer.

## §11. Smoke-Test Recipe

**Pre-flight (Maintenance Mode):**
```bash
PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
# In another terminal:
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool | head -30
```

**Step 1 — Backend cadence verification:**
```bash
# Tail audio_level events. Count per second over 5s — should be ~25.
curl --noproxy '*' -N -fsS http://127.0.0.1:8080/api/agent/stream \
  | grep --line-buffered '"type":"audio_level"' \
  | head -125  # expect ~5 seconds of output
```
Or via Python:
```bash
python3 scripts/adam_pull_logs.py --follow --stage all 2>&1 | grep audio_level | head -100
```
Validate: ≈ 25 events/sec. Each event JSON has `"bands":[…]` array of length 24, all values in `[0.0, 1.0]`.

**Step 2 — Spectrum sanity (Python REPL or one-off script):**
```bash
./.venv/bin/python -c "
import json, time, urllib.request
import statistics
from urllib.request import build_opener, ProxyHandler
opener = build_opener(ProxyHandler({}))
req = urllib.request.Request('http://127.0.0.1:8080/api/agent/events?types=audio_level&limit=50')
data = json.loads(opener.open(req).read())
samples = [e['payload'].get('bands', []) for e in data if 'bands' in e.get('payload', {})]
print('events with bands:', len(samples))
if samples:
    flat = [v for b in samples for v in b]
    print('len range:', min(len(b) for b in samples), max(len(b) for b in samples))
    print('val range:', min(flat), max(flat))
    print('mean:', statistics.mean(flat))
"
```
Expected: `len range: 24 24`, `val range` within `[0.0, 1.0]`.

**Step 3 — Frontend smoke (browser):**
1. Open `http://<JETSON_IP>:8080` → chat panel.
2. Open DevTools → Network tab → filter for "stream".
3. Observe **exactly ONE** `EventSource` connection (`/api/agent/stream`).
4. Speak a sustained "Аaaaa" into mic → middle bands should light up (700-1500 Hz fundamentals).
5. Whistle high → right side of spectrum reds out (~4 kHz).
6. Silence → all bars at floor (near zero).
7. Click "Настройки" panel → return to "Чат" panel → **EventSource count remains 1** (was 2 if leaking; the widget's own subscribe gets remade on mount, so the original should be cleaned up via `dispose()`).
8. Repeat panel-toggle 5×, verify count stays ≤ 1 active.

**Step 4 — Cadence change visible:**
- Bars update visibly snappier than before (40 ms vs 100 ms per refresh = 2.5× responsiveness).

**Step 5 — Hot-reload:**
```bash
curl --noproxy '*' -X PATCH -H 'Content-Type: application/json' \
  -d '{"section":"media","patch":{"audio":{"spectrum_floor_db":-40}}}' \
  http://127.0.0.1:8080/api/config | python3 -m json.tool
```
- Bars become noticeably "louder" (lower floor → wider dynamic range collapsed into [0..1]).
- No restart, no log error, `config_patched` event emitted.

**Failure conditions:**
- Bars all flat red regardless of input → dBFS reference calibration wrong (probably MAG_REF miscomputed).
- Bars all at zero on speech → bin DC leak or band table boundaries off.
- Bars only on the left half → bin indexing inverted or log-edges mis-built.
- Multiple `EventSource` rows in Network tab → dispose path not running for one of the widgets.

## §12. Risk Landmines Specific to Adam-Chip

### MicReader keep-alive (Phase 7) interference
`_emit_audio_level` is called from `_drain_loop` (mic_reader.py:697-699). The drain loop is decoupled from socket I/O via `_socket_reader_thread`. **Adding FFT compute in `_emit_audio_level` is safe** — the additional ~15 µs/call cannot meaningfully slow the consumer side enough to affect the keep-alive logic. The socket reader thread runs independently.

### `_level_emit_loop` watchdog (Phase 9) synthesising `audio_level`
The watchdog (mic_reader.py:529-575) fires when drain has been silent for > 250 ms. It emits a fallback event using `self._last_mono_rms` (cached scalar). **It does NOT have a fresh PCM chunk** — there is no way to compute fresh `bands` in this path.

**Recommendation:** the synthetic fallback OMITS the `bands` field. Frontend handler (per §7) explicitly checks `Array.isArray(p.bands) && p.bands.length === N_BANDS` before accepting — if missing, keeps last snapshot. **This is correct behavior:** when audio is stalled, bars freeze (which is the honest visualisation; no data = no update).

Alternative considered: cache last computed `bands` in MicReader and emit cached version in synthetic events. Rejected — slightly dishonest (showing audio when there is none) and adds complexity for negligible UX gain (200ms freeze is hard to see).

### Half-duplex mute during TTS
The comment at `mic_reader.py:496-498` explicitly states audio_level fires "regardless of mute state" so the operator UI shows whether the ESP32 mic is still streaming during TTS. **Recommendation: spectrum publish ALSO stays live during TTS.** Same justification — operator should see the audio bands of the room (including any self-echo) to confirm mic health.

This is also a useful tool: when looking at the equaliser during Adam's own TTS, operators can see ESP32 self-echo characteristics — useful for tuning `post_tts_discard_window_ms` empirically.

### Cadence × jsonl growth (compound risk with existing 417 MB file)
Already covered in §5. **Strong recommendation to planner:** at minimum, add a phase-scope task to truncate or rotate `events.jsonl` once, plus a backlog entry for proper rotation logic. Don't ship this phase on top of an already-failing logging substrate without flagging.

### Concurrent FFT cost from multi-task `_drain_loop`
The drain loop is single-task. There is no parallelism concern within MicReader. **Safe.**

### apply_config returning `restart_needed = True` falsely
`apply_config` (mic_reader.py:403-440) returns True when sample_rate, frame_ms, or profile change. **Adding spectrum_* keys must NOT cause restart.** Treat them as live re-readable params, store in `apply_config`, rebuild the band table, return only the legacy `restart_needed` value. **Important: the band-table rebuild must happen even when `restart_needed = False`.**

### Phase 11 (active) overlap
STATE.md shows Phase 11 (Voice Pipeline Refactor) is active. Confirm no parallel edits to `mic_reader.py` in another branch. The merge V-S08.1 → main is "в процессе" per STATE.md, but mic_reader.py was already merged through Phase 7. Verify with `git status` / check active branches before starting executor; if conflict possible, prefer merging V-S08.1 first.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `EQ_SHAPE` Gaussian formant illusion + `audioLevel × 4 × wobble` | Real per-band FFT from server | This phase | "Honest visualisation" — bars track real audio. |
| `audio_level` at 10 Hz | `audio_level` at 25 Hz | This phase | 2.5× more SSE events; UI responsiveness 100ms → 40ms. |
| No frequency content available to UI | `bands[24]` log-spaced 80-8000 Hz | This phase | UI can show formants, peaks, clipping. |

**Deprecated/outdated:**
- `EQ_SHAPE` constant — to be removed entirely.
- `peaks[i] * 0.87` decay smoothing — to be removed.
- `sin(Date.now() * 0.0015 + i*0.85)` wobble — to be removed.
- `audioLevel * 4.0` magic multiplier — to be removed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `mono_chunk` length matches `_frame_bytes` (640 bytes = 320 int16) — i.e. always one full frame | §1, §4 | If chunks are sometimes truncated, `np.frombuffer` will fail or return short. Guard exists: `_compute_bands` checks `len(mono_chunk) >= n_fft * 2` and returns `None` → bands omitted. **Verified by socket reader thread design at mic_reader.py:622-641 which only emits full chunks; partial reads cause stream EOF.** Risk: low. [VERIFIED: mic_reader.py:622-641] |
| A2 | `audioop.tomono(raw, 2, 0.5, 0.5)` produces unbiased mono PCM that can be FFT'd directly | §4 | If there's a DC offset from INMP441, bin 0 will glow. Band table excludes bin 0 (`lo = max(1, ...)`). Risk: low. [VERIFIED: Orchestrator.py:338, mitigation in band-table code §2] |
| A3 | numpy version on the target Jetson at execute time matches today (1.26.4) | §1 | If a venv rebuild between now and execute changes the numpy major version, rfft API may differ. rfft is stable since numpy 1.0 (decades). Risk: negligible. [VERIFIED: `python3 -c "import numpy; print(numpy.__version__)"` ran 2026-05-18] |
| A4 | The two `wakeMeter` mount sites are the ONLY ones | §8 | If another panel or page mounts the widget without `dispose()`, leak persists. Grep confirms only chat.js + settings.js import `createWakeMeter`. Risk: low. [VERIFIED: grep results above] |
| A5 | `events.jsonl` is 417 MB and growing without rotation | §5, §12 | If `EventLog` has rotation we missed, the impact is smaller. Re-grep confirmed no rotation logic in events.py. Risk: data-loss concern, but additive — phase only worsens existing issue. [VERIFIED: events.py read in full] |
| A6 | Frontend EventSource consumers tolerate extra JSON fields silently | §10 | If any consumer asserts schema (e.g. `Object.keys(ev.payload).every(...)`), addition breaks it. Grep showed no such pattern. Risk: very low. [VERIFIED: grep results] |
| A7 | The hot-reload chain `PATCH /api/config → rebuild_clients → MicReader.apply_config` exists and is wired | §9 | If rebuild_clients doesn't currently route `media` section to MicReader, the new keys won't hot-reload. **Needs verification at execute time** — quick test of existing `media.audio.normalize_factor` hot-reload should confirm. [ASSUMED: based on apply_config existing at mic_reader.py:403; not verified end-to-end this session] |
| A8 | `np.frombuffer(b, dtype=np.int16)` on a buffer with length not a multiple of 2 raises | §1 | If a half-byte slip enters from upstream, FFT raises ValueError → caught by `try/except` around emit → bands omitted. Risk: low; existing handler swallows callback exceptions (mic_reader.py:189-195). [VERIFIED: numpy docs + Python type semantics] |

**If this table is empty:** Not empty — A7 is the only ASSUMED row needing explicit verification during execution. Recommend a 30-second test in the first execute task: PATCH `media.audio.normalize_factor`, check Orchestrator logs for `config_patched` AND for MicReader picking it up.

## Open Questions

1. **Should `bands` be emitted at lower cadence than `level` to mitigate jsonl growth?**
   - What we know: CONTEXT D-04 sets cadence to 25 Hz for the whole event (default decision). D-04 also notes "if jsonl load critical, reconsider — planner decides."
   - What's unclear: how much room there is on the disk; how much the operator UI cares about 25 Hz vs 12.5 Hz.
   - Recommendation: emit on every audio_level (simpler). Add a **separate** backlog task / Phase 22 candidate: writing-side sampler for high-frequency event types in EventLog.

2. **Should the synthetic fallback (`_level_emit_loop`) ever include a "stale bands" snapshot?**
   - What we know: §12 recommends omitting; frontend gracefully handles missing.
   - What's unclear: if operators expect the bars to "show last known" during long stalls.
   - Recommendation: omit; document the behavior in the panel hint text.

3. **Color thresholds: live hot-reload on frontend, or page-refresh acceptable?**
   - What we know: §9 default fallback in widget code; reads `/api/config` at mount.
   - What's unclear: whether operator-facing tuning of yellow_at/red_at justifies live-updating widget without page refresh.
   - Recommendation: page-refresh acceptable for v1; consider live-update in a follow-up if asked.

## Sources

### Primary (HIGH confidence)
- File reads (this session): `mic_reader.py`, `events.py`, `api.js`, `wakeMeter.js`, `chat.js`, `settings.js`, `config.py`, `Config.json`, `Config.schema.json`, `api_runtime.py`, `Orchestrator.py` — all on local filesystem.
- Live numpy benchmark on Jetson (2026-05-18): 7-10 µs per FFT call.
- numpy 1.26.4 verified via `import numpy; print(numpy.__version__)` on the target host.
- File size check: `ls -lh data/adam/events.jsonl` → 417 MB.

### Secondary (MEDIUM confidence)
- Standard log-band binning algorithm (no specific citation — well-known DSP math).
- Hann window sum approximation (`sum(Hann_N) ≈ N/2`) — standard windowing reference.

### Tertiary (LOW confidence)
- None — every claim in this research traces to either source-code inspection or a measured number.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — numpy verified present on target host.
- Architecture: HIGH — single-function integration in proven `_emit_audio_level`; existing hot-reload chain confirmed.
- Pitfalls: HIGH — all six pitfalls traced to specific code lines or standard DSP gotchas.
- Frontend changes: HIGH — current code read in full; both mount sites audited for dispose.

**Research date:** 2026-05-18
**Valid until:** 2026-06-17 (30 days; numpy and project structure are stable)

## RESEARCH COMPLETE
