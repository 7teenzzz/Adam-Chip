"""WebRTC VAD wrapper — stateless, CPU-only, no PyTorch required.

Example::

    vad = WebRtcVadWrapper(aggressiveness=2)
    voiced = vad.predict(chunk_bytes, sample_rate=16000) >= 0.5
"""
from __future__ import annotations

try:
    import webrtcvad as _webrtcvad
except OSError as exc:
    raise OSError(
        "webrtcvad shared library failed to load. "
        "Install with: pip install webrtcvad"
    ) from exc
except ImportError as exc:
    raise ImportError(
        "webrtcvad is required. Install with: pip install webrtcvad"
    ) from exc

_VALID_FRAME_MS = frozenset({10, 20, 30})
_VALID_RATES = frozenset({8000, 16000, 32000, 48000})


class WebRtcVadWrapper:
    """Drop-in replacement for Silero VAD in VoiceLoopController.

    aggressiveness — 0 (least) to 3 (most aggressive noise filtering).
    Default 2 is a good balance for exhibition environments.
    """

    def __init__(self, aggressiveness: int = 2) -> None:
        if aggressiveness not in range(4):
            raise ValueError(f"aggressiveness must be 0–3, got {aggressiveness!r}")
        self._aggressiveness = aggressiveness
        self._vad = _webrtcvad.Vad(aggressiveness)

    @property
    def aggressiveness(self) -> int:
        return self._aggressiveness

    @aggressiveness.setter
    def aggressiveness(self, value: int) -> None:
        if value not in range(4):
            raise ValueError(f"aggressiveness must be 0–3, got {value!r}")
        # Rebuild the underlying Vad — _webrtcvad.Vad takes aggressiveness only
        # at construction; there is no live setter on the C++ side.
        self._aggressiveness = value
        self._vad = _webrtcvad.Vad(value)

    def predict(self, audio_bytes: bytes, sample_rate: int = 16000) -> float:
        """Return 1.0 if speech detected, 0.0 if not.

        audio_bytes: raw 16-bit mono PCM (10/20/30ms worth of samples)
        sample_rate: must be 8000, 16000, 32000, or 48000 Hz

        Return value is float so callers can use ``>= 0.5`` threshold,
        matching the Silero VAD interface used previously.
        """
        if not audio_bytes:
            return 0.0
        if sample_rate not in _VALID_RATES:
            raise ValueError(
                f"sample_rate must be one of {sorted(_VALID_RATES)}, got {sample_rate}"
            )
        n_samples = len(audio_bytes) // 2
        frame_ms = n_samples * 1000 // sample_rate
        if frame_ms not in _VALID_FRAME_MS:
            raise ValueError(
                f"frame duration must be 10/20/30 ms, got {frame_ms} ms "
                f"({n_samples} samples at {sample_rate} Hz, {len(audio_bytes)} bytes)"
            )
        try:
            return 1.0 if self._vad.is_speech(audio_bytes, sample_rate) else 0.0
        except Exception:
            return 0.0

    def is_speech(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        """Convenience wrapper returning bool instead of float."""
        return self.predict(audio_bytes, sample_rate) >= 0.5

    def reset_states(self) -> None:
        """No-op — WebRTC VAD is stateless. Exists for API compatibility."""
