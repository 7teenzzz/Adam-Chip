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
    assert speech["peak_duty_pct"] <= 71, "peak_duty_pct must not exceed 71% brightness cap"

    # Vibro policy (D-11): silent in listening/attentive.
    assert "attentive" in flora["vibro"]["silent_states"]


class _FakeMCU:
    """Records set_flora_state calls without touching the network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.channel_calls: list[list[dict]] = []
        self.value_max = 4095

    async def set_flora_state(self, state: str, params: dict | None = None):
        self.calls.append((state, dict(params or {})))
        return None

    async def set_channels(self, updates: list[dict]):
        self.channel_calls.append([dict(u) for u in updates])
        return None


def _make_controller(mcu) -> "object":
    """Build a FloraController with the real flora config section + fake MCU.

    event_log is None because these tests drive _handle directly (no subscribe
    loop / no asyncio queue) — the event->state mapping is the unit under test.
    """
    from adam.flora import FloraController

    flora_cfg = Settings.load().section("flora")
    return FloraController(flora_cfg, mcu, event_log=None)


def _states(mcu: "_FakeMCU") -> list[str]:
    return [state for state, _params in mcu.calls]


def test_event_mapping() -> None:
    """FLORA-03: voice pipeline event -> flora preset mapping."""
    import asyncio

    mcu = _FakeMCU()
    ctrl = _make_controller(mcu)

    async def drive() -> None:
        await ctrl._handle({"type": "wake_word_detected"})
        # First boot-exit is consumed by wake_bloom; mark booted so the plain
        # listening/standby mapping is exercised here.
        ctrl._booted = True
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "listening"}})
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "standby"}})
        await ctrl._handle({"type": "llm_thinking_started"})

    asyncio.run(drive())

    assert _states(mcu) == ["accent", "attentive", "breathe", "think_pulse"]


def test_wake_bloom_on_boot_exit() -> None:
    """FLORA-03: first voice_state_change out of boot_warmup -> wake_bloom (once)."""
    import asyncio

    mcu = _FakeMCU()
    ctrl = _make_controller(mcu)

    async def drive() -> None:
        # First transition OUT of boot_warmup = system coming alive.
        await ctrl._handle(
            {"type": "voice_state_change", "payload": {"from": "boot_warmup", "to": "standby"}}
        )
        # A LATER standby transition whose `from` is NOT boot_warmup -> breathe.
        await ctrl._handle(
            {"type": "voice_state_change", "payload": {"from": "reply", "to": "standby"}}
        )

    asyncio.run(drive())

    assert _states(mcu) == ["wake_bloom", "breathe"]


def test_vibro_silent_listening() -> None:
    """FLORA-06: vibro channels muted while in attentive (listening) state."""
    import asyncio

    mcu = _FakeMCU()
    ctrl = _make_controller(mcu)

    async def drive() -> None:
        ctrl._booted = True
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "listening"}})

    asyncio.run(drive())

    assert len(mcu.calls) == 1
    state, params = mcu.calls[0]
    assert state == "attentive"
    assert params.get("vibro_enabled") is False


def test_rms_envelope() -> None:
    """FLORA-04: WAV -> RMS brightness envelope shape (uses _make_sine_wav).

    Drives the real WAV->RMS pipeline on FloraController:
      - envelope is a list of floats in [0.0, 1.0]
      - sample count ~= duration_ms / frame_interval_ms (within +-1)
      - a louder WAV yields a higher mean level than a quieter WAV
      - duties map into base_duty_pct..peak_duty_pct of value_max
    """
    mcu = _FakeMCU()
    ctrl = _make_controller(mcu)

    duration_s = 0.5
    sample_rate = 24000
    loud = _make_sine_wav(duration_s=duration_s, sample_rate=sample_rate, amplitude=18000)
    quiet = _make_sine_wav(duration_s=duration_s, sample_rate=sample_rate, amplitude=3000)

    levels = ctrl._rms_envelope(loud)

    # Shape: list of floats normalized 0..1.
    assert isinstance(levels, list) and levels, "envelope must be a non-empty list"
    assert all(isinstance(x, float) for x in levels)
    assert all(0.0 <= x <= 1.0 for x in levels)

    # Count ~= duration / frame_interval (within +-1).
    flora_cfg = Settings.load().section("flora")
    frame_interval_ms = int(flora_cfg["speech"]["frame_interval_ms"])
    expected = int((duration_s * 1000) / frame_interval_ms)
    assert abs(len(levels) - expected) <= 1, (len(levels), expected)

    # Louder WAV -> higher mean level (monotonic w.r.t. amplitude).
    loud_mean = sum(levels) / len(levels)
    quiet_levels = ctrl._rms_envelope(quiet)
    quiet_mean = sum(quiet_levels) / len(quiet_levels)
    assert loud_mean > quiet_mean

    # Duty mapping stays within base..peak of value_max.
    duties = ctrl._envelope_to_duties(levels)
    assert len(duties) == len(levels)
    value_max = mcu.value_max
    base = int(round(value_max * flora_cfg["speech"]["base_duty_pct"] / 100.0))
    peak = int(round(value_max * flora_cfg["speech"]["peak_duty_pct"] / 100.0))
    assert all(base <= d <= peak for d in duties), (min(duties), max(duties), base, peak)

    # Empty / short WAV returns [] gracefully.
    assert ctrl._rms_envelope(b"") == []
