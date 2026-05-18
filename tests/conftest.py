"""Pytest shared fixtures for the Adam-Chip test suite.

Phase 21A — Wave 0:
  Synthetic mono-chunk fixtures producing raw little-endian int16 PCM bytes
  that match the MicReader._emit_audio_level input contract:
    sample_rate = 16000 Hz, frame_ms = 20, channels = 1 (mono) =>
    320 int16 samples = 640 bytes per chunk.

  These fixtures back UI-EQ-01 / UI-EQ-02 / UI-EQ-06 tests in
  tests/test_mic_reader_spectrum.py and any future tests that need
  deterministic synthetic mic frames without touching the ESP32.
"""
from __future__ import annotations

import math

import numpy as np
import pytest


# ─── Constants matching MicReader / mic_reader.py production wiring ──────────
_SAMPLE_RATE = 16000  # Hz — services.asr.sample_rate (also media.audio.sample_rate)
_FRAME_MS = 20        # ms — media.audio.frame_ms (WebRTC VAD requirement)
_FRAME_SAMPLES = _SAMPLE_RATE * _FRAME_MS // 1000  # 320 int16 samples
_FRAME_BYTES = _FRAME_SAMPLES * 2                    # 640 bytes (int16 little-endian)
_INT16_MAX = 32767


# ─── Synthetic mono-chunk fixtures ───────────────────────────────────────────

@pytest.fixture
def mono_chunk_silence() -> bytes:
    """One 20 ms frame of pure digital silence (640 zero bytes)."""
    return bytes(_FRAME_BYTES)


@pytest.fixture
def mono_chunk_sine():
    """Factory fixture returning a windowed pure-tone mono chunk.

    Returns a callable so each test can pick its own freq / amplitude:
        chunk = mono_chunk_sine(freq_hz=1000.0, amplitude=0.5)
        # chunk is 640 bytes of int16 little-endian PCM.

    A Hann window is applied to reduce spectral leakage — the resulting
    FFT magnitude peak is sharply localised at freq_hz, matching what
    _compute_bands(mono_chunk) is expected to detect.
    """
    def _factory(freq_hz: float = 1000.0, amplitude: float = 0.5) -> bytes:
        n = _FRAME_SAMPLES
        t = np.arange(n, dtype=np.float64) / _SAMPLE_RATE
        # Hann window prevents discontinuity at frame edges
        window = np.hanning(n)
        wave = np.sin(2.0 * math.pi * freq_hz * t) * window
        peak = float(amplitude) * _INT16_MAX
        samples = (wave * peak).astype(np.int16)
        return samples.tobytes()
    return _factory


@pytest.fixture
def mono_chunk_white_noise():
    """Factory fixture returning a deterministic white-noise mono chunk.

    Returns a callable so each test can pick its own amplitude / seed:
        chunk = mono_chunk_white_noise(amplitude=0.9, seed=0)
        # chunk is 640 bytes of int16 little-endian PCM.

    Uses numpy.random.default_rng(seed) so output is byte-for-byte stable
    across test runs — critical for reproducible spectrum assertions.
    """
    def _factory(amplitude: float = 0.5, seed: int = 0) -> bytes:
        rng = np.random.default_rng(seed)
        # uniform [-1, 1) scaled to int16 range by amplitude
        raw = rng.uniform(-1.0, 1.0, size=_FRAME_SAMPLES)
        peak = float(amplitude) * _INT16_MAX
        samples = (raw * peak).astype(np.int16)
        return samples.tobytes()
    return _factory
