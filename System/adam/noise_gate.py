"""Stationary noise suppression via spectral gating (noisereduce).

Applied to accumulated PCM before sending to ASR. Supports two modes:
- stationary: no reference sample needed, estimates noise from the signal itself
- sample: uses a recorded noise reference for more aggressive suppression

The noise sample is loaded from a WAV file (16kHz, mono, S16_LE).
"""
from __future__ import annotations

from pathlib import Path


class NoiseGate:
    SAMPLE_RATE = 16000

    def __init__(self, noise_sample_path: str | None = None) -> None:
        self._noise_ref: "np.ndarray | None" = None  # type: ignore[name-defined]
        self._enabled = True
        if noise_sample_path:
            self.load(noise_sample_path)

    @property
    def has_sample(self) -> bool:
        return self._noise_ref is not None

    def load(self, path: str) -> bool:
        """Load noise reference from WAV file. Returns True on success."""
        import wave
        import numpy as np

        p = Path(path)
        if not p.exists():
            return False
        try:
            with wave.open(str(p), "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            self._noise_ref = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return True
        except Exception:
            return False

    def clear_sample(self) -> None:
        self._noise_ref = None

    def process(self, pcm: bytes) -> bytes:
        """Apply noise suppression to raw S16_LE PCM. Returns processed PCM."""
        if not self._enabled:
            return pcm
        try:
            import numpy as np
            import noisereduce as nr

            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            reduced = nr.reduce_noise(
                y=audio,
                sr=self.SAMPLE_RATE,
                y_noise=self._noise_ref,
                stationary=(self._noise_ref is None),
            )
            return (np.clip(reduced, -1.0, 1.0) * 32768.0).astype(np.int16).tobytes()
        except Exception:
            return pcm
