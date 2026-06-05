---
phase: 21A
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - tests/test_mic_reader_spectrum.py
  - tests/conftest.py
autonomous: true
requirements:
  - UI-EQ-01
  - UI-EQ-02
  - UI-EQ-06
must_haves:
  truths:
    - "Pytest discovers tests/test_mic_reader_spectrum.py"
    - "All stub tests fail/skip with a clear MISSING marker pointing to Wave 1/2 plans"
    - "tests/conftest.py exposes synthetic mono-chunk fixtures (sine, silence, white noise)"
  artifacts:
    - path: "tests/test_mic_reader_spectrum.py"
      provides: "Stubs for UI-EQ-01/02/06 unit + integration tests"
      contains: "test_sine_localised, test_silence_floor, test_noise_distributed, test_payload_shape, test_cadence_constant, test_spectrum_keys_in_schema, test_hot_reload"
    - path: "tests/conftest.py"
      provides: "Synthetic mono-chunk fixtures (16 kHz, 320 int16 samples)"
      contains: "mono_chunk_sine, mono_chunk_silence, mono_chunk_white_noise"
  key_links:
    - from: "tests/test_mic_reader_spectrum.py"
      to: "tests/conftest.py fixtures"
      via: "pytest fixture injection (function args)"
      pattern: "def test_.*\\(.*mono_chunk_"
    - from: "tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema"
      to: "System/Config.schema.json"
      via: "json.load + key assertion"
      pattern: "spectrum_bands|spectrum_min_hz"
---

<objective>
Wave 0 test scaffold for Phase 21A. Create a pytest file with seven failing/MISSING stub tests covering every Wave 1+ requirement so the subsequent waves can iterate against red-green-refactor cycles.

Purpose: VALIDATION.md mandates Wave 0 BEFORE any code changes (Nyquist rule). Without these stubs, Wave 1 has no automated feedback loop and `pytest tests/test_mic_reader_spectrum.py -x -q` cannot run.
Output: One test file + one updated conftest fixture file. Tests are expected to FAIL (or `pytest.skip` with WAVE-1 marker) until Wave 1 lands.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-VALIDATION.md
@tests/test_memory_pipeline.py
@tests/conftest.py

<interfaces>
<!-- Synthetic mono-chunk fixtures must produce bytes matching MicReader's input contract: -->
<!-- sample_rate=16000, frame_ms=20, channels=1 (mono after audioop.tomono upstream) -->
<!-- => 320 int16 samples = 640 bytes per chunk. -->

Expected fixture signatures:
  mono_chunk_sine(freq_hz: float = 1000.0, amplitude: float = 0.5) -> bytes  # 640 bytes int16
  mono_chunk_silence() -> bytes                                              # 640 zero bytes
  mono_chunk_white_noise(amplitude: float = 0.5, seed: int = 0) -> bytes     # 640 bytes int16

These return raw little-endian int16 bytes ready for np.frombuffer(..., dtype=np.int16).

Schema test reads System/Config.schema.json directly via json.load. Required keys (all under properties.media.properties.audio.properties):
  spectrum_bands, spectrum_min_hz, spectrum_max_hz,
  spectrum_floor_db, spectrum_ceiling_db, spectrum_cadence_hz,
  spectrum_color_yellow_at, spectrum_color_red_at
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add synthetic mono-chunk fixtures to tests/conftest.py</name>
  <read_first>
    - tests/conftest.py (entire file) — preserve any existing fixtures; do not delete
    - tests/test_memory_pipeline.py (top of file, ~30 lines) — see pytest fixture import style used in this repo
    - 21A-RESEARCH.md §1 "IMPORTANT correction note on N" (line ~410) — confirms N=320 samples per chunk
    - 21A-VALIDATION.md "Wave 0 Requirements" section
  </read_first>
  <files>tests/conftest.py</files>
  <behavior>
    - mono_chunk_silence() returns exactly 640 bytes, all zero
    - mono_chunk_sine(freq_hz=1000.0, amplitude=0.5) returns 640 bytes of a windowed sine producing a single dominant frequency near freq_hz
    - mono_chunk_white_noise(amplitude=0.5, seed=0) returns 640 bytes of pseudo-random int16 PCM (deterministic via seed)
    - All three return raw little-endian int16 bytes (Python bytes, NOT numpy arrays) — same shape MicReader._emit_audio_level receives
  </behavior>
  <action>
    Append (do not overwrite) three pytest fixture functions to tests/conftest.py:
      - `mono_chunk_silence` — returns `bytes(640)`.
      - `mono_chunk_sine` — accepts optional freq_hz and amplitude params; uses numpy.sin to build an int16 array length 320, then `.tobytes()`. Sample rate is 16000. amplitude is fraction of int16 max (32767).
      - `mono_chunk_white_noise` — uses `numpy.random.default_rng(seed)` to build int16 white noise length 320, then `.tobytes()`. amplitude scales the rng output.

    Each fixture should be decorated `@pytest.fixture` (function-scoped). Use plain pytest fixtures (no `pytest_generate_tests`). Import numpy at the top of conftest.py if not already imported.

    If the file does not exist, create it. If it exists, append the new fixtures at the end without altering existing fixtures.
  </action>
  <verify>
    <automated>./.venv/bin/python -m pytest tests/ --collect-only -q 2>&1 | grep -E "mono_chunk_(sine|silence|white_noise)" | head -5; ./.venv/bin/python -c "import numpy; print('numpy ok', numpy.__version__)"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/conftest.py` contains `def mono_chunk_silence`, `def mono_chunk_sine`, `def mono_chunk_white_noise`
    - `grep -c "@pytest.fixture" tests/conftest.py | grep -v '^#'` returns at least 3 (or matches pre-existing count + 3)
    - `./.venv/bin/python -m pytest tests/ --collect-only -q` exits 0 (no import errors)
    - All three fixtures return objects of type `bytes` with length `640`
  </acceptance_criteria>
  <done>Three fixtures exist, pytest can collect them, conftest.py imports cleanly.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create tests/test_mic_reader_spectrum.py stubs for all UI-EQ-01/02/06 tests</name>
  <read_first>
    - tests/test_memory_pipeline.py (top 60 lines) — repo test style: imports, fixture use, asserts
    - tests/test_webrtc_vad.py — small pytest file using the same /tests pattern
    - 21A-RESEARCH.md §"Phase Requirements → Test Map" — exact test names and expected behaviors
    - 21A-VALIDATION.md "Per-Task Verification Map" — pytest command for each test
    - 21A-CONTEXT.md decision D-05 (24 bands), D-09 (dBFS floor -60 / ceiling 0)
  </read_first>
  <files>tests/test_mic_reader_spectrum.py</files>
  <behavior>
    File contains seven test functions, each implementing the assertion described below.
    Each test imports `MicReader` from `System.adam.mic_reader` lazily inside the test body, so the file is importable even before Wave 1 lands.
    Tests use `pytest.skip("WAVE-1: ...")` or `pytest.xfail("WAVE-1: ...")` when the feature is unimplemented; once Wave 1 lands they MUST run and assert. Choose `skip` for tests requiring backend code that does not exist yet; choose direct assertion (no skip) for tests reading on-disk artifacts that DO exist (e.g. schema file).
    Specifically:
      - test_sine_localised: build MicReader with audio_cfg dict containing spectrum_bands=24, spectrum_min_hz=80, spectrum_max_hz=8000, sample_rate=16000, frame_ms=20; call `_compute_bands(mono_chunk_sine(freq_hz=1000.0, amplitude=0.5))`; assert returned list length==24; assert index of max-value band corresponds to a band whose [min_hz, max_hz] range contains 1000 Hz. Skip with "WAVE-1: _compute_bands not yet implemented" until method exists.
      - test_silence_floor: feed mono_chunk_silence; assert all 24 values are in [0.0, 0.05].
      - test_noise_distributed: feed mono_chunk_white_noise(amplitude=0.9); assert at least 18 of 24 bands are > 0.5 (rough flat-ish distribution; account for log-band weighting).
      - test_payload_shape: monkeypatch MicReader._emit to capture the payload; call _emit_audio_level with a non-silent mono_chunk; assert "bands" key present, value is list[float] length 24, every value in [0.0, 1.0].
      - test_cadence_constant: assert that MicReader, constructed with audio_cfg containing spectrum_cadence_hz=25 and frame_ms=20, exposes an attribute (e.g. `_audio_level_emit_every_n` or named constant) whose value == 2 (i.e. emit every 2nd 20ms frame for 25 Hz). For 10 Hz it should be 5.
      - test_spectrum_keys_in_schema: open System/Config.schema.json, navigate to properties.media.properties.audio.properties, assert all 8 spectrum_* keys exist AND each has a non-empty "description" field.
      - test_hot_reload: construct MicReader with audio_cfg spectrum_floor_db=-60; call `apply_config(asr_cfg={}, audio_cfg={...spectrum_floor_db=-50})`; assert `self._spec_floor_db == -50.0`; assert that calling _compute_bands on a fixed mono_chunk returns different values vs. before the patch (dynamic range changed).
  </behavior>
  <action>
    Create `tests/test_mic_reader_spectrum.py` with module docstring `"""Phase 21A — FFT spectrum tests (UI-EQ-01/02/06)."""`.

    Top of file imports: `import json`, `import math`, `import pytest`, `import numpy as np`. Path to schema: `Path(__file__).resolve().parents[1] / "System" / "Config.schema.json"` — use `pathlib.Path`.

    Write each of the seven tests as a function `def test_<name>(<fixture_args>):`. Use the fixtures from Task 1 (`mono_chunk_sine`, `mono_chunk_silence`, `mono_chunk_white_noise`) as arguments where applicable.

    For tests that require `_compute_bands`, `_spec_floor_db`, or `_audio_level_emit_every_n` (Wave 1 attributes that do not yet exist), wrap the body in a `try: from System.adam.mic_reader import MicReader` and if the required attribute/method is missing call `pytest.skip("WAVE-1: <attribute> not yet implemented")`. Use `hasattr` / `getattr` rather than relying on AttributeError catches.

    For `test_spectrum_keys_in_schema`: do NOT skip — schema file exists today; the test should FAIL until Plan 02 adds keys. The eight keys to assert are: spectrum_bands, spectrum_min_hz, spectrum_max_hz, spectrum_floor_db, spectrum_ceiling_db, spectrum_cadence_hz, spectrum_color_yellow_at, spectrum_color_red_at.

    Do NOT instantiate a real MicReader (it has many constructor deps). Instead, build a minimal helper inside the test file `def _make_mic_reader(audio_cfg)` that calls the real constructor with stub callables for `read_fn_factory`, `on_chunk_callback`, `event_bus_emit`, `voice_loop_provider` (look at MicReader.__init__ signature and pass `lambda *a, **k: None` for each callable; pass `asr_cfg={}` and minimal required-but-non-callable args). If even that is too involved at stub time, mark those individual tests `pytest.skip("WAVE-1: MicReader construction stub needs implementation in plan 03")` — and add an explicit TODO comment on each skip naming Plan 03.

    Do NOT inline any FFT implementation in the test file. Tests describe expected behavior of `_compute_bands`; they do not implement it.

    Compile-check after writing: `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py --collect-only -q` must exit 0.
  </action>
  <verify>
    <automated>./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py --collect-only -q 2>&1 | tail -5; ./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -q 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_mic_reader_spectrum.py` exists
    - File contains exactly the seven function names: `test_sine_localised`, `test_silence_floor`, `test_noise_distributed`, `test_payload_shape`, `test_cadence_constant`, `test_spectrum_keys_in_schema`, `test_hot_reload` (verify with `grep -c "^def test_" tests/test_mic_reader_spectrum.py` == 7)
    - `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py --collect-only -q` exits 0 (no import errors, no syntax errors)
    - `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -q` runs; test_spectrum_keys_in_schema FAILS (expected — schema keys not yet added in Plan 02); all six others either FAIL or are SKIPPED with a "WAVE-1:" message
    - Wave 0 marker — add a top-level docstring line: `WAVE_0_NYQUIST_STUB = True` so reviewers can grep for it
  </acceptance_criteria>
  <done>Stub file collected by pytest, all seven test functions defined, expected red state (failures/skips with WAVE-1 markers) is observed and documented in the commit message.</done>
</task>

</tasks>

<verification>
- `./.venv/bin/python -m pytest tests/ --collect-only -q` exits 0 (whole suite collects)
- `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -q` runs and exits non-zero (expected red — Wave 1+ not yet landed)
- `grep -c "^def test_" tests/test_mic_reader_spectrum.py` outputs `7`
- `grep -c "@pytest.fixture" tests/conftest.py` is at least 3
- VALIDATION.md frontmatter `wave_0_complete: false` → flip to `true` in commit message reference (the executor of /gsd-verify will flip it)
</verification>

<success_criteria>
- Wave 0 NYQUIST gate satisfied: every UI-EQ-01/02/06 requirement has a named pytest test before Wave 1 begins
- Synthetic fixtures usable by Wave 1 tests without modification
- No false-green: every stub test either fails or skips with an explicit WAVE-1 marker
- Sampling latency target met: `pytest tests/test_mic_reader_spectrum.py -x -q` completes in < 5 seconds (verified by `time` wrapper if curious)
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-01-SUMMARY.md`
</output>
