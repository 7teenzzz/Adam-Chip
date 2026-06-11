"""Flora coexistence priority system tests (Phase 36, Direction 1).

Tests for FloraPriority (P1/P2/P3) coexistence logic in FloraController:
  - P2 pushed immediately when P3 is idle
  - P2 deferred while P3 is active (non-breathe preset)
  - P2 restored after tts_finished → breathe
  - P2 restored after voice_state_change → standby
  - D-11: vibro still silent in attentive state even with P2 pending
  - RMS multiplier updates from audio_level events
  - push_preset_p2_emotion variant selection (a vs b)

Run: PYTHONPATH=System .venv/bin/python -m pytest tests/test_flora_priority.py -v
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))

from adam.flora import FloraController, FloraPriority
from adam.config import Settings


class _FakeResult:
    ok = True
    status = 200
    error = None


class _FakeMCU:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.value_max = 4095

    async def set_flora_state(self, state: str, params: dict | None = None):
        self.calls.append((state, dict(params or {})))
        return _FakeResult()

    async def set_channels(self, updates: list[dict]):
        return _FakeResult()


def _make_ctrl(mcu: _FakeMCU) -> FloraController:
    flora_cfg = Settings.load().section("flora")
    ctrl = FloraController(flora_cfg, mcu, event_log=None)
    ctrl._booted = True  # skip wake_bloom in all tests
    return ctrl


def _states(mcu: _FakeMCU) -> list[str]:
    return [s for s, _ in mcu.calls]


# ── P2 immediate push when P3 is idle ─────────────────────────────────────────

def test_p2_pushed_immediately_when_idle() -> None:
    """P2 preset fires immediately when no P3 pipeline is active."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    asyncio.run(ctrl.push_preset_p2("curious_a"))

    assert _states(mcu) == ["curious_a"]
    assert ctrl._current_priority == FloraPriority.P2_SUBCONSCIOUS
    assert ctrl._current_preset == "curious_a"


def test_p2_priority_set_on_push() -> None:
    """_current_priority becomes P2_SUBCONSCIOUS after immediate P2 push."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    asyncio.run(ctrl.push_preset_p2("calm_b"))

    assert ctrl._current_priority == FloraPriority.P2_SUBCONSCIOUS


# ── P2 deferred while P3 is active ────────────────────────────────────────────

def test_p2_deferred_during_think_pulse() -> None:
    """P2 push during think_pulse (P3 active) is saved but NOT sent to MCU."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        await ctrl._handle({"type": "llm_thinking_started"})  # P3 → think_pulse
        mcu.calls.clear()  # clear setup calls
        await ctrl.push_preset_p2("curious_a")               # P2 attempt

    asyncio.run(drive())

    # P2 was saved but NOT sent (P3 is active)
    assert _states(mcu) == []
    assert ctrl._p2_preset == "curious_a"
    assert ctrl._current_preset == "think_pulse"  # P3 still owns lights


def test_p2_deferred_during_attentive() -> None:
    """P2 push during attentive (listening) is deferred."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "listening"}})
        mcu.calls.clear()
        await ctrl.push_preset_p2("calm_a")

    asyncio.run(drive())

    assert _states(mcu) == []
    assert ctrl._p2_preset == "calm_a"


def test_p2_not_deferred_during_breathe() -> None:
    """P2 push while current preset is breathe is NOT deferred (breathe = idle)."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "standby"}})
        # standby → breathe + _restore_p2 (no P2 yet, so just breathe)
        mcu.calls.clear()
        await ctrl.push_preset_p2("curious_b")

    asyncio.run(drive())

    assert _states(mcu) == ["curious_b"]
    assert ctrl._current_priority == FloraPriority.P2_SUBCONSCIOUS


# ── P2 restored after P3 ends ─────────────────────────────────────────────────

def test_p2_restored_after_tts_finished() -> None:
    """P2 preset is restored after tts_finished → breathe."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        # Set P2 while idle
        await ctrl.push_preset_p2("curious_a")
        mcu.calls.clear()

        # P3 cycle: TTS runs
        ctrl._answer_active = True
        ctrl._current_priority = FloraPriority.P3_PIPELINE
        ctrl._current_preset = "external"

        # TTS finishes
        await ctrl._handle({"type": "tts_finished"})

    asyncio.run(drive())

    # Should see: breathe (P3 cleanup) → curious_a (P2 restore)
    states = _states(mcu)
    assert "breathe" in states
    assert "curious_a" in states
    assert states.index("breathe") < states.index("curious_a")
    assert ctrl._current_priority == FloraPriority.P2_SUBCONSCIOUS


def test_p2_restored_after_standby() -> None:
    """P2 preset is restored after voice_state_change → standby."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        await ctrl.push_preset_p2("calm_b")
        mcu.calls.clear()

        # Simulate P3 active then standby
        ctrl._current_priority = FloraPriority.P3_PIPELINE
        ctrl._current_preset = "attentive"
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "standby"}})

    asyncio.run(drive())

    states = _states(mcu)
    assert "breathe" in states
    assert "calm_b" in states
    assert states.index("breathe") < states.index("calm_b")


def test_p2_not_restored_if_p3_still_active() -> None:
    """_restore_p2 is a no-op when P3 is still holding a non-breathe preset."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)
    ctrl._p2_preset = "curious_a"
    ctrl._current_priority = FloraPriority.P3_PIPELINE
    ctrl._current_preset = "think_pulse"

    asyncio.run(ctrl._restore_p2())

    assert _states(mcu) == []  # nothing sent


# ── D-11: vibro always OFF in attentive ───────────────────────────────────────

def test_d11_attentive_forces_vibro_off_with_p2_pending() -> None:
    """D-11 invariant: attentive state silences vibro even if P2 wants it ON."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        # Pre-set a P2 state that might have vibro (for future Phase 2 presets)
        ctrl._p2_preset = "curious_a"
        # P3 → attentive
        await ctrl._handle({"type": "voice_state_change", "payload": {"to": "listening"}})

    asyncio.run(drive())

    attentive_calls = [(s, p) for s, p in mcu.calls if s == "attentive"]
    assert attentive_calls, "attentive must be sent"
    for _, params in attentive_calls:
        assert params.get("vibro_enabled") is False, "D-11: vibro must be OFF in attentive"


# ── RMS multiplier from audio_level events ────────────────────────────────────

def test_rms_multiplier_updates_from_audio_level() -> None:
    """audio_level events update _rms_multiplier to 0.80..1.0 range."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        # Feed 30 audio_level events at level 0.0 (silence)
        for _ in range(30):
            await ctrl._handle({"type": "audio_level", "payload": {"level": 0.0}})

    asyncio.run(drive())

    assert ctrl._rms_multiplier == pytest.approx(0.80, abs=0.01)


def test_rms_multiplier_full_signal() -> None:
    """At full level (1.0), rms_multiplier saturates at 1.0."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        for _ in range(30):
            await ctrl._handle({"type": "audio_level", "payload": {"level": 1.0}})

    asyncio.run(drive())

    assert ctrl._rms_multiplier == pytest.approx(1.0, abs=0.01)


def test_rms_multiplier_mid_level() -> None:
    """At level 0.5, rms_multiplier should be approximately 0.90."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        for _ in range(30):
            await ctrl._handle({"type": "audio_level", "payload": {"level": 0.5}})

    asyncio.run(drive())

    assert ctrl._rms_multiplier == pytest.approx(0.90, abs=0.01)


def test_audio_level_does_not_change_flora_state() -> None:
    """audio_level events must NOT trigger any flora state changes."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        await ctrl._handle({"type": "audio_level", "payload": {"level": 0.8}})
        await ctrl._handle({"type": "audio_level", "payload": {"level": 0.9}})

    asyncio.run(drive())

    assert mcu.calls == []  # no MCU calls from audio_level events


def test_rms_multiplier_applied_to_p2_peak() -> None:
    """When rms_multiplier < 1.0, peak_duty in P2 preset is scaled down."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    async def drive() -> None:
        # Drive RMS to 0.0 → multiplier = 0.80
        for _ in range(30):
            await ctrl._handle({"type": "audio_level", "payload": {"level": 0.0}})

        await ctrl.push_preset_p2("curious_a")

    asyncio.run(drive())

    assert mcu.calls, "curious_a must be sent"
    state, params = mcu.calls[-1]
    assert state == "curious_a"

    # Build expected unscaled peak_duty from config
    flora = Settings.load().section("flora")
    preset = flora["states"]["curious_a"]
    max_duty = int(round(4095 * flora["max_duty_pct"] / 100))
    unscaled_peak = min(int(round(4095 * preset["peak_pct"] / 100)), max_duty)
    expected_scaled = int(round(unscaled_peak * 0.80))

    assert params["peak_duty"] == expected_scaled, (
        f"Expected peak_duty={expected_scaled}, got {params['peak_duty']}"
    )


# ── push_preset_p2_emotion variant selection ─────────────────────────────────

def test_emotion_variant_a_for_low_intensity() -> None:
    """intensity <= 0.65 selects variant _a."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    asyncio.run(ctrl.push_preset_p2_emotion("curious", intensity=0.4))

    assert _states(mcu) == ["curious_a"]


def test_emotion_variant_b_for_high_intensity() -> None:
    """intensity > 0.65 selects variant _b."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    asyncio.run(ctrl.push_preset_p2_emotion("curious", intensity=0.8))

    assert _states(mcu) == ["curious_b"]


def test_emotion_fallback_to_a_if_b_missing() -> None:
    """If _b variant not in config, falls back to _a."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    # "warm" is not in Phase 1 config — should fall back gracefully (no crash)
    asyncio.run(ctrl.push_preset_p2_emotion("warm", intensity=0.9))

    # warm_b/warm_a not in config → no MCU call, no crash
    assert mcu.calls == []


def test_unknown_emotion_skipped_gracefully() -> None:
    """Completely unknown emotion name produces no MCU call and no exception."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)

    asyncio.run(ctrl.push_preset_p2_emotion("nonexistent_emotion", intensity=0.5))

    assert mcu.calls == []


# ── P2 state saved correctly ──────────────────────────────────────────────────

def test_p2_state_saved_on_defer() -> None:
    """When P2 is deferred, _p2_preset and _p2_params are saved for restore."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)
    ctrl._current_priority = FloraPriority.P3_PIPELINE
    ctrl._current_preset = "think_pulse"

    asyncio.run(ctrl.push_preset_p2("calm_a", params={"crossfade_ms": 100}))

    assert ctrl._p2_preset == "calm_a"
    assert ctrl._p2_params == {"crossfade_ms": 100}


def test_p2_overwritten_by_newer_call() -> None:
    """A second push_preset_p2 call while P3 active updates the saved preset."""
    mcu = _FakeMCU()
    ctrl = _make_ctrl(mcu)
    ctrl._current_priority = FloraPriority.P3_PIPELINE
    ctrl._current_preset = "think_pulse"

    async def drive() -> None:
        await ctrl.push_preset_p2("calm_a")
        await ctrl.push_preset_p2("curious_b")  # newer

    asyncio.run(drive())

    assert ctrl._p2_preset == "curious_b"  # latest wins
    assert mcu.calls == []  # still deferred
