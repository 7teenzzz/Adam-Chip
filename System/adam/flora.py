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
import logging
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
