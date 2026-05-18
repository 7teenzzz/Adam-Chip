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
import math
import queue as _queue_module
import threading
import time
from typing import Any, Callable, Optional
from urllib.request import build_opener, ProxyHandler

import numpy as np

# Mandatory per CLAUDE.md: bypass env http_proxy / HTTP_PROXY (v2ray).
# Without this, urlopen() to ESP32:81 leaks sockets through the SOCKS proxy
# and exhausts the firmware's 4 stream-server slots within minutes.
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))

# Queue depth ~ 1 second of audio at 20 ms frames (D-02).
_QUEUE_MAX_DEFAULT = 50

# Rate-limit for mic_reader_overflow events; one emission per N seconds.
_OVERFLOW_EVENT_INTERVAL_SEC = 5.0

# DEPRECATED Phase 21A: cadence now per-instance via spectrum_cadence_hz;
# retained for backwards-compat readers. Live cadence reads from
# `MicReader._audio_level_emit_every_n` (derived in __init__ / apply_config
# from `media.audio.spectrum_cadence_hz` and `media.audio.frame_ms`).
_AUDIO_LEVEL_EMIT_EVERY_N_FRAMES = 5

# W-2 fix: NO time-based stability threshold is defined. Counter management
# uses the fixed backoff sequence only. Adaptive backoff is a deferred
# idea (see 07-CONTEXT.md "Deferred Ideas").


def _build_log_band_table(
    n_fft: int,
    sample_rate: int,
    n_bands: int,
    min_hz: float,
    max_hz: float,
) -> list[tuple[int, int]]:
    """Phase 21A: log-spaced FFT-bin binning table for the chat EQ widget.

    Returns a list of (lo_bin, hi_bin) inclusive index ranges into the
    rfft output (length n_fft // 2 + 1). Each tuple covers one of the
    `n_bands` log-frequency bands between `min_hz` and `max_hz`. Band
    edges are computed as exp(linspace(log(min_hz), log(max_hz), n_bands+1))
    so each band spans equal-octave fractions.

    DC bin 0 is skipped (lo >= 1) to suppress the INMP441 DC-offset
    artefact (RESEARCH §1, Pitfall 1). Degenerate bands where the
    integer floor/ceil collapse the range have hi == lo, so the band
    still reads at least one bin's magnitude.
    """
    n_bins = n_fft // 2 + 1
    bin_hz = sample_rate / n_fft
    log_min = math.log(min_hz)
    log_max = math.log(max_hz)
    edges_hz = [
        math.exp(log_min + i * (log_max - log_min) / n_bands)
        for i in range(n_bands + 1)
    ]
    table: list[tuple[int, int]] = []
    for i in range(n_bands):
        lo = max(1, int(math.floor(edges_hz[i] / bin_hz)))
        hi = min(n_bins - 1, int(math.ceil(edges_hz[i + 1] / bin_hz)))
        if hi < lo:
            hi = lo
        table.append((lo, hi))
    return table


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

        # Phase 21A spectrum config — all 8 keys live under media.audio.* in
        # Config.json. Values consumed by _compute_bands at every drained
        # frame and by the chat-panel equaliser widget on the frontend.
        # color_yellow_at / color_red_at are NOT used inside Python; we
        # store them so they round-trip through /api/config without loss.
        self._spec_n_bands = int(audio_cfg.get("spectrum_bands", 24))
        self._spec_min_hz = float(audio_cfg.get("spectrum_min_hz", 80.0))
        self._spec_max_hz = float(audio_cfg.get("spectrum_max_hz", 8000.0))
        self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", -60.0))
        self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", 0.0))
        self._spec_cadence_hz = float(audio_cfg.get("spectrum_cadence_hz", 25.0))
        self._spec_color_yellow_at = float(audio_cfg.get("spectrum_color_yellow_at", 0.6))
        self._spec_color_red_at = float(audio_cfg.get("spectrum_color_red_at", 0.85))

        # Derived spectrum runtime tables. n_fft = mono samples per frame:
        # sample_rate * frame_ms / 1000 → 320 at prod defaults (16000 × 20/1000).
        # bin_hz = sample_rate / n_fft = 50 Hz at prod defaults.
        # mag_ref = 0.5 * INT16_MAX * sum(Hann) — full-scale rfft peak
        # reference (RESEARCH §3, Pitfall 3).
        self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))
        self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
        self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())
        self._spec_band_table = _build_log_band_table(
            self._spec_n_fft,
            self._sample_rate,
            self._spec_n_bands,
            self._spec_min_hz,
            self._spec_max_hz,
        )

        # Per-instance audio_level cadence: emit every Nth drained frame.
        # Derived from spectrum_cadence_hz and frame_ms. At sample_rate=16000,
        # frame_ms=20, spectrum_cadence_hz=25 → every 2nd frame (25 Hz).
        # Replaces the legacy module-level _AUDIO_LEVEL_EMIT_EVERY_N_FRAMES.
        frame_hz = 1000.0 / max(1, self._frame_ms)
        self._audio_level_emit_every_n = max(
            1, int(round(frame_hz / max(1e-6, self._spec_cadence_hz)))
        )

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
        # Phase 21A-08 watchdog: auto-restart ESP :81 web-server when
        # `:81/audio` open keeps failing despite `:80` being alive.
        # ESP firmware's 4-slot limit + zombie keepalive-death sockets
        # create deadlocks that normal backoff cannot recover from
        # (see CLAUDE.md gotcha). 0 disables the watchdog entirely.
        self._esp_stream_restart_after_fails = int(
            asr_cfg.get("esp_stream_restart_after_fails", 5)
        )
        self._esp_stream_restart_cooldown_sec = float(
            asr_cfg.get("esp_stream_restart_cooldown_sec", 120.0)
        )

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
        # Phase 21A-08 watchdog: perf_counter() of last auto-restart trigger.
        # Cooldown gate prevents restart-loop while ESP firmware reboots :81.
        self._last_auto_restart_t: float = 0.0
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
        # Phase 10 (REQ-FLUSH-ON-STATE-TRANSITION): wall-clock deadline. While
        # perf_counter() < this value, drain_loop reads from the ESP32 socket
        # as usual (keeps kernel TCP buffer empty) BUT skips _put_or_drop so
        # the consumer never sees those chunks. Mirrors V-S07.1's
        # _drain_esp32_backlog intent at the MicReader layer: after a long
        # mute window, the stream stays open and live but stale frames are
        # silently dropped. Set via flush_queue() from VoiceLoopController.
        # NEVER called on wake_word_detected — that would eat the user's
        # request (Phase 10 v1 regression in Test 5: 33% success rate).
        self._discard_until_ts: float = 0.0
        # Phase 11 diagnostic (lag-source detection):
        # When set to a positive perf_counter() value, drain_loop logs RMS of
        # every chunk drained (or queued) until time exceeds this value. Used
        # to capture the audio envelope right after mute_unmute so we can
        # distinguish "TTS-tail leaking through" from "ALSA buffer drain" from
        # "ESP32 firmware buffer". Set via begin_lag_diag().
        self._lag_diag_until_ts: float = 0.0
        self._lag_diag_started_t: float = 0.0
        self._lag_diag_origin: str = ""

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

    def begin_lag_diag(self, duration_ms: float, origin: str) -> None:
        """Start RMS-envelope logging on _drain_loop for `duration_ms`.

        Emits one ``mic_lag_diag_chunk`` event per drained chunk:
          {"t_offset_ms": <ms since start>, "rms": <int>, "muted": bool,
           "discarded": bool, "origin": str}

        Used to pinpoint the ~2.3s post-TTS lag source — by overlaying the
        envelope against tts_finished / mute_unmute timestamps we can tell
        whether echo is ALSA buffer drain, room reverb, or ESP32 firmware FIFO.

        Light overhead — ~one event per 20 ms frame.
        """
        if duration_ms <= 0:
            return
        now = time.perf_counter()
        self._lag_diag_started_t = now
        self._lag_diag_until_ts = now + (duration_ms / 1000.0)
        self._lag_diag_origin = origin
        self._emit("mic_lag_diag_started", {
            "duration_ms": duration_ms,
            "origin": origin,
        })

    def flush_queue(self, discard_window_ms: float = 200.0) -> int:
        """Phase 10 (REQ-FLUSH-ON-STATE-TRANSITION): drain stale audio.

        Drops every chunk currently in the queue AND sets a wall-clock
        deadline so drain_loop discards any chunk read from the ESP32
        socket for the next ``discard_window_ms`` ms. The stream stays
        OPEN — drain_loop keeps pumping bytes (kernel TCP buffer drains
        as usual, ESP32 W5500 SPI does not overflow), but no chunks
        reach the consumer for the window.

        Adapted from V-S07.1's _drain_esp32_backlog. V-S07.1 read the
        socket directly inside _vad_loop; here MicReader owns the
        socket, so the consumer-visible drain is queue-flush plus a
        post-flush discard window — same effective semantics, MicReader
        streaming contract preserved.

        CALL ONLY at safe transition points where the user is unlikely
        to be speaking right at that moment:
          - after _transcribe_and_dispatch returns (V-S07.1 equivalent;
            also covered downstream by _REPLY_GUARD_SEC=0.6 anyway)
          - on reply_silence_timeout (user just timed out without
            speaking; _STANDBY_GUARD_SEC=0.3 covers the next 300 ms too)
        DO NOT CALL on wake_word_detected — the user's request follows
        the wake word within ~50-300 ms and a 200 ms discard window
        eats the start of their speech (Phase 10 v1 regression).

        Returns: number of frames dropped from the queue (does not
        count frames discarded during the post-flush window).
        """
        dropped = 0
        while True:
            try:
                self._queue.get_nowait()
                dropped += 1
            except asyncio.QueueEmpty:
                break
        if discard_window_ms > 0:
            self._discard_until_ts = time.perf_counter() + (discard_window_ms / 1000.0)
        return dropped

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

        # Phase 21A: hot-reload spectrum_* keys (D-16). spectrum_* deltas
        # are LIVE — they MUST NOT force restart_needed=True. Floor/ceiling
        # and the colour thresholds are simple scalar updates; bands/min/max
        # plus a structural sample_rate/frame_ms change rebuild the band
        # table; cadence_hz or frame_ms changes recompute the emit gate.
        old_bands = self._spec_n_bands
        old_min = self._spec_min_hz
        old_max = self._spec_max_hz
        old_cad = self._spec_cadence_hz

        self._spec_n_bands = int(audio_cfg.get("spectrum_bands", self._spec_n_bands))
        self._spec_min_hz = float(audio_cfg.get("spectrum_min_hz", self._spec_min_hz))
        self._spec_max_hz = float(audio_cfg.get("spectrum_max_hz", self._spec_max_hz))
        self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", self._spec_floor_db))
        self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", self._spec_ceiling_db))
        self._spec_cadence_hz = float(audio_cfg.get("spectrum_cadence_hz", self._spec_cadence_hz))
        self._spec_color_yellow_at = float(
            audio_cfg.get("spectrum_color_yellow_at", self._spec_color_yellow_at)
        )
        self._spec_color_red_at = float(
            audio_cfg.get("spectrum_color_red_at", self._spec_color_red_at)
        )

        table_dirty = (
            self._spec_n_bands != old_bands
            or self._spec_min_hz != old_min
            or self._spec_max_hz != old_max
            or restart_needed  # sample_rate / frame_ms / profile already flagged a rebuild
        )
        cadence_dirty = (
            self._spec_cadence_hz != old_cad or restart_needed
        )

        if table_dirty:
            self._spec_n_fft = max(64, int(self._sample_rate * self._frame_ms / 1000))
            self._spec_hann = np.hanning(self._spec_n_fft).astype(np.float32)
            self._spec_mag_ref = 0.5 * 32768.0 * float(self._spec_hann.sum())
            self._spec_band_table = _build_log_band_table(
                self._spec_n_fft,
                self._sample_rate,
                self._spec_n_bands,
                self._spec_min_hz,
                self._spec_max_hz,
            )
            self._emit(
                "spectrum_band_table_rebuilt",
                {
                    "n_bands": self._spec_n_bands,
                    "n_fft": self._spec_n_fft,
                    "min_hz": self._spec_min_hz,
                    "max_hz": self._spec_max_hz,
                },
            )

        if cadence_dirty:
            frame_hz = 1000.0 / max(1, self._frame_ms)
            self._audio_level_emit_every_n = max(
                1, int(round(frame_hz / max(1e-6, self._spec_cadence_hz)))
            )

        # ASR-side (live re-read, no restart).
        self._disable_local_fallback = bool(asr_cfg.get("disable_local_fallback", self._disable_local_fallback))
        self._open_timeout_sec = int(asr_cfg.get("esp_open_timeout_sec", self._open_timeout_sec))
        self._probe_after_fails = int(asr_cfg.get("esp_probe_after_fails", self._probe_after_fails))
        backoff_seq = list(asr_cfg.get("esp_retry_backoff_sec", self._backoff_seq) or [])
        cleaned = [float(x) for x in backoff_seq if isinstance(x, (int, float)) and x > 0]
        if cleaned:
            self._backoff_seq = cleaned
        # Phase 21A-08 watchdog — hot-reload.
        self._esp_stream_restart_after_fails = int(
            asr_cfg.get("esp_stream_restart_after_fails", self._esp_stream_restart_after_fails)
        )
        self._esp_stream_restart_cooldown_sec = float(
            asr_cfg.get("esp_stream_restart_cooldown_sec", self._esp_stream_restart_cooldown_sec)
        )

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

        # Phase 21A: attach 24-band log-frequency FFT spectrum (UI-EQ-01/02).
        # Emits as payload["bands"] = list[float], length spec_n_bands,
        # each value in [0.0, 1.0] (dBFS-normalised). When the chunk is too
        # short or FFT fails, _compute_bands returns None and the key is
        # omitted — frontend keeps its last snapshot.
        bands = self._compute_bands(mono_chunk)
        if bands is not None:
            payload["bands"] = bands

        self._emit("audio_level", payload)

    def _compute_bands(self, mono_chunk: bytes) -> list[float] | None:
        """Phase 21A: 24-band log-frequency FFT spectrum (UI-EQ-01).

        Real-time per-frame FFT over the same mono PCM buffer that already
        feeds RMS / OWW / ASR. Returns a list of `_spec_n_bands` floats in
        [0.0, 1.0] dBFS-normalised, rounded to 3 decimals. Returns None
        when the chunk is missing or shorter than n_fft samples (frontend
        keeps the last snapshot in that case — RESEARCH §12 / Pitfall 4).

        Math (RESEARCH §1 + §3):
          windowed     = int16_samples * Hann(n_fft).float32
          spectrum     = |rfft(windowed)|
          ref(band)    = 0.5 * 32768 * sum(Hann) * bin_count
          db(band)     = 20 * log10(sum(spectrum[lo:hi+1]) / ref)
          norm(band)   = clamp(db, floor_db, ceiling_db)
                         mapped linearly into [0, 1]

        Exceptions are swallowed (emitting a `spectrum_error` event) so
        any FFT failure cannot stall the audio_level emit path that the
        UI VU-meter relies on. Mirrors Pitfall A8 from RESEARCH.
        """
        try:
            if not mono_chunk or len(mono_chunk) < self._spec_n_fft * 2:
                return None
            samples = np.frombuffer(
                mono_chunk[: self._spec_n_fft * 2], dtype=np.int16
            ).astype(np.float32)
            windowed = samples * self._spec_hann
            spectrum = np.abs(np.fft.rfft(windowed))
            out: list[float] = []
            floor_db = self._spec_floor_db
            ceiling_db = self._spec_ceiling_db
            span_db = ceiling_db - floor_db
            if span_db <= 0:
                # Degenerate config — would divide by zero / give NaN.
                span_db = 1.0
            for (lo, hi) in self._spec_band_table:
                band_mag = float(spectrum[lo : hi + 1].sum())
                bin_count = hi - lo + 1
                ref = self._spec_mag_ref * max(1, bin_count)
                if band_mag < 1e-9 or ref <= 0:
                    norm = 0.0
                else:
                    db = 20.0 * math.log10(band_mag / ref)
                    if db < floor_db:
                        db_clamped = floor_db
                    elif db > ceiling_db:
                        db_clamped = ceiling_db
                    else:
                        db_clamped = db
                    norm = (db_clamped - floor_db) / span_db
                out.append(round(norm, 3))
            return out
        except Exception as exc:  # noqa: BLE001 — must never break emit
            self._emit("spectrum_error", {"err": str(exc)[:200]})
            return None

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
                # Phase 21A: synthetic events OMIT 'bands' by design
                # (RESEARCH §12). No fresh PCM → no honest spectrum.
                # Frontend keeps last snapshot.
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

    def _should_trigger_stream_restart(self, now: float | None = None) -> bool:
        """Phase 21A-08 watchdog gate predicate. Extracted from `_run` for testability.

        Returns True when the watchdog should fire a `:81` restart:
        - feature is enabled (`esp_stream_restart_after_fails > 0`)
        - failure budget exceeded
        - cooldown since previous trigger has elapsed
        The caller is responsible for the probe-alive precondition; in
        `_run` this is implicit because a failing probe earlier in the
        same iteration `continue`s before reaching this gate.
        """
        if self._esp_stream_restart_after_fails <= 0:
            return False
        if self._consecutive_fails < self._esp_stream_restart_after_fails:
            return False
        ts = time.perf_counter() if now is None else now
        return (ts - self._last_auto_restart_t) >= self._esp_stream_restart_cooldown_sec

    async def _trigger_stream_restart(self) -> bool:
        """Phase 21A-08 watchdog: POST :80/api/system/stream/restart to ESP32.

        Called from `_run` when `_consecutive_fails` crosses the configured
        threshold AND probe shows ESP control-plane is alive. The endpoint
        restarts the firmware's :81 web-server only — releases the 4-slot
        audio-stream socket pool from zombie keepalive-death sessions
        (CLAUDE.md gotcha). Returns True on HTTP 2xx.
        """
        if self._mcu is None:
            self._emit(
                "mic_reader_stream_restart_triggered",
                {"ok": False, "consecutive_fails": self._consecutive_fails, "error": "no_mcu"},
            )
            return False
        try:
            result = await self._mcu.stream_restart()
            ok = bool(getattr(result, "ok", False))
            payload: dict[str, Any] = {
                "ok": ok,
                "consecutive_fails": self._consecutive_fails,
                "status_code": int(getattr(result, "status", 0) or 0),
            }
            if not ok:
                payload["error"] = str(getattr(result, "error", "") or "")[:200]
            self._emit("mic_reader_stream_restart_triggered", payload)
            return ok
        except Exception as exc:  # noqa: BLE001 — watchdog must never crash the loop
            self._emit(
                "mic_reader_stream_restart_triggered",
                {
                    "ok": False,
                    "consecutive_fails": self._consecutive_fails,
                    "error": str(exc)[:200],
                },
            )
            return False

    # ── Internal: socket reader thread ────────────────────────────────

    def _socket_reader_thread(
        self,
        read_fn: Callable[[int], bytes],
        out_q: "_queue_module.Queue[bytes | None]",
        stop_ev: threading.Event,
    ) -> None:
        """Read ESP32 socket into out_q in a dedicated OS thread.

        Root-cause fix for the 2.3-second post-TTS dead zone: the original
        asyncio.to_thread(read_fn, N) per-chunk pattern cannot guarantee
        continuous socket draining during the 16-22s mute window (ASR + LLM
        + TTS + playback). Event-loop scheduling delays let the TCP receive
        buffer fill, the W5500 RTR/RCR timer expire, and the connection reset —
        producing a 2-second reconnect-backoff dead zone after every turn.

        This thread runs at OS-thread priority, decoupled from the asyncio
        event loop entirely. out_q uses drop-oldest overflow (mirrors
        _put_or_drop) so the live audio edge is always preserved when
        _drain_loop is momentarily behind.
        """
        empty_streak = 0
        while not stop_ev.is_set():
            try:
                chunk = read_fn(self._frame_bytes)
            except Exception:
                try:
                    out_q.put(None, timeout=1.0)
                except Exception:
                    pass
                return
            if not chunk:
                empty_streak += 1
                if empty_streak >= 3:
                    try:
                        out_q.put(None, timeout=1.0)
                    except Exception:
                        pass
                    return
                time.sleep(0.005)
                continue
            empty_streak = 0
            try:
                out_q.put_nowait(chunk)
            except _queue_module.Full:
                # Drop oldest, keep live edge (mirrors _put_or_drop policy).
                try:
                    out_q.get_nowait()
                except _queue_module.Empty:
                    pass
                try:
                    out_q.put_nowait(chunk)
                except Exception:
                    pass

    # ── Internal: drain loop (per-chunk consumer logic) ────────────────

    async def _drain_loop(self, read_fn: Callable[[int], bytes]) -> None:
        """Tight chunk-read loop. Exits on `self._running = False` or via
        a propagating exception (caller's outer loop triggers reconnect).

        Per-chunk sequence (B-1 final rule):
          1. read chunk from socket reader thread via _frame_q
          2. tally drained_bytes_total
          3. tick level counter
          4. if tick threshold reached: emit audio_level (ALWAYS, even
             when muted) and reset tick
          5. mute gate: skip _put_or_drop only if voice_loop.muted_by_tts
          6. else: put on queue

        Socket reading is decoupled from the asyncio event loop via
        _socket_reader_thread — see that method for rationale.
        """
        # 2048 frames ≈ 40s at 50 fps — 2× headroom over worst-case 22s mute
        # window. Drop-oldest overflow is handled by _socket_reader_thread.
        _frame_q: "_queue_module.Queue[bytes | None]" = _queue_module.Queue(maxsize=2048)
        _stop_ev = threading.Event()
        _reader = threading.Thread(
            target=self._socket_reader_thread,
            args=(read_fn, _frame_q, _stop_ev),
            daemon=True,
            name="adam_mic_socket_reader",
        )
        _reader.start()
        try:
            while self._running:
                try:
                    chunk = await asyncio.to_thread(_frame_q.get, True, 0.5)
                except _queue_module.Empty:
                    continue

                if chunk is None:
                    raise RuntimeError("audio source ended: socket reader thread signaled EOF")

                self._drained_bytes_total += len(chunk)

                self._level_tick += 1
                if self._level_tick >= self._audio_level_emit_every_n:
                    self._emit_audio_level(chunk)
                    self._level_tick = 0

                now_perf = time.perf_counter()

                # Phase 11 diagnostic: RMS envelope log.
                # Emit per-chunk RMS during the lag-diag window so we can plot
                # the audio envelope and correlate against tts_finished /
                # mute_unmute timestamps. Cheap — ~50 events/s for 1-2s.
                if self._lag_diag_until_ts > 0.0 and now_perf < self._lag_diag_until_ts:
                    muted_now = bool(
                        self._voice_loop is not None
                        and getattr(self._voice_loop, "muted_by_tts", False)
                    )
                    discard_now = self._discard_until_ts > 0.0 and now_perf < self._discard_until_ts
                    self._emit("mic_lag_diag_chunk", {
                        "t_offset_ms": int((now_perf - self._lag_diag_started_t) * 1000),
                        "rms": audioop.rms(chunk, 2),
                        "muted": muted_now,
                        "discarded": discard_now,
                        "origin": self._lag_diag_origin,
                    })
                elif self._lag_diag_until_ts > 0.0:
                    # Window just closed — emit terminator and disarm.
                    self._emit("mic_lag_diag_finished", {"origin": self._lag_diag_origin})
                    self._lag_diag_until_ts = 0.0
                    self._lag_diag_origin = ""

                # B-1 mute gate: drain-and-discard while voice_loop is muted
                # by TTS. The socket still drains (socket reader thread handles
                # that now), audio_level still emits; only the queue write is
                # skipped.
                if self._voice_loop is not None and getattr(self._voice_loop, "muted_by_tts", False):
                    continue

                # Phase 10 (REQ-FLUSH-ON-STATE-TRANSITION): post-flush discard
                # window. After flush_queue(window_ms), drain_loop keeps reading
                # from the thread queue (socket is already draining) but skips
                # the consumer queue put so the consumer never sees stale audio.
                if self._discard_until_ts > 0.0 and now_perf < self._discard_until_ts:
                    continue

                self._put_or_drop(chunk)
        finally:
            _stop_ev.set()
            _reader.join(timeout=2.0)

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

            # Phase 21A-08 watchdog gate. Probe just succeeded (or was
            # skipped), so ESP :80 is alive. If :81/audio open keeps
            # failing past the configured threshold, ESP firmware's :81
            # web-server is likely deadlocked on zombie audio slots —
            # restart it via :80/api/system/stream/restart. Cooldown is
            # enforced via _last_auto_restart_t so we do not loop when
            # ESP takes >backoff to come back up.
            if self._should_trigger_stream_restart():
                self._last_auto_restart_t = time.perf_counter()
                restart_ok = await self._trigger_stream_restart()
                # Give ESP firmware time to spin :81 back up. ~8 sec is
                # comfortably above observed reboot time on this hardware.
                try:
                    await asyncio.sleep(8.0)
                except asyncio.CancelledError:
                    raise
                if restart_ok:
                    # Reset fail counter so we don't immediately re-arm
                    # the watchdog on the very next attempt; the next
                    # :81/audio open gets a clean retry budget.
                    self._consecutive_fails = 0
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
