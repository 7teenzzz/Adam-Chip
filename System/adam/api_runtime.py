"""Runtime API extensions for the Adam Chip orchestrator.

Exposes config read/write, model discovery, conversation history, SSE event
stream, camera snapshot, audio device list, and an in-browser ASR upload
endpoint. Wired into the FastAPI app via :func:`build_router`.

Designed for dependency injection — the orchestrator passes already-built
service clients and a rebuild callback so this module stays free of cyclic
imports against ``Orchestrator.py``.
"""

from __future__ import annotations

import asyncio
import io
import json
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from .config import Settings, PROJECT_ROOT
from .events import EventLog
from .memory import MemoryStore
from .metrics import MetricsLog
from .wake_calibration import collect_noise_profile, persist_noise_profile


WHISPER_SIZES = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]

# Sections whose patches require which client to be rebuilt. Keys are dotted
# section prefixes; values are the rebuild scope tag returned to the UI.
CLIENT_REBUILD_MAP = {
    "services.llm": "llm",
    "services.asr": "asr",
    "services.vlm": "vlm",
    "services.tts": "tts",
    "mcu": "mcu",
    "media.audio": "voice_loop",
    "media.video": "scene_worker",
}


@dataclass
class RuntimeDeps:
    settings: Settings
    event_log: EventLog
    memory: MemoryStore
    metrics_log: MetricsLog
    runtime_state: dict[str, Any]
    get_llm: Callable[[], Any]
    get_asr: Callable[[], Any]
    get_tts: Callable[[], Any]
    get_vlm: Callable[[], Any]
    get_mcu: Callable[[], Any]
    rebuild_clients: Callable[[str], list[str]]
    capture_snapshot: Callable[[], bytes]
    run_dialogue_turn: Callable[..., Awaitable[dict[str, Any]]]
    get_voice_loop: Callable[[], Any] | None = None


def build_router(deps: RuntimeDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/api/config")
    async def get_config() -> dict[str, Any]:
        return deps.settings.to_public_dict()

    @router.patch("/api/config")
    async def patch_config(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        section = str(payload.get("section", "")).strip()
        patch = payload.get("patch")
        if not section:
            raise HTTPException(status_code=400, detail="section is required")
        if not isinstance(patch, dict):
            raise HTTPException(status_code=400, detail="patch must be an object")
        try:
            applied = deps.settings.apply_patch(section, patch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        target = deps.settings.save()
        restarted = deps.rebuild_clients(section)
        deps.event_log.append("config_patched", {"section": section, "patch": patch, "restarted": restarted, "saved_to": str(target)})
        return {"ok": True, "section": section, "applied": applied, "restarted": restarted, "saved_to": str(target)}

    # ── Wake-word sensitivity ─────────────────────────────────────────────
    # Live tuning of OpenWakeWord threshold/debounce. Does NOT rebuild the
    # engine (engine init is expensive — ONNX load + 20× silence warmup).
    # Setters live on OpenWakeWordEngine and just mutate state.
    def _wake_engine() -> Any:
        if deps.get_voice_loop is None:
            return None
        loop = deps.get_voice_loop()
        return getattr(loop, "_wake_engine", None)

    @router.get("/api/wake_word/sensitivity")
    async def get_wake_sensitivity() -> dict[str, Any]:
        engine = _wake_engine()
        if engine is None:
            return {"ok": False, "engine": None, "reason": "no_engine"}
        if not hasattr(engine, "sensitivity"):
            return {"ok": False, "engine": type(engine).__name__, "reason": "engine_read_only"}
        return {"ok": True, **engine.sensitivity}

    @router.patch("/api/wake_word/sensitivity")
    async def patch_wake_sensitivity(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        engine = _wake_engine()
        if engine is None or not hasattr(engine, "set_threshold"):
            raise HTTPException(status_code=409, detail="wake word engine not active or read-only")
        changes: dict[str, Any] = {}
        if "threshold" in payload:
            engine.set_threshold(float(payload["threshold"]))
            changes["threshold"] = engine._threshold
        if "debounce_hits" in payload:
            engine.set_debounce_hits(int(payload["debounce_hits"]))
            changes["debounce_hits"] = engine._debounce_hits
        persisted = False
        if payload.get("persist") and changes:
            deps.settings.apply_patch("wake_word", changes)
            deps.settings.save()
            persisted = True
        deps.event_log.append(
            "wake_sensitivity_updated",
            {"changes": changes, "persisted": persisted, **engine.sensitivity},
        )
        return {"ok": True, "persisted": persisted, "changes": changes, **engine.sensitivity}

    @router.post("/api/wake_word/calibrate/noise")
    async def calibrate_noise(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """Record ambient noise for N seconds, return recommended OWW threshold.

        Caller is expected to keep the room quiet for `duration_sec`. The
        endpoint subscribes to live `oww_score` events from the voice loop;
        if the voice loop is not running, the queue stays empty and we
        return a `no_samples` warning instead of failing.
        """
        engine = _wake_engine()
        if engine is None:
            raise HTTPException(status_code=409, detail="wake word engine not active")
        duration_sec = float(payload.get("duration_sec", 20.0))
        margin = float(payload.get("margin", 0.08))
        deps.event_log.append(
            "wake_calibrate_started", {"duration_sec": duration_sec, "margin": margin}
        )
        result = await collect_noise_profile(
            deps.event_log, duration_sec=duration_sec, margin=margin
        )
        # Archive for later diffing across sessions / rooms.
        record = {
            **result,
            "engine": {
                "model": getattr(engine, "_model_name", None),
                "vad_threshold": getattr(engine, "_oww", None) and getattr(engine._oww, "vad_threshold", 0),
                "threshold_before": getattr(engine, "_threshold", None),
                "debounce_hits": getattr(engine, "_debounce_hits", None),
            },
        }
        try:
            persist_noise_profile(deps.settings.data_dir, record)
        except Exception as exc:  # pragma: no cover — best-effort archive
            deps.event_log.append("wake_calibrate_archive_error", {"error": str(exc)})
        deps.event_log.append("wake_calibrate_finished", record)
        return result

    @router.get("/api/models/llm")
    async def models_llm() -> dict[str, Any]:
        llm_cfg = deps.settings.section("services").get("llm", {})
        provider = str(llm_cfg.get("provider", "ollama"))
        base_url = str(llm_cfg.get("base_url", "")).rstrip("/")
        current = str(llm_cfg.get("model", ""))
        available: list[dict[str, Any]] = []
        error: str | None = None
        try:
            async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
                if provider == "ollama":
                    resp = await client.get(f"{base_url}/api/tags")
                    resp.raise_for_status()
                    body = resp.json()
                    for tag in body.get("models", []):
                        available.append({
                            "name": tag.get("name"),
                            "size": tag.get("size"),
                            "modified_at": tag.get("modified_at"),
                        })
                else:
                    resp = await client.get(f"{base_url}/v1/models")
                    resp.raise_for_status()
                    body = resp.json()
                    for entry in body.get("data", []):
                        available.append({"name": entry.get("id")})
        except Exception as exc:
            error = str(exc)
        return {"provider": provider, "current": current, "available": available, "error": error}

    @router.get("/api/models/tts")
    async def models_tts() -> dict[str, Any]:
        tts_cfg = deps.settings.section("services").get("tts", {})
        return {
            "provider": str(tts_cfg.get("provider", "silero")),
            "model": str(tts_cfg.get("model", "v5_5_ru")),
            "current": str(tts_cfg.get("speaker", "eugene")),
            "available": [{"name": s} for s in tts_cfg.get("available_speakers", ["eugene"])],
        }

    @router.get("/api/models/asr")
    async def models_asr() -> dict[str, Any]:
        asr_cfg = deps.settings.section("services").get("asr", {})
        provider = str(asr_cfg.get("provider", "riva"))
        whisper_current = str(asr_cfg.get("model", "medium")) if provider == "whisper" else "medium"
        whisper_status: dict[str, Any] = {"provider_active": provider == "whisper"}
        whisper_base = str(asr_cfg.get("base_url", "http://127.0.0.1:8095")).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                resp = await client.get(f"{whisper_base}/health")
                whisper_status["reachable"] = resp.status_code in (200, 503)
                whisper_status["body"] = resp.json()
        except Exception as exc:
            whisper_status["reachable"] = False
            whisper_status["error"] = str(exc)
        return {
            "provider": provider,
            "whisper": {
                "current": whisper_current,
                "available": [{"name": size} for size in WHISPER_SIZES],
                "service": whisper_status,
            },
            "riva": {
                "host": asr_cfg.get("host"),
                "port": asr_cfg.get("port"),
                "language_code": asr_cfg.get("language_code"),
            },
        }

    @router.get("/api/models/vlm")
    async def models_vlm() -> dict[str, Any]:
        vlm_cfg = deps.settings.section("services").get("vlm", {})
        base_url = str(vlm_cfg.get("base_url", "")).rstrip("/")
        current = str(vlm_cfg.get("model", ""))
        available: list[dict[str, Any]] = []
        error: str | None = None
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                resp = await client.get(f"{base_url}/v1/models")
                resp.raise_for_status()
                body = resp.json()
                for entry in body.get("data", []):
                    available.append({"name": entry.get("id")})
        except Exception as exc:
            error = str(exc)
        return {"current": current, "available": available, "error": error}

    @router.get("/api/memory/dialogue")
    async def memory_dialogue(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
        return {"turns": deps.memory.recent_dialogue(limit)}

    @router.get("/api/memory/summary")
    async def memory_summary() -> dict[str, Any]:
        return {"text": deps.memory.summary_text()}

    @router.get("/api/metrics/turns")
    async def metrics_turns(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        return {"turns": deps.metrics_log.tail(limit)}

    @router.get("/api/metrics/summary")
    async def metrics_summary(window: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        return deps.metrics_log.summary(window)

    @router.get("/api/metrics/export")
    async def metrics_export() -> Response:
        path = deps.metrics_log.path
        if not path.exists():
            raise HTTPException(status_code=404, detail="metrics log is empty")
        data = path.read_bytes()
        headers = {
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Cache-Control": "no-store",
        }
        return Response(content=data, media_type="application/x-ndjson", headers=headers)

    @router.get("/api/audio/devices")
    async def audio_devices() -> dict[str, Any]:
        return await asyncio.to_thread(_aplay_devices)

    @router.get("/api/audio/input_devices")
    async def audio_input_devices() -> dict[str, Any]:
        return await asyncio.to_thread(_arecord_devices)

    @router.get("/api/persona")
    async def get_persona() -> dict[str, Any]:
        paths = deps.settings.section("agent").get("persona_paths", [])
        files = []
        for rel in paths:
            p = PROJECT_ROOT / rel
            name = p.stem
            content = p.read_text("utf-8") if p.exists() else ""
            files.append({"name": name, "path": rel, "content": content})
        return {"base_prompt": "", "files": files}

    @router.put("/api/persona")
    async def put_persona(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        rel = str(payload.get("path", "")).strip()
        content = str(payload.get("content", ""))
        if not rel:
            raise HTTPException(status_code=400, detail="path required")
        allowed = deps.settings.section("agent").get("persona_paths", [])
        if rel not in allowed:
            raise HTTPException(status_code=403, detail="path not in persona_paths")
        target = PROJECT_ROOT / rel
        target.write_text(content, "utf-8")
        deps.event_log.append("persona_updated", {"path": rel})
        return {"ok": True, "path": rel, "bytes": len(content.encode())}

    @router.get("/api/camera/snapshot.jpg")
    async def camera_snapshot() -> Response:
        try:
            data = await asyncio.to_thread(deps.capture_snapshot)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not data:
            raise HTTPException(status_code=503, detail="camera not ready")
        return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @router.get("/api/live_vlm/status")
    async def live_vlm_status() -> dict[str, Any]:
        """Probe the adam-live-vlm Docker container."""
        return await asyncio.to_thread(_docker_inspect, "adam-live-vlm")

    @router.post("/api/live_vlm/start")
    async def live_vlm_start() -> dict[str, Any]:
        """Start the VLM Docker container via adam_live_vlm.sh bg."""
        import subprocess, pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        script = root / "scripts" / "adam_live_vlm.sh"
        result = await asyncio.to_thread(
            subprocess.run, [str(script), "bg"],
            capture_output=True, text=True, timeout=30,
        )
        ok = result.returncode == 0
        return {"ok": ok, "stdout": result.stdout[-500:], "stderr": result.stderr[-500:]}

    @router.post("/api/live_vlm/stop")
    async def live_vlm_stop() -> dict[str, Any]:
        """Stop and remove the VLM Docker container."""
        import subprocess
        r1 = await asyncio.to_thread(
            subprocess.run, ["docker", "stop", "adam-live-vlm"],
            capture_output=True, text=True, timeout=30,
        )
        r2 = await asyncio.to_thread(
            subprocess.run, ["docker", "rm", "adam-live-vlm"],
            capture_output=True, text=True, timeout=10,
        )
        return {"ok": r1.returncode == 0, "stop_rc": r1.returncode, "rm_rc": r2.returncode}

    @router.post("/api/agent/asr/upload")
    async def asr_upload(request: Request, auto_turn: bool = Query(False)) -> dict[str, Any]:
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="audio body is required")
        content_type = request.headers.get("content-type", "")
        try:
            pcm, sample_rate = _decode_to_pcm(body, content_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        asr_client = deps.get_asr()
        t_asr = time.perf_counter()
        try:
            transcript = (await asr_client.transcribe_pcm(pcm)).strip()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"asr_failed: {exc}") from exc
        asr_ms = round((time.perf_counter() - t_asr) * 1000, 1)
        deps.runtime_state["last_asr_ms"] = asr_ms

        deps.event_log.append("asr_final", {
            "text": transcript, "source": "ui_upload",
            "sample_rate": sample_rate, "asr_ms": asr_ms,
        })

        result: dict[str, Any] = {
            "transcript": transcript,
            "sample_rate": sample_rate,
            "asr_ms": asr_ms,
        }
        if auto_turn and transcript:
            result["turn"] = await deps.run_dialogue_turn(transcript, "ui_upload", asr_ms=asr_ms)
        return result

    @router.get("/api/agent/stream")
    async def agent_stream(request: Request) -> StreamingResponse:
        queue = deps.event_log.subscribe()

        async def generator():
            try:
                yield ":\n\n"  # initial keep-alive
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ":\n\n"
                        continue
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"id: {event.get('id', '')}\n"
                    yield f"data: {payload}\n\n"
            finally:
                deps.event_log.unsubscribe(queue)

        headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        return StreamingResponse(generator(), media_type="text/event-stream", headers=headers)

    @router.get("/api/events")
    async def events_history(
        limit: int = Query(100, ge=1, le=500),
        type: str | None = Query(None),
    ) -> dict[str, Any]:
        types = [type] if type else None
        return {"events": deps.event_log.tail(limit, types=types)}

    return router


def _docker_inspect(name: str) -> dict[str, Any]:
    docker = shutil.which("docker")
    if docker is None:
        return {"running": False, "error": "docker not installed"}
    try:
        proc = subprocess.run(
            [docker, "inspect", "--format", "{{.State.Status}}|{{.State.StartedAt}}|{{.Config.Image}}", name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"running": False, "error": str(exc)}
    if proc.returncode != 0:
        return {"running": False, "error": "container not found"}
    parts = proc.stdout.decode("utf-8", errors="replace").strip().split("|")
    status = parts[0] if parts else ""
    started_at = parts[1] if len(parts) > 1 else ""
    image = parts[2] if len(parts) > 2 else ""
    return {
        "running": status == "running",
        "status": status,
        "started_at": started_at,
        "image": image,
        "name": name,
    }


_USEFUL_OUTPUT_PREFIXES = ("pulse", "default", "hw:", "plughw:", "sysdefault:", "dmix:", "hdmi:", "iec958:", "front:", "rear:", "surround")
_USEFUL_INPUT_PREFIXES  = ("pulse", "default", "hw:", "plughw:", "sysdefault:", "dsnoop:")


def _filter_alsa_devices(devices: list[dict[str, str]], prefixes: tuple[str, ...]) -> list[dict[str, str]]:
    return [d for d in devices if any(d["name"] == p or d["name"].startswith(p) for p in prefixes)]


def _run_alsa_list(cmd: str) -> dict[str, Any]:
    binary = shutil.which(cmd)
    if binary is None:
        return {"devices": [], "error": f"{cmd} not installed"}
    try:
        proc = subprocess.run([binary, "-L"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"devices": [], "error": str(exc)}
    if proc.returncode != 0:
        return {"devices": [], "error": proc.stderr.decode("utf-8", errors="replace")[-300:]}
    raw = proc.stdout.decode("utf-8", errors="replace")
    devices: list[dict[str, str]] = []
    name: str | None = None
    description_parts: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and not line.startswith("\t"):
            if name is not None:
                devices.append({"name": name, "description": "\n".join(description_parts).strip()})
            name = line.strip()
            description_parts = []
        else:
            description_parts.append(line.strip())
    if name is not None:
        devices.append({"name": name, "description": "\n".join(description_parts).strip()})
    return {"devices": devices}


def _aplay_devices() -> dict[str, Any]:
    result = _run_alsa_list("aplay")
    result["devices"] = _filter_alsa_devices(result.get("devices", []), _USEFUL_OUTPUT_PREFIXES)
    return result


def _arecord_devices() -> dict[str, Any]:
    result = _run_alsa_list("arecord")
    result["devices"] = _filter_alsa_devices(result.get("devices", []), _USEFUL_INPUT_PREFIXES)
    return result


def _decode_to_pcm(body: bytes, content_type: str) -> tuple[bytes, int]:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct in {"audio/wav", "audio/x-wav", "audio/wave"} or body[:4] == b"RIFF":
        with wave.open(io.BytesIO(body), "rb") as handle:
            if handle.getsampwidth() != 2:
                raise ValueError("only 16-bit PCM WAV is supported")
            channels = handle.getnchannels()
            sample_rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
        if channels == 1:
            return frames, sample_rate
        if channels == 2:
            return _stereo_to_mono(frames), sample_rate
        raise ValueError(f"unsupported channel count: {channels}")
    raise ValueError(f"unsupported content-type: {content_type or '(none)'}")


def _stereo_to_mono(stereo: bytes) -> bytes:
    import audioop  # local import — only needed on stereo upload
    return audioop.tomono(stereo, 2, 0.5, 0.5)
