"""System/adam/mic_reader.py

Long-lived producer task that owns the ESP32 :81 WAV mic stream lifecycle
(open -> drain -> reconnect-on-error) and is the single emitter of
`audio_level` events. Consumer side is VoiceLoopController which pulls
mono PCM chunks from `MicReader.get_chunk()` via an asyncio.Queue.

See `.planning/phases/07-esp32-mic-pipeline-refactor-micreader-keep-alive/
07-CONTEXT.md` for decisions D-01..D-20 driving this design.

Key invariants (mandatory):
- _NO_PROXY_OPENER is mandatory for all urlopen() calls (v2ray on
  127.0.0.1:10808 hijacks LAN traffic via http_proxy env vars and leaks
  ESP32:81 socket slots — see CLAUDE.md gotchas).
- Queue policy is drop_oldest (D-02): voice_loop always reads the live
  edge; staleness > ~1 s would push wake-word detection out of band.
- audio_level emits every Nth frame REGARDLESS of mute state (B-1 fix).
  Mute gate only skips the queue put, never the level emission.
- consecutive_fails resets ONLY on successful WAV header receipt (W-2).
  No time-based stability threshold.
- `_make_stereo_reader` (stereo->mono downmix closure factory) is NOT
  duplicated here. The factory is injected via constructor or setter as
  `stereo_reader_factory`. Orchestrator.py is the single source of truth
  for that algorithm. Plan 07-03 wires the actual factory in.
"""

from __future__ import annotations

import asyncio
import audioop
import time
from typing import Any, Callable, Optional
from urllib.request import build_opener, ProxyHandler

# Mandatory per CLAUDE.md: bypass env http_proxy / HTTP_PROXY (v2ray).
# Without this, urlopen() to ESP32:81 leaks sockets through the SOCKS proxy
# and exhausts the firmware's 4 stream-server slots within minutes.
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))

# Queue depth ~ 1 second of audio at 20 ms frames (D-02).
_QUEUE_MAX_DEFAULT = 50

# Rate-limit for mic_reader_overflow events; one emission per N seconds.
_OVERFLOW_EVENT_INTERVAL_SEC = 5.0

# audio_level emission cadence: every N drained frames. Mirrors the
# `level_tick >= 5` pattern in the legacy VoiceLoopController._vad_loop
# (5 frames * 20 ms = ~100 ms cadence).
_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5

# W-2 fix: NO time-based stability threshold is defined. Counter management
# uses the fixed backoff sequence only. Adaptive backoff is a deferred
# idea (see 07-CONTEXT.md "Deferred Ideas").


class MicReader:
    """Long-lived ESP32 :81 WAV mic stream producer.

    Architectural template is `System/adam/camera.py::CameraReader`. The
    producer/consumer split is intentional: this task owns network I/O
    only; VAD/OWW/endpointing all live in VoiceLoopController which pulls
    chunks via `get_chunk()`.

    Lifecycle:
        mr = MicReader(asr_cfg, audio_cfg, mcu, on_event=cb)
        await mr.start()                # spawns _run task, returns
        await mr.wait_active(timeout=…) # block until first stream_active
        chunk = await mr.get_chunk(1.0) # consumer side
        await mr.stop()                 # cancels task, awaits, drains queue

    The constructor takes a `stereo_reader_factory` callable instead of
    importing Orchestrator's `_make_stereo_reader` to avoid a circular
    import. Plan 07-03 wires the factory in at construction time. If the
    factory is None, the reader degrades to mono only — stereo profiles
    will fall back to raw `resp.read` (legacy behaviour, no per-channel
    RMS).
    """

    def __init__(
        self,
        asr_cfg: dict[str, Any],
        audio_cfg: dict[str, Any],
        mcu: Any,
        voice_loop: Any | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        stereo_reader_factory: Optional[
            Callable[[Callable[[int], bytes], int, Callable[[float, float], None]], Callable[[int], bytes]]
        ] = None,
    ) -> None:
        # Audio-side parameters (force a restart when changed via apply_config).
        self._sample_rate = int(audio_cfg.get("sample_rate", 16000))
        self._channels = int(audio_cfg.get("channels", 1))
        self._frame_ms = int(audio_cfg.get("frame_ms", 20))
        self._profile = str(audio_cfg.get("esp32_mic_profile", "inmp441_philips32_stereo"))
        self._normalize_factor = int(audio_cfg.get("normalize_factor", 8000))

        # frame_bytes formula matches the legacy _run_esp32 / _vad_loop math.
        # sample_rate * 2 bytes/sample * frame_ms / 1000. Channels is folded
        # into the stereo reader (doubles the request internally), so frame
        # size from the consumer's POV is always mono.
        self._frame_bytes = max(2, int(self._sample_rate * 2 * self._frame_ms / 1000))

        # ASR-side parameters (re-read live by the loop on each iteration).
        self._disable_local_fallback = bool(asr_cfg.get("disable_local_fallback", True))
        self._open_timeout_sec = int(asr_cfg.get("esp_open_timeout_sec", 8))
        self._probe_after_fails = int(asr_cfg.get("esp_probe_after_fails", 2))
        backoff_seq = list(asr_cfg.get("esp_retry_backoff_sec", [2, 4, 8, 15]) or [])
        self._backoff_seq = [float(x) for x in backoff_seq if isinstance(x, (int, float)) and x > 0]
        if not self._backoff_seq:
            self._backoff_seq = [2.0]

        self._mcu = mcu
        self._on_event = on_event
        self._voice_loop = voice_loop
        self._stereo_reader_factory = stereo_reader_factory

        # Runtime state.
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_MAX_DEFAULT)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        # stream_state ∈ {"idle", "connecting", "active", "failed"}.
        self._stream_state: str = "idle"
        self._is_stereo: bool = False
        self._raw_level_l: float = 0.0
        self._raw_level_r: float = 0.0
        self._consecutive_fails: int = 0
        self._dropped_total: int = 0
        self._dropped_since_last_event: int = 0
        self._last_overflow_event_t: float = 0.0
        self._stream_open_t: float = 0.0
        self._drained_bytes_total: int = 0
        self._start_t: float = 0.0
        self._level_tick: int = 0
        self._active_event: asyncio.Event = asyncio.Event()
        # Phase 9 (REQ-AUDIO-LEVEL-CONTINUOUS): wall-clock fallback emitter.
        # _drain_loop is the primary path (per-frame, 5-frame cadence ≈ 100 ms),
        # but when the ESP32 stream stalls / reconnects / TTS playback blocks
        # downstream consumers, drain emissions go silent for seconds. The
        # _level_emit_loop task fills those gaps so the UI VU-meter never
        # freezes for more than ~250 ms.
        self._level_emit_task: asyncio.Task[None] | None = None
        # perf_counter() of the most recent _emit_audio_level call (any source).
        # Used by the watchdog task to decide whether to backfill.
        self._last_level_emit_t: float = 0.0
        # Cached last mono RMS for the watchdog task (filled by _emit_audio_level).
        self._last_mono_rms: float = 0.0

    # ── External wiring ────────────────────────────────────────────────

    def set_voice_loop(self, voice_loop: Any) -> None:
        """Wire VoiceLoopController post-construction (chicken-and-egg)."""
        self._voice_loop = voice_loop

    def set_stereo_reader_factory(
        self,
        factory: Callable[[Callable[[int], bytes], int, Callable[[float, float], None]], Callable[[int], bytes]],
    ) -> None:
        """Inject the stereo-to-mono downmix factory (Plan 07-03 wiring).

        Signature: factory(read_fn, normalize_factor, level_setter) -> Callable[[int], bytes]
        where level_setter(level_l: float, level_r: float) is invoked on each
        successful read so MicReader can store live per-channel RMS values.
        """
        self._stereo_reader_factory = factory

    # ── Event emission ─────────────────────────────────────────────────

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._on_event is not None:
            try:
                self._on_event(event_type, payload)
            except Exception:
                # Never let event-callback failures break the audio loop.
                pass

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Spawn the long-lived `_run` task. Idempotent."""
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._start_t = time.perf_counter()
        self._active_event.clear()
        self._task = asyncio.create_task(self._run(), name="adam_mic_reader")
        # Phase 9 (REQ-AUDIO-LEVEL-CONTINUOUS): start the watchdog emitter.
        if self._level_emit_task is None or self._level_emit_task.done():
            self._level_emit_task = asyncio.create_task(
                self._level_emit_loop(), name="adam_mic_level_emit"
            )
        self._emit(
            "mic_reader_started",
            {
                "profile": self._profile,
                "frame_bytes": self._frame_bytes,
                "queue_max": self._queue.maxsize,
            },
        )

    async def stop(self) -> None:
        """Cancel `_run`, await it, drain the queue, emit stopped event."""
        self._running = False
        # Phase 9 (REQ-AUDIO-LEVEL-CONTINUOUS): tear down the watchdog before
        # the drain task so the watchdog cannot race the queue cleanup below.
        emit_task = self._level_emit_task
        if emit_task is not None and not emit_task.done():
            emit_task.cancel()
            try:
                await emit_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._level_emit_task = None
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                # _run should never propagate a non-cancellation exception
                # past its top-level handler, but guard anyway.
                pass
        self._task = None

        # Drain pending queue items so a subsequent start() begins clean.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

        uptime = round(time.perf_counter() - self._start_t, 1) if self._start_t else 0.0
        self._emit(
            "mic_reader_stopped",
            {"drained_bytes_total": self._drained_bytes_total, "uptime_sec": uptime},
        )
        self._active_event.clear()
        self._stream_state = "idle"

    async def wait_active(self, timeout: float | None = None) -> bool:
        """Block until first `stream_active` event (or timeout)."""
        try:
            await asyncio.wait_for(self._active_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    # ── Consumer API ───────────────────────────────────────────────────

    async def get_chunk(self, timeout: float = 1.0) -> bytes | None:
        """Pull one mono PCM frame from the queue, or return None on timeout."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ── Introspection ──────────────────────────────────────────────────

    @property
    def frame_bytes(self) -> int:
        return self._frame_bytes

    @property
    def is_stereo(self) -> bool:
        return self._is_stereo

    @property
    def raw_level_l(self) -> float:
        return self._raw_level_l

    @property
    def raw_level_r(self) -> float:
        return self._raw_level_r

    @property
    def active_source(self) -> str:
        """Canonical short label of the mic source for audio_level events.

        Ported from VoiceLoopController._active_audio_source_label, scoped
        to the ESP32 path only — MicReader does not own local fallback.
        """
        if self._stream_state == "active":
            return "esp32_stereo" if self._is_stereo else "esp32_mono"
        if self._stream_state == "failed":
            return "failed"
        # Both "idle" (pre-start) and "connecting" report as "connecting"
        # so UI treats the mic as not-yet-ready in either case.
        return "connecting"

    def status(self) -> dict[str, Any]:
        """Snapshot for /api/agent/status (Plan 07-03 surfaces this)."""
        uptime = round(time.perf_counter() - self._start_t, 1) if self._start_t else 0.0
        return {
            "running": self._running,
            "stream_state": self._stream_state,
            "is_stereo": self._is_stereo,
            "consecutive_fails": self._consecutive_fails,
            "dropped_total": self._dropped_total,
            "raw_level_l": self._raw_level_l,
            "raw_level_r": self._raw_level_r,
            "queue_depth": self._queue.qsize(),
            "queue_max": self._queue.maxsize,
            "active_source": self.active_source,
            "disable_local_fallback": self._disable_local_fallback,
            "open_timeout_sec": self._open_timeout_sec,
            "probe_after_fails": self._probe_after_fails,
            "backoff_seq": list(self._backoff_seq),
            "uptime_sec": uptime,
        }

    def apply_config(self, asr_cfg: dict[str, Any], audio_cfg: dict[str, Any]) -> bool:
        """Re-read config values. Returns True iff a restart is required.

        Audio-side changes (profile/sample_rate/frame_ms) require socket
        reopen because they affect either the WAV header request or the
        frame chunk size. Timeouts / backoff / probe / normalize_factor
        are re-read live by the running loop on each iteration so they
        do not need a restart.
        """
        new_profile = str(audio_cfg.get("esp32_mic_profile", self._profile))
        new_sample_rate = int(audio_cfg.get("sample_rate", self._sample_rate))
        new_frame_ms = int(audio_cfg.get("frame_ms", self._frame_ms))

        restart_needed = (
            new_profile != self._profile
            or new_sample_rate != self._sample_rate
            or new_frame_ms != self._frame_ms
        )

        # Update audio-side (these only take effect after restart, but we
        # store them so a subsequent start() picks up the new values).
        self._profile = new_profile
        self._sample_rate = new_sample_rate
        self._frame_ms = new_frame_ms
        self._channels = int(audio_cfg.get("channels", self._channels))
        self._normalize_factor = int(audio_cfg.get("normalize_factor", self._normalize_factor))
        self._frame_bytes = max(2, int(self._sample_rate * 2 * self._frame_ms / 1000))

        # ASR-side (live re-read, no restart).
        self._disable_local_fallback = bool(asr_cfg.get("disable_local_fallback", self._disable_local_fallback))
        self._open_timeout_sec = int(asr_cfg.get("esp_open_timeout_sec", self._open_timeout_sec))
        self._probe_after_fails = int(asr_cfg.get("esp_probe_after_fails", self._probe_after_fails))
        backoff_seq = list(asr_cfg.get("esp_retry_backoff_sec", self._backoff_seq) or [])
        cleaned = [float(x) for x in backoff_seq if isinstance(x, (int, float)) and x > 0]
        if cleaned:
            self._backoff_seq = cleaned

        return restart_needed

    # ── Internal: queue / overflow ─────────────────────────────────────

    def _put_or_drop(self, chunk: bytes) -> None:
        """drop_oldest queue policy (D-02).

        On QueueFull: discard the oldest item, then put the new one.
        Voice_loop always reads the live edge — staleness > ~1 s would
        push wake-word detection out of band.
        """
        try:
            self._queue.put_nowait(chunk)
            return
        except asyncio.QueueFull:
            pass

        try:
            self._queue.get_nowait()
        except Exception:
            pass
        try:
            self._queue.put_nowait(chunk)
        except Exception:
            pass

        self._dropped_total += 1
        self._dropped_since_last_event += 1
        self._try_emit_overflow()

    def _try_emit_overflow(self) -> None:
        """Rate-limited mic_reader_overflow event emission."""
        now = time.perf_counter()
        if now - self._last_overflow_event_t < _OVERFLOW_EVENT_INTERVAL_SEC:
            return
        self._emit(
            "mic_reader_overflow",
            {
                "dropped_total": self._dropped_total,
                "since_last_event": self._dropped_since_last_event,
            },
        )
        self._last_overflow_event_t = now
        self._dropped_since_last_event = 0

    # ── Internal: audio_level emission ─────────────────────────────────

    def _voice_state_for_event(self) -> str:
        """Per D-11: state = voice_loop._voice_state if set, else 'boot_warmup'."""
        if self._voice_loop is not None:
            return getattr(self._voice_loop, "_voice_state", "boot_warmup") or "boot_warmup"
        return "boot_warmup"

    def _emit_audio_level(self, mono_chunk: bytes) -> None:
        """Single emitter of audio_level events (D-10).

        Fires on every Nth drained frame regardless of mute state (B-1):
        the UI VU-meter MUST stay live during TTS playback so operators
        can see whether the ESP32 mic is still streaming (silence vs echo).
        """
        rms = audioop.rms(mono_chunk, 2)
        # Phase 9 (REQ-AUDIO-LEVEL-CONTINUOUS): cache the latest mono RMS so
        # _level_emit_loop can backfill audio_level events when drain_loop is
        # stalled. Also stamp _last_level_emit_t so the watchdog only fills
        # actual gaps, not steady-state cadence.
        self._last_mono_rms = float(rms)
        self._last_level_emit_t = time.perf_counter()
        norm = round(min(1.0, (rms / self._normalize_factor) ** 0.5), 3)
        payload: dict[str, Any] = {
            "level": norm,
            "state": self._voice_state_for_event(),
            "source": self.active_source,
        }
        if self._is_stereo:
            payload["channels"] = 2
            payload["level_l"] = self._raw_level_l
            payload["level_r"] = self._raw_level_r
        else:
            payload["channels"] = 1

        # W-1 fix: include utterance_id ONLY when non-empty. Drop the key
        # otherwise — never emit `utterance_id: null`.
        if self._voice_loop is not None:
            utt_id = getattr(self._voice_loop, "_utterance_id", "") or ""
            if utt_id:
                payload["utterance_id"] = utt_id

        self._emit("audio_level", payload)

    async def _level_emit_loop(self) -> None:
        """Phase 9 (REQ-AUDIO-LEVEL-CONTINUOUS): wall-clock fallback emitter.

        Wakes every 200 ms. If _emit_audio_level has fired within the last
        250 ms, skip (drain_loop is keeping the UI updated). Otherwise
        synthesise an audio_level event using the last cached RMS values so
        the UI VU-meter does not freeze for multi-second stretches when the
        drain loop is blocked on reconnect, stall, or downstream backpressure.

        Marks the synthetic event with source field unchanged but adds
        `synthetic: true` so log consumers can distinguish backfill from real
        per-frame emissions.
        """
        period_sec = 0.2
        gap_threshold_sec = 0.25
        try:
            while self._running:
                await asyncio.sleep(period_sec)
                if not self._running:
                    break
                now = time.perf_counter()
                if now - self._last_level_emit_t < gap_threshold_sec:
                    continue
                # Backfill — synthesise from cached RMS.
                rms = self._last_mono_rms
                norm = round(min(1.0, (rms / self._normalize_factor) ** 0.5), 3)
                payload: dict[str, Any] = {
                    "level": norm,
                    "state": self._voice_state_for_event(),
                    "source": self.active_source,
                    "synthetic": True,
                }
                if self._is_stereo:
                    payload["channels"] = 2
                    payload["level_l"] = self._raw_level_l
                    payload["level_r"] = self._raw_level_r
                else:
                    payload["channels"] = 1
                if self._voice_loop is not None:
                    utt_id = getattr(self._voice_loop, "_utterance_id", "") or ""
                    if utt_id:
                        payload["utterance_id"] = utt_id
                self._emit("audio_level", payload)
                self._last_level_emit_t = now
        except asyncio.CancelledError:
            raise

    # ── Internal: probe + backoff ──────────────────────────────────────

    async def _probe_esp_status(self) -> tuple[bool, str]:
        """Probe ESP32 /api/status on :80 before retrying :81 (D-19).

        Returns (ok, error_message). If ESP control-plane is dead, this
        saves us an 8 s urlopen timeout on :81.
        """
        if self._mcu is None:
            return (False, "no_mcu")
        try:
            result = await self._mcu.request("GET", "/api/status")
            return (bool(getattr(result, "ok", False)), str(getattr(result, "error", "") or ""))
        except Exception as exc:
            return (False, str(exc)[:120])

    def _backoff_for(self, fail_idx: int) -> float:
        """Fixed-sequence backoff (D-20). Last value reuses on overflow."""
        if not self._backoff_seq:
            return 2.0
        idx = min(max(0, fail_idx - 1), len(self._backoff_seq) - 1)
        return float(self._backoff_seq[idx])

    # ── Internal: drain loop (per-chunk consumer logic) ────────────────

    async def _drain_loop(self, read_fn: Callable[[int], bytes]) -> None:
        """Tight chunk-read loop. Exits on `self._running = False` or via
        a propagating exception (caller's outer loop triggers reconnect).

        Per-chunk sequence (B-1 final rule):
          1. read chunk
          2. handle empty (3 consecutive empties => raise)
          3. tally drained_bytes_total
          4. tick level counter
          5. if tick threshold reached: emit audio_level (ALWAYS, even
             when muted) and reset tick
          6. mute gate: skip _put_or_drop only if voice_loop.muted_by_tts
          7. else: put on queue
        """
        empty_streak = 0
        while self._running:
            chunk = await asyncio.to_thread(read_fn, self._frame_bytes)

            if not chunk:
                empty_streak += 1
                if empty_streak >= 3:
                    raise RuntimeError("audio source ended: 3 consecutive empty reads")
                await asyncio.sleep(0.005)
                continue
            empty_streak = 0

            self._drained_bytes_total += len(chunk)

            self._level_tick += 1
            if self._level_tick >= _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES:
                self._emit_audio_level(chunk)
                self._level_tick = 0

            # B-1 mute gate: drain-and-discard while voice_loop is muted
            # by TTS. The socket still drains, audio_level still emits;
            # only the queue write is skipped. Without the drain the
            # W5500 SPI send buffer (~64 KB) overflows in ~1 s and the
            # ESP firmware closes the connection.
            if self._voice_loop is not None and getattr(self._voice_loop, "muted_by_tts", False):
                continue

            self._put_or_drop(chunk)

    # ── Internal: main loop ────────────────────────────────────────────

    async def _run(self) -> None:
        """Outer open / drain / reconnect loop. Runs until self._running flips False."""
        while self._running:
            # Probe gate (D-19).
            if self._probe_after_fails > 0 and self._consecutive_fails >= self._probe_after_fails:
                ok, err = await self._probe_esp_status()
                if not ok:
                    self._emit(
                        "mic_reader_probe_skip",
                        {
                            "consecutive_fails": self._consecutive_fails,
                            "probe_error": err[:120],
                        },
                    )
                    self._consecutive_fails += 1
                    try:
                        await asyncio.sleep(self._backoff_for(self._consecutive_fails))
                    except asyncio.CancelledError:
                        raise
                    continue

            url = self._mcu.mic_stream_url() if self._mcu is not None else ""
            profile = self._profile
            is_stereo_profile = profile.endswith("stereo")
            self._stream_state = "connecting"
            self._is_stereo = False
            resp = None
            stage = "open"

            try:
                # Tell ESP which mic profile to use (mirror legacy _run_esp32).
                if self._mcu is not None:
                    try:
                        await self._mcu.request("POST", "/api/audio", {"profile": profile})
                    except Exception:
                        # Profile-set is best-effort — the stream open below
                        # is the real ready-check. Fall through.
                        pass

                if not url:
                    raise RuntimeError("mic_stream_url is empty (mcu not configured)")

                # _NO_PROXY_OPENER is mandatory — see CLAUDE.md gotchas.
                resp = await asyncio.to_thread(_NO_PROXY_OPENER.open, url, None, self._open_timeout_sec)
                self._emit("mic_reader_stream_opened", {"url": url, "profile": profile})

                header = await asyncio.to_thread(resp.read, 44)
                if len(header) < 44:
                    raise RuntimeError(f"WAV header truncated ({len(header)}/44)")

                self._is_stereo = is_stereo_profile
                if is_stereo_profile and self._stereo_reader_factory is not None:
                    # Inject our level_setter so MicReader can store live
                    # raw_level_l / raw_level_r values used by audio_level.
                    def _level_setter(l: float, r: float) -> None:
                        self._raw_level_l = l
                        self._raw_level_r = r

                    read_fn = self._stereo_reader_factory(
                        resp.read, self._normalize_factor, _level_setter
                    )
                else:
                    # Either mono profile, or stereo without an injected
                    # factory (early-boot / unit tests). Raw resp.read in
                    # both cases — VAD math still works on mono PCM.
                    if is_stereo_profile and self._stereo_reader_factory is None:
                        # Surface that we degraded so debug logs catch it.
                        self._emit(
                            "mic_reader_stream_active",
                            {
                                "profile": profile,
                                "is_stereo": False,
                                "note": "no stereo_reader_factory injected; reading raw",
                            },
                        )
                    self._is_stereo = False
                    read_fn = resp.read

                self._stream_open_t = time.perf_counter()
                self._stream_state = "active"
                # W-2 fix: counter resets ONLY here, on successful WAV
                # header receipt. Never on a time-based threshold.
                self._consecutive_fails = 0
                self._active_event.set()
                self._emit(
                    "mic_reader_stream_active",
                    {"profile": profile, "is_stereo": self._is_stereo},
                )
                stage = "read"

                await self._drain_loop(read_fn)

            except asyncio.CancelledError:
                # Closing resp on cancel is critical: ESP32:81 has only 4
                # socket slots — leaked half-open sockets block reconnect.
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass
                raise
            except Exception as exc:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass
                stream_alive = (
                    time.perf_counter() - self._stream_open_t
                    if self._stream_open_t
                    else 0.0
                )
                self._stream_state = "failed"
                self._is_stereo = False
                self._active_event.clear()
                # W-2: counter increments here; reset lives in the success
                # branch above. No time threshold.
                self._consecutive_fails += 1
                self._emit(
                    "mic_reader_error",
                    {
                        "stage": stage,
                        "error": str(exc)[:200],
                        "consecutive_fails": self._consecutive_fails,
                        "stream_alive_sec": round(stream_alive, 1),
                    },
                )
                # D-16: with disable_local_fallback=true (default) NEVER
                # break the loop. Backoff and continue. Even when false,
                # the legacy local fallback lives in VoiceLoopController,
                # not here — MicReader is ESP-only.
                if self._running:
                    try:
                        await asyncio.sleep(self._backoff_for(self._consecutive_fails))
                    except asyncio.CancelledError:
                        raise
            finally:
                if resp is not None:
                    try:
                        resp.close()
                    except Exception:
                        pass
                self._stream_open_t = 0.0
