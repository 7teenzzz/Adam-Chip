#!/usr/bin/env python3
from __future__ import annotations

import audioop
import json
import os
import shutil
import sys
import asyncio
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    from fastapi import Body, FastAPI, HTTPException, Query, Request
    from fastapi.responses import HTMLResponse, RedirectResponse
except ImportError as exc:  # pragma: no cover - exercised only on missing runtime deps.
    raise SystemExit(
        "FastAPI is required for the orchestrator. Install with: "
        "python3 -m pip install -r System/requirements.txt"
    ) from exc

from adam.action import ActionLayer
from adam.config import Settings
from adam.device import MCUClient
from adam.events import EventLog, utc_now
from adam.inference import RivaASRClient, SceneCache, TTSClient, VLMClient, create_llm_client
from adam.media import MediaHealth
from adam.memory import MemoryStore
from adam.power import PowerGate
from adam.prompt import PromptBuilder
from adam.config import PROJECT_ROOT
from adam.sound import play_local_sound
from adam.system import docker_health, gate_summary
from adam.ui import agent_page, dash_page, debug_page


settings = Settings.load()
event_log = EventLog(settings.data_dir)
memory = MemoryStore(settings.data_dir)
power_gate = PowerGate(settings.section("power"))
media_health = MediaHealth(settings.section("media"))
mcu = MCUClient(settings.section("mcu"))
llm = create_llm_client(settings.section("services").get("llm", {}))
asr = RivaASRClient(settings.section("services").get("asr", {}))
vlm = VLMClient(settings.section("services").get("vlm", {}))
tts = TTSClient(settings.section("services").get("tts", {}))
scene_cache = SceneCache()
prompt_builder = PromptBuilder(
    settings.persona_paths,
    int(settings.section("agent").get("history_turns", 8)),
)
action_layer = ActionLayer(settings.section("mcu"), settings.section("safety"))

runtime_state: dict[str, Any] = {
    "mode": settings.mode,
    "speaking": False,
    "thinking": False,
    "last_error": None,
    "success_sound_played": False,
}

turn_lock = asyncio.Lock()


class VoiceLoopController:
    def __init__(self, audio_config: dict[str, Any], asr_client: RivaASRClient) -> None:
        self.audio_device = str(audio_config.get("input_device", "hw:0,0"))
        self.capture_device = self._capture_device_for(self.audio_device)
        self.sample_rate = int(audio_config.get("sample_rate", 16000))
        self.channels = int(audio_config.get("channels", 1))
        self.frame_ms = int(audio_config.get("frame_ms", 20))
        self.vad_threshold = int(audio_config.get("vad_threshold", 650))
        self.min_speech_ms = int(audio_config.get("min_speech_ms", 280))
        self.endpointing_ms = int(settings.section("services").get("asr", {}).get("endpointing_ms", 450))
        self.max_segment_ms = int(audio_config.get("max_segment_ms", 9000))
        self.asr_client = asr_client
        self._task: asyncio.Task[None] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self.running = False
        self.vad_state = "idle"
        self.last_transcript = ""
        self.last_transcript_at = ""
        self.last_asr_error = ""
        self.muted_by_tts = False

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "vad_state": self.vad_state,
            "last_transcript": self.last_transcript,
            "last_transcript_at": self.last_transcript_at,
            "muted_by_tts": self.muted_by_tts,
            "last_asr_error": self.last_asr_error,
            "audio_device": self.audio_device,
            "capture_device": self.capture_device,
            "sample_rate": self.sample_rate,
            "frame_ms": self.frame_ms,
        }

    async def start(self) -> dict[str, Any]:
        if self._task and not self._task.done():
            return {"ok": True, **self.status()}
        self.running = True
        self.last_asr_error = ""
        self._task = asyncio.create_task(self._run(), name="adam_voice_loop")
        await asyncio.sleep(0.2)
        if self._task.done():
            self.running = False
            return {"ok": False, **self.status()}
        event_log.append("voice_loop_started", self.status())
        return {"ok": True, **self.status()}

    async def stop(self) -> dict[str, Any]:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._stop_process()
        self.vad_state = "idle"
        event_log.append("voice_loop_stopped", self.status())
        return {"ok": True, **self.status()}

    async def _run(self) -> None:
        frame_bytes = max(2, int(self.sample_rate * self.channels * 2 * self.frame_ms / 1000))
        speech_frames: list[bytes] = []
        speech_ms = 0
        silence_ms = 0
        try:
            self._process = self._start_arecord()
            stdout = self._process.stdout
            if stdout is None:
                raise RuntimeError("arecord stdout unavailable")
            while self.running:
                chunk = await asyncio.to_thread(stdout.read, frame_bytes)
                if not chunk:
                    raise RuntimeError(f"arecord ended: {self._read_process_stderr()}")
                muted = bool(runtime_state.get("speaking")) and bool(settings.section("safety").get("half_duplex_mute", True))
                self.muted_by_tts = muted
                if muted:
                    speech_frames.clear()
                    speech_ms = 0
                    silence_ms = 0
                    self.vad_state = "muted"
                    continue

                level = audioop.rms(chunk, 2)
                voiced = level >= self.vad_threshold
                if voiced:
                    if not speech_frames:
                        event_log.append("asr_partial", {"state": "speech_started", "level": level})
                    speech_frames.append(chunk)
                    speech_ms += self.frame_ms
                    silence_ms = 0
                    self.vad_state = "speech"
                elif speech_frames:
                    speech_frames.append(chunk)
                    silence_ms += self.frame_ms
                    self.vad_state = "endpointing"
                else:
                    self.vad_state = "silence"

                if speech_frames and (silence_ms >= self.endpointing_ms or speech_ms >= self.max_segment_ms):
                    pcm = b"".join(speech_frames)
                    enough_speech = speech_ms >= self.min_speech_ms
                    speech_frames.clear()
                    speech_ms = 0
                    silence_ms = 0
                    if enough_speech:
                        await self._transcribe_and_dispatch(pcm)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.running = False
            self.vad_state = "error"
            self.last_asr_error = str(exc)
            runtime_state["last_error"] = f"voice_loop:{exc}"
            event_log.append("voice_loop_error", {"error": str(exc)})
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

    async def _transcribe_and_dispatch(self, pcm: bytes) -> None:
        self.vad_state = "transcribing"
        try:
            transcript = (await self.asr_client.transcribe_pcm(pcm)).strip()
        except Exception as exc:
            self.last_asr_error = str(exc)
            event_log.append("voice_loop_error", {"stage": "asr", "error": str(exc)})
            return
        if not transcript:
            return
        self.last_transcript = transcript
        self.last_transcript_at = utc_now()
        self.last_asr_error = ""
        event_log.append("asr_final", {"text": transcript, "source": "voice_loop"})
        await _run_dialogue_turn(transcript, "voice_loop")


class SceneWorker:
    def __init__(self, media_config: dict[str, Any], vlm_client: VLMClient) -> None:
        self.media_config = media_config
        self.vlm_client = vlm_client
        self.interval_sec = float(media_config.get("scene_interval_sec", 8))
        self.stale_after_sec = float(media_config.get("scene_stale_after_sec", 20))
        self.enabled = bool(media_config.get("scene_worker_enabled", True))
        self.running = False
        self.last_error = ""
        self._task: asyncio.Task[None] | None = None

    def status(self) -> dict[str, Any]:
        return {"running": self.running, "enabled": self.enabled, "last_error": self.last_error}

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
            try:
                jpeg = await asyncio.to_thread(self._capture_snapshot)
                summary = (await self.vlm_client.describe_jpeg(jpeg)).strip()
                updated = scene_cache.update(summary, {"source": "vlm", "updated_at": utc_now(), "stale": False})
                self.last_error = ""
                event_log.append("scene_updated", updated)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                stale = scene_cache.mark_stale(str(exc))
                event_log.append("scene_stale", stale)
            await asyncio.sleep(self.interval_sec)

    def _capture_snapshot(self) -> bytes:
        gst = shutil.which("gst-launch-1.0")
        if gst is None:
            raise RuntimeError("gst-launch-1.0 is not installed")
        video = self.media_config.get("video", {})
        pipeline = str(video.get("gstreamer_pipeline", ""))
        device = MediaHealth._extract_v4l2_device(pipeline) or "/dev/video0"
        target = settings.data_dir / "scene_snapshot.jpg"
        command = [
            gst,
            "-q",
            "v4l2src",
            f"device={device}",
            "num-buffers=1",
            "!",
            "image/jpeg",
            "!",
            "filesink",
            f"location={target}",
        ]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-300:] or "gstreamer snapshot failed")
        data = target.read_bytes()
        if not data:
            raise RuntimeError("empty gstreamer snapshot")
        return data


voice_loop = VoiceLoopController(settings.section("media").get("audio", {}), asr)
scene_worker = SceneWorker(settings.section("media"), vlm)


@asynccontextmanager
async def lifespan(_: FastAPI):
    power = power_gate.check()
    event_log.append("orchestrator_started", {"mode": runtime_state["mode"], "power": power.as_dict()})
    await scene_worker.start()
    if runtime_state["mode"] == "exhibition" and settings.section("power").get("enforce_in_exhibition", True):
        status_payload = await _status_payload()
        gate = status_payload["exhibition_gate"]
        if not gate["ok"]:
            runtime_state["mode"] = "maintenance"
            event_log.append("exhibition_gate_failed", gate)
            raise RuntimeError(f"exhibition mode gate failed: {gate['failed']}")
        _schedule_success_sound("startup_exhibition_gate_ok")
        await voice_loop.start()
    try:
        yield
    finally:
        await voice_loop.stop()
        await scene_worker.stop()


app = FastAPI(title="Adam Chip Orchestrator", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse("/dash", status_code=307)


@app.get("/agent", response_class=HTMLResponse)
async def agent() -> str:
    return agent_page()


@app.get("/dash", response_class=HTMLResponse)
async def dash() -> str:
    return dash_page(_ui_settings_public())


@app.get("/debug", response_class=HTMLResponse)
async def debug() -> str:
    return debug_page(_ui_settings_public())


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
        "scene_cache": scene_cache.as_dict(),
        "scene_worker": scene_worker.status(),
        "mcu": mcu_public,
    }


@app.get("/api/agent/gate")
async def gate() -> dict[str, Any]:
    status_payload = await _status_payload()
    return status_payload["exhibition_gate"]


@app.get("/api/agent/events")
async def events(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    return {"events": event_log.tail(limit)}


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


@app.post("/api/agent/turn")
async def dialogue_turn(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    transcript = str(payload.get("transcript", "")).strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript is required")
    return await _run_dialogue_turn(transcript, "manual")

async def _run_dialogue_turn(transcript: str, source: str) -> dict[str, Any]:
    if turn_lock.locked() and source == "voice_loop":
        event_log.append("voice_loop_error", {"stage": "turn", "error": "turn_already_in_progress", "text": transcript})
        return {"ok": False, "error": "turn_already_in_progress"}

    async with turn_lock:
        runtime_state["thinking"] = True
        try:
            return await _run_dialogue_turn_locked(transcript, source)
        finally:
            runtime_state["thinking"] = False


async def _run_dialogue_turn_locked(transcript: str, source: str) -> dict[str, Any]:
    sensors = await _sensor_payload()
    history = memory.recent_dialogue(int(settings.section("agent").get("history_turns", 8)))
    messages = prompt_builder.build_messages(
        transcript=transcript,
        dialogue_history=history,
        memory_summary=memory.summary_text(),
        scene_cache=scene_cache.text,
        sensors=sensors,
    )
    memory.add_dialogue("viewer", transcript)
    event_log.append("viewer_transcript", {"text": transcript, "source": source, "sensors": sensors})

    try:
        reply = await llm.generate(messages)
    except Exception as exc:
        runtime_state["last_error"] = str(exc)
        reply = "Я слышу тебя, но мой речевой контур сейчас нестабилен. Дай мне несколько секунд."
        event_log.append("llm_error", {"error": str(exc)})

    memory.add_dialogue("adam", reply)
    tts_result = await _speak(reply)
    action = action_layer.infer(reply, {"sensors": sensors, "scene": scene_cache.as_dict()})
    mcu_result = await _execute_action(action)

    event_log.append(
        "adam_reply",
        {
            "text": reply,
            "source": source,
            "voice_degraded": bool(tts_result.get("degraded")),
            "tts": tts_result,
            "action": action.as_dict(),
            "mcu": mcu_result,
        },
    )
    return {
        "ok": True,
        "reply": reply,
        "source": source,
        "voice_degraded": bool(tts_result.get("degraded")),
        "tts": tts_result,
        "action": action.as_dict(),
        "mcu": mcu_result,
    }


async def _speak(text: str) -> dict[str, Any]:
    runtime_state["speaking"] = True
    event_log.append("tts_started", {"text": text})
    try:
        result = await tts.speak(text)
        event_log.append("tts_finished", {"ok": bool(result.get("ok")), "degraded": bool(result.get("degraded"))})
        return result
    except Exception as exc:
        event_log.append("tts_finished", {"ok": False, "error": str(exc)})
        raise
    finally:
        runtime_state["speaking"] = False


async def _sensor_payload() -> dict[str, Any]:
    result = await mcu.sensor_snapshot()
    return result.data if result.ok else {}


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
    output_device = str(settings.section("sounds").get("local_output_device", "default"))
    result = await asyncio.to_thread(play_local_sound, path, output_device)
    payload = {"reason": reason, "path": str(path), **result.as_dict()}
    event_log.append("sound_success", payload)
    if not result.ok:
        runtime_state["last_error"] = f"success_sound_failed:{result.error}"
    return payload


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
