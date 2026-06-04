"""Phase 29 technoflora tests — Wave 0 scaffold.

This file is the single Wave 0 home for all flora unit tests
(29-VALIDATION.md). Plan 02 fills `test_flora_config` (FLORA-05);
plans 03/04 fill the other three (`test_event_mapping` FLORA-03,
`test_vibro_silent_listening` FLORA-06, `test_rms_envelope` FLORA-04),
which exist now as skipped stubs so the names are stable.

Run: PYTHONPATH=System .venv/Scripts/python -m pytest tests/test_flora.py -x

Do NOT import `adam.flora` at module top — that module does not exist
until plan 03. The skipped stubs import it lazily inside their bodies.
"""
from __future__ import annotations

import io
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

# Make `adam.*` importable without relying solely on PYTHONPATH
# (mirrors tests/test_memory.py).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))

from adam.config import Settings  # noqa: E402


def _make_sine_wav(
    freq: int = 220,
    duration_s: float = 0.5,
    sample_rate: int = 24000,
    amplitude: int = 12000,
) -> bytes:
    """Synthesize a small mono 16-bit PCM WAV in-memory via stdlib `wave`.

    Returned as raw WAV bytes for plan 04's RMS-envelope assertions
    (no numpy — matches the audioop/wave idiom used elsewhere).
    """
    n_frames = int(duration_s * sample_rate)
    samples = (
        int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
        for i in range(n_frames)
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{n_frames}h", *samples))
    return buf.getvalue()


def test_flora_config() -> None:
    """FLORA-05: the flora config section parses with documented defaults."""
    flora = Settings.load().section("flora")
    assert isinstance(flora, dict) and flora, "flora section must be a non-empty dict"

    # Channel masks (D-02): light 0-10, vibro 11-14.
    assert flora["light_channels"] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert flora["vibro_channels"] == [11, 12, 13, 14]
    # All channel indices stay within the PCA9685 0-15 range.
    for ch in flora["light_channels"] + flora["vibro_channels"]:
        assert 0 <= ch <= 15

    # Gamma + crossfade (D-13 / D-09).
    assert flora["gamma"] == 2.2
    assert 150 <= flora["crossfade_ms"] <= 250

    # Speech RMS params (D-07 / D-08).
    speech = flora["speech"]
    assert speech["base_duty_pct"] == 25
    assert speech["peak_duty_pct"] == 90

    # Vibro policy (D-11): silent in listening/attentive.
    assert "attentive" in flora["vibro"]["silent_states"]


@pytest.mark.skip(reason="filled in plan 03 (FLORA-03 event->state mapping)")
def test_event_mapping() -> None:
    """FLORA-03: voice pipeline event -> flora preset mapping."""
    raise NotImplementedError


@pytest.mark.skip(reason="filled in plan 03 (FLORA-06 vibro silent in listening)")
def test_vibro_silent_listening() -> None:
    """FLORA-06: vibro channels muted while in attentive (listening) state."""
    raise NotImplementedError


@pytest.mark.skip(reason="filled in plan 04 (FLORA-04 WAV->RMS envelope)")
def test_rms_envelope() -> None:
    """FLORA-04: WAV -> RMS brightness envelope shape (uses _make_sine_wav)."""
    raise NotImplementedError
