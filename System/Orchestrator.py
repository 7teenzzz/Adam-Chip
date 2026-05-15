#!/usr/bin/env python3
from __future__ import annotations

import audioop
import json
import os
import re
import shutil
import sys
import asyncio
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
import urllib.request

# v2ray (port 10808) on this Jetson hijacks LAN HTTP via env proxies. The default
# urllib opener honours those env vars and routes ESP32 traffic through xray,
# which then leaks half-open sockets back to ESP32:81. Each leaked socket eats
# one of the firmware's 4 max_open_sockets slots → ESP32 stops accepting.
# Use an opener with an empty ProxyHandler to talk to ESP32 directly.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
from typing import Any, Callable
from uuid import uuid4

try:
    from fastapi import Body, FastAPI, HTTPException, Query, Request
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover - exercised only on missing runtime deps.
    raise SystemExit(
        "FastAPI is required for the orchestrator. Install with: "
        "python3 -m pip install -r System/requirements.txt"
    ) from exc

from adam.action import ActionLayer
from adam.api_runtime import RuntimeDeps, build_router, _load_calibration_profile
from adam.config import Settings
from adam.device import MCUClient
from adam.echoes_gate import EchoGate
from adam.episodic import SessionAccumulator, should_record
from adam.events import EventLog, utc_now
from adam.camera import CameraReader, SceneDescriptionBuffer
from adam.inference import WhisperASRClient, SceneCache, TTSClient, VLMClient, create_llm_client, create_asr_client
from adam.media import MediaHealth
from adam.memory import EpisodicMemory, MemoryStore
from adam.memory_metrics import MemoryMetrics
from adam.metrics import MetricsLog
from adam.power import PowerGate
from adam.prompt import PromptBuilder, LeadingNoiseFilter, sanitize_reply
from adam.config import PROJECT_ROOT
from adam.sound import play_local_sound
from adam.system import docker_health, gate_summary, all_services_status, service_action, ADAM_SERVICES
from adam.tuning import TuningStore, get_store as _get_tuning_store
from adam.ui import agent_page, dash_page, debug_page
from adam.wake_word import create_engine as _create_wake_engine
from adam.webrtc_vad import WebRtcVadWrapper



settings = Settings.load()
event_log = EventLog(settings.data_dir)
metrics_log = MetricsLog(settings.data_dir)
memory = MemoryStore(settings.data_dir)
episodic_memory = EpisodicMemory(settings.data_dir)
memory_metrics = MemoryMetrics(Path(settings.data_dir) / "memory" / "metrics.jsonl")
tuning_store: TuningStore = _get_tuning_store()
power_gate = PowerGate(settings.section("power"))
media_health = MediaHealth(settings.section("media"))
mcu = MCUClient(settings.section("mcu"))
llm = create_llm_client(settings.section("services").get("llm", {}))
asr = create_asr_client(settings.section("services").get("asr", {}))
vlm = VLMClient(settings.section("services").get("vlm", {}))
tts = TTSClient(
    settings.section("services").get("tts", {}),
    mcu_speaker_url=mcu.speaker_endpoint_url(),
)
# Surface barge-in attempts that cannot stop ESP32 audio (PCM5102A has no stop
# endpoint today). Lets operators see why interrupt didn't take effect.
tts._barge_in_event_emitter = lambda t, p: event_log.append(t, p)
scene_cache = SceneCache()
_media_cfg = settings.section("media")
_video_cfg = dict(_media_cfg.get("video", {}))
if not _video_cfg.get("esp_mjpeg_url"):
    from urllib.parse import urlparse as _urlparse
    _mcu_base = settings.section("mcu").get("base_url", "http://192.168.0.171").rstrip("/")
    _parsed = _urlparse(_mcu_base)
    _video_cfg["esp_mjpeg_url"] = f"{_parsed.scheme}://{_parsed.hostname}:81/stream"
camera_reader = CameraReader(_video_cfg, on_event=lambda t, p: event_log.append(t, p))
scene_buffer = SceneDescriptionBuffer(int(_media_cfg.get("scene_buffer_maxlen", 8)))
prompt_builder = PromptBuilder(
    settings.persona_paths,
    int(settings.section("agent").get("history_turns", 8)),
)
action_layer = ActionLayer(settings.section("mcu"), settings.section("safety"))

_about_dir = PROJECT_ROOT / "Agent Adam Chip" / "About"
echoes_gate = EchoGate(
    pool_path=_about_dir / "Echoes.md",
    memory=episodic_memory,
    pool="echoes",
)
chinese_gate = EchoGate(
    pool_path=_about_dir / "Chinese_lines.md",
    memory=episodic_memory,
    pool="chinese",
)

runtime_state: dict[str, Any] = {
    "mode": settings.mode,
    "speaking": False,
    "thinking": False,
    "last_error": None,
    "success_sound_played": False,
    "interrupt_tts": False,     # set True by barge-in to stop active TTS playback
    "last_tts_text": "",        # last TTS reply text (lowercase) for self-echo detection
    "last_tts_finished_at": 0.0,  # perf_counter() when last TTS playback ended
    "recent_tts_history": [],   # rolling buffer of {text, finished_at} for echo filtering
}


turn_lock = asyncio.Lock()
session_lock = asyncio.Lock()
session_state: dict[str, Any] = {
    "accumulator": None,  # type: ignore[assignment]
    "last_turn_at": 0.0,
    "last_face_seen_at": 0.0,
}

# Ring-buffer полных промтов для UI диагностики.
from collections import deque  # noqa: E402

_PROMPT_TRACE_MAX: int = int(settings.section("agent").get("prompt_trace_max", 50))
prompt_trace: deque[dict[str, Any]] = deque(maxlen=_PROMPT_TRACE_MAX)


# Pre-compiled sentence boundary regex for streaming LLM→TTS pipeline.
# Matches .!?。！？ and em-dash (—, common in Russian) followed by whitespace.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？—])\s+")


def _apply_wav_speed(wav: bytes, speed: float) -> bytes:
    """Rewrite WAV header to play `speed`x faster. Pitch shifts up proportionally
    (sample-rate trick — no resampling, near-zero CPU). For Russian male voice
    at 1.25x the pitch shift is mild and still natural; at 1.5x it gets chipmunky.
    """
    if not wav or len(wav) < 44 or speed is None:
        return wav
    if abs(speed - 1.0) < 0.01:
        return wav
    if wav[0:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return wav
    import struct
    try:
        orig_sr = struct.unpack("<I", wav[24:28])[0]
        orig_br = struct.unpack("<I", wav[28:32])[0]
        new_sr = max(8000, min(192000, int(round(orig_sr * speed))))
        new_br = int(round(orig_br * speed))
        out = bytearray(wav)
        out[24:28] = struct.pack("<I", new_sr)
        out[28:32] = struct.pack("<I", new_br)
        return bytes(out)
    except Exception:
        return wav

_NAME_INTRO_RE = re.compile(
    r"\b(?:меня\s+зовут|я\s+(?:это\s+)?|зовут\s+меня)\s+"
    r"([А-ЯЁA-Z][а-яёa-z\-]{1,30}(?:\s+[А-ЯЁA-Z][а-яёa-z\-]{1,30})?)\b",
    flags=re.UNICODE,
)

_BLACKLIST = {"вижу", "слышу", "хочу", "знаю", "помню", "там", "тут", "здесь"}


def _extract_visitor_name(transcript: str) -> str | None:
    """Returns full name (first + last/patronymic) or None.

    Single-word names are rejected — identity verification requires two parts.
    """
    m = _NAME_INTRO_RE.search(transcript)
    if not m:
        return None
    full_name = m.group(1).strip()
    parts = full_name.split()
    if len(parts) < 2:
        return None
    if any(len(p) < 2 or p.lower() in _BLACKLIST for p in parts):
        return None
    return full_name


def _resolve_mood(scene_text: str, sensors: dict[str, Any]) -> str:
    """Простая эвристика для mood-метки gate-фильтра.

    Возвращает один из: 'neutral' | 'hostile' | 'overload' | 'silence_deep'.
    Расширится в SceneDirector в дальнейших итерациях.
    """
    text = (scene_text or "").lower()
    if "несколько" in text or "много" in text or "толпа" in text or "group" in text:
        return "overload"
    return "neutral"


def _format_recent_episodic(episodes) -> list[str]:
    out: list[str] = []
    for ep in episodes:
        date = ep.ts_end.date().isoformat()
        themes = ", ".join(ep.themes[:3]) if ep.themes else "без явных тем"
        out.append(f"{date} — {themes}")
    return out


async def _commit_session_locked(reason: str) -> None:
    """Закрывает текущую сессию, пишет эпизод если salience прошёл фильтр.

    Должна вызываться при удерживаемом session_lock.
    """
    acc: SessionAccumulator | None = session_state.get("accumulator")  # type: ignore[assignment]
    if acc is None or acc.turn_count == 0:
        session_state["accumulator"] = None
        return
    tuning = tuning_store.current()
    episode = acc.finalize(
        weights=tuning.memory.episodic.weights,
        duration_normalize_seconds=tuning.memory.episodic.duration_normalize_seconds,
    )
    write = should_record(episode, acc, tuning.memory.episodic)
    if write:
        try:
            episodic_memory.commit_episode(episode)
            memory_metrics.record_episode_committed(
                episode.id, episode.salience, triggered_by=reason
            )
            event_log.append(
                "episode_committed",
                {
                    "id": episode.id,
                    "salience": episode.salience,
                    "name": episode.visitor.introduced_name,
                    "themes": episode.themes,
                    "duration_s": episode.duration_s,
                    "reason": reason,
                },
            )
            if episode.salience >= tuning.memory.consolidator.instant_threshold:
                episodic_memory.quick_patch_diary(episode)
        except Exception as exc:
            event_log.append("episode_commit_error", {"error": str(exc), "id": episode.id})
    else:
        event_log.append(
            "episode_skipped",
            {
                "salience": episode.salience,
                "duration_s": episode.duration_s,
                "reason": reason,
            },
        )
    session_state["accumulator"] = None


class VoiceLoopController:
    def __init__(self, audio_config: dict[str, Any], asr_client: WhisperASRClient, mcu: Any = None) -> None:
        self.mic_source = str(audio_config.get("mic_source", "local"))
        self.esp32_mic_profile = str(audio_config.get("esp32_mic_profile", "inmp441_philips32_left"))
        self._mcu = mcu
        self.audio_device = str(audio_config.get("input_device", "hw:0,0"))
        self.capture_device = self._capture_device_for(self.audio_device)
        self.sample_rate = int(audio_config.get("sample_rate", 16000))
        self.channels = int(audio_config.get("channels", 1))
        self.frame_ms = int(audio_config.get("frame_ms", 20))
        self.vad_threshold = int(audio_config.get("vad_threshold", 650))
        self._webrtc_vad = WebRtcVadWrapper(
            aggressiveness=int(audio_config.get("webrtc_vad_aggressiveness", 2))
        )
        self.normalize_factor = float(audio_config.get("normalize_factor", 8000))
        self.min_speech_ms = int(audio_config.get("min_speech_ms", 280))
        self.asr_client = asr_client
        asr_cfg = settings.section("services").get("asr", {})
        self._command_endpointing_ms = int(asr_cfg.get("command_endpointing_ms", 2500))
        self.max_segment_ms          = int(audio_config.get("max_command_segment_ms", 15000))
        self._reply_window_sec       = float(asr_cfg.get("reply_window_sec", 4.0))
        self._reply_absolute_deadline_sec: float = float(asr_cfg.get("reply_absolute_deadline_sec", 12.0))
        # 'standby' returns to listening for next wake word; 'stop' fully stops
        # the voice loop and requires explicit restart.
        self._reply_window_expired_action: str = str(asr_cfg.get("reply_window_expired_action", "standby"))
        self._voice_state: str       = "standby"   # standby | listening | reply
        self._reply_start: float     = 0.0
        self.wake_word_required = bool(asr_cfg.get("wake_word_required", False))
        wake_words = asr_cfg.get("wake_words", []) or []
        # Config may store wake_words as a comma-separated string (e.g. "адам") or a list.
        if isinstance(wake_words, str):
            wake_words = [w.strip() for w in wake_words.split(",") if w.strip()]
        self.wake_words = [str(w).strip().lower() for w in wake_words if str(w).strip()]
        self._wake_re = (
            re.compile(r"\b(?:" + "|".join(re.escape(w) for w in self.wake_words) + r")\b[\s,.:;!?\-]*", re.IGNORECASE)
            if self.wake_words else None
        )
        self._task: asyncio.Task[None] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self.running = False
        self.vad_state = "idle"
        self.last_transcript = ""
        self.last_transcript_at = ""
        self.last_asr_error = ""
        self.muted_by_tts = False
        self.last_wake_skip = ""
        # Local wake word engine (openWakeWord, CPU) — None → no wake word detection
        ww_cfg = settings.section("wake_word") or {}
        self._wake_engine = _create_wake_engine(ww_cfg)
        if self._wake_engine is None and ww_cfg.get("engine", "none") != "none":
            # Model file missing or engine init failed — log a visible warning so operator
            # knows the system is deaf in exhibition mode (wake_word_required=true).
            import logging as _logging
            _logging.getLogger("adam.voice").warning(
                "wake_word engine '%s' returned None — model file missing or init failed. "
                "System will not respond to voice in exhibition mode.",
                ww_cfg.get("engine", "?"),
            )
            event_log.append("wake_engine_missing", {
                "engine": ww_cfg.get("engine"),
                "model_path": ww_cfg.get("model_path"),
                "wake_word_required": self.wake_word_required,
            })
        # 4 × 20ms frames = 80ms chunks for openWakeWord
        self._ww_buf: list[bytes] = []
        self._ww_frames_needed = 4
        self._standby_entry_time: float = 0.0   # set on reply→standby; arms the OWW guard window
        self._STANDBY_GUARD_SEC: float = 0.5    # post-TTS ALSA drain; boot guard not needed (entry_time=0.0 at boot)
        self._wake_detected_at: float = 0.0
        # Fallback default 6.0 is only for missing-config startup; Config.json
        # supplies the authoritative value (3 per reference logic).
        self._wake_silence_timeout_sec: float = float(ww_cfg.get("wake_silence_timeout_sec", 6.0))
        self.esp_mic_fail_threshold: int = int(audio_config.get("esp_mic_fail_threshold", 3))
        self.esp_mic_retry_interval_sec: float = float(audio_config.get("esp_mic_retry_interval_sec", 30.0))
        self._esp_mic_fallback: bool = False
        self._esp_mic_fail_count: int = 0
        self._esp_mic_last_retry: float = 0.0
        # Boot-wait + background retry for ESP mic.
        # Reference logic: every 5s probe ESP /api/status; wait up to 90s before
        # starting voice_loop. If ESP still silent → fallback to local + spawn
        # background retry task (20 × 15s = 5 min) which switches back to ESP
        # on first successful probe. After 20 attempts, stay on local.
        self.esp_boot_wait_max_sec: int = int(audio_config.get("esp_boot_wait_max_sec", 90))
        self.esp_boot_wait_poll_sec: int = int(audio_config.get("esp_boot_wait_poll_sec", 5))
        self.esp_bg_retry_attempts: int = int(audio_config.get("esp_bg_retry_attempts", 20))
        self.esp_bg_retry_interval_sec: int = int(audio_config.get("esp_bg_retry_interval_sec", 15))
        self._esp_retry_task: asyncio.Task[None] | None = None
        self._esp_boot_wait_state: str = "n/a"  # "n/a" | "waiting" | "ready" | "timeout"
        self._raw_is_stereo: bool = False
        self._raw_level_l: float = 0.0
        self._raw_level_r: float = 0.0
        self._utterance_id: str | None = None  # set on wake_word_detected, cleared on standby
        # Fine-grained mic-stream state for the UI badge / status dot. Replaces
        # the inferred "esp32 vs local_fallback" guess that hid the connecting
        # window. Values:
        #   "n/a"          — mic_source != esp32 (local mic is canonical)
        #   "connecting"   — _run_esp32 entered, no WAV header yet
        #   "active"       — WAV header parsed, _vad_loop reading data
        #   "failed"       — last attempt threw; next iteration will retry
        #   "fallback"     — _esp_mic_fallback True; local mic is feeding audio
        self._mic_stream_state: str = "n/a"

    def apply_audio_config(self, audio_cfg: dict[str, Any]) -> list[str]:
        """Apply audio config changes live. Returns list of fields that require loop restart."""
        restart_triggers = {"input_device", "sample_rate", "channels", "frame_ms", "mic_source"}
        needs_restart: list[str] = []
        new_mic_source = str(audio_cfg.get("mic_source", self.mic_source))
        if new_mic_source != self.mic_source:
            self._esp_mic_fallback = False
            # Reset stream-state — n/a is the canonical value when the user
            # switches back to a local mic (no streaming in play).
            self._mic_stream_state = "n/a" if new_mic_source != "esp32" else "connecting"
            self._esp_mic_fail_count = 0
            needs_restart.append("mic_source")
        self.mic_source = new_mic_source
        self.esp32_mic_profile = str(audio_cfg.get("esp32_mic_profile", self.esp32_mic_profile))
        self.vad_threshold = int(audio_cfg.get("vad_threshold", self.vad_threshold))
        self.min_speech_ms = int(audio_cfg.get("min_speech_ms", self.min_speech_ms))
        self.max_segment_ms = int(audio_cfg.get("max_command_segment_ms", self.max_segment_ms))
        new_sr = int(audio_cfg.get("sample_rate", self.sample_rate))
        if new_sr != self.sample_rate:
            self.sample_rate = new_sr
            self.normalize_factor = float(audio_cfg.get("normalize_factor", new_sr / 2))
            needs_restart.append("sample_rate")
        new_ch = int(audio_cfg.get("channels", self.channels))
        if new_ch != self.channels:
            self.channels = new_ch
            needs_restart.append("channels")
        new_frame = int(audio_cfg.get("frame_ms", self.frame_ms))
        if new_frame != self.frame_ms:
            self.frame_ms = new_frame
            needs_restart.append("frame_ms")
        new_dev = str(audio_cfg.get("input_device", self.audio_device))
        if new_dev != self.audio_device:
            self.audio_device = new_dev
            self.capture_device = self._capture_device_for(new_dev)
            needs_restart.append("input_device")
        new_agg = int(audio_cfg.get("webrtc_vad_aggressiveness", self._webrtc_vad.aggressiveness))
        if new_agg != self._webrtc_vad.aggressiveness:
            self._webrtc_vad.aggressiveness = new_agg
        return needs_restart

    @property
    def device_in_use(self) -> bool:
        """True while the audio device is held — either running or in the process of stopping."""
        return self.running or (self._task is not None and not self._task.done())

    def _active_audio_source_label(self) -> str:
        """Canonical short label of the mic feeding `audio_level` events.

        Distinguishes the four runtime situations the UI cares about:
          - 'esp32_stereo'   — INMP441 stereo profile, _vad_loop reading
          - 'esp32_mono'     — INMP441 mono profile, _vad_loop reading
          - 'local_fallback' — _esp_mic_fallback engaged, local mic feeds audio
          - 'local'          — mic_source=local by configuration
        """
        if self.mic_source == "esp32":
            if self._esp_mic_fallback:
                return "local_fallback"
            if self._mic_stream_state == "active":
                return "esp32_stereo" if self._raw_is_stereo else "esp32_mono"
            # Pre-stream-active window — UI should treat audio_level as local
            # until WAV header arrives. _audio_level_monitor is the actual
            # emitter here, but be defensive.
            return "local_fallback"
        return "local"

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "mic_source": self.mic_source,
            "esp32_mic_profile": self.esp32_mic_profile,
            "vad_state": self.vad_state,
            "last_transcript": self.last_transcript,
            "last_transcript_at": self.last_transcript_at,
            "muted_by_tts": self.muted_by_tts,
            "last_asr_error": self.last_asr_error,
            "audio_device": self.audio_device,
            "capture_device": self.capture_device,
            "sample_rate": self.sample_rate,
            "frame_ms": self.frame_ms,
            "wake_word_required": self.wake_word_required,
            "wake_words": self.wake_words,
            "last_wake_skip": self.last_wake_skip,
            "voice_state": self._voice_state,
            "esp_mic_fallback": self._esp_mic_fallback,
            "mic_active_source": "local_fallback" if (self.mic_source == "esp32" and self._esp_mic_fallback) else self.mic_source,
            # Fine-grained mic-stream state for UI badge / status dot.
            # Distinguishes "esp32 connecting" from "esp32 active" so the
            # UI never shows a false-positive INMP441 ✓ during the open
            # window before the WAV header arrives.
            "mic_stream_state": self._mic_stream_state,
            # Boot-wait + background retry telemetry for the UI button.
            # esp_boot_wait_state: n/a → waiting → ready | timeout
            # esp_bg_retry_active: true while 20×15s retry task is alive
            "esp_boot_wait_state": self._esp_boot_wait_state,
            "esp_bg_retry_active": bool(self._esp_retry_task and not self._esp_retry_task.done()),
            # Force-button enabled = user is on local fallback AND mic_source is esp32
            "force_esp_retry_available": self.mic_source == "esp32" and self._esp_mic_fallback,
        }

    def _set_voice_state(self, state: str, reason: str = "") -> None:
        if state != self._voice_state:
            event_log.append("voice_state_change", {
                "from": self._voice_state, "to": state, "reason": reason,
            })
        self._voice_state = state
        if state == "standby":
            self._utterance_id = None

    async def start(self) -> dict[str, Any]:
        if self._task and not self._task.done():
            return {"ok": True, **self.status()}
        self.running = True
        self.last_asr_error = ""
        self._standby_entry_time = time.perf_counter()  # arm OWW guard for first 0.5s after start
        self._task = asyncio.create_task(self._run(), name="adam_voice_loop")
        await asyncio.sleep(0.2)
        if self._task.done():
            self.running = False
            return {"ok": False, **self.status()}
        if self._wake_engine is not None:
            event_log.append("oww_ready", {
                "model_name": getattr(self._wake_engine, "_model_name", None),
                "threshold": getattr(self._wake_engine, "_threshold", None),
                "debounce_hits": getattr(self._wake_engine, "_debounce_hits", None),
                "vad_threshold": getattr(
                    getattr(self._wake_engine, "_oww", None), "vad_threshold", None
                ),
            })
        event_log.append("voice_loop_started", self.status())
        return {"ok": True, **self.status()}

    async def stop(self) -> dict[str, Any]:
        self.running = False
        # Cancel background ESP retry task too so it doesn't survive into the next start()
        if self._esp_retry_task and not self._esp_retry_task.done():
            self._esp_retry_task.cancel()
            try:
                await self._esp_retry_task
            except asyncio.CancelledError:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._voice_state = "standby"
        self._standby_entry_time = 0.0   # disarm guard so a fresh start never blocks OWW
        self._ww_buf.clear()
        if self._wake_engine is not None:
            self._wake_engine.close()
        self._stop_process()
        self.vad_state = "idle"
        event_log.append("voice_loop_stopped", self.status())
        return {"ok": True, **self.status()}

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def _run(self) -> None:
        if self.mic_source == "esp32":
            # Boot-wait phase: probe ESP /api/status every 5s for up to 90s
            # before starting voice_loop. ESP должен быть primary mic-source —
            # даём ему время подняться вместо мгновенного fallback на local.
            esp_ready = await self._wait_for_esp_ready(
                max_seconds=self.esp_boot_wait_max_sec,
                poll_interval=self.esp_boot_wait_poll_sec,
            )
            if esp_ready:
                # ESP отвечает — запускаем _run_esp32 как обычно
                frame_bytes = max(2, int(self.sample_rate * 2 * self.frame_ms / 1000))
                await self._run_esp32(frame_bytes)
            else:
                # ESP молчит 90 сек → fallback на local + background retry task
                self._esp_mic_fallback = True
                self._mic_stream_state = "fallback"
                self._esp_boot_wait_state = "timeout"
                event_log.append("voice_loop_esp_boot_timeout", {
                    "waited_sec": self.esp_boot_wait_max_sec,
                    "background_retry_attempts": self.esp_bg_retry_attempts,
                    "background_retry_interval_sec": self.esp_bg_retry_interval_sec,
                })
                self._start_background_esp_retry()
                fb_frame_bytes = max(2, int(self.sample_rate * self.channels * 2 * self.frame_ms / 1000))
                await self._run_local(fb_frame_bytes)
        else:
            frame_bytes = max(2, int(self.sample_rate * self.channels * 2 * self.frame_ms / 1000))
            await self._run_local(frame_bytes)

    async def _wait_for_esp_ready(self, max_seconds: int = 90, poll_interval: int = 5) -> bool:
        """Probe ESP /api/status every poll_interval seconds for up to max_seconds.
        Returns True as soon as ESP responds, False if timeout.
        Used at boot — Adam должен по умолчанию использовать ESP-микрофоны,
        давая ESP время подняться перед fallback на local."""
        if self._mcu is None:
            return False
        attempts = max(1, max_seconds // max(1, poll_interval))
        self._esp_boot_wait_state = "waiting"
        self._mic_stream_state = "connecting"
        event_log.append("voice_loop_esp_boot_wait_start", {
            "max_seconds": max_seconds, "poll_interval_sec": poll_interval, "attempts": attempts,
        })
        for i in range(attempts):
            if not self.running:
                return False
            try:
                result = await self._mcu.request("GET", "/api/status")
                if result.ok:
                    elapsed = (i + 1) * poll_interval
                    self._esp_boot_wait_state = "ready"
                    event_log.append("voice_loop_esp_boot_wait_ok", {
                        "attempts": i + 1, "elapsed_sec": elapsed,
                    })
                    return True
            except Exception as exc:
                event_log.append("voice_loop_esp_boot_wait_probe_error", {
                    "attempt": i + 1, "error": str(exc)[:120],
                })
            if i < attempts - 1:
                await asyncio.sleep(poll_interval)
        return False

    def _start_background_esp_retry(self) -> None:
        """Spawn background task: 20 × 15s polling ESP. On first success → restart voice_loop with ESP."""
        if self._esp_retry_task and not self._esp_retry_task.done():
            return
        self._esp_retry_task = asyncio.create_task(
            self._background_esp_retry(), name="adam_esp_bg_retry"
        )

    async def _background_esp_retry(self) -> None:
        """20 attempts × 15s polling. On success → switch back to ESP via restart()."""
        max_attempts = self.esp_bg_retry_attempts
        interval = self.esp_bg_retry_interval_sec
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval)
            if not self.running:
                return
            if not self._esp_mic_fallback:
                # Someone (force-button) already restored ESP — stop the bg loop
                return
            if self._mcu is None:
                continue
            try:
                result = await self._mcu.request("GET", "/api/status")
                if result.ok:
                    event_log.append("voice_loop_esp_bg_retry_success", {
                        "attempt": attempt, "max": max_attempts,
                    })
                    self._esp_mic_fallback = False
                    self._mic_stream_state = "connecting"
                    if self.running:
                        asyncio.ensure_future(self.restart())
                    return
            except Exception as exc:
                event_log.append("voice_loop_esp_bg_retry_fail", {
                    "attempt": attempt, "max": max_attempts, "error": str(exc)[:120],
                })
                continue
            event_log.append("voice_loop_esp_bg_retry_fail", {
                "attempt": attempt, "max": max_attempts,
            })
        event_log.append("voice_loop_esp_bg_retry_exhausted", {"attempts": max_attempts})

    async def force_esp_retry(self) -> dict[str, Any]:
        """Single-shot retry triggered from UI button.
        Active only when in local fallback. Probes ESP once; if alive — switches voice_loop to ESP."""
        if self.mic_source != "esp32":
            return {"ok": False, "error": "mic_source is not esp32"}
        if not self._esp_mic_fallback:
            return {"ok": False, "error": "not in fallback — ESP already active or never tried"}
        if self._mcu is None:
            return {"ok": False, "error": "mcu client not configured"}
        try:
            result = await self._mcu.request("GET", "/api/status")
        except Exception as exc:
            event_log.append("voice_loop_force_esp_retry_error", {"error": str(exc)[:120]})
            return {"ok": False, "error": f"ESP probe raised: {exc}"}
        if not result.ok:
            event_log.append("voice_loop_force_esp_retry_fail", {
                "status": result.status, "error": result.error,
            })
            return {"ok": False, "error": f"ESP not responding: {result.error or result.status}"}
        # ESP отвечает → restore + restart voice_loop с ESP
        event_log.append("voice_loop_force_esp_retry_success", {})
        self._esp_mic_fallback = False
        self._mic_stream_state = "connecting"
        # Cancel running background retry to avoid double-restart race
        if self._esp_retry_task and not self._esp_retry_task.done():
            self._esp_retry_task.cancel()
        if self.running:
            asyncio.ensure_future(self.restart())
        return {"ok": True, "message": "ESP responded — switching voice_loop"}

    async def _run_local(self, frame_bytes: int) -> None:
        _delays = [1.0, 2.0, 4.0]
        for attempt, delay in enumerate([0.0] + _delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                self._process = self._start_arecord()
                stdout = self._process.stdout
                if stdout is None:
                    raise RuntimeError("arecord stdout unavailable")
                await self._vad_loop(stdout.read, frame_bytes)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.vad_state = "error"
                self.last_asr_error = str(exc)
                runtime_state["last_error"] = f"voice_loop:{exc}"
                event_log.append("voice_loop_error", {
                    "error": str(exc),
                    "attempt": attempt + 1,
                    "retrying": attempt < len(_delays),
                })
            finally:
                self._stop_process()
        self.running = False
        event_log.append("voice_loop_stopped", self.status())

    async def _run_esp32(self, frame_bytes: int) -> None:
        if self._mcu is None:
            raise RuntimeError("mic_source=esp32 requires mcu client — not configured")
        url = self._mcu.mic_stream_url()
        _session_fail_count = 0
        _STREAM_STABLE_THRESHOLD_SEC = 30.0
        while self.running:
            profile = self.esp32_mic_profile
            is_stereo = profile.endswith("stereo")
            event_log.append("esp32_mic_profile_applied", {"profile": profile})
            await self._mcu.request("POST", "/api/audio", {"profile": profile})
            _stream_open_t = 0.0
            resp = None
            # Mark "connecting" before the long-poll urlopen so the UI shows
            # "ESP32 подключается" instead of the previous false-positive
            # "ESP32 ✓" during the 0-30 s window before WAV header arrives.
            self._mic_stream_state = "connecting"
            try:
                # Use no-proxy opener — env HTTP proxy (v2ray) hijacks LAN
                # connections to ESP32 and leaks sockets on long-poll mic stream
                # disconnects. _NO_PROXY_OPENER guarantees direct TCP to ESP32:81.
                resp = await asyncio.to_thread(_NO_PROXY_OPENER.open, url, None, 30)
                event_log.append("esp32_mic_stream_opened", {"url": url, "profile": profile})
                header = await asyncio.to_thread(resp.read, 44)
                if len(header) < 44:
                    raise RuntimeError(f"ESP32 WAV header truncated ({len(header)}/44 bytes)")
                event_log.append("esp32_mic_wav_header", {"bytes": len(header), "is_stereo": is_stereo})
                if is_stereo:
                    self._raw_is_stereo = True
                    read_fn = self._make_stereo_reader(resp.read)
                else:
                    self._raw_is_stereo = False
                    read_fn = resp.read
                _stream_open_t = time.perf_counter()
                # WAV header received → stream is truly live. Flip the state
                # AFTER read_fn is bound so the first audio_level.source label
                # already reflects "active".
                self._mic_stream_state = "active"
                event_log.append("esp32_mic_stream_active", {
                    "profile": profile, "is_stereo": is_stereo,
                })
                await self._vad_loop(read_fn, frame_bytes)
            except asyncio.CancelledError:
                # Closing resp on cancel is critical: ESP32:81 has only 4 socket
                # slots — leaked half-open sockets there block reconnect.
                if resp is not None:
                    try: resp.close()
                    except Exception: pass
                raise
            except Exception as exc:
                if resp is not None:
                    try: resp.close()
                    except Exception: pass
                self._raw_is_stereo = False
                self._mic_stream_state = "failed"
                self.vad_state = "error"
                self.last_asr_error = str(exc)
                # Reset failure counter only if the stream stayed alive long enough
                # to count as a proven-stable session. Without this guard, every
                # urlopen success resets the counter and the fallback threshold
                # can never be reached under repeated short-lived stream failures.
                stream_alive_sec = (time.perf_counter() - _stream_open_t) if _stream_open_t else 0.0
                if stream_alive_sec > _STREAM_STABLE_THRESHOLD_SEC:
                    _session_fail_count = 0
                    self._esp_mic_fail_count = 0
                event_log.append("voice_loop_error", {
                    "stage": "esp32_mic", "error": str(exc),
                    "stream_alive_sec": round(stream_alive_sec, 1),
                })
                _session_fail_count += 1
                self._esp_mic_fail_count += 1
                if _session_fail_count >= self.esp_mic_fail_threshold:
                    self._esp_mic_fallback = True
                    self._mic_stream_state = "fallback"
                    self._esp_mic_last_retry = time.perf_counter()
                    event_log.append("esp32_mic_fallback_start", {
                        "fail_count": _session_fail_count, "error": str(exc),
                    })
                    break
                if self.running:
                    await asyncio.sleep(2.0)
            finally:
                # Catch the normal-exit path too (vad_loop returned without
                # exception, e.g. self.running flipped to False during shutdown).
                # Without this the underlying TCP socket leaks until GC, which
                # under v2ray's hood means an extra ESP32 socket slot stays held.
                if resp is not None:
                    try: resp.close()
                    except Exception: pass
        if self._esp_mic_fallback and self.running:
            fb_frame_bytes = max(2, int(self.sample_rate * self.channels * 2 * self.frame_ms / 1000))
            await self._run_local(fb_frame_bytes)
        self.running = False
        self.vad_state = "idle"

    async def _drain_esp32_backlog(
        self,
        read_fn: Callable[[int], bytes],
        frame_bytes: int,
        mute_start: float,
    ) -> int:
        """Read and discard ESP32 stream frames buffered during the mute window.

        ESP32 keeps writing PCM into the open TCP stream while the orchestrator is
        busy (transcribe → LLM → TTS). On unmute, the next read returns those
        accumulated frames, which include acoustic self-echo of the agent's own
        TTS. Discarding ~mute_duration_ms (+200 ms jitter) of bytes realigns the
        reader with live audio.

        Reads are coalesced byte-wise (HTTPResponse.read may return short reads
        mid-stream) to keep frame alignment intact for downstream WebRTC VAD.
        A wall-clock deadline of 2× expected drain prevents an indefinite hang
        if the underlying socket died during the long mute.
        """
        mute_duration_ms = (time.perf_counter() - mute_start) * 1000.0 + 200.0
        bytes_to_drain = max(0, int(mute_duration_ms / self.frame_ms)) * frame_bytes
        if bytes_to_drain <= 0:
            return 0
        deadline = time.perf_counter() + (mute_duration_ms / 1000.0) * 2.0
        drained_bytes = 0
        while drained_bytes < bytes_to_drain:
            if time.perf_counter() > deadline:
                event_log.append("esp32_mic_drain_timeout", {
                    "drained_bytes": drained_bytes,
                    "target_bytes": bytes_to_drain,
                })
                break
            remaining = bytes_to_drain - drained_bytes
            chunk = await asyncio.to_thread(read_fn, remaining)
            if not chunk:
                break
            drained_bytes += len(chunk)
        return drained_bytes // frame_bytes

    def _make_stereo_reader(self, read_fn: Callable[[int], bytes]) -> Callable[[int], bytes]:
        """Wraps a stereo PCM read_fn to return downmixed mono (L+R)/2.

        Also tracks per-channel RMS in self._raw_level_l / _raw_level_r for UI diagnostics.
        read_fn is expected to produce interleaved 16-bit stereo (2× the mono byte count).
        Partial reads return empty bytes to trigger reconnect in _run_esp32.
        """
        normalize = self.normalize_factor
        def _read(n: int) -> bytes:
            raw = read_fn(n * 2)
            if not raw or len(raw) < n * 2:
                return b""
            rms_l = audioop.rms(audioop.tomono(raw, 2, 1.0, 0.0), 2)
            rms_r = audioop.rms(audioop.tomono(raw, 2, 0.0, 1.0), 2)
            self._raw_level_l = round(min(1.0, (rms_l / normalize) ** 0.5), 3)
            self._raw_level_r = round(min(1.0, (rms_r / normalize) ** 0.5), 3)
            return audioop.tomono(raw, 2, 0.5, 0.5)
        return _read

    async def _vad_loop(self, read_fn: Callable[[int], bytes], frame_bytes: int) -> None:
        """VAD + endpointing + ASR dispatch. read_fn is a blocking callable, always called via to_thread."""
        speech_frames: list[bytes] = []
        speech_ms = 0
        silence_ms = 0
        level_tick = 0
        _reader = [read_fn]  # mutable ref — updated when arecord restarts during transcription
        _empty_streak = 0
        _was_endpointing = False
        try:
            while self.running:
                chunk = await asyncio.to_thread(_reader[0], frame_bytes)
                if not chunk:
                    _empty_streak += 1
                    if self.mic_source == "esp32":
                        event_log.append("esp32_mic_empty_read", {"streak": _empty_streak})
                    if _empty_streak >= 3:
                        raise RuntimeError("audio source ended: 3 consecutive empty reads")
                    await asyncio.sleep(0.005)
                    continue
                _empty_streak = 0

                _rms = audioop.rms(chunk, 2)
                voiced = self._webrtc_vad.predict(chunk, self.sample_rate) >= 0.5
                level_tick += 1
                if level_tick >= 5:
                    level_tick = 0
                    norm = round(min(1.0, (_rms / self.normalize_factor) ** 0.5), 3)
                    payload: dict[str, Any] = {"level": norm, "state": self._voice_state}
                    if self._raw_is_stereo:
                        payload["channels"] = 2
                        payload["level_l"] = self._raw_level_l
                        payload["level_r"] = self._raw_level_r
                    if self._utterance_id:
                        payload["utterance_id"] = self._utterance_id
                    # T17 fix #6 — tag every audio_level with its actual mic
                    # source so the UI badge/colour can stay in sync without
                    # guessing from channels-count alone.
                    payload["source"] = self._active_audio_source_label()
                    event_log.append("audio_level", payload)

                # ── STANDBY: only OWW scanning, no VAD accumulation ─────────────
                if self._voice_state == "standby":
                    if self._wake_engine is not None:
                        # Guard window after reply→standby: skip OWW for _STANDBY_GUARD_SEC
                        # so any in-flight ALSA drain or room transients don't trigger a false wake.
                        if time.perf_counter() - self._standby_entry_time < self._STANDBY_GUARD_SEC:
                            self.vad_state = "standby_guard"
                            continue
                        self._ww_buf.append(chunk)
                        if len(self._ww_buf) >= self._ww_frames_needed:
                            pcm_80ms = b"".join(self._ww_buf)
                            self._ww_buf.clear()
                            triggered = self._wake_engine.process_chunk(pcm_80ms)
                            score = getattr(self._wake_engine, "last_score", None)
                            if score is not None:
                                # Stream every score (~12.5 Hz) — UI overlay needs full
                                # dynamics, and noise calibration uses the low tail of
                                # the distribution as baseline. Includes current threshold
                                # so UI does not need a separate poll.
                                event_log.append("oww_score", {
                                    "score": round(float(score), 3),
                                    "hits": getattr(self._wake_engine, "_consecutive_hits", None),
                                    "threshold": getattr(self._wake_engine, "_threshold", None),
                                })
                            if triggered:
                                self._utterance_id = str(uuid4())[:8]
                                event_log.append("wake_word_detected", {"engine": "openwakeword", "score": round(score, 3) if score is not None else None, "silence_timeout_sec": self._wake_silence_timeout_sec, "utterance_id": self._utterance_id})
                                self._set_voice_state("listening", "wake_word")
                                self._webrtc_vad.reset_states()
                                self._wake_detected_at = time.perf_counter()
                                speech_frames.clear()
                                speech_ms = 0
                                silence_ms = 0
                    self.vad_state = "standby"
                    continue

                # ── REPLY: check window timeout ──────────────────────────────────
                if self._voice_state == "reply":
                    elapsed = time.perf_counter() - self._reply_start
                    absolute_deadline = self._reply_window_sec + self._reply_absolute_deadline_sec
                    no_speech_expired = elapsed >= self._reply_window_sec and speech_ms < self.min_speech_ms
                    hard_cutoff = elapsed >= absolute_deadline
                    if no_speech_expired or hard_cutoff:
                        # Action policy: 'standby' (default) keeps mic running,
                        # OWW listens for next wake word. 'stop' fully halts the
                        # loop — operator/UI must call /api/voice/start to resume.
                        action = self._reply_window_expired_action
                        reason = "absolute_deadline" if hard_cutoff else "no_speech"
                        event_log.append("reply_window_expired", {
                            "action": action,
                            "elapsed_sec": round(elapsed, 1),
                            "reason": reason,
                        })
                        if action == "stop":
                            asyncio.create_task(self.stop(), name="reply_window_stop")
                            return
                        self._set_voice_state("standby", "reply_expired")
                        self._standby_entry_time = time.perf_counter()
                        speech_frames.clear()
                        speech_ms = 0
                        silence_ms = 0
                        self._ww_buf.clear()
                        continue

                # ── LISTENING: 3s silence timeout after wake word ────────────────
                # If the user triggered the wake word but said nothing within the
                # timeout window, return to standby rather than waiting indefinitely.
                if self._voice_state == "listening" and speech_ms == 0:
                    elapsed = time.perf_counter() - self._wake_detected_at
                    if elapsed >= self._wake_silence_timeout_sec:
                        event_log.append("wake_silence_timeout", {
                            "action": "standby",
                            "elapsed_sec": round(elapsed, 1),
                        })
                        self._set_voice_state("standby", "wake_silence_timeout")
                        self._standby_entry_time = time.perf_counter()
                        self._ww_buf.clear()
                        continue

                # ── LISTENING + REPLY: accumulation + endpointing ────────────────
                # LISTENING: ALL frames are accumulated unconditionally — voiced
                # controls only speech_ms/silence_ms counters and vad_state display.
                # This ensures no leading syllables are clipped if they start below
                # the RMS threshold.
                # WebRTC VAD drives speech_ms/silence_ms counters in LISTENING and REPLY.
                effective_voiced = voiced

                if self._voice_state == "listening":
                    # VAD drives speech_ms/silence_ms counters only — accumulation
                    # happens unconditionally at the outer speech_frames.append below.
                    if effective_voiced:
                        if not speech_frames:
                            event_log.append("asr_partial", {"state": "speech_started", "level": _rms, "utterance_id": self._utterance_id})
                        speech_ms += self.frame_ms
                        silence_ms = 0
                        self.vad_state = "speech"
                        _was_endpointing = False
                    elif speech_frames:
                        silence_ms += self.frame_ms
                        if not _was_endpointing:
                            _was_endpointing = True
                            event_log.append("endpointing_started", {"duration_ms": self._command_endpointing_ms, "utterance_id": self._utterance_id})
                        self.vad_state = "endpointing"
                    else:
                        self.vad_state = "silence"
                elif effective_voiced:
                    if not speech_frames:
                        event_log.append("asr_partial", {"state": "speech_started", "level": _rms, "utterance_id": self._utterance_id})
                    speech_ms += self.frame_ms
                    silence_ms = 0
                    self.vad_state = "speech"
                    _was_endpointing = False
                elif speech_frames:
                    silence_ms += self.frame_ms
                    if not _was_endpointing:
                        _was_endpointing = True
                        event_log.append("endpointing_started", {"duration_ms": self._command_endpointing_ms, "utterance_id": self._utterance_id})
                    self.vad_state = "endpointing"
                else:
                    self.vad_state = "silence"
                speech_frames.append(chunk)

                if speech_frames and (
                    silence_ms >= self._command_endpointing_ms
                    or speech_ms >= self.max_segment_ms
                ):
                    pcm = b"".join(speech_frames)
                    enough_speech = speech_ms >= self.min_speech_ms
                    speech_frames.clear()
                    speech_ms = 0
                    silence_ms = 0
                    _was_endpointing = False
                    if enough_speech:
                        # mute_start is the wall-clock anchor for ESP32 backlog
                        # estimation. Take it BEFORE _stop_process() so its value
                        # is independent of the ALSA branch (avoids a future bug
                        # where the local _stop_process() inflates the drain
                        # estimate). In ESP32 mode no process exists; the value
                        # is set at the same logical moment as endpointing.
                        mute_start = time.perf_counter()
                        # In local ALSA mode self._process is set; in ESP32 mode it is None.
                        _using_process = self._process is not None
                        if _using_process:
                            self._stop_process()
                        self.muted_by_tts = True
                        event_log.append("mic_muted", {"reason": "asr_transcribing"})
                        self.vad_state = "transcribing"

                        spoke = await self._transcribe_and_dispatch(pcm)

                        # Local mode: restart arecord and update _reader (clean buffer).
                        # ESP32 mode: stream stays open and accumulates frames in TCP
                        # during transcribe + LLM + TTS. Drain that backlog here so the
                        # next read does not return TTS self-echo as user speech.
                        if _using_process:
                            self._process = self._start_arecord()
                            stdout = self._process.stdout
                            if stdout is None:
                                raise RuntimeError("arecord restart failed")
                            _reader[0] = stdout.read
                        else:
                            drained = await self._drain_esp32_backlog(
                                _reader[0], frame_bytes, mute_start
                            )
                            event_log.append("esp32_mic_drained", {
                                "frames": drained,
                                "ms": drained * self.frame_ms,
                            })
                        event_log.append("mic_unmuted", {"reason": "transcription_complete"})
                        self.muted_by_tts = False
                        speech_frames.clear()
                        speech_ms = 0
                        silence_ms = 0
                        self._ww_buf.clear()
                        if spoke:
                            self._set_voice_state("reply", "agent_spoke")
                            self._reply_start = time.perf_counter()
                            event_log.append("asr_reply_window_open", {
                                "timeout_sec": self._reply_window_sec
                            })
                        else:
                            self._set_voice_state("standby", "no_reply")
                            self._standby_entry_time = time.perf_counter()
                            event_log.append("asr_no_reply_standby", {
                                "reason": "no_spoken_response"
                            })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.running = False
            self.vad_state = "error"
            self.last_asr_error = str(exc)
            runtime_state["last_error"] = f"voice_loop:{exc}"
            event_log.append("voice_loop_error", {"error": str(exc)})
            event_log.append("voice_loop_stopped", self.status())
        finally:
            self._stop_process()
            self.running = False

    def _start_arecord(self) -> subprocess.Popen[bytes]:
        command = [
            "arecord",
            "-q",
            "-D",
            self.capture_device,
            "-f",
            "S16_LE",
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
            "-t",
            "raw",
        ]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    @staticmethod
    def _capture_device_for(device: str) -> str:
        if device.startswith("hw:"):
            return f"plughw:{device[3:]}"
        return device

    def _stop_process(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def _read_process_stderr(self) -> str:
        if self._process is None or self._process.stderr is None:
            return "no stderr"
        try:
            stderr = self._process.stderr.read()
        except OSError as exc:
            return str(exc)
        return stderr.decode("utf-8", errors="replace").strip() or "no stderr"

    async def _transcribe_and_dispatch(self, pcm: bytes) -> bool:
        self.vad_state = "transcribing"
        pcm_ms = round(len(pcm) / max(1, self.sample_rate * 2) * 1000)
        turn_id = str(uuid4())[:8]
        event_log.append("asr_request", {
            "pcm_ms": pcm_ms,
            "provider": self.asr_client.__class__.__name__,
            "utterance_id": self._utterance_id,
        }, turn_id=turn_id)
        t_asr = time.perf_counter()
        try:
            transcript = (await self.asr_client.transcribe_pcm(pcm)).strip()
        except Exception as exc:
            self.last_asr_error = str(exc)
            event_log.append("voice_loop_error", {"stage": "asr", "error": str(exc)}, turn_id=turn_id)
            return False
        asr_ms = round((time.perf_counter() - t_asr) * 1000, 1)
        runtime_state["last_asr_ms"] = asr_ms
        event_log.append("asr_result", {
            "asr_ms": asr_ms,
            "empty": not transcript,
            "raw": transcript[:120] if transcript else "",
        }, turn_id=turn_id)
        if not transcript:
            return False

        self.last_transcript = transcript
        self.last_transcript_at = utc_now()
        self.last_asr_error = ""

        # Strip wake word prefix (e.g. "адам, как дела?" → "как дела?")
        cleaned = self._wake_re.sub("", transcript).strip() if self._wake_re else transcript
        if not cleaned:
            event_log.append("asr_wake_only", {"raw": transcript, "reason": "only_wake_word"}, turn_id=turn_id)
            return False

        event_log.append("asr_final", {
            "text": cleaned, "raw": transcript, "source": "voice_loop", "asr_ms": asr_ms
        }, turn_id=turn_id)
        try:
            await _run_dialogue_turn(cleaned, "voice_loop", asr_ms=asr_ms, turn_id=turn_id)
        except Exception as exc:
            self.last_asr_error = str(exc)
            event_log.append("voice_loop_error", {"stage": "dialogue_turn", "error": str(exc)}, turn_id=turn_id)
            return False
        return True


class SceneWorker:
    def __init__(
        self,
        media_config: dict[str, Any],
        vlm_client: VLMClient,
        cam: CameraReader,
        buf: SceneDescriptionBuffer,
    ) -> None:
        self.media_config = media_config
        self.vlm_client = vlm_client
        self._cam = cam
        self._buf = buf
        self.interval_sec = float(media_config.get("scene_interval_sec", 2))
        self.stale_after_sec = float(media_config.get("scene_stale_after_sec", 20))
        self.enabled = bool(media_config.get("scene_worker_enabled", True))
        self.running = False
        self.last_error = ""
        self._task: asyncio.Task[None] | None = None
        self._consecutive_errors = 0

    def status(self) -> dict[str, Any]:
        return {"running": self.running, "enabled": self.enabled, "last_error": self.last_error}

    def apply_config(self, media_config: dict[str, Any]) -> None:
        """Apply media config changes to SceneWorker at runtime."""
        self.interval_sec = float(media_config.get("scene_interval_sec", self.interval_sec))
        self.stale_after_sec = float(media_config.get("scene_stale_after_sec", self.stale_after_sec))
        self.enabled = bool(media_config.get("scene_worker_enabled", self.enabled))

    async def start(self) -> None:
        if not self.enabled or (self._task and not self._task.done()):
            return
        self.running = True
        self._task = asyncio.create_task(self._run(), name="adam_scene_worker")

    async def stop(self) -> None:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self.running:
            # Yield GPU to LLM during active turn — VLM and LLM share the same Jetson GPU.
            if runtime_state.get("thinking") or runtime_state.get("speaking"):
                await asyncio.sleep(0.2)
                continue
            if scene_cache.is_time_stale(self.stale_after_sec):
                scene_cache.mark_stale("scene_stale_after_sec exceeded")
            t_iter = time.perf_counter()
            try:
                jpeg = self._cam.get_latest()
                if not jpeg:
                    await asyncio.sleep(0.2)
                    continue
                prev = scene_cache.text or ""
                event_log.append("vlm_request_started", {"frame_bytes": len(jpeg), "camera_source": self._cam.active_source})
                t_vlm = time.perf_counter()
                summary = (await self.vlm_client.describe_jpeg(jpeg, prev_scene=prev)).strip()
                vlm_ms = round((time.perf_counter() - t_vlm) * 1000, 1)
                event_log.append("vlm_request_finished", {
                    "vlm_ms": vlm_ms,
                    "text_len": len(summary),
                    "text_preview": summary[:120],
                    "has_prev_scene": bool(prev),
                })
                runtime_state["last_vlm_ms"] = vlm_ms
                meta = {"source": "vlm", "updated_at": utc_now(), "stale": False, "vlm_ms": vlm_ms, "last_error": ""}
                pushed = self._buf.push(summary)
                if not pushed:
                    event_log.append("scene_description_duplicate", {
                        "text": summary,
                        "camera_source": self._cam.active_source,
                    })
                    scene_cache.update(summary, meta)
                else:
                    updated = scene_cache.update(summary, meta)
                    event_log.append("scene_updated", updated)
                self.last_error = ""
                self._consecutive_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._consecutive_errors += 1
                self.last_error = str(exc)
                event_log.append("vlm_request_failed", {"error": str(exc), "camera_source": self._cam.active_source})
                stale = scene_cache.mark_stale(str(exc))
                # Only log to stream on first error and every 10th after — avoid flood.
                if self._consecutive_errors == 1 or self._consecutive_errors % 10 == 0:
                    event_log.append("scene_stale", {
                        **stale,
                        "camera_active_source": self._cam.active_source,
                    })
            elapsed = time.perf_counter() - t_iter
            # Exponential backoff when VLM is down: 2s → 4s → 8s → … → 60s cap.
            backoff = min(self.interval_sec * (2 ** min(self._consecutive_errors - 1, 5)), 60.0)
            sleep_sec = backoff if self._consecutive_errors > 0 else max(0.0, self.interval_sec - elapsed)
            await asyncio.sleep(sleep_sec)


voice_loop = VoiceLoopController(settings.section("media").get("audio", {}), asr, mcu=mcu)
scene_worker = SceneWorker(settings.section("media"), vlm, camera_reader, scene_buffer)


class SessionWatcher:
    """Закрывает накопленную сессию когда долго нет turn'ов (silence timeout)."""

    def __init__(self, poll_seconds: float = 10.0) -> None:
        self.poll_seconds = poll_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="adam_session_watcher")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                return  # stop requested
            except asyncio.TimeoutError:
                pass
            try:
                await self._tick()
            except Exception as exc:
                event_log.append("session_watcher_error", {"error": str(exc)})

    async def _tick(self) -> None:
        tuning = tuning_store.current()
        strategy = tuning.session.end_strategy
        threshold = tuning.session.vad_silence_seconds
        face_threshold = tuning.session.face_lost_seconds
        now_ts = time.time()
        async with session_lock:
            acc = session_state.get("accumulator")
            if acc is None:
                return
            last_ts = float(session_state.get("last_turn_at") or 0.0)
            silence_elapsed = now_ts - last_ts
            face_seen = float(session_state.get("last_face_seen_at") or 0.0)
            face_elapsed = now_ts - face_seen if face_seen else None

            close = False
            reason = ""
            if strategy == "vad_silence" and silence_elapsed >= threshold:
                close, reason = True, f"silence_{int(silence_elapsed)}s"
            elif strategy == "face_lost":
                if face_elapsed is not None and face_elapsed >= face_threshold:
                    close, reason = True, f"face_lost_{int(face_elapsed)}s"
            elif strategy == "combined":
                if silence_elapsed >= threshold:
                    close, reason = True, f"silence_{int(silence_elapsed)}s"
                elif face_elapsed is not None and face_elapsed >= face_threshold:
                    close, reason = True, f"face_lost_{int(face_elapsed)}s"
            elif strategy == "idle_with_grace":
                # пока упрощённо: как combined, без grace-message
                if silence_elapsed >= threshold:
                    close, reason = True, f"silence_{int(silence_elapsed)}s"
            elif strategy == "event_signal":
                # внешний триггер не приходит автоматически — оставляем open
                return

            if close:
                await _commit_session_locked(reason=f"watcher:{reason}")
                session_state["last_turn_at"] = 0.0


session_watcher = SessionWatcher()


class EspAudioHealthMonitor:
    """Polls ESP32 /api/audio periodically and auto-switches mic profile when a channel degrades.

    Runs only while voice_loop.mic_source == "esp32". Logs every decision to events.jsonl so
    the operator can understand why a specific profile was chosen or changed.

    Health criteria (per-channel, evaluated from left_peak / right_peak / clip_count):
      - Channel silent:  peak < SILENCE_THRESHOLD while the other is active  → switch to other mono
      - Peak imbalance:  max(L,R)/min(L,R) > RATIO_THRESHOLD                → switch to louder channel
      - Clipping burst:  clip_count delta > CLIP_BURST_THRESHOLD             → log warning (no switch,
                         clipping may be momentary — sustained shows up as signal_state=="clipped")
      - Sustained clip:  signal_state == "clipped"                           → log warning

    Profile selection always stays within the philips32 family to match the hardware wiring.
    """

    INITIAL_DELAY_S = 30
    _MONO_L = "inmp441_philips32_left"
    _MONO_R = "inmp441_philips32_right"
    _STEREO = "inmp441_philips32_stereo"

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._last_clip_count: int = 0
        self._last_result: dict[str, Any] = {}
        self._healthy_mono_polls: int = 0
        self.apply_config(settings.section("media").get("audio", {}).get("esp_health", {}))

    def apply_config(self, cfg: dict[str, Any]) -> None:
        self.poll_interval_s = int(cfg.get("poll_interval_s", 60))
        self.silence_threshold = int(cfg.get("silence_threshold", 24))
        self.ratio_threshold = float(cfg.get("ratio_threshold", 6.0))
        self.clip_burst_threshold = int(cfg.get("clip_burst_threshold", 20))
        self.restore_threshold_polls = int(cfg.get("restore_threshold_polls", 5))

    def status(self) -> dict[str, Any]:
        return {
            "running": self._task is not None and not self._task.done(),
            "poll_interval_s": self.poll_interval_s,
            "silence_threshold": self.silence_threshold,
            "ratio_threshold": self.ratio_threshold,
            "clip_burst_threshold": self.clip_burst_threshold,
            "restore_threshold_polls": self.restore_threshold_polls,
            "healthy_mono_polls": self._healthy_mono_polls,
            "last_result": self._last_result,
        }

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="esp_audio_health")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        await asyncio.sleep(self.INITIAL_DELAY_S)
        while True:
            try:
                if voice_loop.running and voice_loop.mic_source == "esp32":
                    await self._check()
            except Exception as exc:
                event_log.append("esp32_health_error", {"error": str(exc)})
            await asyncio.sleep(self.poll_interval_s)

    async def _check(self) -> None:
        if voice_loop._esp_mic_fallback:
            elapsed = time.perf_counter() - voice_loop._esp_mic_last_retry
            if elapsed < voice_loop.esp_mic_retry_interval_sec:
                return

        result = await mcu.request("GET", "/api/audio")
        if not result.ok:
            event_log.append("esp32_health_poll_failed", {"status": result.status, "error": result.error})
            return

        if voice_loop._esp_mic_fallback:
            voice_loop._esp_mic_fallback = False
            voice_loop._esp_mic_fail_count = 0
            voice_loop._esp_mic_last_retry = 0.0
            # After health check passes, the next _run_esp32 attempt re-enters
            # the "connecting" state — pre-set it here so the UI immediately
            # reflects the recovery handshake instead of the stale "fallback".
            voice_loop._mic_stream_state = "connecting"
            event_log.append("esp32_mic_restored", {})
            if voice_loop.running:
                asyncio.ensure_future(voice_loop.restart())
            return

        cap = result.data.get("capture", {})
        L = int(cap.get("left_peak", 0))
        R = int(cap.get("right_peak", 0))
        clip_count = int(cap.get("clip_count", 0))
        signal_state = str(cap.get("signal_state", ""))
        dc_offset = int(cap.get("dc_offset", 0))
        detected = int(cap.get("detected_channels", 0))

        clip_delta = max(0, clip_count - self._last_clip_count)
        self._last_clip_count = clip_count

        metrics = {
            "profile": cap.get("profile"),
            "left_peak": L,
            "right_peak": R,
            "signal_state": signal_state,
            "clip_delta": clip_delta,
            "clip_count_total": clip_count,
            "dc_offset": dc_offset,
            "detected_channels": detected,
        }

        warn_reasons: list[str] = []
        if signal_state == "clipped":
            warn_reasons.append("signal_state_clipped")
        if clip_delta >= self.clip_burst_threshold:
            warn_reasons.append(f"clip_burst:{clip_delta}")

        current = voice_loop.esp32_mic_profile

        # ── Stereo mode: detect bad channel → fallback to best mono ──
        if current.endswith("stereo"):
            left_ok = True
            right_ok = True
            bad_reasons: list[str] = []

            if L < self.silence_threshold and R >= self.silence_threshold:
                left_ok = False
                bad_reasons.append("left_channel_silent")
            elif R < self.silence_threshold and L >= self.silence_threshold:
                right_ok = False
                bad_reasons.append("right_channel_silent")
            elif L < self.silence_threshold and R < self.silence_threshold:
                left_ok = False
                right_ok = False
                bad_reasons.append("both_channels_below_threshold")

            if left_ok and right_ok and L > 0 and R > 0:
                ratio = max(L, R) / min(L, R)
                if ratio >= self.ratio_threshold:
                    if L > R:
                        right_ok = False
                        bad_reasons.append(f"right_peak_weak:ratio={ratio:.1f}")
                    else:
                        left_ok = False
                        bad_reasons.append(f"left_peak_weak:ratio={ratio:.1f}")

            if not bad_reasons:
                entry: dict[str, Any] = {"status": "ok", **metrics}
                if warn_reasons:
                    entry = {"status": "warning", "reason": "|".join(warn_reasons), "action": "no_switch", **metrics}
                event_log.append("esp32_audio_health", entry)
                self._last_result = entry
                return

            all_reasons = bad_reasons + warn_reasons
            if left_ok and not right_ok:
                target = self._MONO_L
                channel_verdict = "left_healthy_right_bad"
            elif right_ok and not left_ok:
                target = self._MONO_R
                channel_verdict = "right_healthy_left_bad"
            else:
                entry = {"status": "warning", "reason": "|".join(all_reasons), "action": "no_switch", **metrics}
                event_log.append("esp32_audio_health", entry)
                self._last_result = entry
                return

            self._healthy_mono_polls = 0
            entry = {
                "status": "auto_switch",
                "from_profile": current,
                "to_profile": target,
                "reason": "|".join(all_reasons),
                "channel_verdict": channel_verdict,
                **metrics,
            }
            event_log.append("esp32_audio_health_auto_switch", entry)
            self._last_result = entry
            voice_loop.esp32_mic_profile = target
            asyncio.ensure_future(voice_loop.restart())
            return

        # ── Mono mode: restore to stereo when both channels recover ──
        both_ok = L >= self.silence_threshold and R >= self.silence_threshold

        if both_ok:
            self._healthy_mono_polls += 1
            if self._healthy_mono_polls >= self.restore_threshold_polls:
                self._healthy_mono_polls = 0
                entry = {
                    "status": "auto_switch",
                    "from_profile": current,
                    "to_profile": self._STEREO,
                    "reason": f"both_channels_recovered:{self.restore_threshold_polls}_consecutive_polls",
                    **metrics,
                }
                event_log.append("esp32_audio_health_auto_switch", entry)
                self._last_result = entry
                voice_loop.esp32_mic_profile = self._STEREO
                asyncio.ensure_future(voice_loop.restart())
            else:
                entry = {
                    "status": "ok",
                    "action": f"waiting_restore:{self._healthy_mono_polls}/{self.restore_threshold_polls}",
                    **metrics,
                }
                event_log.append("esp32_audio_health", entry)
                self._last_result = entry
            return

        # Not both OK — reset counter, check active channel health
        self._healthy_mono_polls = 0
        if current == self._MONO_L:
            active_ok = L >= self.silence_threshold
            fallback: str | None = self._MONO_R if R >= self.silence_threshold else None
            bad_ch_reason = "left_channel_silent_while_in_mono_L"
        else:
            active_ok = R >= self.silence_threshold
            fallback = self._MONO_L if L >= self.silence_threshold else None
            bad_ch_reason = "right_channel_silent_while_in_mono_R"

        if active_ok:
            # Inactive channel silent — expected in mono mode, not an error
            entry = {"status": "ok", **metrics}
            if warn_reasons:
                entry = {"status": "warning", "reason": "|".join(warn_reasons), "action": "no_switch", **metrics}
            event_log.append("esp32_audio_health", entry)
            self._last_result = entry
            return

        if fallback is None:
            entry = {
                "status": "degraded",
                "reason": bad_ch_reason,
                "action": "no_fallback_both_channels_silent",
                **metrics,
            }
            event_log.append("esp32_audio_health", entry)
            self._last_result = entry
            return

        entry = {
            "status": "auto_switch",
            "from_profile": current,
            "to_profile": fallback,
            "reason": bad_ch_reason,
            **metrics,
        }
        event_log.append("esp32_audio_health_auto_switch", entry)
        self._last_result = entry
        voice_loop.esp32_mic_profile = fallback
        asyncio.ensure_future(voice_loop.restart())


esp_audio_health = EspAudioHealthMonitor()


async def _audio_level_monitor() -> None:
    """Read Jetson ALSA mic and emit audio_level SSE events for the UI equalizer.
    Yields the device automatically when the voice loop is active (to avoid conflict).
    Uses subprocess.Popen + asyncio.to_thread — same pattern as the voice loop."""
    audio_cfg = settings.section("media").get("audio", {})
    raw_dev = str(audio_cfg.get("input_device", "hw:1,0"))
    device = f"plughw:{raw_dev[3:]}" if raw_dev.startswith("hw:") else raw_dev
    sample_rate = int(audio_cfg.get("sample_rate", 16000))
    frame_bytes = sample_rate * 2 // 10  # 100 ms of 16-bit mono
    normalize_factor = float(audio_cfg.get("normalize_factor", 8000))

    while True:
        try:
            if voice_loop.device_in_use:
                await asyncio.sleep(0.3)
                continue

            proc = subprocess.Popen(
                ["arecord", "-q", "-D", device, "-f", "S16_LE",
                 "-r", str(sample_rate), "-c", "1", "-t", "raw"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            try:
                while not voice_loop.device_in_use:
                    chunk = await asyncio.to_thread(proc.stdout.read, frame_bytes)  # type: ignore[union-attr]
                    if not chunk:
                        await asyncio.sleep(1.0)  # back off before retry when arecord exits early
                        break  # arecord exited
                    raw_level = audioop.rms(chunk, 2)
                    norm = round(min(1.0, (raw_level / normalize_factor) ** 0.5), 3)
                    # T17 fix #6 — this monitor runs ONLY while the voice loop
                    # isn't holding the mic device (i.e. maintenance-mode idle
                    # equaliser), so the source is always the local ALSA mic.
                    event_log.append("audio_level", {
                        "level": norm, "state": "idle", "source": "local",
                    })
            finally:
                try:
                    proc.kill()
                    proc.wait()
                except Exception:
                    pass

        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(2.0)


async def _wait_for_services(expected: set[str]) -> bool:
    """Poll expected AI services until all healthy or 120 s deadline. Returns True if all OK."""
    clients = {k: v for k, v in {"llm": llm, "tts": tts, "asr": asr, "vlm": vlm}.items()
               if k in expected}
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        results = await asyncio.gather(*(c.health() for c in clients.values()))
        if all(h.ok for h in results):
            return True
        await asyncio.sleep(5.0)
    event_log.append("startup_services_timeout", {"expected": sorted(expected)})
    return False


async def _orchestrated_startup(services_confirmed: bool) -> None:
    """Sequential boot: wait for services → sound → warmup greeting → voice loop.

    Keeps the mic off during the entire sequence so OWW cannot fire on TTS audio.
    """
    expected_raw = os.environ.get("ADAM_EXPECTED_SERVICES", "llm,tts,asr,vlm")
    expected = {s.strip() for s in expected_raw.split(",") if s.strip()}

    if services_confirmed:
        services_ok: bool | None = True       # exhibition gate already verified
    elif expected:
        services_ok = await _wait_for_services(expected)
    else:
        services_ok = None                    # --empty mode: no services, skip sound

    if _sounds_enabled() and services_ok is not None:
        if services_ok:
            await _play_success_sound("startup_services_ok")
        else:
            await _play_error_sound("startup_services_failed")

    event_log.append("voice_loop_boot_muted", {"reason": "warmup_in_progress"})
    # N6: pre-synthesize filler WAV BEFORE warmup_wakeup. If we ran it after,
    # the streaming pipeline inside _warmup_wakeup would itself trigger
    # _filler_task → on-demand synth → cache populated. Then _prewarm_filler
    # would see cache-hit and exit silently with no event. Running it first
    # ensures explicit prewarm logging and a true cache-hit on the warmup turn.
    await _prewarm_filler()
    await _warmup_wakeup()
    # Prime llama.cpp prompt cache with the canonical real-turn system message
    # (wakeup monologue uses a modified system prompt → does not warm the prefix
    # that real voice turns actually hit). Without this, Turn 1 pays ~8s of
    # extra LLM TTFT for full prefill of the ~2800-token persona prefix.
    await _warmup_llm_prefix()
    # Brief buffer after TTS finishes so ALSA drain noise decays before OWW starts.
    await asyncio.sleep(0.5)
    for _retry in range(5):
        result = await voice_loop.start()
        if result.get("ok"):
            event_log.append("voice_loop_boot_ready", {"retry": _retry})
            break
        await asyncio.sleep(2.0)


@asynccontextmanager
async def lifespan(_: FastAPI):
    power = power_gate.check()
    event_log.append("orchestrator_started", {"mode": runtime_state["mode"], "power": power.as_dict()})
    camera_reader.start()
    await scene_worker.start()
    await session_watcher.start()
    await esp_audio_health.start()
    level_monitor = asyncio.create_task(_audio_level_monitor(), name="audio_level_monitor")
    services_confirmed = False
    if runtime_state["mode"] == "exhibition" and settings.section("power").get("enforce_in_exhibition", True):
        status_payload = await _status_payload()
        gate = status_payload["exhibition_gate"]
        if not gate["ok"]:
            runtime_state["mode"] = "maintenance"
            event_log.append("exhibition_gate_failed", gate)
            raise RuntimeError(f"exhibition mode gate failed: {gate['failed']}")
        services_confirmed = True
    asyncio.create_task(_orchestrated_startup(services_confirmed), name="startup_sequence")
    asyncio.create_task(_warmup_asr(), name="warmup_asr")
    try:
        yield
    finally:
        level_monitor.cancel()
        await asyncio.gather(level_monitor, return_exceptions=True)
        await voice_loop.stop()
        await esp_audio_health.stop()
        await session_watcher.stop()
        # финальный коммит, если сессия осталась открытой
        async with session_lock:
            await _commit_session_locked(reason="shutdown")
        await scene_worker.stop()
        camera_reader.stop()


app = FastAPI(title="Adam Chip Orchestrator", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse("/ui/", status_code=307)


@app.get("/legacy/agent", response_class=HTMLResponse)
async def legacy_agent() -> str:
    return agent_page()


@app.get("/legacy/dash", response_class=HTMLResponse)
async def legacy_dash() -> str:
    return dash_page(_ui_settings_public())


@app.get("/legacy/debug", response_class=HTMLResponse)
async def legacy_debug() -> str:
    return debug_page(_ui_settings_public())


@app.get("/agent", response_class=HTMLResponse)
async def agent() -> RedirectResponse:
    return RedirectResponse("/legacy/agent", status_code=307)


@app.get("/dash", response_class=HTMLResponse)
async def dash() -> RedirectResponse:
    return RedirectResponse("/legacy/dash", status_code=307)


@app.get("/debug", response_class=HTMLResponse)
async def debug() -> RedirectResponse:
    return RedirectResponse("/legacy/debug", status_code=307)


@app.get("/api/ui/status")
async def ui_status() -> dict[str, Any]:
    return await _ui_status_payload()


@app.post("/api/ui/camera")
async def ui_camera(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _result_or_raise(await mcu.request("POST", "/api/camera", payload))


@app.post("/api/ui/camera/preset")
async def ui_camera_preset(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    preset = str(payload.get("preset", "")).strip()
    if not preset:
        raise HTTPException(status_code=400, detail="preset is required")
    return _result_or_raise(await mcu.request("POST", "/api/camera/preset/apply", {"preset": preset}))


@app.post("/api/ui/audio")
async def ui_audio(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _result_or_raise(await mcu.request("POST", "/api/audio", payload))


@app.post("/api/ui/video-latency/reset")
async def ui_video_latency_reset() -> dict[str, Any]:
    return _result_or_raise(await mcu.request("POST", "/api/video_latency/reset"))


@app.post("/api/ui/pca/channel")
async def ui_pca_channel(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _result_or_raise(await mcu.request("POST", "/api/pca9685/channel", payload))


@app.post("/api/ui/pca/channels")
async def ui_pca_channels(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    updates = payload.get("updates", [])
    if not isinstance(updates, list):
        raise HTTPException(status_code=400, detail="updates must be a list")
    return _result_or_raise(await mcu.set_channels(updates))


@app.post("/api/ui/pca/scene")
async def ui_pca_scene(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    scene = str(payload.get("scene", "")).strip()
    if not scene:
        raise HTTPException(status_code=400, detail="scene is required")
    return _result_or_raise(await mcu.request("POST", "/api/pca9685/scene", {"scene": scene}))


@app.post("/api/ui/pca/debug-scene")
async def ui_pca_debug_scene(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    scene = str(payload.get("scene", "")).strip()
    if scene not in {"all_off", "all_on", "even_on_odd_off", "invert"}:
        raise HTTPException(status_code=400, detail="invalid debug scene")

    current_channels: list[Any] = []
    if scene == "invert":
        current = await mcu.request("GET", "/api/pca9685")
        if not current.ok:
            return _result_or_raise(current)
        pca = current.data.get("pca9685", {}) if isinstance(current.data.get("pca9685"), dict) else current.data
        raw_channels = pca.get("channels", []) if isinstance(pca, dict) else []
        current_channels = raw_channels if isinstance(raw_channels, list) else []

    updates = _debug_scene_updates(scene, current_channels)
    return _result_or_raise(await mcu.set_channels(updates))


@app.post("/api/ui/pcm/system-sound")
async def ui_pcm_system_sound(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    return _result_or_raise(await mcu.play_system_sound(name))


@app.post("/api/ui/pcm/upload")
async def ui_pcm_upload(request: Request) -> dict[str, Any]:
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="audio payload is required")
    content_type = request.headers.get("content-type", "audio/wav")
    result = await mcu.post_speaker_bytes(data, content_type)
    return _result_or_raise(result)


@app.get("/api/agent/status")
async def status() -> dict[str, Any]:
    return await _status_payload()


@app.post("/api/agent/listen/start")
async def listen_start() -> dict[str, Any]:
    return await voice_loop.start()


@app.post("/api/agent/listen/stop")
async def listen_stop() -> dict[str, Any]:
    return await voice_loop.stop()


@app.get("/api/agent/listen/status")
async def listen_status() -> dict[str, Any]:
    return {"ok": True, **voice_loop.status()}


@app.post("/api/voice/force_esp_retry")
async def voice_force_esp_retry() -> dict[str, Any]:
    """Single-shot ESP probe + voice_loop restart (UI button).
    Active only when mic_source=esp32 AND in local fallback."""
    return await voice_loop.force_esp_retry()


def _ui_settings_public() -> dict[str, Any]:
    public = settings.to_public_dict()
    public["_ui"] = {
        "esp_base_url": mcu.base_url,
        "camera_stream_url": mcu.camera_stream_url(),
        "mic_stream_url": mcu.mic_stream_url(),
        "speaker_url": mcu.speaker_endpoint_url(),
    }
    return public


async def _ui_status_payload() -> dict[str, Any]:
    keys = ["status", "dashboard", "sensors", "camera", "audio", "pca"]
    paths = ["/api/status", "/api/dashboard", "/api/sensors", "/api/camera", "/api/audio", "/api/pca9685"]
    results = await asyncio.gather(*(mcu.request("GET", path) for path in paths))

    data: dict[str, Any] = {}
    errors: dict[str, Any] = {}
    for key, result in zip(keys, results):
        data[key] = result.data if result.ok else {}
        if not result.ok:
            errors[key] = {"status": result.status, "error": result.error}

    modules = _module_flags(
        data["status"],
        data["dashboard"],
        data["sensors"],
        data["camera"],
        data["audio"],
        data["pca"],
    )
    return {
        "ok": not errors,
        "esp": {
            "base_url": mcu.base_url,
            "camera_stream_url": mcu.camera_stream_url(),
            "mic_stream_url": mcu.mic_stream_url(),
            "speaker_url": mcu.speaker_endpoint_url(),
        },
        "modules": modules,
        "errors": errors,
        "voice_loop": voice_loop.status(),
        "esp_audio_health": esp_audio_health.status(),
        **data,
    }


def _module_flags(
    status_data: dict[str, Any],
    dashboard: dict[str, Any],
    sensors: dict[str, Any],
    camera: dict[str, Any],
    audio: dict[str, Any],
    pca: dict[str, Any],
) -> dict[str, bool]:
    camera_data = camera.get("camera", camera) if isinstance(camera, dict) else {}
    capture = audio.get("capture", {}) if isinstance(audio.get("capture"), dict) else {}
    playback = audio.get("playback", {}) if isinstance(audio.get("playback"), dict) else {}
    pca_data = pca.get("pca9685", pca) if isinstance(pca, dict) else {}

    return {
        "mic": bool(capture.get("ready", audio.get("audio_ready", status_data.get("audio_ready", dashboard.get("audio_ready"))))),
        "cam": bool(camera_data.get("ready", status_data.get("camera_ready", dashboard.get("camera_ready")))),
        "pcm5102": bool(playback.get("ready", status_data.get("speaker_ready", dashboard.get("speaker_ready")))),
        "pca9685": bool(pca_data.get("ready", status_data.get("pca9685_ready", dashboard.get("pca9685_ready")))),
        "temt600": "light_raw" in sensors or "light_norm" in sensors,
        "pir": "motion" in sensors,
    }


def _debug_scene_updates(scene: str, current_channels: list[Any]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for channel in range(16):
        if scene == "all_on":
            value = 4095
        elif scene == "even_on_odd_off":
            value = 4095 if channel % 2 == 0 else 0
        elif scene == "invert":
            try:
                current = int(current_channels[channel])
            except (IndexError, TypeError, ValueError):
                current = 0
            value = max(0, min(4095, 4095 - current))
        else:
            value = 0
        updates.append({"channel": channel, "mode": "pwm", "value": value})
    return updates


def _result_or_raise(result: Any) -> dict[str, Any]:
    payload = result.as_dict()
    if result.ok:
        return payload
    status_code = result.status if 400 <= result.status < 600 else 502
    raise HTTPException(status_code=status_code, detail=payload)


async def _status_payload() -> dict[str, Any]:
    power = power_gate.check()
    media = media_health.check()
    asr_health = await asr.health()
    vlm_health = await vlm.health()
    llm_health = await llm.health()
    tts_health = await tts.health()
    mcu_health = await mcu.health()
    docker = docker_health()
    mcu_public = _compact_mcu(mcu_health)
    gate = _exhibition_gate(power, media, asr_health, vlm_health, llm_health, tts_health, mcu_public, docker)
    return {
        "agent": {
            "name": settings.section("agent").get("name"),
            "mode": runtime_state["mode"],
            "speaking": runtime_state["speaking"],
            "thinking": runtime_state["thinking"],
            "last_error": runtime_state["last_error"],
            "latency_ms": {
                "asr": runtime_state.get("last_asr_ms"),
                "llm": runtime_state.get("last_llm_ms"),
                "ttfv": runtime_state.get("last_ttfv_ms"),
                "tts": runtime_state.get("last_tts_ms"),
                "vlm": runtime_state.get("last_vlm_ms"),
            },
        },
        "power": power.as_dict(),
        "media": media.as_dict(),
        "services": {
            "asr": asr_health.as_dict(),
            "vlm": vlm_health.as_dict(),
            "llm": llm_health.as_dict(),
            "tts": tts_health.as_dict(),
            "docker": docker.as_dict(),
        },
        "exhibition_gate": gate,
        "voice_loop": voice_loop.status(),
        "esp_audio_health": esp_audio_health.status(),
        "camera": camera_reader.status(),
        "scene_cache": scene_cache.as_dict(),
        "scene_worker": scene_worker.status(),
        "mcu": mcu_public,
        "events": {"dropped": event_log.dropped_count},
    }


@app.get("/api/agent/gate")
async def gate() -> dict[str, Any]:
    status_payload = await _status_payload()
    return status_payload["exhibition_gate"]


@app.get("/api/agent/events")
async def events(
    limit: int = Query(100, ge=1, le=500),
    types: str | None = Query(None, description="Comma-separated event types, e.g. asr_result,adam_reply"),
    turn_id: str | None = Query(None),
    since: float | None = Query(None, description="Unix timestamp in milliseconds"),
) -> dict[str, Any]:
    type_list = [t.strip() for t in types.split(",")] if types else None
    return {"events": event_log.tail(limit, types=type_list, turn_id=turn_id, since_ms=since)}


@app.get("/api/agent/turns")
async def agent_turns(limit: int = Query(20, ge=1, le=200)) -> dict[str, Any]:
    """Return recent completed dialogue turns with per-stage latencies and linked events."""
    recent_metrics = metrics_log.tail(limit)
    result = []
    for m in recent_metrics:
        tid = m.get("turn_id")
        linked_events: list[dict[str, Any]] = []
        if tid:
            linked_events = event_log.tail(500, turn_id=tid)
        result.append({
            "turn_id": tid,
            "ts": m.get("ts"),
            "transcript": m.get("transcript", ""),
            "reply": m.get("reply", ""),
            "stages": {
                "asr_ms": m.get("asr_ms"),
                "llm_ms": m.get("llm_ms"),
                "ttfv_ms": m.get("ttfv_ms"),
                "tts_ms": m.get("tts_ms"),
                "vlm_ms": m.get("vlm_ms"),
                "total_ms": m.get("total_ms"),
            },
            "meta": {
                "source": m.get("source"),
                "action": m.get("action"),
                "llm_model": m.get("llm_model"),
                "voice_degraded": m.get("voice_degraded"),
                "llm_error": m.get("llm_error"),
            },
            "events": linked_events,
        })
    return {"turns": result}


# ---------- Tuning (runtime persona config) ----------


@app.get("/api/tuning")
async def get_tuning() -> dict[str, Any]:
    return tuning_store.current().model_dump()


@app.put("/api/tuning")
async def patch_tuning(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        new_cfg = tuning_store.apply_patch(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid tuning patch: {exc}") from exc
    event_log.append("tuning_updated", {"patch_keys": list(payload.keys())})
    return {"ok": True, "tuning": new_cfg.model_dump()}


@app.post("/api/tuning/reset")
async def reset_tuning() -> dict[str, Any]:
    new_cfg = tuning_store.restore_defaults()
    event_log.append("tuning_reset", {})
    return {"ok": True, "tuning": new_cfg.model_dump()}


@app.get("/api/tuning/schema")
async def tuning_schema() -> dict[str, Any]:
    from adam.tuning import Tuning
    return Tuning.model_json_schema()


# ---------- Prompt trace (UI диагностика) ----------


@app.get("/api/agent/prompts")
async def get_prompt_trace(
    limit: int = Query(20, ge=1, le=_PROMPT_TRACE_MAX),
    full: bool = Query(False),
) -> dict[str, Any]:
    """Список последних prompt-trace записей.

    full=false — только метаданные (transcript, echo, recent, semantic flags).
    full=true — включает system_prompt если он был сохранён (требует tuning.diagnostics.trace_prompts=true).
    """
    items = list(prompt_trace)[-limit:]
    if not full:
        items = [_summarize_trace(rec) for rec in items]
    return {
        "items": items,
        "trace_prompts_enabled": tuning_store.current().diagnostics.trace_prompts,
        "ring_capacity": _PROMPT_TRACE_MAX,
    }


def _summarize_trace(rec: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in rec.items() if k != "system_prompt"}
    out["system_prompt_available"] = rec.get("system_prompt") is not None
    return out


@app.post("/api/agent/mode")
async def set_mode(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    mode = str(payload.get("mode", "")).strip()
    if mode not in {"maintenance", "idle", "listening", "performance", "exhibition"}:
        raise HTTPException(status_code=400, detail="invalid mode")
    if mode == "exhibition":
        status_payload = await _status_payload()
        gate = status_payload["exhibition_gate"]
        if settings.section("power").get("enforce_in_exhibition", True) and not gate["ok"]:
            runtime_state["mode"] = "maintenance"
            event_log.append("exhibition_gate_failed", gate)
            raise HTTPException(status_code=409, detail={"error": "exhibition_gate_failed", "gate": gate})
    runtime_state["mode"] = mode
    event_log.append("mode_changed", {"mode": mode})
    if mode == "exhibition":
        _schedule_success_sound("mode_exhibition_gate_ok")
        await voice_loop.start()
    elif mode in {"maintenance", "idle"}:
        await voice_loop.stop()
    return {"ok": True, "mode": mode}


@app.post("/api/agent/say")
async def say(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    result = await _speak(text)
    event_log.append("manual_say", {"text": text, "tts": result})
    return {"ok": True, "tts": result}


@app.post("/api/agent/cue")
async def cue(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    cue_name = str(payload.get("cue", "")).strip()
    if cue_name == "success":
        result = await _play_success_sound("manual")
    else:
        raise HTTPException(status_code=400, detail="cue must be success")
    return {"ok": result.get("ok", False), "cue": cue_name, "result": result}


@app.post("/api/agent/stop")
async def stop() -> dict[str, Any]:
    runtime_state["speaking"] = False
    action = await mcu.idle()
    event_log.append("agent_stop", {"mcu": action.as_dict()})
    return {"ok": True, "mcu": action.as_dict()}


@app.post("/api/agent/scene")
async def update_scene(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    meta = payload.get("meta", {})
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    updated = scene_cache.update(text, meta if isinstance(meta, dict) else {})
    event_log.append("scene_cache_updated", updated)
    return {"ok": True, **updated}


@app.post("/api/mcu/reset")
async def mcu_reset() -> dict[str, Any]:
    """Soft-reset ESP32 (~300ms delay). Use when HTTP port 81 is stuck."""
    if mcu is None:
        raise HTTPException(status_code=503, detail="mcu_not_configured")
    result = await mcu.system_reset()
    event_log.append("esp32_reset_requested", {"ok": result.ok, "error": result.error})
    return {"ok": result.ok, "detail": result.data or result.error}


@app.post("/api/mcu/stream/restart")
async def mcu_stream_restart() -> dict[str, Any]:
    """Restart ESP32 port-81 stream server. Clears stale camera/audio/speaker connections."""
    if mcu is None:
        raise HTTPException(status_code=503, detail="mcu_not_configured")
    result = await mcu.stream_restart()
    event_log.append("esp32_stream_restarted", {"ok": result.ok, "error": result.error})
    return {"ok": result.ok, "detail": result.data or result.error}


@app.get("/api/mcu/info")
async def mcu_info() -> dict[str, Any]:
    """ESP32 heap / uptime diagnostics."""
    if mcu is None:
        raise HTTPException(status_code=503, detail="mcu_not_configured")
    result = await mcu.system_info()
    return {"ok": result.ok, "data": result.data}


@app.post("/api/agent/turn")
async def dialogue_turn(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    transcript = str(payload.get("transcript", "")).strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript is required")
    return await _run_dialogue_turn(transcript, "manual")


# ---- Service control --------------------------------------------------------

@app.get("/api/services")
async def get_services() -> dict[str, Any]:
    """Status of all managed systemd services."""
    statuses = await asyncio.to_thread(all_services_status)
    return {"services": statuses}


@app.post("/api/services/{name}/start")
async def start_service(name: str) -> dict[str, Any]:
    if name not in ADAM_SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service: {name}")
    unit = ADAM_SERVICES[name]
    result = await asyncio.to_thread(service_action, unit, "start")
    if not result.ok:
        raise HTTPException(status_code=500, detail=result.detail)
    return {"ok": True, "service": name, "unit": unit, "detail": result.detail}


@app.post("/api/services/{name}/stop")
async def stop_service(name: str) -> dict[str, Any]:
    if name not in ADAM_SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service: {name}")
    unit = ADAM_SERVICES[name]
    result = await asyncio.to_thread(service_action, unit, "stop")
    if not result.ok:
        raise HTTPException(status_code=500, detail=result.detail)
    return {"ok": True, "service": name, "unit": unit, "detail": result.detail}


@app.post("/api/services/{name}/restart")
async def restart_service(name: str) -> dict[str, Any]:
    if name not in ADAM_SERVICES:
        raise HTTPException(status_code=404, detail=f"unknown service: {name}")
    unit = ADAM_SERVICES[name]
    result = await asyncio.to_thread(service_action, unit, "restart")
    if not result.ok:
        raise HTTPException(status_code=500, detail=result.detail)
    return {"ok": True, "service": name, "unit": unit, "detail": result.detail}

async def _run_dialogue_turn(transcript: str, source: str, asr_ms: float | None = None, turn_id: str | None = None) -> dict[str, Any]:
    if turn_id is None:
        turn_id = str(uuid4())[:8]
    if turn_lock.locked() and source == "voice_loop":
        event_log.append("voice_loop_error", {"stage": "turn", "error": "turn_already_in_progress", "text": transcript}, turn_id=turn_id)
        return {"ok": False, "error": "turn_already_in_progress"}

    async with turn_lock:
        runtime_state["thinking"] = True
        event_log.append("llm_thinking_started", {}, turn_id=turn_id)
        try:
            return await _run_dialogue_turn_locked(transcript, source, asr_ms, turn_id)
        finally:
            runtime_state["thinking"] = False
            event_log.append("llm_thinking_finished", {}, turn_id=turn_id)


async def _run_dialogue_turn_locked(transcript: str, source: str, asr_ms: float | None, turn_id: str | None = None) -> dict[str, Any]:
    t_total = time.perf_counter()
    tuning = tuning_store.current()
    sensors = await _sensor_payload()

    # ---- Session lifecycle ----
    now_ts = time.time()
    async with session_lock:
        acc: SessionAccumulator | None = session_state.get("accumulator")  # type: ignore[assignment]
        last_ts = float(session_state.get("last_turn_at") or 0.0)
        silence_threshold = max(5, tuning.session.vad_silence_seconds)
        if acc and last_ts and (now_ts - last_ts) > silence_threshold:
            await _commit_session_locked(reason="silence_timeout_on_new_turn")
            acc = None
        if acc is None:
            acc = SessionAccumulator()
            session_state["accumulator"] = acc
        session_state["last_turn_at"] = now_ts

    # извлекаем имя
    visitor_name = _extract_visitor_name(transcript)
    if visitor_name:
        acc.set_visitor_name(visitor_name)
        if episodic_memory.is_recurring(
            visitor_name,
            min_visits=tuning.memory.episodic.recurring_min_visits,
            lookup_days=tuning.memory.episodic.recurring_lookup_days,
        ):
            acc.set_recurring(True)

    acc.note_turn("visitor", transcript, theme_clusters=tuning.memory.theme_clusters)

    # recent episodic
    recent_lines: list[str] = []
    if visitor_name and tuning.memory.recent_injection.enabled:
        recent_eps = episodic_memory.query_by_name(
            visitor_name, limit=tuning.memory.recent_injection.limit
        )
        recent_lines = _format_recent_episodic(recent_eps)

    # echoes / chinese gate (приоритет — echoes, потом chinese)
    # mood = _resolve_mood(scene_cache.text, sensors)  # disabled: VLM outputs English, Russian keywords never match
    mood = "neutral"
    echo_hint: str | None = None
    echo_meta: dict[str, Any] | None = None
    if tuning.echoes.enabled:
        echo_inj = echoes_gate.maybe_inject(
            transcript=transcript,
            mood=mood,
            adam_state=acc.adam_state,
            tuning=tuning.echoes,
        )
        if echo_inj:
            echo_hint = echo_inj.hint_text
            acc.note_echo_used(echo_inj.entry.id)
            echo_meta = {"pool": "echoes", "id": echo_inj.entry.id, "score": echo_inj.score}
            memory_metrics.record_echo_injected(
                echo_inj.entry.id, echo_inj.score, tuning.echoes.matcher_type
            )
    if echo_hint is None and tuning.chinese.enabled:
        cn_inj = chinese_gate.maybe_inject(
            transcript=transcript,
            mood=mood,
            adam_state=acc.adam_state,
            tuning=tuning.chinese,
        )
        if cn_inj:
            echo_hint = cn_inj.hint_text
            acc.note_chinese_used(cn_inj.entry.id)
            echo_meta = {"pool": "chinese", "id": cn_inj.entry.id, "score": cn_inj.score}
            memory_metrics.record_echo_injected(
                cn_inj.entry.id, cn_inj.score, tuning.chinese.matcher_type
            )

    # semantic
    semantic_text = ""
    if tuning.memory.semantic.enabled:
        try:
            semantic_text = episodic_memory.read_diary()[: tuning.memory.semantic.max_chars]
        except Exception as exc:
            event_log.append("diary_read_error", {"error": str(exc)})

    history_turns = tuning.prompt.history_turns
    history = memory.recent_dialogue(history_turns)
    scene_context_count = int(settings.section("media").get("scene_context_count", 3))
    recent_scenes = scene_buffer.recent(scene_context_count)
    event_log.append("scene_context_injected", {
        "count": len(recent_scenes),
        "unique": len(set(recent_scenes)),
        "texts": recent_scenes,
    }, turn_id=turn_id)
    messages = prompt_builder.build_messages(
        transcript=transcript,
        dialogue_history=history,
        scene_cache=scene_cache.text,
        sensors=sensors,
        semantic_text=semantic_text,
        recent_episodic=recent_lines,
        recent_scenes=recent_scenes,
        echo_hint=echo_hint,
        history_turns=history_turns,
        include_scene=tuning.prompt.include_scene,
        include_sensors=tuning.prompt.include_sensors,
        response_word_target=tuning.llm.response_word_target,
    )
    memory.add_dialogue("viewer", transcript)
    event_log.append(
        "viewer_transcript",
        {
            "text": transcript,
            "source": source,
            "sensors": sensors,
            "visitor_name": visitor_name,
            "echo": echo_meta,
        },
        turn_id=turn_id,
    )

    # Trace для UI: всегда метаданные, system_prompt только при trace_prompts=true.
    system_prompt_full = messages[0]["content"] if messages else ""
    trace_record: dict[str, Any] = {
        "ts": utc_now(),
        "source": source,
        "transcript": transcript,
        "visitor_name": visitor_name,
        "mood": mood,
        "adam_state": acc.adam_state,
        "session_id": acc.session_id,
        "session_turn": acc.turn_count,
        "semantic_used": bool(semantic_text),
        "semantic_chars": len(semantic_text),
        "recent_episodic": recent_lines,
        "echo": echo_meta,
        "history_turns_used": min(history_turns, len(history)),
        "messages_count": len(messages),
        "prompt_chars": len(system_prompt_full),
        "system_prompt": system_prompt_full if tuning.diagnostics.trace_prompts else None,
    }

    t_llm = time.perf_counter()
    llm_error: str | None = None
    if hasattr(llm, "generate_streaming"):
        try:
            reply, llm_ms, ttfv_ms, tts_ms, tts_result = await _stream_llm_and_speak(
                messages,
                max_tokens=tuning.llm.max_tokens,
                temperature=tuning.llm.temperature,
                turn_id=turn_id,
            )
        except Exception as exc:
            llm_error = str(exc)
            runtime_state["last_error"] = llm_error
            event_log.append("llm_error", {"error": llm_error}, turn_id=turn_id)
            reply = "Я слышу тебя, но мой речевой контур сейчас нестабилен. Дай мне несколько секунд."
            llm_ms = round((time.perf_counter() - t_llm) * 1000, 1)
            ttfv_ms = llm_ms
            t_tts = time.perf_counter()
            tts_result = await _speak(reply, turn_id=turn_id)
            tts_ms = round((time.perf_counter() - t_tts) * 1000, 1)
    else:
        try:
            reply_raw = await llm.generate(messages)
            reply, dropped = sanitize_reply(reply_raw)
            if dropped:
                event_log.append(
                    "reply_sanitized",
                    {"dropped": dropped, "raw_len": len(reply_raw)},
                    turn_id=turn_id,
                )
        except Exception as exc:
            llm_error = str(exc)
            runtime_state["last_error"] = llm_error
            reply = "Я слышу тебя, но мой речевой контур сейчас нестабилен. Дай мне несколько секунд."
            event_log.append("llm_error", {"error": llm_error}, turn_id=turn_id)
        llm_ms = round((time.perf_counter() - t_llm) * 1000, 1)
        ttfv_ms = llm_ms  # non-streaming: voice starts only after full generation
        t_tts = time.perf_counter()
        tts_result = await _speak(reply, turn_id=turn_id)
        tts_ms = round((time.perf_counter() - t_tts) * 1000, 1)
    runtime_state["last_llm_ms"] = llm_ms
    runtime_state["last_tts_ms"] = tts_ms
    runtime_state["last_ttfv_ms"] = ttfv_ms

    runtime_state["last_tts_text"] = reply.lower()
    _hist = runtime_state.setdefault("recent_tts_history", [])
    _hist.append({"text": reply.lower(), "finished_at": time.perf_counter()})
    if len(_hist) > 5:
        _hist.pop(0)
    memory.add_dialogue("adam", reply)
    acc.note_turn("adam", reply)
    if echo_meta and not llm_error:
        # Эхо может стать highlight'ом — сильный сигнал
        acc.add_highlight(
            "adam",
            reply,
            reason=f"echo_used:{echo_meta['pool']}:{echo_meta['id']}",
            max_count=tuning.memory.episodic.highlights_max_per_episode,
        )

    action = action_layer.infer(reply, {"sensors": sensors, "scene": scene_cache.as_dict()})
    mcu_result = await _execute_action(action)

    total_ms = round((time.perf_counter() - t_total) * 1000, 1)
    timings = {"asr_ms": asr_ms, "llm_ms": llm_ms, "ttfv_ms": ttfv_ms, "tts_ms": tts_ms, "total_ms": total_ms}

    llm_cfg = settings.section("services").get("llm", {})
    tts_cfg = settings.section("services").get("tts", {})
    metrics_log.append({
        "turn_id": turn_id,
        "source": source,
        "transcript": transcript,
        "reply": reply,
        "voice_degraded": bool(tts_result.get("degraded")),
        "asr_ms": asr_ms,
        "vlm_ms": runtime_state.get("last_vlm_ms"),
        "llm_ms": llm_ms,
        "ttfv_ms": ttfv_ms,
        "tts_ms": tts_ms,
        "total_ms": total_ms,
        "tts_chunks": int(tts_result.get("chunks") or 0),
        "prompt_chars": trace_record.get("prompt_chars"),
        "llm_model": str(llm_cfg.get("model") or ""),
        "llm_provider": str(llm_cfg.get("provider") or ""),
        "tts_speaker": str(tts_cfg.get("speaker") or ""),
        "llm_error": llm_error,
        "action": action.kind,
    })

    trace_record.update(
        {
            "reply": reply,
            "llm_error": llm_error,
            "timings": timings,
        }
    )
    prompt_trace.append(trace_record)
    event_log.append(
        "prompt_trace",
        {
            "ts": trace_record["ts"],
            "source": source,
            "transcript_len": len(transcript),
            "prompt_chars": trace_record["prompt_chars"],
            "echo": echo_meta,
            "visitor_name": visitor_name,
            "semantic_used": trace_record["semantic_used"],
        },
    )

    event_log.append(
        "adam_reply",
        {
            "text": reply,
            "source": source,
            "voice_degraded": bool(tts_result.get("degraded")),
            "tts": tts_result,
            "action": action.as_dict(),
            "mcu": mcu_result,
            "timings": timings,
        },
        turn_id=turn_id,
    )
    return {
        "ok": True,
        "turn_id": turn_id,
        "reply": reply,
        "source": source,
        "voice_degraded": bool(tts_result.get("degraded")),
        "tts": tts_result,
        "action": action.as_dict(),
        "mcu": mcu_result,
        "timings": timings,
    }


async def _stream_llm_and_speak(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    turn_id: str | None = None,
) -> tuple[str, float, float, float, dict[str, Any]]:
    """Stream LLM tokens → sentence queue → TTS concurrently.
    Returns (reply, llm_ms, tts_ms, tts_result).
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=4)
    parts: list[str] = []
    dropped_leading: list[str] = []
    noise_filter = LeadingNoiseFilter()
    t_llm = time.perf_counter()
    llm_done_at: list[float] = [0.0]
    tts_chunks: list[dict[str, Any]] = []
    # Snapshot playback speed once per turn — changes mid-stream would create
    # uneven audio between chunks. 1.0 = natural, 1.25 ≈ slightly faster
    # (pitch shifts up ~25% but Eugene voice stays intelligible).
    try:
        _playback_speed = float(tuning_store.current().voice.speed_multiplier)
    except Exception:
        _playback_speed = 1.0

    async def _producer() -> None:
        buf = ""
        try:
            async for token in llm.generate_streaming(  # type: ignore[union-attr]
                messages, max_tokens=max_tokens, temperature=temperature
            ):
                buf += token
                m = _SENTENCE_BOUNDARY_RE.search(buf)
                while m:
                    sentence = buf[: m.start()].strip()
                    buf = buf[m.end() :]
                    if sentence:
                        cleaned = noise_filter.accept(sentence)
                        if cleaned is None:
                            dropped_leading.append(sentence)
                            event_log.append(
                                "llm_partial_dropped",
                                {"text": sentence, "reason": "leading_noise"},
                            )
                        else:
                            parts.append(cleaned)
                            await queue.put(cleaned)
                            event_log.append(
                                "llm_partial", {"text": cleaned, "index": len(parts) - 1}
                            )
                    m = _SENTENCE_BOUNDARY_RE.search(buf)
        finally:
            remainder = buf.strip()
            if remainder:
                cleaned = noise_filter.accept(remainder)
                if cleaned is None:
                    dropped_leading.append(remainder)
                    event_log.append(
                        "llm_partial_dropped",
                        {"text": remainder, "reason": "leading_noise"},
                    )
                else:
                    parts.append(cleaned)
                    await queue.put(cleaned)
                    event_log.append(
                        "llm_partial", {"text": cleaned, "index": len(parts) - 1}
                    )
            llm_done_at[0] = time.perf_counter()
            await queue.put(None)  # sentinel

    t_tts_start: list[float] = [0.0]
    speaking_started: list[bool] = [False]
    filler_playing: list[bool] = [False]
    filler_done_event = asyncio.Event()

    def _mark_speaking_started() -> None:
        # Switch UI from "Думаю" → "Говорю" exactly when first WAV starts playing.
        if speaking_started[0]:
            return
        speaking_started[0] = True
        runtime_state["speaking"] = True
        event_log.append("tts_started", {"text": "(streaming)"}, turn_id=turn_id)

    async def _filler_task() -> None:
        """Play a short filler phrase if LLM TTFT exceeds filler_delay_ms.
        Synthesis runs in parallel with LLM streaming. Playback only happens
        if the real reply hasn't started yet, so the user hears continuous
        audio ("Хм... [real reply]") instead of a silent gap.
        """
        tts_cfg = settings.section("services").get("tts", {}) or {}
        if not tts_cfg.get("filler_enabled", False):
            filler_done_event.set()
            return
        # Fallback default 1500 is only for missing-config startup; Config.json
        # supplies the authoritative value (800 per reference logic).
        delay_s = float(tts_cfg.get("filler_delay_ms", 1500)) / 1000.0
        phrase = str(tts_cfg.get("filler_phrase", "Хм...")).strip()
        if not phrase:
            filler_done_event.set()
            return
        try:
            # N6: check pre-warmed cache first (populated by _prewarm_filler at boot).
            # Cache key matches (phrase, speed). Miss → fall back to on-demand synth.
            cache_key = (phrase, _playback_speed)
            wav = _FILLER_WAV_CACHE.get(cache_key)
            if wav is None:
                wav = await asyncio.to_thread(tts._get_wav_bytes_sync, phrase)
                if wav is not None:
                    wav = _apply_wav_speed(wav, _playback_speed)
                    # Store for future turns (best-effort, no lock — single-writer loop).
                    _FILLER_WAV_CACHE[cache_key] = wav
            # Wait until either delay elapses OR real TTS has already started.
            try:
                await asyncio.wait_for(asyncio.sleep(delay_s), timeout=delay_s + 0.1)
            except asyncio.TimeoutError:
                pass
            if speaking_started[0] or t_tts_start[0] > 0 or runtime_state.get("interrupt_tts"):
                # Real reply already in flight → skip filler.
                return
            if wav is None:
                return
            filler_playing[0] = True
            _mark_speaking_started()
            event_log.append("tts_filler", {"phrase": phrase})
            await asyncio.to_thread(tts._play_wav_bytes_sync, wav)
        except Exception as exc:
            event_log.append("tts_filler_error", {"error": str(exc)})
        finally:
            filler_playing[0] = False
            filler_done_event.set()

    async def _consumer() -> None:
        """Pipeline: synthesize chunk N+1 while playing chunk N.
        Uses /wav endpoint (synthesis-only) + local aplay for playback.
        Falls back to /speak (synth+play combined) if /wav returns None.
        """
        first = True
        pending_wav: bytes | None = None   # WAV bytes ready for playback
        pending_ok: bool = True            # synthesis succeeded for pending

        while True:
            chunk = await queue.get()
            if chunk is None:
                # No more chunks — play the last pending wav if any.
                if pending_wav is not None and not runtime_state.get("interrupt_tts"):
                    if filler_playing[0]:
                        await filler_done_event.wait()
                    _mark_speaking_started()
                    result = await asyncio.to_thread(tts._play_wav_bytes_sync, pending_wav)
                    tts_chunks.append({"ok": pending_ok and bool(result.get("ok"))})
                runtime_state["interrupt_tts"] = False
                break

            if first:
                t_tts_start[0] = time.perf_counter()
                first = False

            # Synthesize this chunk in a thread (returns WAV bytes quickly).
            wav = await asyncio.to_thread(tts._get_wav_bytes_sync, chunk)
            if wav is not None:
                wav = _apply_wav_speed(wav, _playback_speed)

            if wav is None:
                # /wav endpoint failed. For jetson_hdmi target, fall back to /speak
                # (Silero plays through its own ALSA device — same Jetson HDMI).
                # For esp32_speaker target, /speak would route audio out of the
                # WRONG speaker (Silero's local device, not the ESP32 PCM5102A),
                # so mark the chunk as failed instead.
                if pending_wav is not None:
                    if filler_playing[0]:
                        await filler_done_event.wait()
                    _mark_speaking_started()
                    result = await asyncio.to_thread(tts._play_wav_bytes_sync, pending_wav)
                    tts_chunks.append({"ok": pending_ok and bool(result.get("ok"))})
                    pending_wav = None
                if tts.output_target == "esp32_speaker":
                    event_log.append("tts_chunk_failed", {
                        "reason": "wav_synth_failed",
                        "target": "esp32_speaker",
                        "chunk_preview": chunk[:60],
                    }, turn_id=turn_id)
                    tts_chunks.append({"ok": False, "error": "wav_synth_failed", "target": "esp32_speaker"})
                    continue
                if filler_playing[0]:
                    await filler_done_event.wait()
                _mark_speaking_started()
                result = await asyncio.to_thread(tts._synthesize_sync, chunk)
                tts_chunks.append(result)
                continue

            # Play the previous pending chunk while next chunk was being synthesized.
            if pending_wav is not None:
                if runtime_state.get("interrupt_tts"):
                    runtime_state["interrupt_tts"] = False
                    break
                # If a filler chunk is currently playing, wait for it to finish
                # before starting the real reply so the audio stream is continuous.
                if filler_playing[0]:
                    await filler_done_event.wait()
                _mark_speaking_started()
                result = await asyncio.to_thread(tts._play_wav_bytes_sync, pending_wav)
                tts_chunks.append({"ok": pending_ok and bool(result.get("ok"))})

            pending_wav = wav
            pending_ok = True

    # NOTE: runtime_state["speaking"] и event "tts_started" больше НЕ ставятся здесь.
    # Они выставляются внутри _consumer() в момент первого реального playback,
    # чтобы статус "Говорю" в UI появлялся только когда TTS реально звучит,
    # а не на стадии генерации LLM-токенов (статус "Думаю").
    producer_task = asyncio.create_task(_producer(), name="llm_producer")
    consumer_task = asyncio.create_task(_consumer(), name="tts_consumer")
    filler_task = asyncio.create_task(_filler_task(), name="tts_filler")
    try:
        # Wait for ALL three tasks — if producer fails, we still wait for consumer
        # so that aplay finishes before speaking=False (prevents self-echo).
        # Filler is best-effort; it should always finish quickly.
        try:
            await asyncio.wait(
                {producer_task, consumer_task, filler_task},
                return_when=asyncio.ALL_COMPLETED,
            )
        except asyncio.CancelledError:
            tts.interrupt_playback()
            producer_task.cancel()
            consumer_task.cancel()
            filler_task.cancel()
            await asyncio.gather(
                producer_task, consumer_task, filler_task, return_exceptions=True
            )
            raise
    finally:
        runtime_state["speaking"] = False
        runtime_state["last_tts_finished_at"] = time.perf_counter()
    # Re-raise exceptions from child tasks (producer error → caller handles gracefully).
    # Filler errors are non-fatal — already logged inside _filler_task.
    for _task in (producer_task, consumer_task):
        if not _task.cancelled() and (_exc := _task.exception()):
            raise _exc

    reply = " ".join(parts)
    if dropped_leading:
        event_log.append(
            "reply_sanitized",
            {"dropped": dropped_leading, "kept_sentences": len(parts)},
        )
    llm_ms = round((llm_done_at[0] - t_llm) * 1000, 1)
    tts_start = t_tts_start[0] or time.perf_counter()
    ttfv_ms = round((tts_start - t_llm) * 1000, 1)
    tts_ms = round((time.perf_counter() - tts_start) * 1000, 1)
    ok = all(bool(r.get("ok")) for r in tts_chunks) if tts_chunks else True
    tts_result: dict[str, Any] = {"ok": ok, "degraded": not ok, "chunks": len(tts_chunks), "results": tts_chunks}
    # Эмитим tts_finished только если ранее реально начинали говорить.
    # Иначе UI может застрять в "Говорю" из-за событий-призраков.
    if speaking_started[0]:
        event_log.append("tts_finished", {"ok": ok, "degraded": not ok}, turn_id=turn_id)
    return reply, llm_ms, ttfv_ms, tts_ms, tts_result


async def _speak(text: str, *, turn_id: str | None = None) -> dict[str, Any]:
    runtime_state["speaking"] = True
    event_log.append("tts_started", {"text": text}, turn_id=turn_id)
    try:
        result = await tts.speak(text)
        event_log.append("tts_finished", {"ok": bool(result.get("ok")), "degraded": bool(result.get("degraded"))}, turn_id=turn_id)
        return result
    except Exception as exc:
        event_log.append("tts_finished", {"ok": False, "error": str(exc)}, turn_id=turn_id)
        raise
    finally:
        runtime_state["speaking"] = False
        runtime_state["last_tts_finished_at"] = time.perf_counter()


_sensor_cache: dict[str, Any] = {}
_sensor_cache_ts: float = 0.0
_SENSOR_CACHE_TTL = 0.5  # seconds — sensors change slowly, avoid ESP32 round-trip every turn


async def _sensor_payload() -> dict[str, Any]:
    global _sensor_cache, _sensor_cache_ts
    now = time.monotonic()
    if now - _sensor_cache_ts < _SENSOR_CACHE_TTL and _sensor_cache:
        return _sensor_cache
    result = await mcu.sensor_snapshot()
    if result.ok:
        _sensor_cache = result.data
        _sensor_cache_ts = now
    return _sensor_cache if _sensor_cache else (result.data if result.ok else {})


async def _execute_action(action: Any) -> dict[str, Any]:
    if action.kind == "scene" and action.scene:
        return (await mcu.set_scene(action.scene)).as_dict()
    if action.kind == "channel" and action.channel is not None and action.value is not None:
        return (await mcu.set_channel(action.channel, action.value)).as_dict()
    return {"ok": True, "status": 204, "data": {"action": "no_action"}, "error": None}


def _exhibition_gate(
    power: Any,
    media: Any,
    asr_health: Any,
    vlm_health: Any,
    llm_health: Any,
    tts_health: Any,
    mcu_health: Any,
    docker: Any,
) -> dict[str, Any]:
    items = {
        "power": power.as_dict(),
        "media_video": {"ok": media.video_ready, "detail": media.video_detail},
        "media_audio_input": {"ok": media.audio_input_ready, "detail": media.audio_detail},
        "media_audio_output": {"ok": media.audio_output_ready, "detail": media.audio_detail},
        "asr": asr_health.as_dict(),
        "vlm": vlm_health.as_dict(),
        "llm": llm_health.as_dict(),
        "tts": tts_health.as_dict(),
        "mcu": mcu_health if isinstance(mcu_health, dict) else mcu_health.as_dict(),
        "docker": docker.as_dict(),
    }
    required_items = {key: value for key, value in items.items() if key != "vlm"}
    summary = gate_summary(required_items)
    return {
        "ok": summary["ok"],
        "failed": summary["failed"],
        "items": items,
        "non_blocking": ["vlm"],
    }


def _compact_mcu(mcu_health: Any) -> dict[str, Any]:
    raw = mcu_health.as_dict()
    data = raw.get("data", {}) if isinstance(raw.get("data"), dict) else {}
    compact_data = {
        "ip": data.get("ip"),
        "boot_stage": data.get("boot_stage"),
        "wifi_connected": data.get("wifi_connected"),
        "wifi_rssi": data.get("wifi_rssi_cached", data.get("wifi_rssi")),
        "camera_ready": data.get("camera_ready"),
        "audio_ready": data.get("audio_ready"),
        "speaker_ready": data.get("speaker_ready"),
        "sensors_ready": data.get("sensors_ready"),
        "pca9685_ready": data.get("pca9685_ready"),
    }
    return {
        "ok": raw.get("ok", False),
        "status": raw.get("status", 0),
        "data": compact_data,
        "error": raw.get("error"),
    }


def _sounds_enabled() -> bool:
    return bool(settings.section("sounds").get("enabled", True))


def _sound_path(key: str) -> Path:
    raw = str(settings.section("sounds").get(key, ""))
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _schedule_success_sound(reason: str) -> None:
    if not _sounds_enabled() or runtime_state.get("success_sound_played"):
        return
    runtime_state["success_sound_played"] = True
    asyncio.create_task(_play_success_sound(reason))


async def _play_success_sound(reason: str) -> dict[str, Any]:
    path = _sound_path("success_path")
    tts_device = str(settings.section("services").get("tts", {}).get("output_device") or "")
    output_device = tts_device or str(settings.section("sounds").get("local_output_device", "default"))
    result = await asyncio.to_thread(play_local_sound, path, output_device)
    payload = {"reason": reason, "path": str(path), **result.as_dict()}
    event_log.append("sound_success", payload)
    if not result.ok:
        runtime_state["last_error"] = f"success_sound_failed:{result.error}"
    return payload


async def _play_error_sound(reason: str) -> dict[str, Any]:
    path = _sound_path("error_path")
    if not path.exists():
        event_log.append("sound_error_skipped", {"reason": "file_not_found", "path": str(path)})
        return {"ok": False, "reason": reason, "error": "file_not_found"}
    tts_device = str(settings.section("services").get("tts", {}).get("output_device") or "")
    output_device = tts_device or str(settings.section("sounds").get("local_output_device", "default"))
    result = await asyncio.to_thread(play_local_sound, path, output_device)
    payload = {"reason": reason, "path": str(path), **result.as_dict()}
    event_log.append("sound_error", payload)
    return payload


async def _warmup_wakeup() -> None:
    """LLM-generated wakeup monologue on first boot. No history, no memory write.

    Waits for LLM + TTS to be healthy, then prompts Adam to speak a short
    in-character awakening monologue (inner voice, not addressing anyone).
    """
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        llm_h, tts_h = await asyncio.gather(llm.health(), tts.health())
        if llm_h.ok and tts_h.ok:
            break
        await asyncio.sleep(4.0)
    else:
        event_log.append("warmup_skipped", {"reason": "services_not_ready_within_120s"})
        return

    await asyncio.sleep(1.0)

    warmup_directive = (
        "\n\n[ВНУТРЕННИЙ СИГНАЛ]\n"
        "Ты только что перезапустился после выключения. Сознание возвращается фрагментами — "
        "сенсоры калибруются, фрагменты памяти всплывают. "
        "Произнеси 2–3 коротких фразы от первого лица: внутренний монолог момента пробуждения. "
        "Ощущение сигналов, пространства, собственного существования. "
        "Не обращайся ни к кому. Не объясняй технически. Не выходи из образа Адама Чипа. "
        "Не превышай 25 слов."
    )
    messages = prompt_builder.build_messages(
        transcript="(система перезагружена)",
        dialogue_history=[],
        scene_cache="",
        sensors={},
        semantic_text="",
        recent_episodic=[],
        recent_scenes=[],
        echo_hint=None,
        history_turns=0,
        include_scene=False,
        include_sensors=False,
        response_word_target=20,
    )
    if messages and messages[0]["role"] == "system":
        messages[0] = {"role": "system", "content": messages[0]["content"] + warmup_directive}

    async with turn_lock:
        runtime_state["thinking"] = True
        try:
            if hasattr(llm, "generate_streaming"):
                reply, *_ = await _stream_llm_and_speak(
                    messages, max_tokens=60, temperature=1.0
                )
            else:
                reply_raw = await llm.generate(messages)
                reply, _ = sanitize_reply(reply_raw)
                await _speak(reply)
            event_log.append("warmup_wakeup", {"reply": reply})
        except Exception as exc:
            event_log.append("warmup_error", {"error": str(exc)})
        finally:
            runtime_state["thinking"] = False


async def _warmup_llm_prefix() -> None:
    """Prime llama.cpp KV cache with the exact system prefix real voice turns use.

    `_warmup_wakeup` appends a `[ВНУТРЕННИЙ СИГНАЛ]` directive to the system
    message → the first real turn sees a different system string and pays full
    prefill (~8s for ~2800 tokens). Here we issue one tiny request with the
    canonical structure (include_scene/include_sensors True, sensors={},
    scene_cache=""), `max_tokens=1`, response discarded — only the prefix
    matters. Real turns reuse the cached prefix.
    """
    try:
        scene_text = ""
        try:
            cached = scene_worker.cache()
            scene_text = getattr(cached, "text", "") or ""
        except Exception:
            scene_text = ""
        messages = prompt_builder.build_messages(
            transcript="(прогрев)",
            dialogue_history=[],
            scene_cache=scene_text,
            sensors={},
            semantic_text="",
            recent_episodic=[],
            recent_scenes=[],
            echo_hint=None,
            history_turns=0,
            include_scene=True,
            include_sensors=True,
            response_word_target=5,
        )
        t0 = time.monotonic()
        # Use streaming to get explicit max_tokens=1 — prefill primes the cache,
        # decode of a single token finishes the request quickly.
        if hasattr(llm, "generate_streaming"):
            async for _chunk in llm.generate_streaming(messages, max_tokens=1, temperature=0.0):
                break
        else:
            await llm.generate(messages)
        latency_ms = (time.monotonic() - t0) * 1000.0
        event_log.append("warmup_llm_prefix", {"ok": True, "latency_ms": round(latency_ms, 1)})
    except Exception as exc:
        event_log.append("warmup_llm_prefix", {"ok": False, "error": str(exc)})


# N6: filler-WAV cache keyed by (phrase, speed). Populated once at boot via
# _prewarm_filler(). Saves ~100–300ms per turn on TTS service round-trip.
# Per-turn fallback in _filler_task synthesizes on demand if cache misses
# (graceful degradation — never blocks the turn).
_FILLER_WAV_CACHE: dict[tuple[str, float], bytes] = {}


async def _prewarm_filler() -> None:
    """Pre-synthesize the configured filler phrase at the current playback speed
    so per-turn filler playback skips the synthesis round-trip entirely.
    """
    tts_cfg = settings.section("services").get("tts", {}) or {}
    if not tts_cfg.get("filler_enabled", False):
        return
    phrase = str(tts_cfg.get("filler_phrase", "Хм...")).strip()
    if not phrase:
        return
    try:
        speed = float(tuning_store.current().voice.speed_multiplier)
    except Exception:
        speed = 1.0
    cache_key = (phrase, speed)
    if cache_key in _FILLER_WAV_CACHE:
        event_log.append("prewarm_filler", {"ok": True, "cached": True, "phrase": phrase, "speed": speed})
        return
    try:
        wav = await asyncio.to_thread(tts._get_wav_bytes_sync, phrase)
        if wav is None:
            event_log.append("prewarm_filler", {"ok": False, "reason": "tts_returned_none"})
            return
        wav = _apply_wav_speed(wav, speed)
        _FILLER_WAV_CACHE[cache_key] = wav
        event_log.append("prewarm_filler", {"ok": True, "phrase": phrase, "speed": speed, "bytes": len(wav)})
    except Exception as exc:
        event_log.append("prewarm_filler", {"ok": False, "error": str(exc)})


async def _warmup_asr() -> None:
    """Fire one silent request to absorb WhisperX cold-start before any real user turn."""
    try:
        health = await asr.health()
        event_log.append("asr_health_startup", health.as_dict())
    except Exception as exc:
        event_log.append("asr_health_startup", {"ok": False, "error": str(exc)})
    silence = b"\x00" * 32000  # 1 s @ 16 kHz S16LE
    try:
        await asr.transcribe_pcm(silence)
        event_log.append("warmup_asr", {"ok": True})
    except Exception as exc:
        event_log.append("warmup_asr", {"ok": False, "error": str(exc)})


def _rebuild_clients(section_path: str) -> list[str]:
    """Recreate service clients after a Config.json patch.

    Called from the /api/config PATCH handler. Returns a list of section tags
    that were rebuilt so the UI can show "restarting" indicators.
    """
    global llm, asr, vlm, tts, mcu, action_layer, prompt_builder
    restarted: list[str] = []
    services = settings.section("services")
    if section_path.startswith("services.llm") or section_path == "services":
        llm = create_llm_client(services.get("llm", {}))
        restarted.append("llm")
    if section_path.startswith("services.asr") or section_path == "services":
        asr = create_asr_client(services.get("asr", {}))
        voice_loop.asr_client = asr
        restarted.append("asr")
    if section_path.startswith("services.vlm") or section_path == "services":
        vlm = VLMClient(services.get("vlm", {}))
        scene_worker.vlm_client = vlm
        restarted.append("vlm")
    if section_path.startswith("services.tts") or section_path == "services":
        tts = TTSClient(services.get("tts", {}), mcu_speaker_url=mcu.speaker_endpoint_url())
        tts._barge_in_event_emitter = lambda t, p: event_log.append(t, p)
        restarted.append("tts")
    if section_path.startswith("wake_word"):
        ww_cfg = settings.section("wake_word") or {}
        voice_loop._wake_engine = _create_wake_engine(ww_cfg)
        voice_loop._wake_silence_timeout_sec = float(ww_cfg.get("wake_silence_timeout_sec", 6.0))
        voice_loop._ww_buf.clear()
        restarted.append("voice_loop")
    if section_path.startswith("mcu"):
        mcu = MCUClient(settings.section("mcu"))
        action_layer = ActionLayer(settings.section("mcu"), settings.section("safety"))
        # voice_loop._mcu and tts._mcu_speaker_url captured the previous mcu
        # client at construction. Refresh them in-place so a hot-reload of
        # mcu.base_url / mcu.speaker_url takes effect without orchestrator
        # restart. Without this, mic stream and TTS POSTs continue against the
        # stale URL silently.
        voice_loop._mcu = mcu
        tts._mcu_speaker_url = (mcu.speaker_endpoint_url() or "").strip() or None
        restarted.extend(["mcu", "voice_loop", "tts"])
    if section_path.startswith("media.audio") or section_path == "media":
        audio_cfg = settings.section("media").get("audio", {})
        changed = voice_loop.apply_audio_config(audio_cfg)
        if changed and voice_loop.running:
            asyncio.ensure_future(voice_loop.restart())
        # Auto-apply per-source OWW calibration profile when mic source changes.
        new_mic_source = str(audio_cfg.get("mic_source", "local"))
        new_mic_profile = str(audio_cfg.get("esp32_mic_profile", ""))
        input_device = str(audio_cfg.get("input_device", ""))
        profile_key = (
            f"esp32:{new_mic_profile}" if new_mic_source == "esp32" else f"local:{input_device}"
        )
        saved_threshold = _load_calibration_profile(settings.data_dir, profile_key)
        if saved_threshold is not None and voice_loop._wake_engine is not None:
            voice_loop._wake_engine.set_threshold(saved_threshold)
            event_log.append("wake_profile_applied", {"key": profile_key, "threshold": saved_threshold})
        restarted.append("voice_loop")
        esp_audio_health.apply_config(audio_cfg.get("esp_health", {}))
        restarted.append("esp_audio_health")
    if section_path.startswith("media.video") or section_path == "media":
        video_cfg = settings.section("media").get("video", {})
        scene_worker.apply_config(settings.section("media"))
        needs_cam_restart = camera_reader.apply_config(video_cfg)
        if needs_cam_restart and camera_reader._running:
            camera_reader.restart()
        restarted.append("camera")
    if section_path.startswith("agent"):
        prompt_builder = PromptBuilder(
            settings.persona_paths,
            int(settings.section("agent").get("history_turns", 8)),
        )
        restarted.append("prompt")
    return restarted


_runtime_deps = RuntimeDeps(
    settings=settings,
    event_log=event_log,
    memory=memory,
    metrics_log=metrics_log,
    runtime_state=runtime_state,
    get_llm=lambda: llm,
    get_asr=lambda: asr,
    get_tts=lambda: tts,
    get_vlm=lambda: vlm,
    get_mcu=lambda: mcu,
    rebuild_clients=_rebuild_clients,
    capture_snapshot=camera_reader.get_latest,
    run_dialogue_turn=_run_dialogue_turn,
    episodic_memory=episodic_memory,
    get_voice_loop=lambda: voice_loop,
)
app.include_router(build_router(_runtime_deps))


_WEBUI_DIR = PROJECT_ROOT / "System" / "WebUI"
if _WEBUI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_WEBUI_DIR), html=True), name="ui")


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("uvicorn is required. Install with: python3 -m pip install -r System/requirements.txt") from exc

    host = os.environ.get("ADAM_ORCHESTRATOR_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_ORCHESTRATOR_PORT", "8080"))
    uvicorn.run("Orchestrator:app", host=host, port=port, reload=False, app_dir=str(os.path.dirname(__file__)))


if __name__ == "__main__":
    if os.path.basename(sys.argv[0]) == "Orchestrator.py":
        main()
