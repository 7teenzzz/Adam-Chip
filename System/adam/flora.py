"""Technoflora reactive layer — Jetson event consumer (FLORA-03 / FLORA-06).

The Jetson half of the hybrid (D-03/D-04): the ESP firmware runs the ambient
animations autonomously per preset; the Jetson only sends *state transitions*
driven by real pipeline events. `FloraController` subscribes to the `EventLog`
pub-sub queue (NOT a callback bus — see events.py), maps VERIFIED pipeline event
names to flora presets, and POSTs them via `MCUClient.set_flora_state`
(_NO_PROXY_OPENER mandatory — CLAUDE.md v2ray socket-leak gotcha).

Event -> preset mapping (29-RESEARCH §Pattern 4, VERIFIED names):
    wake_word_detected                       -> accent       (детекция)
    voice_state_change(from=boot_warmup)     -> wake_bloom   (пробуждение, once)
    voice_state_change(to=listening)         -> attentive    (слушание, vibro OFF)
    voice_state_change(to=standby)           -> breathe      (покой)
    llm_thinking_started                     -> think_pulse  (раздумье)
    tts_started / tts_finished               -> answer boundary (RMS stream is plan 04)

All numbers come from FloraStore / System/Flora.json (Config-First, D-13) — nothing
hardcoded here. Gamma is applied firmware-side, so this layer sends raw percent
duties; the firmware converts via its gamma LUT.
"""
from __future__ import annotations

import asyncio
import audioop
import collections
import copy
import io
import json
import logging
import os
import random
import threading
import wave
from enum import IntEnum
from pathlib import Path
from time import perf_counter
from typing import Any

logger = logging.getLogger("adam.flora")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLORA_PATH = _PROJECT_ROOT / "System" / "Flora.json"


class FloraStore:
    """Hot-reloadable loader for System/Flora.json.

    Independent from Settings / Config.json so flora tuning can be edited
    and reloaded without touching the main runtime config. Mirrors the
    TuningStore pattern: mtime-based reload on every current() call, atomic
    save via temp-file rename.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_FLORA_PATH
        self._lock = threading.Lock()
        self._mtime: float = 0.0
        self._data: dict[str, Any] = {}
        self._load_locked()

    def _load_locked(self) -> dict[str, Any]:
        try:
            mtime = self.path.stat().st_mtime
            if mtime == self._mtime and self._data:
                return self._data
            with self.path.open("r", encoding="utf-8") as fh:
                self._data = json.load(fh)
            self._mtime = mtime
        except Exception:
            pass
        return self._data

    def current(self) -> dict[str, Any]:
        """Return flora config, reloading from disk if the file changed."""
        with self._lock:
            return copy.deepcopy(self._load_locked())

    def apply_patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge *patch* into the current flora data (in memory + reload first)."""
        with self._lock:
            self._load_locked()  # refresh before merge
            self._data = _deep_merge_flora(self._data, patch)
            return copy.deepcopy(self._data)

    def save(self) -> Path:
        """Write current flora data to Flora.json atomically."""
        with self._lock:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2, sort_keys=False)
                fh.write("\n")
            os.replace(tmp, self.path)
        return self.path


def _deep_merge_flora(base: dict, patch: dict) -> dict:
    result = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge_flora(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


# Module-level singleton — shared across Orchestrator + FloraController.
_flora_store: FloraStore | None = None


def get_flora_store(path: str | Path | None = None) -> FloraStore:
    """Return (or lazily create) the module-level FloraStore singleton."""
    global _flora_store
    if _flora_store is None:
        _flora_store = FloraStore(path)
    return _flora_store


# Preset names owned by the pipeline — cannot be used as user_presets keys.
SYSTEM_PRESET_NAMES: frozenset[str] = frozenset({
    "breathe", "accent", "attentive", "think_pulse", "wake_bloom", "external", "idle",
})


class FloraPriority(IntEnum):
    """Priority levels for flora preset ownership.

    Higher value wins. When a lower-priority layer tries to push while a
    higher-priority layer is active, the push is deferred or ignored.

    P1_BARGE_IN:    wake_word during TTS — snaps lights immediately.
    P3_PIPELINE:    normal voice pipeline (accent/attentive/think_pulse/external).
    P2_SUBCONSCIOUS: AIIM emotion presets pushed from Orchestrator.
                     Active between P3 turns; deferred while P3 runs.
    """
    P1_BARGE_IN = 3
    P3_PIPELINE = 2
    P2_SUBCONSCIOUS = 1


class FloraController:
    """Consumes pipeline events and pushes flora preset transitions to the ESP.

    Lifecycle mirrors mic_reader (start()/stop()): start() subscribes to the
    event_log queue and spawns a consumer task; stop() cancels the task and
    unsubscribes. The mapping logic in _handle/_set_state is unit-testable
    without a running loop (the tests drive _handle directly).
    """

    def __init__(
        self,
        settings_section: dict[str, Any],
        mcu_client: Any,
        event_log: Any | None = None,
    ) -> None:
        self._cfg: dict[str, Any] = settings_section or {}
        self._mcu = mcu_client
        self._event_log = event_log
        self._states_cfg: dict[str, Any] = self._cfg.get("states", {}) or {}
        self._vibro_cfg: dict[str, Any] = self._cfg.get("vibro", {}) or {}
        # Preset names that MUST keep vibro silent (D-11). "attentive" is
        # mandatory — motor vibration couples into the INMP441 chassis and
        # corrupts ASR.
        self._silent_states: set[str] = set(self._vibro_cfg.get("silent_states", ["attentive"]))
        self._crossfade_ms: int = int(self._cfg.get("crossfade_ms", 200))
        self._vibro_intensity_pct: int = int(self._vibro_cfg.get("intensity_pct", 95))

        # Light/vibro channel masks (D-02) — all numbers Config-First.
        self._light_channels: list[int] = list(self._cfg.get("light_channels", list(range(11))))
        self._vibro_channels: list[int] = list(self._cfg.get("vibro_channels", [0, 1, 2, 3]))
        # PCA9685 full-scale duty (12-bit). mcu_client clamps anyway, but the
        # base..peak percent mapping needs the ceiling. Mirror mcu.channels.value_max.
        self._value_max: int = int(getattr(self._mcu, "value_max", 4095))

        # RMS speech-sync params (D-07/D-08) — flora.speech.* section.
        self._speech_cfg: dict[str, Any] = self._cfg.get("speech", {}) or {}
        self._frame_interval_ms: int = int(self._speech_cfg.get("frame_interval_ms", 80))
        self._hdmi_offset_ms: int = int(self._speech_cfg.get("hdmi_latency_offset_ms", 150))
        self._base_duty_pct: float = float(self._speech_cfg.get("base_duty_pct", 25))
        self._peak_duty_pct: float = float(self._speech_cfg.get("peak_duty_pct", 71))
        self._spark_probability: float = float(self._speech_cfg.get("spark_probability", 0.15))

        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._task: asyncio.Task[None] | None = None
        # wake_bloom fires only on the FIRST transition out of boot_warmup
        # (the system coming alive). Subsequent standby transitions -> breathe.
        self._booted: bool = False
        self._enabled: bool = bool(self._cfg.get("enabled", True))

        # Answer-state (RMS speech sync, FLORA-04). Active between tts_started and
        # tts_finished. While active, feed_speech_wav drives the light stream from
        # the GUARANTEED per-chunk WAV pushed by the Orchestrator consumer.
        self._answer_active: bool = False
        # Whether any WAV chunk was fed during the current answer — distinguishes
        # the streaming path (real RMS sync) from the /speak no-WAV degraded path.
        self._fed_wav_this_answer: bool = False
        self._rms_task: asyncio.Task[None] | None = None

        # Flora coexistence priority system (Phase 36, Direction 1).
        self._current_priority: FloraPriority | None = None
        self._current_preset: str | None = None
        self._p2_preset: str | None = None
        self._p2_params: dict[str, Any] | None = None

        # Visitor audio RMS multiplier (post-filter source of truth).
        # Updated from audio_level events at 25 Hz. Applied as gentle brightness
        # scale on P2 presets: effective_peak = peak * rms_multiplier (0.80..1.0).
        self._rms_window: collections.deque[float] = collections.deque(maxlen=30)
        self._rms_multiplier: float = 1.0

        # SmartFlora (Phase 37): running animation sequence task. Cancelled by
        # P1/P3 pipeline events (wake_word, listening, standby) and stop_sequence().
        self._sequence_task: asyncio.Task[None] | None = None

        # wake_bloom auto-settle task (bugfix): wake_bloom has no firmware-side
        # one-shot mechanism — without this, it loops at flora.states.wake_bloom
        # .period_ms forever until the next P1/P3 event. This task settles to
        # wake_bloom.settle_to after one animation cycle, cancellable by any
        # later P1/P3 event so it never overrides a real pipeline state.
        self._bloom_task: asyncio.Task[None] | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Subscribe to the event log and spawn the consumer task. Idempotent."""
        if not self._enabled:
            logger.info("flora disabled in config — controller not started")
            return
        if self._task is not None and not self._task.done():
            return
        if self._event_log is None:
            logger.warning("flora start() called without an event_log — nothing to consume")
            return
        self._queue = self._event_log.subscribe()
        self._task = asyncio.create_task(self._consume(), name="flora_consumer")

    async def stop(self) -> None:
        """Cancel the consumer task, await it, and unsubscribe from the event log."""
        await self._cancel_sequence_task()
        await self._cancel_bloom_task()
        # Kill any live RMS streamer first so it cannot keep POSTing frames.
        await self._cancel_rms_task()
        self._answer_active = False
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover - guard; _consume swallows its own
                pass
        self._task = None
        if self._event_log is not None and self._queue is not None:
            self._event_log.unsubscribe(self._queue)
        self._queue = None

    def is_enabled(self) -> bool:
        return self._enabled

    # ── Consume loop ───────────────────────────────────────────────────

    async def _consume(self) -> None:
        assert self._queue is not None
        try:
            while True:
                event = await self._queue.get()
                try:
                    await self._handle(event)
                except Exception:
                    # A bad event must never kill the consumer loop.
                    logger.exception("flora event handling failed")
        finally:
            if self._event_log is not None and self._queue is not None:
                self._event_log.unsubscribe(self._queue)

    # ── Event -> preset mapping ────────────────────────────────────────

    async def _handle(self, event: dict[str, Any]) -> None:
        etype = event.get("type")

        # Track visitor audio level (post-filter source of truth, Phase 36 D-1).
        # audio_level.payload.level is already normalised 0.0-1.0 by MicReader.
        if etype == "audio_level":
            level = float((event.get("payload") or {}).get("level", 0.0))
            self._rms_window.append(level)
            if self._rms_window:
                avg = sum(self._rms_window) / len(self._rms_window)
                self._rms_multiplier = 0.80 + 0.20 * min(1.0, avg)
            return

        if etype == "wake_word_detected":
            # Barge-in (D-09): snap light to accent and kill any live RMS stream.
            # Also cancel any running user sequence (P1 preempts everything).
            await self._cancel_sequence_task()
            await self._cancel_bloom_task()
            if self._answer_active or self._rms_task is not None:
                await self._cancel_rms_task()
                self._answer_active = False
                self._fed_wav_this_answer = False
            self._current_priority = FloraPriority.P1_BARGE_IN
            await self._set_state("accent")  # детекция
            # Hold accent visible before attentive overrides it.
            # voice_state_change(to=listening) fires ~20ms later; without this hold
            # it overwrites accent in firmware's sTarget before the first 20ms tick.
            flora = self._live_flora_cfg()
            hold_ms = int(flora.get("accent_hold_ms", 220))
            if hold_ms > 0:
                await asyncio.sleep(hold_ms / 1000.0)
        elif etype == "voice_state_change":
            payload = event.get("payload", {}) or {}
            if payload.get("from") == "boot_warmup" and not self._booted:
                # First exit from boot = system coming alive (RESEARCH Open Q1).
                self._booted = True
                self._current_priority = FloraPriority.P3_PIPELINE
                await self._set_state("wake_bloom")  # пробуждение (once)
                # wake_bloom has no firmware one-shot — schedule auto-settle to
                # settle_to (default breathe) after one animation cycle so it
                # doesn't loop forever until the next pipeline event.
                wake_cfg = (self._live_flora_cfg().get("states") or {}).get("wake_bloom", {}) or {}
                settle_to = str(wake_cfg.get("settle_to") or "breathe")
                settle_after_ms = int(wake_cfg.get("period_ms", 3000))
                await self._cancel_bloom_task()
                self._bloom_task = asyncio.create_task(
                    self._schedule_bloom_settle(settle_after_ms, settle_to),
                    name="flora_bloom_settle",
                )
                return
            self._booted = True
            to = payload.get("to")
            if to == "listening":
                # Barge-in (D-09): cancel RMS stream and any user sequence.
                await self._cancel_sequence_task()
                await self._cancel_bloom_task()
                if self._answer_active or self._rms_task is not None:
                    await self._cancel_rms_task()
                    self._answer_active = False
                    self._fed_wav_this_answer = False
                self._current_priority = FloraPriority.P3_PIPELINE
                await self._set_state("attentive")  # слушание — вибро OFF (D-11)
            elif to == "standby":
                # Barge-in guard: cancel sequence, RMS, then settle to breathe.
                await self._cancel_sequence_task()
                await self._cancel_bloom_task()
                if self._answer_active or self._rms_task is not None:
                    await self._cancel_rms_task()
                    self._answer_active = False
                    self._fed_wav_this_answer = False
                self._current_priority = FloraPriority.P3_PIPELINE
                await self._set_state("breathe")  # покой
                # After settling to breathe, restore P2 subconscious preset if set.
                self._current_priority = None
                await self._restore_p2()
        elif etype == "llm_thinking_started":
            # A running SmartFlora sequence (P2) must not keep overriding
            # think_pulse with its own _set_state calls mid-thought.
            await self._cancel_sequence_task()
            await self._cancel_bloom_task()
            self._current_priority = FloraPriority.P3_PIPELINE
            await self._set_state("think_pulse")  # раздумье
        elif etype == "tts_started":
            self._current_priority = FloraPriority.P3_PIPELINE
            await self._on_answer_start(event)
        elif etype == "tts_finished":
            await self._on_answer_end()

    # ── Answer boundary + RMS streamer (FLORA-04) ─────────────────────

    async def _on_answer_start(self, event: dict[str, Any]) -> None:
        """Mark the start of an answer.  The RMS stream is driven by the
        Orchestrator consumer via feed_speech_wav (per-chunk WAV, D-07).

        If no WAV arrives (non-streaming /speak path — Silero plays
        internally and never exposes the WAV bytes), we fall through to the
        generic 'attentive' plateau so the lights at least react with a
        steady brightness rather than going dark.  That is the ONLY degraded
        path (RESEARCH Open Q2 RESOLVED); document it here so future
        reviewers understand the architectural constraint.
        """
        self._answer_active = True
        self._fed_wav_this_answer = False
        # Push the firmware into `external` (animation-suppressed) so floraTask
        # stops drawing its own frames @50 Hz and the per-chunk RMS stream we POST
        # via set_channels actually sticks (fixes C2 — was 'attentive', which the
        # firmware kept animating over the RMS frames). If no WAV ever arrives
        # (non-streaming /speak path), the firmware External watchdog auto-recovers
        # to breathe after flora.external_timeout_ms — the only degraded path.
        await self._set_state("external")

    async def _on_answer_end(self) -> None:
        """Answer finished — stop the RMS streamer and settle to calm idle."""
        # R2 guard: after a barge-in the handler already cleared _answer_active and
        # transitioned to accent/attentive.  A late tts_finished event must NOT
        # override that post-barge-in state by forcing breathe.
        if not self._answer_active:
            return
        await self._stop_rms_stream()
        self._answer_active = False
        self._fed_wav_this_answer = False
        await self._set_state("breathe")
        # P3 done — restore P2 subconscious emotion preset if one was deferred.
        self._current_priority = None
        await self._restore_p2()

    # ── State push ─────────────────────────────────────────────────────

    def _live_flora_cfg(self) -> dict[str, Any]:
        """Return current flora config — re-read from Flora.json for hot-reload.

        Falls back to the __init__ snapshot on any load error (e.g. malformed
        JSON mid-edit). Monkeypatchable in unit tests via assignment.
        """
        try:
            return get_flora_store().current() or self._cfg
        except Exception:
            return self._cfg

    async def push_preset(self, state: str) -> bool:
        """Manually push a flora preset with current Config.json values.

        Public entry point for the /api/flora/state Orchestrator endpoint and
        manual testing. Returns False for unknown preset names.
        """
        flora = self._live_flora_cfg()
        known = set((flora.get("states") or {}).keys())
        known.update(SYSTEM_PRESET_NAMES)
        known.update((flora.get("user_presets") or {}).keys())  # SmartFlora user presets
        if state not in known:
            return False
        await self._set_state(state)
        return True

    async def _set_state(self, state: str, **overrides: Any) -> None:
        """Build per-state params from the flora config and POST the transition.

        All numbers come from settings.section("flora") (Config-First). Vibro is
        forced off for any preset in silent_states (belt-and-suspenders mirror of
        the firmware, D-11). Percent duties are sent raw — gamma is firmware-side.
        """
        self._current_preset = state  # track for priority coexistence logic
        params = self._build_params(state)
        params.update(overrides)
        # Belt-and-suspenders using cached set (D-11 invariant must survive hot-reload errors).
        if state in self._silent_states:
            params["vibro_enabled"] = False
        result = await self._mcu.set_flora_state(state, params)
        if not result.ok:
            logger.warning("flora set_state %r -> MCU error %s: %s", state, result.status, result.error)
        if self._event_log is not None:
            try:
                payload: dict[str, Any] = {"state": state}
                if not result.ok:
                    payload["mcu_error"] = result.status
                self._event_log.append("flora_state_change", payload)
            except Exception:
                pass
        logger.info(
            "flora state -> %r (priority=%s, ok=%s)",
            state,
            self._current_priority.name if self._current_priority else None,
            result.ok,
        )

    # ── wake_bloom auto-settle (bugfix) ────────────────────────────────

    async def _cancel_bloom_task(self) -> None:
        """Cancel the pending wake_bloom auto-settle task, if any."""
        task = self._bloom_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._bloom_task = None

    async def _schedule_bloom_settle(self, after_ms: int, settle_to: str) -> None:
        """Auto-transition out of wake_bloom after one animation cycle.

        wake_bloom has no firmware-side one-shot mechanism (settle_to/from_dark
        are dropped in _build_params — firmware only sees base/peak/period like
        any looping preset). Without this, wake_bloom loops at period_ms forever
        until the next P1/P3 pipeline event, which can be minutes away if no one
        approaches after boot. This task settles to wake_bloom.settle_to
        (default "breathe") after after_ms, but only if nothing has taken over
        the lights in the meantime — any later P1/P3 event cancels this task via
        _cancel_bloom_task() before it fires.
        """
        try:
            await asyncio.sleep(after_ms / 1000.0)
        except asyncio.CancelledError:
            raise
        if self._current_preset != "wake_bloom":
            # Something else already took the lights — nothing to settle.
            return
        logger.info("flora wake_bloom auto-settle -> %r after %dms", settle_to, after_ms)
        self._current_priority = FloraPriority.P3_PIPELINE
        await self._set_state(settle_to)
        self._current_priority = None
        await self._restore_p2()

    def _build_params(self, state: str) -> dict[str, Any]:
        """Translate a config preset into the flat param dict the firmware expects.

        Re-reads flora config from disk on every call (hot-reload, Config-First D-13)
        so Config.json edits take effect on the next state transition without an
        orchestrator restart. Falls back to __init__ snapshot on load error.

        *_pct keys are translated to firmware-native base_duty / peak_duty (0-4095).
        Keys the firmware ignores (attack_ms, from_dark, settle_to,
        vibro_pulse_ms) are dropped to keep the payload compact.
        flash_ms maps to period_ms (think_pulse flash interval).
        """
        _SKIP = frozenset({"attack_ms", "vibro_pulse_ms", "from_dark", "settle_to"})

        flora = self._live_flora_cfg()
        states_cfg: dict[str, Any] = flora.get("states", {}) or {}
        vibro_cfg: dict[str, Any] = flora.get("vibro", {}) or {}
        crossfade_ms = int(flora.get("crossfade_ms", self._crossfade_ms))
        vibro_intensity_pct = int(vibro_cfg.get("intensity_pct", self._vibro_intensity_pct))
        silent_states: set[str] = set(vibro_cfg.get("silent_states", list(self._silent_states)))
        # D-03 safe-ceiling: global raw-PWM cap, hot-reload-aware.
        max_duty_pct: float = float(flora.get("max_duty_pct", 100))
        max_duty: int = int(round(self._value_max * max_duty_pct / 100.0))

        # SmartFlora (Phase 37): fall back to user_presets when state is not a system preset.
        user_presets_cfg: dict[str, Any] = flora.get("user_presets", {}) or {}
        preset: dict[str, Any] = states_cfg.get(state) or user_presets_cfg.get(state) or {}
        params: dict[str, Any] = {
            "crossfade_ms": crossfade_ms,
            "vibro_intensity_pct": vibro_intensity_pct,
        }
        for key, value in preset.items():
            if key == "vibro":
                if isinstance(value, bool):
                    params["vibro_enabled"] = value
                else:
                    params["vibro_enabled"] = True
                    params["vibro_mode"] = value
            elif key in ("base_pct", "peak_pct"):
                duty_key = "base_duty" if key == "base_pct" else "peak_duty"
                # D-03: clamp each duty to the safe ceiling.
                params[duty_key] = min(
                    int(round(self._value_max * float(value) / 100.0)), max_duty
                )
            elif key == "plateau_pct":
                # D-03: clamp plateau (both base and peak use the same value).
                duty = min(
                    int(round(self._value_max * float(value) / 100.0)), max_duty
                )
                params["base_duty"] = duty
                params["peak_duty"] = duty
            elif key in ("wave_period_ms", "flash_ms"):
                # wave_period_ms: attentive fast-wave period.
                # flash_ms: think_pulse flash interval.
                # Both map to firmware's period_ms.
                params["period_ms"] = int(value)
            elif key in _SKIP:
                pass
            else:
                params[key] = value
        if state in silent_states:
            params["vibro_enabled"] = False
        return params

    # ── RMS speech sync (FLORA-04) ─────────────────────────────────────

    def _rms_envelope(self, wav_bytes: bytes) -> list[float]:
        """Downsample a TTS WAV into a 0..1 RMS brightness envelope (D-07/D-08).

        Windows the PCM into `frame_interval_ms`-wide chunks (~12.5 fps at 80 ms),
        takes `audioop.rms` per window, and normalizes by the sample-width FULL
        SCALE (not the per-WAV peak) so absolute loudness is preserved — a quiet
        utterance reads dimmer than a loud one, and a steady tone does not get
        stretched to full brightness. Pure stdlib (`wave`+`audioop`, no numpy) —
        matches the project idiom (mic_reader.py / inference.py). Empty/short/
        undecodable WAV returns [] gracefully so the streamer simply does nothing.
        """
        if not wav_bytes:
            return []
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
                sampwidth = wav.getsampwidth()
                framerate = wav.getframerate()
                nchannels = wav.getnchannels()
                nframes = wav.getnframes()
                pcm = wav.readframes(nframes)
        except (wave.Error, EOFError, OSError):
            return []
        if not pcm or framerate <= 0 or sampwidth <= 0:
            return []
        # Collapse to mono so the RMS reflects perceived loudness, not channel count.
        if nchannels > 1:
            try:
                pcm = audioop.tomono(pcm, sampwidth, 0.5, 0.5)
            except audioop.error:
                pass
        bytes_per_frame = sampwidth  # mono after tomono
        window_frames = max(1, int(framerate * self._frame_interval_ms / 1000))
        window_bytes = window_frames * bytes_per_frame
        levels: list[int] = []
        for start in range(0, len(pcm), window_bytes):
            window = pcm[start : start + window_bytes]
            if not window:
                continue
            try:
                levels.append(audioop.rms(window, sampwidth))
            except audioop.error:
                levels.append(0)
        if not levels:
            return []
        # Full-scale RMS for this sample width (2**(bits-1) - 1). Normalizing by
        # this fixed ceiling keeps the envelope proportional to true loudness.
        full_scale = float((1 << (8 * sampwidth - 1)) - 1)
        if full_scale <= 0:
            return [0.0 for _ in levels]
        return [min(1.0, lvl / full_scale) for lvl in levels]

    def _envelope_to_duties(self, levels: list[float]) -> list[int]:
        """Map 0..1 envelope levels to PCA9685 duties in base..peak (D-08).

        base_duty_pct (~25%) is the floor so lamps never go dark mid-utterance;
        peak_duty_pct (~90%) is the crest. Percent duties; gamma is firmware-side.
        D-03: every duty is clamped to max_duty (flora.max_duty_pct, hot-reload).
        """
        flora = self._live_flora_cfg()
        max_duty_pct: float = float(flora.get("max_duty_pct", 100))
        max_duty: int = int(round(self._value_max * max_duty_pct / 100.0))

        base = min(int(round(self._value_max * self._base_duty_pct / 100.0)), max_duty)
        peak = min(int(round(self._value_max * self._peak_duty_pct / 100.0)), max_duty)
        lo, hi = (base, peak) if base <= peak else (peak, base)
        span = hi - lo
        duties: list[int] = []
        for level in levels:
            clamped = 0.0 if level < 0.0 else (1.0 if level > 1.0 else level)
            # D-03: output is already bounded by [base, peak] which are both <= max_duty.
            duties.append(lo + int(round(span * clamped)))
        return duties

    # ── Guaranteed-WAV public entry point (FLORA-04, D-07) ────────────

    def feed_speech_wav(self, wav_bytes: bytes) -> None:
        """Feed a synthesized WAV chunk to the RMS light streamer.

        This is the GUARANTEED per-chunk WAV entry point called by the
        Orchestrator _consumer at the SAME instant it dispatches each chunk
        to to_thread(_play_wav_bytes_sync) — so the timer starts together
        with playback (D-07 single-timer per-chunk sync).

        Design notes:
        - One asyncio task per chunk.  If a previous chunk's task is still
          running (i.e. its envelope is longer than the chunk's audio — not
          typical but possible during slow I2C bursts), it is cancelled
          before the new one starts.  This keeps each chunk's visual sync
          independent and avoids envelope drift across chunks.
        - Guard: if the controller is not in answer state or is disabled,
          the call is a fast no-op (filler "Хм..." chunks are fine to react
          to but are outside _answer_active because they fire before
          tts_started is emitted — a minor known gap, acceptable).
        - Synchronous fast (never blocks): asyncio.create_task() is ~µs;
          the actual WAV decoding (_rms_envelope) and HTTP POSTs run inside
          the spawned task (R9: _rms_envelope is CPU work — wave.open +
          audioop.rms — and must NOT block the event loop).

        Degraded path (non-streaming /speak): Silero's internal /speak
        endpoint plays audio natively without exposing WAV bytes, so this
        method is NEVER called for that path.  _on_answer_start already
        put the lights on the 'attentive' plateau as a fallback — that
        stays until tts_finished arrives.  This is the ONLY degraded path
        (RESEARCH Open Q2 RESOLVED).
        """
        if not self._enabled or not self._answer_active:
            return
        # R9: offload CPU-bound WAV decode + RMS computation to a thread so
        # the event loop is not stalled.  Cancel any prior chunk task first
        # (preserves the cancel-then-create semantics of the old _start_rms_stream).
        if self._rms_task is not None and not self._rms_task.done():
            self._rms_task.cancel()
        self._rms_task = asyncio.create_task(
            self._rms_chunk_task(wav_bytes), name="flora_rms"
        )
        self._fed_wav_this_answer = True

    async def _rms_chunk_task(self, wav_bytes: bytes) -> None:
        """Compute RMS envelope in a thread, then stream duties.  R9."""
        try:
            levels = await asyncio.to_thread(self._rms_envelope, wav_bytes)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("flora rms_chunk_task: _rms_envelope failed", exc_info=True)
            return
        if not levels:
            return
        duties = self._envelope_to_duties(levels)
        await self._rms_stream(duties)

    async def _rms_stream(self, duties: list[int]) -> None:
        """Stream brightness frames to light channels 4-14 in lockstep with playback.

        Algorithm (D-07):
          t0 = perf_counter() at task-start (≈ same instant playback dispatched)
          For frame i: sleep until t0 + hdmi_latency_offset_ms/1000 + i*interval/1000
          Then POST set_channels to all light channels with this frame's duty.

        Sparks (D-08): on frames where the duty is near peak, with
        spark_probability boost a random channel subset to full peak for one frame.
        This adds subtle texture — cluster-friendly (random, no spatial centre, D-01).

        Vibro (channels 0-3): driven from the same phase as lights at the
        configured intensity_pct ceiling (D-11); NOT forced silent here —
        only 'attentive' state silences vibro.  The RMS modulation shares the
        lamp duty scaled to vibro_intensity_pct so the motors throb subtly with
        the voice without overwhelming (D-12, intensity_pct=95).

        Frame rate ceiling: frame_interval_ms from config defaults to 80 ms
        (~12.5 fps) — well within the ESP LWIP socket budget (T-29-10).
        """
        t0 = perf_counter()
        # WR-01: read all speech/vibro params fresh per stream (hot-reload-aware).
        flora = self._live_flora_cfg()
        speech_cfg: dict = (flora.get("speech") or {})
        offset_s: float = int(speech_cfg.get("hdmi_latency_offset_ms", self._hdmi_offset_ms)) / 1000.0
        interval_s: float = int(speech_cfg.get("frame_interval_ms", self._frame_interval_ms)) / 1000.0
        peak_duty_pct: float = float(speech_cfg.get("peak_duty_pct", self._peak_duty_pct))
        spark_probability: float = float(speech_cfg.get("spark_probability", self._spark_probability))
        vibro_intensity_pct: int = int((flora.get("vibro") or {}).get("intensity_pct", self._vibro_intensity_pct))

        max_duty_pct: float = float(flora.get("max_duty_pct", 100))
        max_duty: int = int(round(self._value_max * max_duty_pct / 100.0))

        peak_duty = min(
            int(round(self._value_max * peak_duty_pct / 100.0)), max_duty
        )
        vibro_scale: float = vibro_intensity_pct / 100.0

        try:
            for i, duty in enumerate(duties):
                target_t = t0 + offset_s + i * interval_s
                delay = target_t - perf_counter()
                # Skip frames that fell behind by more than one interval (e.g. after
                # a set_channels timeout). Without this guard a 1-second timeout
                # schedules ~12 frames for the past; they burst out simultaneously,
                # saturate ESP max_open_sockets=3 and cascade into more failures.
                if delay < -interval_s:
                    continue
                if delay > 0:
                    await asyncio.sleep(delay)

                # D-03: clamp per-frame light duty to safe ceiling.
                raw_duty = duty  # pre-clamp value for vibro (WR-03)
                duty = min(duty, max_duty)

                # Build the batch update: all light channels at this frame's duty.
                updates: list[dict] = [
                    {"channel": ch, "value": duty} for ch in self._light_channels
                ]

                # Sparks (D-08): near-peak frames — randomly boost a subset.
                if (
                    spark_probability > 0.0
                    and duty >= int(peak_duty * 0.75)
                    and random.random() < spark_probability
                ):
                    # Pick a random non-empty subset of light channels (cluster-friendly).
                    n_sparks = max(1, random.randint(1, len(self._light_channels) // 2))
                    spark_chs = random.sample(self._light_channels, n_sparks)
                    spark_set = set(spark_chs)
                    updates = [
                        # D-03: spark peak is already clamped (peak_duty <= max_duty).
                        {"channel": ch, "value": peak_duty if ch in spark_set else duty}
                        for ch in self._light_channels
                    ]

                # Vibro: scaled RMS duty — throbs with the voice (vibro_scale =
                # vibro.intensity_pct). Uses raw (pre-light-clamp) duty so the
                # светофлора power ceiling does NOT reduce vibro energy (D-12).
                vibro_duty = int(round(raw_duty * vibro_scale))
                updates.extend(
                    {"channel": ch, "value": vibro_duty}
                    for ch in self._vibro_channels
                )

                try:
                    await self._mcu.set_channels(updates)
                except Exception:
                    logger.debug("flora rms: set_channels failed at frame %d", i, exc_info=True)
        except asyncio.CancelledError:
            raise  # let asyncio manage the task lifecycle
        except Exception:
            logger.exception("flora _rms_stream unexpected error")

    async def _stop_rms_stream(self) -> None:
        """Cancel the RMS task and await its completion (tts_finished path)."""
        await self._cancel_rms_task()

    async def _cancel_rms_task(self) -> None:
        """Cancel _rms_task if live, swallowing CancelledError."""
        task = self._rms_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._rms_task = None

    # ── P2 subconscious emotion presets (Phase 36 Direction 1) ────────────

    async def push_preset_p2(
        self, preset: str, params: dict[str, Any] | None = None
    ) -> None:
        """Push a P2 (subconscious/AIIM emotion) flora preset.

        If P3 pipeline is currently running a non-breathe state, the request is
        saved and automatically restored when P3 settles.  The RMS brightness
        multiplier is applied to peak_duty so the ambient lighting gently tracks
        the visitor's audio level.
        """
        if not self._enabled:
            return
        self._p2_preset = preset
        self._p2_params = params

        # Defer if a higher-priority layer (P3 pipeline or P1 barge-in) holds
        # the lights in an active (non-breathe) state. P1_BARGE_IN > P3_PIPELINE
        # > P2_SUBCONSCIOUS, so ">= P3_PIPELINE" covers both.
        if (
            self._current_priority is not None
            and self._current_priority >= FloraPriority.P3_PIPELINE
            and self._current_preset not in (None, "breathe")
        ):
            logger.debug(
                "flora P2 preset %r deferred (priority=%s active at %r)",
                preset, self._current_priority.name, self._current_preset,
            )
            return

        self._current_priority = FloraPriority.P2_SUBCONSCIOUS
        overrides = dict(params or {})
        # Apply visitor RMS multiplier to peak brightness (gentle ambient scaling).
        if self._rms_multiplier < 1.0:
            built = self._build_params(preset)
            if "peak_duty" in built:
                overrides.setdefault(
                    "peak_duty", int(round(built["peak_duty"] * self._rms_multiplier))
                )
        await self._set_state(preset, **overrides)
        logger.debug(
            "flora P2 set: %r (rms_mult=%.2f, priority=%s)",
            preset, self._rms_multiplier, self._current_priority.name,
        )

    # ── SmartFlora: sequence runner (Phase 37) ────────────────────────

    async def run_sequence(self, name: str) -> bool:
        """Start a named animation sequence from flora.sequences.

        Cancels any currently running sequence first.  Returns False if the
        sequence name is not found in the config.  Steps execute in order;
        each step pushes a preset, then sleeps hold_ms.  The task is
        cancellable — any P1/P3 pipeline event will abort it.
        """
        if not self._enabled:
            return False
        flora = self._live_flora_cfg()
        sequences: list[dict[str, Any]] = flora.get("sequences") or []
        seq = next((s for s in sequences if s.get("name") == name), None)
        if seq is None:
            logger.debug("flora run_sequence: %r not found", name)
            return False
        steps: list[dict[str, Any]] = seq.get("steps") or []
        if not steps:
            logger.debug("flora run_sequence: %r has no steps", name)
            return False

        await self._cancel_sequence_task()
        self._sequence_task = asyncio.create_task(
            self._run_sequence_steps(name, steps), name="flora_sequence"
        )
        logger.info("flora sequence started: %r (%d steps)", name, len(steps))
        return True

    async def stop_sequence(self) -> None:
        """Cancel any running animation sequence and return to breathe."""
        await self._cancel_sequence_task()
        if self._enabled:
            await self._set_state("breathe")

    async def _cancel_sequence_task(self) -> None:
        """Cancel _sequence_task if live, swallowing CancelledError."""
        task = self._sequence_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._sequence_task = None

    async def _run_sequence_steps(
        self, name: str, steps: list[dict[str, Any]]
    ) -> None:
        """Execute sequence steps sequentially.  Runs as asyncio Task."""
        flora = self._live_flora_cfg()
        global_crossfade = int(flora.get("crossfade_ms", self._crossfade_ms))
        try:
            for i, step in enumerate(steps):
                preset = str(step.get("preset", "")).strip()
                hold_ms = int(step.get("hold_ms", 1000))
                crossfade_ms = int(step.get("crossfade_ms", global_crossfade))
                if not preset:
                    logger.debug("flora sequence %r step %d: missing preset, skipping", name, i)
                    continue
                await self._set_state(preset, crossfade_ms=crossfade_ms)
                if hold_ms > 0:
                    await asyncio.sleep(hold_ms / 1000.0)
            logger.info("flora sequence finished: %r", name)
        except asyncio.CancelledError:
            logger.debug("flora sequence cancelled: %r at step %d", name, i)
            raise

    # ── SmartFlora: emotion → preset mapping (Phase 37) ───────────────

    async def push_preset_p2_emotion(
        self, emotion: str, intensity: float = 0.5
    ) -> None:
        """Push a flora preset for an AIIM emotion state.

        Checks flora.emotion_map first (explicit user mapping). Falls back to
        the naming convention (emotion_a / emotion_b by intensity) when the map
        entry is absent or empty.  If no matching preset exists in either
        flora.states or flora.user_presets, the call is silently dropped.
        """
        if not self._enabled:
            return
        flora = self._live_flora_cfg()
        states: dict[str, Any] = flora.get("states") or {}
        user_presets: dict[str, Any] = flora.get("user_presets") or {}
        emotion_map: dict[str, str] = flora.get("emotion_map") or {}

        # Explicit map entry takes priority over naming convention.
        mapped = emotion_map.get(emotion, "")
        if mapped:
            preset = mapped
        else:
            # Naming convention: emotion_b for high intensity, emotion_a otherwise.
            variant = "b" if intensity > 0.65 else "a"
            preset = f"{emotion}_{variant}"
            if preset not in states and preset not in user_presets:
                preset = f"{emotion}_a"

        if preset not in states and preset not in user_presets:
            logger.debug("flora P2 emotion %r → preset %r not found, skipping", emotion, preset)
            return

        # Route through push_preset_p2 to respect Phase 36 priority system.
        await self.push_preset_p2(preset)
        logger.debug("flora P2 emotion %r → %r (intensity=%.2f)", emotion, preset, intensity)

    async def _restore_p2(self) -> None:
        """Re-apply saved P2 preset after P3 pipeline settles to breathe/idle."""
        if self._p2_preset is None:
            return
        if (
            self._current_priority is not None
            and self._current_priority >= FloraPriority.P3_PIPELINE
            and self._current_preset not in (None, "breathe")
        ):
            return
        preset = self._p2_preset
        params = self._p2_params or {}
        self._current_priority = FloraPriority.P2_SUBCONSCIOUS
        overrides = dict(params)
        if self._rms_multiplier < 1.0:
            built = self._build_params(preset)
            if "peak_duty" in built:
                overrides.setdefault(
                    "peak_duty", int(round(built["peak_duty"] * self._rms_multiplier))
                )
        await self._set_state(preset, **overrides)
        logger.debug("flora P2 restored: %r (rms_mult=%.2f)", preset, self._rms_multiplier)
