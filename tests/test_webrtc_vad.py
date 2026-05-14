"""Tests for WebRtcVadWrapper."""
from __future__ import annotations

import struct
import math
import pytest

from adam.webrtc_vad import WebRtcVadWrapper


RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = RATE * FRAME_MS // 1000  # 320
FRAME_BYTES = FRAME_SAMPLES * 2           # 640


def _silence_frame() -> bytes:
    return bytes(FRAME_BYTES)


def _sine_frame(freq: int = 300, amplitude: int = 8000) -> bytes:
    samples = [
        int(amplitude * math.sin(2 * math.pi * freq * i / RATE))
        for i in range(FRAME_SAMPLES)
    ]
    return struct.pack(f"<{FRAME_SAMPLES}h", *samples)


def _frame_for_ms(ms: int) -> bytes:
    n = RATE * ms // 1000
    return bytes(n * 2)


class TestInit:
    def test_default_aggressiveness(self):
        vad = WebRtcVadWrapper()
        assert vad is not None

    def test_all_valid_aggressiveness(self):
        for level in range(4):
            WebRtcVadWrapper(aggressiveness=level)

    def test_invalid_aggressiveness(self):
        with pytest.raises(ValueError):
            WebRtcVadWrapper(aggressiveness=4)


class TestPredict:
    def test_silence_returns_float(self):
        vad = WebRtcVadWrapper()
        result = vad.predict(_silence_frame(), sample_rate=RATE)
        assert isinstance(result, float)
        assert result in (0.0, 1.0)

    def test_silence_is_not_speech(self):
        vad = WebRtcVadWrapper(aggressiveness=3)
        assert vad.predict(_silence_frame(), RATE) < 0.5

    def test_sine_does_not_crash(self):
        vad = WebRtcVadWrapper()
        result = vad.predict(_sine_frame(), RATE)
        assert result in (0.0, 1.0)

    def test_empty_bytes_returns_zero(self):
        vad = WebRtcVadWrapper()
        assert vad.predict(b"", RATE) == 0.0

    def test_invalid_sample_rate(self):
        vad = WebRtcVadWrapper()
        with pytest.raises(ValueError, match="sample_rate"):
            vad.predict(_silence_frame(), sample_rate=44100)

    def test_10ms_frame(self):
        vad = WebRtcVadWrapper()
        frame = _frame_for_ms(10)
        result = vad.predict(frame, RATE)
        assert result in (0.0, 1.0)

    def test_30ms_frame(self):
        vad = WebRtcVadWrapper()
        frame = _frame_for_ms(30)
        result = vad.predict(frame, RATE)
        assert result in (0.0, 1.0)

    def test_invalid_frame_size(self):
        vad = WebRtcVadWrapper()
        bad_frame = _frame_for_ms(15)
        with pytest.raises(ValueError, match="frame duration"):
            vad.predict(bad_frame, RATE)


class TestIsSpeech:
    def test_returns_bool(self):
        vad = WebRtcVadWrapper()
        result = vad.is_speech(_silence_frame(), RATE)
        assert isinstance(result, bool)

    def test_consistent_with_predict(self):
        vad = WebRtcVadWrapper()
        frame = _silence_frame()
        assert vad.is_speech(frame, RATE) == (vad.predict(frame, RATE) >= 0.5)


class TestResetStates:
    def test_reset_is_noop(self):
        vad = WebRtcVadWrapper()
        vad.reset_states()
        result = vad.predict(_silence_frame(), RATE)
        assert result in (0.0, 1.0)
