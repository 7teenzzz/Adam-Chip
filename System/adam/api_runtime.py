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
from typing import Any, AsyncGenerator, Awaitable, Callable

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

from pydantic import ValidationError

from .config import Settings, PROJECT_ROOT
from .events import EventLog
from .tuning import EqPreset, get_store as get_tuning_store
from .memory import EpisodicMemory, MemoryStore
from .metrics import MetricsLog
from .metrics_sessions import SessionsLog
from .metrics_dashboard import MetricsDashboard
from .wake_calibration import collect_noise_profile, persist_noise_profile
from pathlib import Path


def _save_calibration_profile(data_dir: Any, profile_key: str, threshold: float) -> None:
    """Save per-source OWW threshold to wake_calibration_profiles.json."""
    target = Path(data_dir) / "wake_calibration_profiles.json"
    profiles: dict[str, Any] = {}
    if target.exists():
        try:
            profiles = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            profiles = {}
    import time as _time
    from datetime import datetime, timezone
    profiles[profile_key] = {
        "threshold": threshold,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    target.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_calibration_profile(data_dir: Any, profile_key: str) -> float | None:
    """Load per-source OWW threshold from wake_calibration_profiles.json."""
    target = Path(data_dir) / "wake_calibration_profiles.json"
    if not target.exists():
        return None
    try:
        profiles = json.loads(target.read_text(encoding="utf-8"))
        entry = profiles.get(profile_key)
        if entry and isinstance(entry.get("threshold"), (int, float)):
            return float(entry["threshold"])
    except Exception:
        pass
    return None


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
    episodic_memory: EpisodicMemory | None = None
    get_voice_loop: Callable[[], Any] | None = None
    sessions_log: SessionsLog | None = None
    metrics_dashboard: MetricsDashboard | None = None


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
        deps.event_log.append("config_patched", {"section": section, "patch": patch, "restarted": restarted, "applied_runtime": bool(restarted), "saved_to": str(target)})
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
        vl = deps.get_voice_loop() if deps.get_voice_loop else None
        mr = getattr(vl, "mic_reader", None)
        audio_cfg = deps.settings.section("media").get("audio", {})
        mic_source = getattr(vl, "mic_source", "local") if vl else "local"
        mic_profile = getattr(vl, "esp32_mic_profile", "") if vl else ""
        mic_active = getattr(mr, "active_source", mic_source) if mr else mic_source
        input_device = audio_cfg.get("input_device", "")
        profile_key = (
            f"esp32:{mic_profile}" if mic_source == "esp32" else f"local:{input_device}"
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
            "mic_source": mic_source,
            "mic_active_source": mic_active,
            "esp32_mic_profile": mic_profile,
            "input_device": input_device,
            "profile_key": profile_key,
            "audio_level_stats": {
                "level_l": getattr(mr, "raw_level_l", None) if mr else None,
                "level_r": getattr(mr, "raw_level_r", None) if mr else None,
            },
        }
        try:
            persist_noise_profile(deps.settings.data_dir, record)
            _save_calibration_profile(deps.settings.data_dir, profile_key, result["recommended_threshold"])
        except Exception as exc:  # pragma: no cover — best-effort archive
            deps.event_log.append("wake_calibrate_archive_error", {"error": str(exc)})
        deps.event_log.append("wake_calibrate_finished", record)
        return result

    @router.post("/api/asr/calibrate/silence_rms")
    async def calibrate_silence_rms(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        """Record ambient noise for N seconds, return recommended silence_rms_threshold.

        Subscribes to audio_level events from the voice loop. Caller should keep
        the room at normal background level (no speech) for the duration.
        """
        duration_sec = max(2.0, min(30.0, float(payload.get("duration_sec", 5.0))))
        margin_factor = max(1.0, min(3.0, float(payload.get("margin_factor", 1.4))))

        audio_cfg = deps.settings.section("media").get("audio", {})
        normalize_factor = float(audio_cfg.get("normalize_factor", 8000))

        queue = deps.event_log.subscribe()
        levels: list[float] = []
        deadline = asyncio.get_event_loop().time() + duration_sec
        try:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if ev.get("type") != "audio_level":
                    continue
                level = (ev.get("payload") or {}).get("level")
                if isinstance(level, (int, float)) and level >= 0:
                    levels.append(float(level))
        finally:
            deps.event_log.unsubscribe(queue)

        if not levels:
            return {
                "ok": False,
                "samples": 0,
                "warning": "no_samples — voice_loop not running or audio_level events not emitting",
            }

        # Invert normalisation: level = sqrt(rms / normalize_factor) → rms = level² × normalize_factor
        raw_rms_vals = sorted(round(l * l * normalize_factor) for l in levels)
        n = len(raw_rms_vals)

        def _pct(pct: float) -> float:
            k = (n - 1) * pct / 100.0
            lo = int(k)
            hi = min(lo + 1, n - 1)
            return raw_rms_vals[lo] * (1 - (k - lo)) + raw_rms_vals[hi] * (k - lo)

        p95 = _pct(95)
        p99 = _pct(99)
        mean_rms = sum(raw_rms_vals) / n
        max_rms = raw_rms_vals[-1]

        # Round to nearest 50, clamp to schema range 0–2000
        recommended = int(max(0, min(2000, round(p95 * margin_factor / 50) * 50)))

        warning: str | None = None
        if p99 > 1000:
            warning = (
                f"Очень высокий фоновый шум (p99={round(p99)}). "
                "Рекомендуется снизить шум в зале или использовать направленный микрофон."
            )

        return {
            "ok": True,
            "duration_sec": duration_sec,
            "samples": n,
            "profile": {
                "mean": round(mean_rms),
                "p95": round(p95),
                "p99": round(p99),
                "max": round(max_rms),
            },
            "recommended_threshold": recommended,
            "warning": warning,
        }

    # ── Phase 31 (D-05): input-EQ preset CRUD ────────────────────────────
    def _tuning_store():
        return get_tuning_store()

    def _presets_list() -> list[dict[str, Any]]:
        return [p.model_dump() for p in _tuning_store().current().audio_input.presets]

    @router.get("/api/audio/presets")
    async def list_audio_presets() -> dict[str, Any]:
        audio_input = _tuning_store().current().audio_input
        return {
            "presets": [p.model_dump() for p in audio_input.presets],
            "active_preset": audio_input.active_preset,
        }

    @router.post("/api/audio/presets")
    async def create_audio_preset(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            preset = EqPreset.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store = _tuning_store()
        existing = store.current().audio_input.presets
        if any(p.name == preset.name for p in existing):
            raise HTTPException(status_code=400, detail=f"preset '{preset.name}' already exists")
        new_presets = [p.model_dump() for p in existing] + [preset.model_dump()]
        try:
            store.apply_patch({"audio_input": {"presets": new_presets}})
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        deps.event_log.append("audio_preset_created", {"name": preset.name})
        return {"ok": True, "preset": preset.model_dump(), "presets": _presets_list()}

    @router.put("/api/audio/presets/{name}")
    async def update_audio_preset(name: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        store = _tuning_store()
        existing = store.current().audio_input.presets
        idx = next((i for i, p in enumerate(existing) if p.name == name), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"preset '{name}' not found")
        merged_payload = {"name": name, **payload}
        try:
            updated = EqPreset.model_validate(merged_payload)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if updated.name != name and any(p.name == updated.name for p in existing):
            raise HTTPException(status_code=400, detail=f"preset '{updated.name}' already exists")
        new_presets = [p.model_dump() for p in existing]
        new_presets[idx] = updated.model_dump()
        tuning_now = store.current().audio_input
        active = tuning_now.active_preset
        patch: dict[str, Any] = {"audio_input": {"presets": new_presets}}
        if active == name:
            patch["audio_input"]["active_preset"] = updated.name
            patch["audio_input"]["dsp"] = {"hpf": updated.hpf.model_dump(), "bands": [b.model_dump() for b in updated.bands]}
        try:
            store.apply_patch(patch)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        deps.event_log.append("audio_preset_updated", {"name": name, "new_name": updated.name})
        return {"ok": True, "preset": updated.model_dump(), "presets": _presets_list()}

    @router.delete("/api/audio/presets/{name}")
    async def delete_audio_preset(name: str) -> dict[str, Any]:
        store = _tuning_store()
        audio_input = store.current().audio_input
        existing = audio_input.presets
        if not any(p.name == name for p in existing):
            raise HTTPException(status_code=404, detail=f"preset '{name}' not found")
        new_presets = [p.model_dump() for p in existing if p.name != name]
        patch: dict[str, Any] = {"audio_input": {"presets": new_presets}}
        cleared_active = False
        if audio_input.active_preset == name:
            patch["audio_input"]["active_preset"] = None
            cleared_active = True
        try:
            store.apply_patch(patch)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        deps.event_log.append("audio_preset_deleted", {"name": name, "cleared_active": cleared_active})
        return {"ok": True, "deleted": name, "active_preset_cleared": cleared_active, "presets": _presets_list()}

    @router.post("/api/audio/presets/{name}/activate")
    async def activate_audio_preset(name: str) -> dict[str, Any]:
        store = _tuning_store()
        existing = store.current().audio_input.presets
        preset = next((p for p in existing if p.name == name), None)
        if preset is None:
            raise HTTPException(status_code=404, detail=f"preset '{name}' not found")
        patch = {
            "audio_input": {
                "active_preset": preset.name,
                "dsp": {
                    "hpf": preset.hpf.model_dump(),
                    "bands": [b.model_dump() for b in preset.bands],
                },
            }
        }
        try:
            new_tuning = store.apply_patch(patch)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        deps.event_log.append("audio_preset_activated", {"name": preset.name})
        return {"ok": True, "active_preset": new_tuning.audio_input.active_preset, "dsp": new_tuning.audio_input.dsp.model_dump()}


    @router.get("/api/models/llm")
    async def models_llm() -> dict[str, Any]:
        llm_cfg = deps.settings.section("services").get("llm", {})
        provider = str(llm_cfg.get("provider", "openai"))
        base_url = str(llm_cfg.get("base_url", "")).rstrip("/")
        current = str(llm_cfg.get("model", ""))
        available: list[dict[str, Any]] = []
        error: str | None = None
        try:
            async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
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

    @router.get("/api/memory/status")
    async def memory_status() -> dict[str, Any]:
        em = deps.episodic_memory
        if em is None:
            raise HTTPException(status_code=503, detail="episodic memory not available")
        from datetime import datetime, timezone
        diary = await asyncio.to_thread(em.read_diary)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        episodes_today = list(await asyncio.to_thread(
            lambda: list(em.iter_episodes_since(today_start))
        ))
        episodes_total = await asyncio.to_thread(
            lambda: sum(1 for _ in em.iter_episodes())
        )
        state = await asyncio.to_thread(em.load_state)
        echoes_pool: int = 0
        from .echoes_gate import EchoGate
        # count echoes pool size via gate file path if available
        echoes_path = em.root.parent.parent / "Agent-Adam-Chip" / "Echoes.txt"
        if not echoes_path.exists():
            echoes_path = em.root.parent / "echoes.txt"
        if echoes_path.exists():
            try:
                text = echoes_path.read_text(encoding="utf-8")
                echoes_pool = text.count("[echo_")
            except OSError:
                pass
        metrics_summary: dict[str, Any] = {}
        metrics_path = em.root / "metrics.jsonl"
        if metrics_path.exists():
            try:
                from .memory_metrics import MemoryMetrics
                mm = MemoryMetrics(metrics_path)
                metrics_summary = mm.summary(hours=24)
            except Exception:
                pass
        return {
            "diary_chars": len(diary),
            "episodes_total": episodes_total,
            "episodes_today": len(episodes_today),
            "echoes_pool_size": echoes_pool,
            "last_consolidation": state.get("last_consolidation"),
            "last_echo_injected": metrics_summary.get("last_echo"),
            "metrics_last_24h": {
                "echo_inject_count": metrics_summary.get("echo_inject_count", 0),
                "episodes_committed": metrics_summary.get("episodes_committed", 0),
                "consolidations": metrics_summary.get("consolidations", 0),
            },
        }

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

    @router.get("/api/metrics/dashboard")
    async def metrics_dashboard(window: int = Query(300, ge=50, le=2000)) -> dict[str, Any]:
        if deps.metrics_dashboard is None:
            raise HTTPException(status_code=503, detail="metrics_dashboard not initialised")
        return await asyncio.to_thread(deps.metrics_dashboard.compute, window)

    @router.get("/api/metrics/sessions")
    async def metrics_sessions(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
        if deps.sessions_log is None:
            return {"sessions": [], "stats": {}}
        return {
            "sessions": deps.sessions_log.tail(limit),
            "stats": deps.sessions_log.stats(limit),
        }

    @router.post("/api/audio/input_gain/apply")
    async def apply_input_gain() -> dict[str, Any]:
        """Apply media.audio.input_gain to ALSA + PulseAudio immediately (live, no restart).
        Called by the volume slider in the Audio Input panel after saving config so the
        monitor stream reflects the change without waiting for an orchestrator restart."""
        gain = deps.settings.section("media").get("audio", {}).get("input_gain", {})
        result = await asyncio.to_thread(
            _apply_input_gain_now,
            str(gain.get("card_name", "WebCamera")),
            str(gain.get("alsa_control", "Mic")),
            int(gain.get("alsa_capture_percent", 100)),
            int(gain.get("pulse_source_percent", 100)),
        )
        deps.event_log.append("input_gain_applied", result)
        return {"ok": True, **result}

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

    @router.get("/api/camera/stream")
    async def camera_stream(request: Request) -> StreamingResponse:
        """MJPEG multipart stream — browser-native, no JS polling needed (~10 FPS)."""
        _BOUNDARY = b"--mjpegframe"

        async def _generate() -> AsyncGenerator[bytes, None]:
            while not await request.is_disconnected():
                frame = deps.capture_snapshot()
                if frame:
                    yield (
                        _BOUNDARY + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                await asyncio.sleep(0.1)

        return StreamingResponse(
            _generate(),
            media_type="multipart/x-mixed-replace; boundary=mjpegframe",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

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

    # ── Phase 31 (D-06/D-07): browser microphone monitor ─────────────────
    # Streams the EXACT post-EQ PCM flowing through _vad_loop (WYSIWYG, D-02) —
    # operator hears precisely what OWW/ASR hear. Raw mono 16-bit LE PCM at
    # media.audio.sample_rate (16000 Hz); browser plays via Web Audio API /
    # AudioWorklet (Wave 3). Mirrors EventLog.subscribe()/unsubscribe() via
    # VoiceLoopController.subscribe_monitor()/unsubscribe_monitor() — bounded
    # ring queue, drop-oldest on overflow, never blocks the voice-processing
    # hot path. Does NOT interact with safety.half_duplex_mute — this taps
    # whatever PCM is flowing (silence during TTS mute is expected/correct;
    # it's a microphone monitor, not a TTS tap).
    @router.websocket("/api/audio/monitor")
    async def audio_monitor_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        voice_loop = deps.get_voice_loop() if deps.get_voice_loop else None
        if voice_loop is None or not hasattr(voice_loop, "subscribe_monitor"):
            await websocket.close(code=1013, reason="voice loop not available")
            return
        queue = voice_loop.subscribe_monitor()
        deps.event_log.append("audio_monitor_connected", {"client": str(websocket.client)})
        try:
            while True:
                try:
                    raw_chunk, processed_chunk = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Idle keep-alive — also doubles as a disconnect probe via send.
                    try:
                        await websocket.send_bytes(b"")
                    except Exception:
                        break
                    continue
                # D-07: pick pre/post per the LIVE config — no resubscribe needed
                # when the operator flips the toggle mid-session.
                try:
                    tap = get_tuning_store().current().audio_input.dsp.monitor_tap
                except Exception:
                    tap = "post_eq"
                frame = raw_chunk if tap == "pre_eq" else processed_chunk
                await websocket.send_bytes(frame)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            deps.event_log.append("audio_monitor_error", {"error": str(exc)})
        finally:
            voice_loop.unsubscribe_monitor(queue)
            deps.event_log.append("audio_monitor_disconnected", {"client": str(websocket.client)})

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


def _apply_input_gain_now(card: str, control: str, alsa_pct: int, pulse_pct: int) -> dict[str, str]:
    """Apply ALSA capture gain + PulseAudio source volume from Python (mirrors adam_audio_input_gain.sh).
    Called live from /api/audio/input_gain/apply so the monitor stream reflects slider changes."""
    results: dict[str, str] = {}
    # ALSA
    if shutil.which("amixer"):
        try:
            r = subprocess.run(
                ["amixer", "-c", card, "sset", control, f"{alsa_pct}%", "cap"],
                capture_output=True, timeout=4,
            )
            results["alsa"] = "ok" if r.returncode == 0 else f"err:{r.stderr.decode(errors='replace')[:80]}"
        except Exception as exc:
            results["alsa"] = f"skip:{exc}"
    else:
        results["alsa"] = "skip:amixer not found"
    # PulseAudio
    if shutil.which("pactl"):
        try:
            ls = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, timeout=4)
            src = next(
                (line.split()[1] for line in ls.stdout.decode(errors="replace").splitlines()
                 if card.lower() in line.lower()),
                None,
            )
            if src:
                subprocess.run(["pactl", "set-source-volume", src, f"{pulse_pct}%"], timeout=4)
                subprocess.run(["pactl", "set-source-mute", src, "0"], timeout=4)
                results["pulse"] = f"ok:{src}"
            else:
                results["pulse"] = f"skip:no source matching '{card}'"
        except Exception as exc:
            results["pulse"] = f"skip:{exc}"
    else:
        results["pulse"] = "skip:pactl not found"
    return results


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
