"""Phase 21A — FFT spectrum tests (UI-EQ-01/02/06).

Wave 0 stub: seven failing/MISSING tests that fence the contract for
Waves 1 and 2. Each test is expected to FAIL or SKIP with a WAVE-1 (or
WAVE-2) marker until the implementation lands in 21A-02 / 21A-03.

Run:
    PYTHONPATH=System .venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q

Wave 0 marker — reviewers may grep for the constant below to verify the
NYQUIST gate is in place before Wave 1 starts.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest


# ─── Wave 0 stub marker — grep target for reviewers ──────────────────────────
WAVE_0_NYQUIST_STUB = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "System"))

SCHEMA_PATH = ROOT / "System" / "Config.schema.json"

# All eight Config.schema.json keys that must live under
# properties.media.properties.audio.properties (CONTEXT D-05 … D-11).
SPECTRUM_KEYS = (
    "spectrum_bands",
    "spectrum_min_hz",
    "spectrum_max_hz",
    "spectrum_floor_db",
    "spectrum_ceiling_db",
    "spectrum_cadence_hz",
    "spectrum_color_yellow_at",
    "spectrum_color_red_at",
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _default_audio_cfg(**overrides) -> dict:
    """Minimal audio_cfg dict consumed by MicReader.__init__ + spectrum reads."""
    cfg = {
        "sample_rate": 16000,
        "channels": 1,
        "frame_ms": 20,
        "esp32_mic_profile": "inmp441_philips32_stereo",
        "normalize_factor": 8000,
        # Phase 21A spectrum params (CONTEXT D-05 … D-11):
        "spectrum_bands": 24,
        "spectrum_min_hz": 80,
        "spectrum_max_hz": 8000,
        "spectrum_floor_db": -60.0,
        "spectrum_ceiling_db": 0.0,
        "spectrum_cadence_hz": 25,
        "spectrum_color_yellow_at": 0.6,
        "spectrum_color_red_at": 0.85,
    }
    cfg.update(overrides)
    return cfg


def _default_asr_cfg() -> dict:
    """Minimal asr_cfg required by MicReader.__init__."""
    return {
        "disable_local_fallback": True,
        "esp_open_timeout_sec": 8,
        "esp_probe_after_fails": 2,
        "esp_retry_backoff_sec": [2, 4, 8, 15],
    }


def _make_mic_reader(audio_cfg: dict | None = None):
    """Construct a MicReader for unit-testing _compute_bands / apply_config.

    Returns None if MicReader cannot be imported (pre-Wave-1 stub mode).
    Callers MUST skip the test when None is returned — never assert.

    Notes:
    - mcu, voice_loop are passed as None / no-op; we never call .start().
    - on_event is a no-op callable.
    - stereo_reader_factory is None — MicReader degrades to mono, which
      is exactly what spectrum tests want.
    """
    try:
        from adam.mic_reader import MicReader  # noqa: WPS433 — lazy import by design
    except ImportError:
        return None
    return MicReader(
        asr_cfg=_default_asr_cfg(),
        audio_cfg=audio_cfg if audio_cfg is not None else _default_audio_cfg(),
        mcu=None,
        voice_loop=None,
        on_event=lambda _ev, _payload: None,
        stereo_reader_factory=None,
    )


def _skip_until_wave_1(attr_or_method: str) -> None:
    """Standard skip marker for attributes that Wave 1 (21A-02) introduces."""
    pytest.skip(f"WAVE-1: {attr_or_method} not yet implemented in MicReader (see 21A-02-PLAN.md)")


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_sine_localised(mono_chunk_sine):
    """UI-EQ-01: 1 kHz sine input → energy concentrated in the band covering 1000 Hz.

    Wave 1 lands `_compute_bands(mono_chunk) -> list[float] | None`.
    """
    mr = _make_mic_reader()
    if mr is None or not hasattr(mr, "_compute_bands"):
        _skip_until_wave_1("MicReader._compute_bands")

    chunk = mono_chunk_sine(freq_hz=1000.0, amplitude=0.5)
    bands = mr._compute_bands(chunk)  # type: ignore[attr-defined]
    assert bands is not None, "_compute_bands returned None for a non-silent chunk"
    assert len(bands) == 24, f"expected 24 bands, got {len(bands)}"

    # The band index whose [min_hz, max_hz) interval contains 1000 Hz must
    # be the max-energy band. Log-spaced: 24 bands from 80 to 8000 Hz.
    min_hz, max_hz = 80.0, 8000.0
    edges = np.exp(np.linspace(math.log(min_hz), math.log(max_hz), 25))
    target_idx = int(np.searchsorted(edges, 1000.0) - 1)
    peak_idx = int(np.argmax(bands))
    # Allow ±1 band slop for Hann leakage at the bin boundary.
    assert abs(peak_idx - target_idx) <= 1, (
        f"peak band {peak_idx} (freq ≈ {edges[peak_idx]:.0f}–{edges[peak_idx+1]:.0f} Hz) "
        f"is more than 1 band away from target {target_idx} "
        f"(freq ≈ {edges[target_idx]:.0f}–{edges[target_idx+1]:.0f} Hz)"
    )


def test_silence_floor(mono_chunk_silence):
    """UI-EQ-01: silence in → all bands at floor [0.0, 0.05]."""
    mr = _make_mic_reader()
    if mr is None or not hasattr(mr, "_compute_bands"):
        _skip_until_wave_1("MicReader._compute_bands")

    bands = mr._compute_bands(mono_chunk_silence)  # type: ignore[attr-defined]
    assert bands is not None, "_compute_bands returned None for silence chunk"
    assert len(bands) == 24
    for i, v in enumerate(bands):
        assert 0.0 <= v <= 0.05, f"band[{i}] = {v} is outside silence floor [0, 0.05]"


def test_noise_distributed(mono_chunk_white_noise):
    """UI-EQ-01: full-scale white noise → most bands above 0.5.

    Allows for log-band weighting and Hann leakage: require ≥18 / 24 bands > 0.5.
    """
    mr = _make_mic_reader()
    if mr is None or not hasattr(mr, "_compute_bands"):
        _skip_until_wave_1("MicReader._compute_bands")

    chunk = mono_chunk_white_noise(amplitude=0.9, seed=0)
    bands = mr._compute_bands(chunk)  # type: ignore[attr-defined]
    assert bands is not None
    assert len(bands) == 24
    above = sum(1 for v in bands if v > 0.5)
    assert above >= 18, (
        f"only {above}/24 white-noise bands exceeded 0.5 — distribution too uneven; "
        f"bands={['%.2f' % v for v in bands]}"
    )


def test_payload_shape(monkeypatch, mono_chunk_sine):
    """UI-EQ-02: audio_level payload carries bands: list[float] length 24, all in [0, 1].

    Captures the payload via a monkeypatched _emit and inspects the bands field.
    """
    mr = _make_mic_reader()
    if mr is None or not hasattr(mr, "_emit_audio_level"):
        _skip_until_wave_1("MicReader._emit_audio_level (with bands field)")

    captured: list[dict] = []

    def _capture_emit(event_type: str, payload: dict) -> None:
        if event_type == "audio_level":
            captured.append(payload)

    monkeypatch.setattr(mr, "_emit", _capture_emit)
    mr._emit_audio_level(mono_chunk_sine(freq_hz=1000.0, amplitude=0.5))  # type: ignore[attr-defined]

    assert captured, "no audio_level event emitted"
    payload = captured[-1]
    assert "bands" in payload, f"audio_level payload missing 'bands' key: {payload}"
    bands = payload["bands"]
    assert isinstance(bands, list), f"bands must be list, got {type(bands).__name__}"
    assert len(bands) == 24, f"expected 24 bands, got {len(bands)}"
    for i, v in enumerate(bands):
        assert isinstance(v, float), f"bands[{i}] = {v!r} is not float"
        assert 0.0 <= v <= 1.0, f"bands[{i}] = {v} outside [0, 1]"


def test_cadence_constant():
    """UI-EQ-02: cadence config drives _audio_level_emit_every_n.

    25 Hz @ 20 ms frame_ms => emit every 2nd frame.
    10 Hz @ 20 ms frame_ms => emit every 5th frame.
    """
    mr_25 = _make_mic_reader(_default_audio_cfg(spectrum_cadence_hz=25))
    if mr_25 is None or not hasattr(mr_25, "_audio_level_emit_every_n"):
        _skip_until_wave_1("MicReader._audio_level_emit_every_n")

    assert mr_25._audio_level_emit_every_n == 2, (  # type: ignore[attr-defined]
        f"25 Hz cadence @ 20 ms frame should emit every 2nd frame, "
        f"got every {mr_25._audio_level_emit_every_n}th"  # type: ignore[attr-defined]
    )

    mr_10 = _make_mic_reader(_default_audio_cfg(spectrum_cadence_hz=10))
    assert mr_10._audio_level_emit_every_n == 5, (  # type: ignore[attr-defined]
        f"10 Hz cadence @ 20 ms frame should emit every 5th frame, "
        f"got every {mr_10._audio_level_emit_every_n}th"  # type: ignore[attr-defined]
    )


def test_spectrum_keys_in_schema():
    """UI-EQ-06: Config.schema.json documents every spectrum_* key with a non-empty description.

    NO skip — schema file exists today. This test FAILS until 21A-02 adds the keys.
    """
    assert SCHEMA_PATH.is_file(), f"Config.schema.json not found at {SCHEMA_PATH}"
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    audio_props = (
        schema.get("properties", {})
        .get("media", {})
        .get("properties", {})
        .get("audio", {})
        .get("properties", {})
    )
    assert audio_props, "media.audio.properties section missing from Config.schema.json"

    missing = []
    no_desc = []
    for key in SPECTRUM_KEYS:
        if key not in audio_props:
            missing.append(key)
            continue
        desc = audio_props[key].get("description", "").strip()
        if not desc:
            no_desc.append(key)

    assert not missing, (
        f"Config.schema.json is missing spectrum keys: {missing}. "
        "Add them under properties.media.properties.audio.properties (21A-02)."
    )
    assert not no_desc, (
        f"spectrum keys have empty 'description': {no_desc}. "
        "Every spectrum_* key must document its purpose for hot-reload UI tooling."
    )


def test_hot_reload(mono_chunk_sine):
    """UI-EQ-06: apply_config updates _spec_floor_db and rebuilds the band table.

    Verifies hot-reload: feeding the same chunk before vs after a floor_db
    patch yields different normalised band values (the dynamic range moves).
    """
    mr = _make_mic_reader(_default_audio_cfg(spectrum_floor_db=-60.0))
    if (
        mr is None
        or not hasattr(mr, "_compute_bands")
        or not hasattr(mr, "_spec_floor_db")
        or not hasattr(mr, "apply_config")
    ):
        _skip_until_wave_1("MicReader._compute_bands / _spec_floor_db / apply_config")

    chunk = mono_chunk_sine(freq_hz=1000.0, amplitude=0.3)
    bands_before = list(mr._compute_bands(chunk))  # type: ignore[attr-defined]

    new_audio_cfg = _default_audio_cfg(spectrum_floor_db=-50.0)
    mr.apply_config(asr_cfg=_default_asr_cfg(), audio_cfg=new_audio_cfg)  # type: ignore[attr-defined]

    assert math.isclose(mr._spec_floor_db, -50.0, abs_tol=1e-6), (  # type: ignore[attr-defined]
        f"_spec_floor_db not updated by apply_config; expected -50.0, got {mr._spec_floor_db}"  # type: ignore[attr-defined]
    )

    bands_after = list(mr._compute_bands(chunk))  # type: ignore[attr-defined]
    assert bands_before != bands_after, (
        "band values did not change after floor_db patch — apply_config "
        "either did not rebuild the binning table or the normalisation "
        "is not floor-dependent"
    )
