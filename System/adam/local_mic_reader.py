"""System/adam/local_mic_reader.py

Shared local audio capture using a single persistent arecord subprocess.
Distributes PCM chunks to all consumers (VAD, OWW, ASR, barge-in) via
asyncio.Queue — the "corporate audio client" pattern.

Architecture mirrors MicReader (ESP32 path) so VoiceLoopController._vad_loop
can handle both paths with the same get_chunk() interface.

Key design decisions:
- ONE arecord process stays alive for the entire voice_loop session.
  No kill/restart between turns — eliminates the 3-process-per-turn pattern.
- PULSE_SOURCE env var: resolved at start() from Config card_name via
  `pactl list short sources`. Without it, arecord picks the wrong PipeWire
  default (e.g. Jetson APE instead of WebCamera).
- Mute gate: when voice_loop.muted_by_tts=True, chunks are NOT put to the
  consumer queue but the process keeps running (no buffer reset, no latency
  spike on unmute). Same as MicReader._drain_loop.
- Barge-in: every chunk pushed to _barge_in_q regardless of mute so OWW
  can detect interrupt during TTS. Same as MicReader._drain_loop.
- Audio level events: emitted every Nth frame regardless of mute (B-1 rule
  from MicReader). Same payload format so UI VU-meter is always live.
- PipeWire quantum: PipeWire delivers smaller frames than PulseAudio
  (e.g. 160 bytes / 5 ms vs 320 bytes / 20 ms). _read_exact() accumulates
  fragments until a full VAD frame is available (same fix as _run_local).
"""

from __future__ import annotations

import asyncio
import audioop
import math
import os
import queue as _queue_module
import subprocess
import threading
import time
from typing import Any, Callable, Optional

import numpy as np

from adam.mic_reader import _build_log_band_table


_QUEUE_MAX_CONSUMER = 50
_QUEUE_MAX_FRAME = 2048  # same headroom as MicReader (covers 22-s mute window)


class LocalMicReader:
    """Single-stream local PipeWire/PulseAudio mic producer.

    Lifecycle:
        lmr = LocalMicReader(audio_cfg, event_log)
        lmr.attach_voice_loop(voice_loop)
        await lmr.start()
        chunk = await lmr.get_chunk(timeout=1.0)
        await lmr.stop()
    """

    def __init__(
        self,
        audio_cfg: dict[str, Any],
        event_log: Any,
    ) -> None:
        # Audio format
        self._sample_rate = int(audio_cfg.get("sample_rate", 16000))
        self._channels = int(audio_cfg.get("channels", 1))
        self._frame_ms = int(audio_cfg.get("frame_ms", 20))
        self._normalize_factor = int(audio_cfg.get("normalize_factor", 8000))

        # frame_bytes: mono 16-bit PCM per VAD frame (matches MicReader formula).
        self._frame_bytes = max(2, int(self._sample_rate * 2 * self._frame_ms / 1000))

        # Spectrum / audio_level parameters (same keys as MicReader for hot-reload parity)
        self._spec_n_bands = int(audio_cfg.get("spectrum_bands", 24))
        self._spec_min_hz = float(audio_cfg.get("spectrum_min_hz", 80.0))
        self._spec_max_hz = float(audio_cfg.get("spectrum_max_hz", 8000.0))
        self._spec_floor_db = float(audio_cfg.get("spectrum_floor_db", -60.0))
        self._spec_ceiling_db = float(audio_cfg.get("spectrum_ceiling_db", 0.0))
        self._spec_cadence_hz = float(audio_cfg.get("spectrum_cadence_hz", 25.0))
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
        frame_hz = 1000.0 / max(1, self._frame_ms)
        self._audio_level_emit_every_n = max(
            1, int(round(frame_hz / max(1e-6, self._spec_cadence_hz)))
        )
        self._level_tick: int = 0

        # event_log must be set before _find_pulse_source so _emit works during init
        self._event_log = event_log

        # PULSE_SOURCE: find PipeWire source by card_name, with retry for cold-start boot races
        card_name = audio_cfg.get("input_gain", {}).get("card_name", "")
        self._card_name: str = card_name  # kept for hotplug re-resolution on each reconnect
        self._pulse_source_retries = int(audio_cfg.get("pulse_source_retries", 3))
        self._pulse_source_retry_delay_sec = float(audio_cfg.get("pulse_source_retry_delay_sec", 1.0))
        self._pulse_source: str | None = None
        if card_name:
            self._pulse_source = self._find_pulse_source(card_name)

        # Silence watchdog: restart arecord after this many consecutive near-zero frames.
        # Catches the case where PULSE_SOURCE resolves to a fallback (monitor/disconnected
        # device) that silently returns zeros instead of failing — so the reconnect loop
        # never fires.  Config key: mic_silence_watchdog_sec (default 12s).
        _watchdog_sec = float(audio_cfg.get("mic_silence_watchdog_sec", 12.0))
        frames_per_sec = 1000.0 / max(1, self._frame_ms)
        self._silence_watchdog_frames: int = max(50, int(_watchdog_sec * frames_per_sec))
        self._silence_frames: int = 0

        # Consumer asyncio queue (voice_loop reads via get_chunk)
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=_QUEUE_MAX_CONSUMER)

        self._voice_loop: Any | None = None
        self._running = False
        self._process: subprocess.Popen | None = None
        self._drain_task: asyncio.Task | None = None

    # ── Public interface ───────────────────────────────────────────────

    @property
    def frame_bytes(self) -> int:
        return self._frame_bytes

    def attach_voice_loop(self, voice_loop: Any) -> None:
        self._voice_loop = voice_loop

    async def start(self) -> None:
        self._running = True
        self._drain_task = asyncio.create_task(
            self._open_drain_reconnect_loop(), name="adam_local_mic_drain"
        )

    async def stop(self) -> None:
        self._running = False
        if self._drain_task is not None and not self._drain_task.done():
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
        self._drain_task = None
        self._kill_process()

    async def get_chunk(self, timeout: float = 1.0) -> bytes | None:
        """Pull the next PCM frame.  Returns None on timeout (queue starved)."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ── Internal: arecord process management ──────────────────────────

    def _find_pulse_source(self, card_name: str, max_retries: int | None = None) -> str | None:
        """Find a PipeWire/PulseAudio source whose name contains card_name.

        Retries up to max_retries (default: self._pulse_source_retries) times with
        a fixed delay between attempts.  Pass max_retries=1 for reconnect-time probes
        where the outer reconnect loop provides the retry cadence; use the default
        (3 retries + sleep) only at cold-start where the boot race can be long.
        """
        retries = self._pulse_source_retries if max_retries is None else max_retries
        for attempt in range(retries):
            try:
                result = subprocess.run(
                    ["pactl", "list", "short", "sources"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and card_name.lower() in parts[1].lower():
                        self._emit("local_mic_pulse_source_resolved", {
                            "source": parts[1], "attempt": attempt,
                        })
                        return parts[1]
            except Exception as exc:
                self._emit("local_mic_pulse_source_error", {"error": str(exc), "attempt": attempt})
            if attempt < retries - 1:
                time.sleep(self._pulse_source_retry_delay_sec)
        self._emit("local_mic_pulse_source_unresolved", {
            "attempts": retries, "card_name": card_name,
        })
        return None

    def _start_process(self) -> subprocess.Popen:
        env = os.environ.copy()
        if self._pulse_source:
            env["PULSE_SOURCE"] = self._pulse_source
        # Request 20ms PulseAudio capture latency so the PipeWire-PulseAudio
        # bridge wakes up every ~20ms instead of the default ~100-300ms.
        env.setdefault("PULSE_LATENCY_MSEC", "20")
        cmd = [
            "arecord", "-q",
            "-D", "pulse",
            "-f", "S16_LE",
            "-r", str(self._sample_rate),
            "-c", str(self._channels),
            "-t", "raw",
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def _kill_process(self) -> None:
        proc = self._process
        self._process = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # ── Internal: reader thread (subprocess → threading.Queue) ────────

    def _reader_thread(
        self,
        read_exact: Callable[[int], bytes],
        out_q: "_queue_module.Queue[bytes | None]",
        stop_ev: threading.Event,
    ) -> None:
        """OS-thread: reads raw PCM from arecord stdout → threading.Queue.

        Decoupled from asyncio so the subprocess never stalls due to event-loop
        scheduling delays (same rationale as MicReader._socket_reader_thread).
        Drop-oldest policy preserves the live audio edge.
        """
        empty_streak = 0
        while not stop_ev.is_set():
            try:
                chunk = read_exact(self._frame_bytes)
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
                try:
                    out_q.get_nowait()
                except _queue_module.Empty:
                    pass
                try:
                    out_q.put_nowait(chunk)
                except Exception:
                    pass

    # ── Internal: asyncio drain loop ──────────────────────────────────

    async def _open_drain_reconnect_loop(self) -> None:
        """Outer open/drain/reconnect loop. Runs until _running goes False."""
        while self._running:
            # Re-resolve PULSE_SOURCE before each attempt so USB hotplug is handled:
            # if the device disappeared and came back, PipeWire creates a new node with
            # the same name — a single probe is enough (outer loop provides retry cadence).
            if self._card_name:
                new_src = self._find_pulse_source(self._card_name, max_retries=3)
                if new_src != self._pulse_source:
                    self._emit("local_mic_pulse_source_changed", {
                        "old": self._pulse_source, "new": new_src,
                    })
                self._pulse_source = new_src

            self._silence_frames = 0  # reset watchdog on each new connection attempt

            try:
                self._process = self._start_process()
                stdout = self._process.stdout
                if stdout is None:
                    raise RuntimeError("arecord stdout unavailable")
                self._emit("local_mic_stream_active", {
                    "pulse_source": self._pulse_source,
                    "device": "pulse",
                })

                _read_exact = self._make_read_exact(stdout.read)
                _frame_q: "_queue_module.Queue[bytes | None]" = _queue_module.Queue(
                    maxsize=_QUEUE_MAX_FRAME
                )
                _stop_ev = threading.Event()
                _reader = threading.Thread(
                    target=self._reader_thread,
                    args=(_read_exact, _frame_q, _stop_ev),
                    daemon=True,
                    name="adam_local_mic_reader",
                )
                _reader.start()
                try:
                    await self._drain_inner(_frame_q)
                finally:
                    _stop_ev.set()
                    _reader.join(timeout=2.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._emit("local_mic_error", {"error": str(exc)})
            finally:
                self._kill_process()

            if self._running:
                await asyncio.sleep(2.0)

    async def _drain_inner(
        self, frame_q: "_queue_module.Queue[bytes | None]"
    ) -> None:
        """Per-chunk consumer loop.  Mirrors MicReader._drain_loop logic:

        1. Read chunk from threading.Queue.
        2. Emit audio_level (ALWAYS, regardless of mute).
        3. Push to barge-in queue (ALWAYS, regardless of mute).
        4. Mute gate: skip consumer queue put while voice_loop.muted_by_tts.
        5. Push to consumer queue (drop-oldest).
        """
        while self._running:
            try:
                chunk = await asyncio.to_thread(frame_q.get, True, 0.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                continue

            if chunk is None:
                raise RuntimeError("arecord EOF")
            if len(chunk) < self._frame_bytes:
                continue

            # Silence watchdog: cheap per-frame RMS (2 bytes per sample, signed 16-bit).
            # If arecord falls back to a monitor/disconnected source, it returns true zeros
            # indefinitely rather than failing — this catches that case and forces a restart
            # so _open_drain_reconnect_loop can re-probe the correct PULSE_SOURCE.
            rms = audioop.rms(chunk, 2)
            if rms < 10:
                self._silence_frames += 1
                if self._silence_frames >= self._silence_watchdog_frames:
                    raise RuntimeError(
                        f"silence watchdog triggered after {self._silence_frames} frames "
                        f"(~{self._silence_frames * self._frame_ms / 1000:.0f}s of silence) — "
                        "re-probing PULSE_SOURCE"
                    )
            else:
                self._silence_frames = 0

            # Always emit audio level (B-1: even when muted); pass pre-computed rms
            self._level_tick += 1
            if self._level_tick >= self._audio_level_emit_every_n:
                self._emit_audio_level(chunk, rms=rms)
                self._level_tick = 0

            # Always feed barge-in queue (OWW during TTS)
            _bq = getattr(self._voice_loop, "_barge_in_q", None) if self._voice_loop else None
            if _bq is not None:
                try:
                    _bq.put_nowait(chunk)
                except Exception:
                    try:
                        _bq.get_nowait()
                    except Exception:
                        pass
                    try:
                        _bq.put_nowait(chunk)
                    except Exception:
                        pass

            # Mute gate: skip consumer queue when TTS is playing
            if self._voice_loop is not None and getattr(self._voice_loop, "muted_by_tts", False):
                continue

            # Push to consumer queue (drop-oldest on overflow)
            try:
                self._queue.put_nowait(chunk)
            except asyncio.QueueFull:
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._queue.put_nowait(chunk)
                except Exception:
                    pass

    # ── Internal: helpers ─────────────────────────────────────────────

    @staticmethod
    def _make_read_exact(raw_read: Callable[[int], bytes]) -> Callable[[int], bytes]:
        """PipeWire delivers audio in smaller quanta than PulseAudio (e.g.
        5 ms / 160 bytes instead of 20 ms / 320 bytes).  Accumulate
        fragments until a full VAD frame is available — same fix as
        _run_local() in Orchestrator."""
        def _read_exact(n: int) -> bytes:
            buf = raw_read(n)
            while buf and len(buf) < n:
                tail = raw_read(n - len(buf))
                if not tail:
                    return buf
                buf += tail
            return buf
        return _read_exact

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            self._event_log.append(event_type, payload)
        except Exception:
            pass

    def _emit_audio_level(self, mono_chunk: bytes, rms: int | None = None) -> None:
        if rms is None:
            rms = audioop.rms(mono_chunk, 2)
        norm = round(min(1.0, (rms / max(1, self._normalize_factor)) ** 0.5), 3)
        payload: dict[str, Any] = {
            "level": norm,
            "channels": 1,
            "source": "local",
        }
        if self._voice_loop is not None:
            utt_id = getattr(self._voice_loop, "_utterance_id", "") or ""
            if utt_id:
                payload["utterance_id"] = utt_id
            vad_state = getattr(self._voice_loop, "vad_state", None)
            if vad_state:
                payload["state"] = vad_state
        bands = self._compute_bands(mono_chunk)
        if bands is not None:
            payload["bands"] = bands
        self._emit("audio_level", payload)

    def _compute_bands(self, mono_chunk: bytes) -> list[float] | None:
        n = self._spec_n_fft
        if len(mono_chunk) < n * 2:
            return None
        try:
            samples = np.frombuffer(mono_chunk[:n * 2], dtype=np.int16).astype(np.float32)
            windowed = samples * self._spec_hann
            spectrum = np.abs(np.fft.rfft(windowed))
            ref = self._spec_mag_ref
            result: list[float] = []
            for lo, hi in self._spec_band_table:
                band_mag = float(spectrum[lo:hi + 1].sum())
                if band_mag <= 0.0 or ref <= 0.0:
                    result.append(0.0)
                    continue
                db = 20.0 * math.log10(band_mag / ref)
                norm = (db - self._spec_floor_db) / max(
                    1e-6, self._spec_ceiling_db - self._spec_floor_db
                )
                result.append(round(max(0.0, min(1.0, norm)), 3))
            return result
        except Exception:
            return None
