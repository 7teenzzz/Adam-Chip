"""Unit tests for LocalMicReader._find_pulse_source retry-with-backoff.

Phase 41 — APLF-02: cold-start boot race fix.
Tests verify Config-driven retry loop without touching real audio hardware.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

# Minimal audio_cfg that triggers _find_pulse_source (card_name set)
# but avoids any hardware calls at construction time.
_BASE_CFG: dict = {
    "sample_rate": 16000,
    "channels": 1,
    "frame_ms": 20,
    "normalize_factor": 8000,
    "spectrum_bands": 4,       # small to keep construction fast
    "spectrum_min_hz": 100.0,
    "spectrum_max_hz": 8000.0,
    "spectrum_floor_db": -60.0,
    "spectrum_ceiling_db": 0.0,
    "spectrum_cadence_hz": 25.0,
    "input_gain": {"card_name": "WebCamera"},
    "pulse_source_retries": 3,
    "pulse_source_retry_delay_sec": 0.0,  # zero so tests run instantly
}


def _make_pactl_result(source_name: str | None) -> MagicMock:
    """Build a fake subprocess.CompletedProcess for pactl list short sources."""
    m = MagicMock()
    if source_name:
        m.stdout = f"0\t{source_name}\tmodule-alsa-source.c\ts16le 1ch 48000Hz\tSUSPENDED\n"
    else:
        m.stdout = "0\talsa_output.hdmi\tmodule-alsa-sink.c\ts16le 2ch 48000Hz\tSUSPENDED\n"
    return m


def _make_event_log() -> MagicMock:
    log = MagicMock()
    log.append = MagicMock()
    return log


class TestFindPulseSourceRetry:
    def test_find_pulse_source_retries(self) -> None:
        """First call returns no match; second call returns WebCamera source.
        _find_pulse_source should retry and ultimately return the source name.
        """
        no_match = _make_pactl_result(None)
        webcam_match = _make_pactl_result(
            "alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback"
        )

        with (
            patch("subprocess.run", side_effect=[no_match, webcam_match]) as mock_run,
            patch("time.sleep") as mock_sleep,
        ):
            from adam.local_mic_reader import LocalMicReader

            cfg = dict(_BASE_CFG)
            cfg["pulse_source_retries"] = 3
            cfg["pulse_source_retry_delay_sec"] = 0.5
            reader = LocalMicReader(cfg, _make_event_log())

        assert reader._pulse_source == (
            "alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback"
        )
        # Two pactl calls: miss on attempt 0, match on attempt 1
        assert mock_run.call_count == 2
        # Sleep called once between attempt 0 and attempt 1
        mock_sleep.assert_called_once_with(0.5)

    def test_find_pulse_source_immediate(self) -> None:
        """Source found on first attempt — no retry, no sleep."""
        webcam_match = _make_pactl_result(
            "alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback"
        )

        with (
            patch("subprocess.run", return_value=webcam_match) as mock_run,
            patch("time.sleep") as mock_sleep,
        ):
            from adam.local_mic_reader import LocalMicReader

            cfg = dict(_BASE_CFG)
            cfg["pulse_source_retries"] = 3
            reader = LocalMicReader(cfg, _make_event_log())

        assert reader._pulse_source == (
            "alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback"
        )
        # Exactly one pactl call — happy path, no retry
        assert mock_run.call_count == 1
        # No sleep on happy path
        mock_sleep.assert_not_called()

    def test_find_pulse_source_all_fail_returns_none(self) -> None:
        """All attempts fail — returns None and emits unresolved event."""
        no_match = _make_pactl_result(None)
        event_log = _make_event_log()

        with (
            patch("subprocess.run", return_value=no_match) as mock_run,
            patch("time.sleep"),
        ):
            from adam.local_mic_reader import LocalMicReader

            cfg = dict(_BASE_CFG)
            cfg["pulse_source_retries"] = 2
            cfg["pulse_source_retry_delay_sec"] = 0.0
            reader = LocalMicReader(cfg, event_log)

        assert reader._pulse_source is None
        assert mock_run.call_count == 2
        # Should emit unresolved event
        emitted_types = [c.args[0] for c in event_log.append.call_args_list]
        assert "local_mic_pulse_source_unresolved" in emitted_types

    def test_no_hardcoded_retry_constants(self) -> None:
        """Config-driven retry: custom retries/delay values are respected."""
        no_match = _make_pactl_result(None)

        with (
            patch("subprocess.run", return_value=no_match),
            patch("time.sleep") as mock_sleep,
        ):
            from adam.local_mic_reader import LocalMicReader

            cfg = dict(_BASE_CFG)
            cfg["pulse_source_retries"] = 5
            cfg["pulse_source_retry_delay_sec"] = 0.25
            reader = LocalMicReader(cfg, _make_event_log())

        # 5 attempts → 4 sleeps between them
        assert mock_sleep.call_count == 4
        for c in mock_sleep.call_args_list:
            assert c == call(0.25)
