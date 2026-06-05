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

All numbers come from settings.section("flora") (Config-First, D-13) — nothing
hardcoded here. Gamma is applied firmware-side, so this layer sends raw percent
duties; the firmware converts via its gamma LUT.
"""
from __future__ import annotations

import asyncio
import audioop
import io
import logging
import wave
from typing import Any

logger = logging.getLogger("adam.flora")


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
        self._vibro_intensity_pct: int = int(self._vibro_cfg.get("intensity_pct", 30))

        # Light/vibro channel masks (D-02) — all numbers Config-First.
        self._light_channels: list[int] = list(self._cfg.get("light_channels", list(range(11))))
        self._vibro_channels: list[int] = list(self._cfg.get("vibro_channels", [11, 12, 13, 14]))
        # PCA9685 full-scale duty (12-bit). mcu_client clamps anyway, but the
        # base..peak percent mapping needs the ceiling. Mirror mcu.channels.value_max.
        self._value_max: int = int(getattr(self._mcu, "value_max", 4095))

        # RMS speech-sync params (D-07/D-08) — flora.speech.* section.
        self._speech_cfg: dict[str, Any] = self._cfg.get("speech", {}) or {}
        self._frame_interval_ms: int = int(self._speech_cfg.get("frame_interval_ms", 80))
        self._hdmi_offset_ms: int = int(self._speech_cfg.get("hdmi_latency_offset_ms", 150))
        self._base_duty_pct: float = float(self._speech_cfg.get("base_duty_pct", 25))
        self._peak_duty_pct: float = float(self._speech_cfg.get("peak_duty_pct", 90))
        self._spark_probability: float = float(self._speech_cfg.get("spark_probability", 0.15))

        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._task: asyncio.Task[None] | None = None
        # wake_bloom fires only on the FIRST transition out of boot_warmup
        # (the system coming alive). Subsequent standby transitions -> breathe.
        self._booted: bool = False
        self._enabled: bool = bool(self._cfg.get("enabled", True))

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
        if etype == "wake_word_detected":
            await self._set_state("accent")  # детекция
        elif etype == "voice_state_change":
            payload = event.get("payload", {}) or {}
            if payload.get("from") == "boot_warmup" and not self._booted:
                # First exit from boot = system coming alive (RESEARCH Open Q1).
                self._booted = True
                await self._set_state("wake_bloom")  # пробуждение (once)
                return
            self._booted = True
            to = payload.get("to")
            if to == "listening":
                await self._set_state("attentive")  # слушание — вибро OFF (D-11)
            elif to == "standby":
                await self._set_state("breathe")  # покой
        elif etype == "llm_thinking_started":
            await self._set_state("think_pulse")  # раздумье
        elif etype == "tts_started":
            await self._on_answer_start(event)
        elif etype == "tts_finished":
            await self._on_answer_end()

    # ── Answer boundary (RMS streamer is plan 04) ──────────────────────

    async def _on_answer_start(self, event: dict[str, Any]) -> None:
        """STUB for plan 04: generic answer pulse while Adam speaks.

        Plan 04 replaces this with the feed_speech_wav-driven RMS streamer that
        modulates light channels in time with TTS playback.
        """
        await self._set_state("accent")

    async def _on_answer_end(self) -> None:
        """Answer finished — settle back to the calm idle preset."""
        await self._set_state("breathe")

    # ── State push ─────────────────────────────────────────────────────

    async def _set_state(self, state: str, **overrides: Any) -> None:
        """Build per-state params from the flora config and POST the transition.

        All numbers come from settings.section("flora") (Config-First). Vibro is
        forced off for any preset in silent_states (belt-and-suspenders mirror of
        the firmware, D-11). Percent duties are sent raw — gamma is firmware-side.
        """
        params = self._build_params(state)
        params.update(overrides)
        if state in self._silent_states:
            params["vibro_enabled"] = False
        await self._mcu.set_flora_state(state, params)
        if self._event_log is not None:
            try:
                self._event_log.append("flora_state_change", {"state": state})
            except Exception:
                pass

    def _build_params(self, state: str) -> dict[str, Any]:
        """Translate a config preset into the flat param dict the firmware expects.

        Keys mirror the Config.schema.json `flora.states.*` shape. Vibro intensity
        ceiling rides along so the firmware can clamp (defence-in-depth, T-29-05).
        """
        preset: dict[str, Any] = self._states_cfg.get(state, {}) or {}
        params: dict[str, Any] = {
            "crossfade_ms": self._crossfade_ms,
            "vibro_intensity_pct": self._vibro_intensity_pct,
        }
        for key, value in preset.items():
            if key == "vibro":
                # config encodes vibro participation as bool or rhythm-mode string
                if isinstance(value, bool):
                    params["vibro_enabled"] = value
                else:
                    params["vibro_enabled"] = True
                    params["vibro_mode"] = value
            else:
                params[key] = value
        # Honour the silent-states policy regardless of preset config (D-11).
        if state in self._silent_states:
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
        """
        base = int(round(self._value_max * self._base_duty_pct / 100.0))
        peak = int(round(self._value_max * self._peak_duty_pct / 100.0))
        lo, hi = (base, peak) if base <= peak else (peak, base)
        span = hi - lo
        duties: list[int] = []
        for level in levels:
            clamped = 0.0 if level < 0.0 else (1.0 if level > 1.0 else level)
            duties.append(lo + int(round(span * clamped)))
        return duties
