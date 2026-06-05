---
phase: 21A
plan: 03
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - System/adam/mic_reader.py
autonomous: true
requirements:
  - UI-EQ-01
  - UI-EQ-02
  - UI-EQ-06
must_haves:
  truths:
    - "MicReader computes a 24-band log-frequency FFT spectrum on every drained mono_chunk that triggers _emit_audio_level"
    - "audio_level SSE event payload contains a `bands: list[float]` field of length 24 with each value in [0.0, 1.0] (dBFS-normalised)"
    - "Real audio_level events fire at 25 Hz (every 2nd 20-ms frame); synthetic fallback events from _level_emit_loop OMIT the bands field entirely"
    - "apply_config() picks up changes to all 8 spectrum_* keys without restart_needed=True and rebuilds the log-band table when bands/min_hz/max_hz change"
    - "_compute_bands handles edge cases: short chunk → returns None (bands key omitted); silence → all bands ≤ 0.05; full-scale 1 kHz sine → max-energy band's [lo_hz, hi_hz] interval contains 1000 Hz"
  artifacts:
    - path: "System/adam/mic_reader.py"
      provides: "Server-side FFT pipeline integrated into _emit_audio_level"
      contains: "def _compute_bands"
    - path: "System/adam/mic_reader.py"
      provides: "Log-band binning table builder"
      contains: "_build_log_band_table"
  key_links:
    - from: "MicReader._emit_audio_level"
      to: "MicReader._compute_bands"
      via: "method call inside emit, appends 'bands' to payload when not None"
      pattern: "self\\._compute_bands\\("
    - from: "MicReader.apply_config"
      to: "MicReader._spec_band_table rebuild"
      via: "dirty-flag check on bands/min_hz/max_hz/sample_rate/frame_ms"
      pattern: "_build_log_band_table\\("
    - from: "MicReader._level_emit_loop synthetic payload"
      to: "frontend handler"
      via: "absence of bands field — bars freeze on last snapshot"
      pattern: "synthetic.*True"
---

<objective>
Integrate real FFT spectrum computation into MicReader. On every drained mono_chunk that triggers `_emit_audio_level`, compute 24 log-frequency band magnitudes via numpy rfft, normalise to dBFS-linear [0..1], and attach as `bands` field on the audio_level event. Bump cadence from 10 Hz → 25 Hz (derived from spectrum_cadence_hz). Extend `apply_config` to read all 8 spectrum_* keys with lazy band-table rebuild.

Purpose: UI-EQ-01 (real spectrum), UI-EQ-02 (event format), UI-EQ-06 (Config-First). Backend half of the phase.
Output: One Python file patched. Plan 05 frontend depends on this emitting valid bands[24].
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-VALIDATION.md
@System/adam/mic_reader.py
@System/adam/CLAUDE.md
@CLAUDE.md

<interfaces>
Required new attributes on MicReader instance, all set in __init__ before _drain_loop entry:
  self._spec_n_bands         : int
  self._spec_min_hz          : float
  self._spec_max_hz          : float
  self._spec_floor_db        : float
  self._spec_ceiling_db      : float
  self._spec_cadence_hz      : float
  self._spec_color_yellow_at : float    # stored for /api/config exposure; NOT used in Python
  self._spec_color_red_at    : float    # stored for /api/config exposure; NOT used in Python
  self._spec_n_fft           : int      # derived from sample_rate * frame_ms / 1000 → 320 at prod defaults
  self._spec_hann            : np.ndarray (float32, length n_fft)
  self._spec_mag_ref         : float    # 0.5 * 32768 * sum(hann)
  self._spec_band_table      : list[tuple[int, int]]    # length n_bands; (lo_bin, hi_bin) inclusive
  self._audio_level_emit_every_n : int  # derived from spectrum_cadence_hz and frame_ms

New module-level helper:
  _build_log_band_table(n_fft, sample_rate, n_bands, min_hz, max_hz) -> list[tuple[int, int]]
  See RESEARCH §1 Pattern 1 for the math.

New method on MicReader:
  _compute_bands(self, mono_chunk: bytes) -> list[float] | None
  See RESEARCH §1 "Concrete code shape" — but use self._spec_n_fft (NOT 160; see correction note in §1).
  Returns None when mono_chunk is None or len < self._spec_n_fft * 2.
  Otherwise returns list[float] length self._spec_n_bands, each rounded to 3 decimals, each in [0.0, 1.0].

Existing constant to replace:
  Line 51: _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5 → derive from spectrum_cadence_hz in __init__ as self._audio_level_emit_every_n.
  Lines 696-699 in _drain_loop: replace the module constant reference with self._audio_level_emit_every_n.

Existing emit site to extend:
  _emit_audio_level (lines 493-527): after the payload dict is built (around line 527, before self._emit), call
  bands = self._compute_bands(mono_chunk); if bands is not None: payload["bands"] = bands.

Synthetic fallback rule (D-04, RESEARCH §12):
  _level_emit_loop (lines 529-575): NO change to add bands. Must remain WITHOUT bands key. Add a comment marker:
  "Phase 21A: synthetic events OMIT bands by design (RESEARCH §12); frontend keeps last snapshot."

apply_config extension:
  apply_config (lines 403-440 currently): after existing audio param re-reads, ALSO read the 8 spectrum_* keys.
  Compute table_dirty := (spectrum_bands changed OR spectrum_min_hz changed OR spectrum_max_hz changed OR sample_rate changed OR frame_ms changed).
  Compute cadence_dirty := (spectrum_cadence_hz changed OR frame_ms changed).
  If table_dirty: rebuild _spec_n_fft, _spec_hann, _spec_mag_ref, _spec_band_table.
  If cadence_dirty: recompute _audio_level_emit_every_n.
  spectrum_floor_db, spectrum_ceiling_db, color_yellow_at, color_red_at are read but require no rebuild.
  restart_needed return value MUST NOT be forced True by spectrum_* changes — they are all live-reloadable.

dBFS math (RESEARCH §3 Pattern 2):
  For each band (lo_bin, hi_bin):
    band_mag = float(spectrum[lo:hi+1].sum())   # sum of magnitudes, NOT power
    bin_count = hi - lo + 1
    ref = self._spec_mag_ref * max(1, bin_count)
    if band_mag < 1e-9: norm = 0.0
    else:
      db = 20.0 * log10(band_mag / ref)
      db = clamp(db, floor_db, ceiling_db)
      norm = (db - floor_db) / (ceiling_db - floor_db)
    append round(norm, 3)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add numpy import, _build_log_band_table helper, and spectrum state to MicReader.__init__</name>
  <read_first>
    - System/adam/mic_reader.py lines 1-60 (module-level imports, _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES constant)
    - System/adam/mic_reader.py lines 81-160 (__init__ method, especially around _normalize_factor at line 97)
    - 21A-RESEARCH.md §1 Pattern 1 (`_build_log_band_table` source)
    - 21A-RESEARCH.md §1 "Concrete code shape" + the correction note about N=320
    - 21A-RESEARCH.md §3 ("0.5 × INT16_MAX × sum(Hann)" reference math)
    - 21A-CONTEXT.md D-05 through D-09 (locked numeric decisions)
    - System/adam/CLAUDE.md rule: Config via audio_cfg dict only; never call Settings.load() inside MicReader
  </read_first>
  <files>System/adam/mic_reader.py, tests/test_mic_reader_spectrum.py</files>
  <behavior>
    - import numpy as np available at module top
    - Module-level function _build_log_band_table(n_fft, sample_rate, n_bands, min_hz, max_hz) returns list[tuple[int,int]] length n_bands; DC bin 0 skipped (lo >= 1); degenerate bands have hi == lo
    - MicReader.__init__ sets all 13 spectrum attributes listed in <interfaces>, deriving _spec_n_fft, _spec_hann (float32), _spec_mag_ref, _spec_band_table, _audio_level_emit_every_n
    - _audio_level_emit_every_n computation: frame_hz = 1000.0 / max(1, self._frame_ms); every_n = max(1, int(round(frame_hz / self._spec_cadence_hz))). At sample_rate=16000, frame_ms=20, spectrum_cadence_hz=25 → every_n=2
    - test_cadence_constant from Plan 01 passes against this attribute
  </behavior>
  <action>
    1. Edit System/adam/mic_reader.py top-of-file imports: add `import numpy as np` after the stdlib block, before any project imports.

    2. Add module-level function _build_log_band_table near the existing constants block (around line 50, beside _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES). Body implements RESEARCH §1 Pattern 1. Use math.log and math.exp. Return list[tuple[int,int]]. Clamp lo = max(1, int(floor(edges_hz[i] / bin_hz))); clamp hi = min(n_bins - 1, int(ceil(edges_hz[i+1] / bin_hz))); force hi = lo when degenerate.

    3. In MicReader.__init__, locate `self._normalize_factor = int(audio_cfg.get("normalize_factor", 8000))` (line 97). Immediately AFTER it, add the spectrum-config block reading all 8 keys via audio_cfg.get(...) with documented defaults (24, 80.0, 8000.0, -60.0, 0.0, 25.0, 0.6, 0.85). Store on self with the names from <interfaces>.

    4. Below that block, derive runtime tables:
       - self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))  (at 16000 × 20/1000 = 320)
       - self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
       - self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())
       - self._spec_band_table = _build_log_band_table(self._spec_n_fft, self._sample_rate, self._spec_n_bands, self._spec_min_hz, self._spec_max_hz)
       - frame_hz = 1000.0 / max(1, self._frame_ms)
       - self._audio_level_emit_every_n = max(1, int(round(frame_hz / self._spec_cadence_hz)))

    5. Keep module-level _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5 for now — Task 2 will switch the usage site to the instance attribute. Do NOT delete the constant in this task.

    6. Update Plan 01 stub helper _make_mic_reader in tests/test_mic_reader_spectrum.py so it can build a MicReader (the constructor signature is now stable). If unable to instantiate (other deps prevent it), unblock test_cadence_constant specifically by directly computing every_n from a minimal MicReader-like dataclass — prefer real construction; document the path chosen in the commit message.
  </action>
  <verify>
    <automated>./.venv/bin/python -c "from System.adam.mic_reader import _build_log_band_table; t=_build_log_band_table(320,16000,24,80.0,8000.0); assert len(t)==24; assert all(1<=lo<=hi for lo,hi in t); assert t[-1][1]<=160; print('table ok', t[0], t[-1])" &amp;&amp; ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_cadence_constant -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^import numpy as np" System/adam/mic_reader.py` returns a line in the top ~20 lines
    - `grep -nE "^def _build_log_band_table" System/adam/mic_reader.py` returns exactly one match
    - `./.venv/bin/python -c "from System.adam.mic_reader import _build_log_band_table; t=_build_log_band_table(320,16000,24,80.0,8000.0); assert len(t)==24 and all(1<=l<=h<=160 for l,h in t)"` exits 0
    - All 13 spectrum-related attributes set in __init__: `grep -c "self\\._spec_" System/adam/mic_reader.py` returns at least 10 (counting init writes + apply_config writes Task 3 will add)
    - `pytest tests/test_mic_reader_spectrum.py::test_cadence_constant -x -q` exits 0
    - `./.venv/bin/python -c "import System.adam.mic_reader"` exits 0
  </acceptance_criteria>
  <done>numpy imported, _build_log_band_table added, MicReader.__init__ populates spectrum_* state, cadence test passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement _compute_bands, wire into _emit_audio_level, switch cadence gate to instance attribute</name>
  <read_first>
    - System/adam/mic_reader.py lines 493-527 (_emit_audio_level — point of integration)
    - System/adam/mic_reader.py lines 696-699 (_drain_loop cadence gate)
    - System/adam/mic_reader.py lines 529-575 (_level_emit_loop synthetic fallback)
    - 21A-RESEARCH.md §1 "Concrete code shape for integration into _emit_audio_level"
    - 21A-RESEARCH.md §3 (dBFS math)
    - 21A-RESEARCH.md §12 ("Half-duplex mute during TTS" — spectrum stays live; "_level_emit_loop watchdog" — synthetic omits bands)
    - 21A-CONTEXT.md D-04 (cadence 25 Hz), D-09 (dBFS), D-17 (mono only)
  </read_first>
  <files>System/adam/mic_reader.py</files>
  <behavior>
    - New method MicReader._compute_bands(mono_chunk) returns None on empty/short input; otherwise returns list[float] length self._spec_n_bands with values in [0.0, 1.0] rounded to 3 decimals.
    - _emit_audio_level appends payload["bands"] when _compute_bands returns non-None. All other payload fields unchanged.
    - _drain_loop cadence gate reads self._audio_level_emit_every_n instead of the module constant.
    - _level_emit_loop synthetic payload continues to NOT include bands. A code comment marks this as by design.
  </behavior>
  <action>
    1. Add method `_compute_bands` to the MicReader class immediately after _emit_audio_level (before _level_emit_loop at line 529).

       Body (wrapped in try/except):
       - If not mono_chunk or len(mono_chunk) &lt; self._spec_n_fft * 2: return None.
       - samples = np.frombuffer(mono_chunk[: self._spec_n_fft * 2], dtype=np.int16).astype(np.float32)
       - windowed = samples * self._spec_hann
       - spectrum = np.abs(np.fft.rfft(windowed))
       - out = []
       - For each (lo, hi) in self._spec_band_table:
           band_mag = float(spectrum[lo : hi + 1].sum())
           bin_count = hi - lo + 1
           ref = self._spec_mag_ref * max(1, bin_count)
           if band_mag &lt; 1e-9: norm = 0.0
           else:
             db = 20.0 * math.log10(band_mag / ref)
             db_clamped = self._spec_floor_db if db &lt; self._spec_floor_db else (self._spec_ceiling_db if db &gt; self._spec_ceiling_db else db)
             span = self._spec_ceiling_db - self._spec_floor_db
             norm = (db_clamped - self._spec_floor_db) / span
           out.append(round(norm, 3))
       - return out

       Exception handler: on any exception, call self._emit("spectrum_error", {"err": str(e)}) AND return None. Do not let FFT failures kill the emit path. (Mirrors pitfall A8.)

    2. Modify _emit_audio_level. Around line 527, immediately before `self._emit("audio_level", payload)`, insert:
         bands = self._compute_bands(mono_chunk)
         if bands is not None:
             payload["bands"] = bands
       Do NOT touch any other payload field.

    3. Modify _drain_loop cadence check at lines 696-699:
       - Replace `if self._level_tick &gt;= _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES:` with `if self._level_tick &gt;= self._audio_level_emit_every_n:`.
       - Leave self._level_tick increment and reset lines unchanged.

    4. In _level_emit_loop (around line 555 where synthetic payload dict is built), add a comment ABOVE the payload dict:
       `# Phase 21A: synthetic events OMIT 'bands' by design (RESEARCH §12). No fresh PCM → no honest spectrum. Frontend keeps last snapshot.`
       Do NOT add bands to the synthetic payload.

    5. Keep _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5 as a module-level constant (deprecated alias). Update its comment to: `# DEPRECATED Phase 21A: cadence now per-instance via spectrum_cadence_hz; retained for backwards-compat readers.`
  </action>
  <verify>
    <automated>./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_sine_localised tests/test_mic_reader_spectrum.py::test_silence_floor tests/test_mic_reader_spectrum.py::test_noise_distributed tests/test_mic_reader_spectrum.py::test_payload_shape -x -q &amp;&amp; ./.venv/bin/python -c "from System.adam.mic_reader import MicReader; import inspect; src=inspect.getsource(MicReader._level_emit_loop); assert 'bands' not in src or 'OMIT' in src, 'synthetic loop must not emit bands'; print('synthetic-omit ok')" &amp;&amp; grep -nE "self\._audio_level_emit_every_n" System/adam/mic_reader.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "def _compute_bands" System/adam/mic_reader.py` returns one match inside class MicReader
    - `grep -nE "self\\._audio_level_emit_every_n" System/adam/mic_reader.py` returns at least 2 matches (init + drain_loop)
    - `grep -nE "_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES" System/adam/mic_reader.py | grep -v '^#'` shows the constant definition but NOT in the drain_loop gate line (gate now references self._audio_level_emit_every_n)
    - The synthetic-payload section of _level_emit_loop contains the literal substring "OMIT" or "Phase 21A" in a comment line preceding the payload dict
    - `pytest tests/test_mic_reader_spectrum.py::test_sine_localised tests/test_mic_reader_spectrum.py::test_silence_floor tests/test_mic_reader_spectrum.py::test_noise_distributed tests/test_mic_reader_spectrum.py::test_payload_shape -x -q` exits 0
    - `./.venv/bin/python -c "import System.adam.mic_reader"` exits 0
  </acceptance_criteria>
  <done>FFT pipeline wired into emit; cadence is per-instance; synthetic events omit bands; four Wave-0 unit tests go green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend apply_config to hot-reload spectrum_* keys with lazy table rebuild</name>
  <read_first>
    - System/adam/mic_reader.py lines 403-440 (existing apply_config; especially the audio block at line 428)
    - 21A-RESEARCH.md §2 "Hot-reload trigger" — code shape for table rebuild
    - 21A-RESEARCH.md §9 "Hot-reload" — flow from PATCH /api/config → rebuild_clients → apply_config
    - 21A-RESEARCH.md §12 "apply_config returning restart_needed = True falsely" — spectrum_* MUST NOT trigger restart_needed
    - 21A-CONTEXT.md D-16 (hot-reload required)
  </read_first>
  <files>System/adam/mic_reader.py</files>
  <behavior>
    - apply_config(asr_cfg, audio_cfg) re-reads all 8 spectrum_* keys from audio_cfg.
    - When spectrum_bands OR spectrum_min_hz OR spectrum_max_hz OR sample_rate OR frame_ms changed → rebuild _spec_n_fft, _spec_hann, _spec_mag_ref, _spec_band_table.
    - When spectrum_cadence_hz OR frame_ms changed → recompute _audio_level_emit_every_n.
    - spectrum_floor_db, spectrum_ceiling_db, spectrum_color_yellow_at, spectrum_color_red_at: stored verbatim, no table rebuild needed.
    - restart_needed return value is unchanged by spectrum_* delta — only the pre-existing sample_rate/frame_ms/profile checks may set it True.
    - test_hot_reload from Plan 01 passes: PATCH spectrum_floor_db=-50 → _spec_floor_db becomes -50.0; _compute_bands on a fixed mono_chunk produces different values pre/post.
  </behavior>
  <action>
    1. In apply_config (currently around line 403-440), after the existing block that re-reads self._normalize_factor (line 428), add a new block re-reading the 8 spectrum_* keys via audio_cfg.get(key, current_value) — same pattern as normalize_factor.

       Capture old values BEFORE overwriting so dirty flags can be computed:
         old_bands = self._spec_n_bands
         old_min   = self._spec_min_hz
         old_max   = self._spec_max_hz
         old_cad   = self._spec_cadence_hz

    2. Overwrite each self._spec_* attribute from audio_cfg.get(...) defaulted to the current value (so missing key = no change).

    3. Compute dirty flags:
       table_dirty = (self._spec_n_bands != old_bands
                      or self._spec_min_hz != old_min
                      or self._spec_max_hz != old_max
                      or restart_needed)   # sample_rate / frame_ms / profile change implies restart_needed already set elsewhere
       cadence_dirty = (self._spec_cadence_hz != old_cad or restart_needed)

    4. If table_dirty:
         self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))
         self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
         self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())
         self._spec_band_table = _build_log_band_table(self._spec_n_fft, self._sample_rate, self._spec_n_bands, self._spec_min_hz, self._spec_max_hz)
         self._emit("spectrum_band_table_rebuilt", {"n_bands": self._spec_n_bands, "n_fft": self._spec_n_fft, "min_hz": self._spec_min_hz, "max_hz": self._spec_max_hz})

    5. If cadence_dirty:
         frame_hz = 1000.0 / max(1, self._frame_ms)
         self._audio_level_emit_every_n = max(1, int(round(frame_hz / self._spec_cadence_hz)))

    6. Do NOT set restart_needed = True for any spectrum_* change. Leave the existing restart_needed computation alone.

    7. Return restart_needed as before.
  </action>
  <verify>
    <automated>./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py::test_hot_reload -x -q &amp;&amp; ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q &amp;&amp; ./.venv/bin/python -m pytest tests/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - apply_config body now references `self._spec_n_bands`, `self._spec_min_hz`, `self._spec_max_hz`, `self._spec_floor_db`, `self._spec_ceiling_db`, `self._spec_cadence_hz`, `self._spec_color_yellow_at`, `self._spec_color_red_at` at least once each (verify via grep on the function-body line range)
    - `grep -nE "spectrum_band_table_rebuilt" System/adam/mic_reader.py` returns at least one match
    - `pytest tests/test_mic_reader_spectrum.py::test_hot_reload -x -q` exits 0
    - `pytest tests/test_mic_reader_spectrum.py -x -q` exits 0 (all 7 Wave-0 tests green)
    - `pytest tests/ -x -q` exits 0 (full suite still green — no regression to memory/vad/scene tests)
    - apply_config still returns the pre-existing restart_needed semantics: a test changing only spectrum_floor_db must observe restart_needed == False (covered by test_hot_reload)
  </acceptance_criteria>
  <done>Hot-reload chain extended; spectrum_* params live-update without restart; all 7 stub tests green; full suite green.</done>
</task>

</tasks>

<verification>
- `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q` exits 0 (all 7 stubs green)
- `./.venv/bin/python -m pytest tests/ -x -q` exits 0 (full repo suite green)
- Manual probe: `./.venv/bin/python -c "from System.adam.mic_reader import MicReader, _build_log_band_table; t=_build_log_band_table(320,16000,24,80.0,8000.0); print('band 0 covers', t[0], 'hz range:', t[0][0]*50, '-', t[0][1]*50); print('band 23 covers', t[-1], 'hz range:', t[-1][0]*50, '-', t[-1][1]*50)"` — band 23 hi_bin × 50 Hz ≤ 8000
- Live run probe (manual, after Orchestrator restart): `curl --noproxy '*' -N -fsS http://127.0.0.1:8080/api/agent/stream | grep --line-buffered '"type":"audio_level"' | head -50` — count ~25 events/sec, each line contains `"bands":[`. Synthetic events (`"synthetic":true`) MUST NOT contain bands.
</verification>

<success_criteria>
- UI-EQ-01 satisfied: real per-band FFT magnitudes flow from MicReader on every drained frame
- UI-EQ-02 satisfied: audio_level event carries bands[24]; cadence at 25 Hz; backward-compat (existing consumers unaffected)
- UI-EQ-06 satisfied: every parameter sourced from Config.json via audio_cfg dict; hot-reload working
- No regression to existing tests; full pytest suite green
- _level_emit_loop watchdog still functions; its synthetic events explicitly omit bands
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-03-SUMMARY.md`
</output>
