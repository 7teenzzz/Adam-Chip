"""Phase 21A-08 — MicReader auto-restart watchdog tests.

Covers:
  * _should_trigger_stream_restart predicate (threshold + cooldown gate)
  * _trigger_stream_restart helper (POST + event emission)
  * disabled state when esp_stream_restart_after_fails = 0

Run:
    PYTHONPATH=System .venv/bin/python -m pytest tests/test_mic_reader_watchdog.py -x -q
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "System"))


def _audio_cfg() -> dict:
    return {
        "sample_rate": 16000,
        "channels": 1,
        "frame_ms": 20,
        "esp32_mic_profile": "inmp441_philips32_stereo",
        "normalize_factor": 8000,
        "spectrum_bands": 24,
        "spectrum_min_hz": 80,
        "spectrum_max_hz": 8000,
        "spectrum_floor_db": -60.0,
        "spectrum_ceiling_db": 0.0,
        "spectrum_cadence_hz": 25,
        "spectrum_color_yellow_at": 0.6,
        "spectrum_color_red_at": 0.85,
    }


def _asr_cfg(**overrides) -> dict:
    cfg = {
        "disable_local_fallback": True,
        "esp_open_timeout_sec": 8,
        "esp_probe_after_fails": 2,
        "esp_retry_backoff_sec": [2, 4, 8, 15],
        "esp_stream_restart_after_fails": 5,
        "esp_stream_restart_cooldown_sec": 120.0,
    }
    cfg.update(overrides)
    return cfg


class _MockMcu:
    """Stand-in for adam.device.Device. Tracks stream_restart() invocations."""

    def __init__(self, ok: bool = True, status: int = 200, error: str = "") -> None:
        self._ok = ok
        self._status = status
        self._error = error
        self.calls: int = 0

    async def stream_restart(self):
        self.calls += 1
        return types.SimpleNamespace(ok=self._ok, status=self._status, error=self._error)


def _make_mr(asr_overrides: dict | None = None, mcu: _MockMcu | None = None):
    from adam.mic_reader import MicReader  # noqa: WPS433
    events: list[tuple[str, dict]] = []

    def on_event(ev: str, payload: dict) -> None:
        events.append((ev, payload))

    mr = MicReader(
        asr_cfg=_asr_cfg(**(asr_overrides or {})),
        audio_cfg=_audio_cfg(),
        mcu=mcu,
        voice_loop=None,
        on_event=on_event,
        stereo_reader_factory=None,
    )
    return mr, events


# ─── _should_trigger_stream_restart predicate ─────────────────────────────────


def test_gate_quiet_when_no_fails():
    """Steady state — zero fails, gate must NOT trigger."""
    mr, _ = _make_mr()
    assert mr._consecutive_fails == 0
    assert mr._should_trigger_stream_restart(now=1000.0) is False


def test_gate_quiet_below_threshold():
    """4 fails (threshold 5) — gate must NOT trigger yet."""
    mr, _ = _make_mr()
    mr._consecutive_fails = 4
    assert mr._should_trigger_stream_restart(now=1000.0) is False


def test_gate_fires_at_threshold():
    """5 fails (threshold 5) and cooldown has never been used — must trigger."""
    mr, _ = _make_mr()
    mr._consecutive_fails = 5
    # _last_auto_restart_t defaults to 0.0; any positive `now` clears cooldown.
    assert mr._should_trigger_stream_restart(now=1000.0) is True


def test_gate_respects_cooldown():
    """After a restart fired at t=1000, gate must NOT trigger again at t=1100
    (cooldown 120 s not elapsed) — even with fails climbing back to threshold."""
    mr, _ = _make_mr()
    mr._consecutive_fails = 7
    mr._last_auto_restart_t = 1000.0
    # 100 s later — still inside cooldown window (120 s)
    assert mr._should_trigger_stream_restart(now=1100.0) is False
    # 121 s later — cooldown elapsed, gate opens again
    assert mr._should_trigger_stream_restart(now=1121.0) is True


def test_gate_disabled_when_threshold_zero():
    """esp_stream_restart_after_fails=0 must disable the watchdog completely
    regardless of how many fails accumulate."""
    mr, _ = _make_mr(asr_overrides={"esp_stream_restart_after_fails": 0})
    mr._consecutive_fails = 999
    assert mr._should_trigger_stream_restart(now=1e9) is False


def test_gate_picks_up_config_changes_via_apply_config():
    """Hot-reload of both watchdog keys via apply_config must take effect
    on the next predicate call — no Orchestrator restart required."""
    mr, _ = _make_mr()
    new_asr = _asr_cfg(
        esp_stream_restart_after_fails=10,
        esp_stream_restart_cooldown_sec=30.0,
    )
    mr.apply_config(asr_cfg=new_asr, audio_cfg=_audio_cfg())

    assert mr._esp_stream_restart_after_fails == 10
    assert mr._esp_stream_restart_cooldown_sec == 30.0
    # 9 fails — under the new threshold, gate stays closed.
    mr._consecutive_fails = 9
    assert mr._should_trigger_stream_restart(now=1000.0) is False
    # 10 fails — at the new threshold, gate opens.
    mr._consecutive_fails = 10
    assert mr._should_trigger_stream_restart(now=1000.0) is True


# ─── _trigger_stream_restart helper ───────────────────────────────────────────


def test_trigger_calls_mcu_and_emits_event_on_success():
    mcu = _MockMcu(ok=True, status=200)
    mr, events = _make_mr(mcu=mcu)
    mr._consecutive_fails = 5
    result = asyncio.run(mr._trigger_stream_restart())
    assert result is True
    assert mcu.calls == 1
    # Exactly one mic_reader_stream_restart_triggered event was emitted.
    fired = [p for (e, p) in events if e == "mic_reader_stream_restart_triggered"]
    assert len(fired) == 1
    assert fired[0]["ok"] is True
    assert fired[0]["status_code"] == 200
    assert fired[0]["consecutive_fails"] == 5


def test_trigger_emits_failure_event_on_non_ok():
    mcu = _MockMcu(ok=False, status=503, error="firmware not ready")
    mr, events = _make_mr(mcu=mcu)
    mr._consecutive_fails = 6
    result = asyncio.run(mr._trigger_stream_restart())
    assert result is False
    fired = [p for (e, p) in events if e == "mic_reader_stream_restart_triggered"]
    assert len(fired) == 1
    assert fired[0]["ok"] is False
    assert fired[0]["status_code"] == 503
    assert "firmware not ready" in fired[0].get("error", "")


def test_trigger_no_mcu_emits_no_mcu_error():
    """When MCU client was not injected, trigger must NOT crash — just emit."""
    mr, events = _make_mr(mcu=None)
    mr._consecutive_fails = 5
    result = asyncio.run(mr._trigger_stream_restart())
    assert result is False
    fired = [p for (e, p) in events if e == "mic_reader_stream_restart_triggered"]
    assert len(fired) == 1
    assert fired[0]["ok"] is False
    assert fired[0]["error"] == "no_mcu"
