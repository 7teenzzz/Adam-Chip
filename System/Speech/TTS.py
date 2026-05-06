#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

try:
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.responses import Response
except ImportError as exc:  # pragma: no cover
    raise SystemExit("FastAPI is required. Install with: python3 -m pip install -r System/requirements.txt") from exc


app = FastAPI(title="Adam Chip Silero TTS", version="0.1.0")
_MODEL: Any = None
_MODEL_DEVICE = "cpu"
_SAMPLE_RATE = 48000
_MODEL_ID = "v5_5_ru"
_DEFAULT_SPEAKER = "eugene"
_PLAYBACK_ENABLED = os.environ.get("ADAM_TTS_PLAYBACK", "1") != "0"
# Default to plughw:0,3 (HDMI 0 on Jetson Orin NX HDA card).
# Override via ADAM_TTS_OUTPUT_DEVICE env var.
_PLAYBACK_DEVICE = os.environ.get("ADAM_TTS_OUTPUT_DEVICE", "plughw:0,3")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODELS_DIR = _PROJECT_ROOT / "Subsystem" / "Models"
_MODELS_DIR = Path(os.environ.get("ADAM_MODELS_DIR", str(_DEFAULT_MODELS_DIR)))
_LOCAL_MODEL_PATH = Path(os.environ.get("ADAM_TTS_MODEL_PATH", str(_MODELS_DIR / "silero" / f"{_MODEL_ID}.pt")))


@app.get("/health")
async def health(response: Response) -> dict[str, Any]:
    dependency_errors = _dependency_errors()
    ok = not dependency_errors
    if not ok:
        response.status_code = 503
    return {
        "ok": ok,
        "provider": "silero",
        "model_loaded": _MODEL is not None,
        "model": _MODEL_ID,
        "speaker": _DEFAULT_SPEAKER,
        "device": _MODEL_DEVICE,
        "model_path": str(_LOCAL_MODEL_PATH) if _LOCAL_MODEL_PATH.exists() else None,
        "playback_device": _PLAYBACK_DEVICE,
        "dependency_errors": dependency_errors,
    }


@app.post("/speak")
async def speak(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    speaker = str(payload.get("speaker", _DEFAULT_SPEAKER)).strip() or _DEFAULT_SPEAKER
    device = str(payload.get("output_device", "")).strip() or _PLAYBACK_DEVICE
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        audio = synthesize(text, speaker)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    wav_bytes = _to_wav(audio, _SAMPLE_RATE)
    playback = _play_wav(wav_bytes, device) if _PLAYBACK_ENABLED else {"enabled": False}
    playback_ok = bool(playback.get("ok", True)) if playback.get("enabled", True) else True
    return {
        "ok": playback_ok,
        "speaker": speaker,
        "output_device": device,
        "sample_rate": _SAMPLE_RATE,
        "samples": len(audio),
        "playback": playback,
    }


@app.post("/wav")
async def wav(payload: dict[str, Any] = Body(...)) -> Response:
    text = str(payload.get("text", "")).strip()
    speaker = str(payload.get("speaker", _DEFAULT_SPEAKER)).strip() or _DEFAULT_SPEAKER
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        audio = synthesize(text, speaker)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(_to_wav(audio, _SAMPLE_RATE), media_type="audio/wav")


def synthesize(text: str, speaker: str = _DEFAULT_SPEAKER) -> list[float]:
    global _MODEL
    if _MODEL is None:
        _MODEL = _load_model()
    audio = _MODEL.apply_tts(text=text, speaker=speaker, sample_rate=_SAMPLE_RATE)
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    return [float(sample) for sample in audio]


def _load_model() -> Any:
    global _MODEL_DEVICE
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch is required for the TTS service") from exc
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _MODEL_DEVICE = device.type
    torch.set_grad_enabled(False)
    if _LOCAL_MODEL_PATH.exists():
        # Silero v5_* shipped as torch.package, not torch.jit.
        # Loader mirrors silero/silero.py:silero_tts (PackageImporter +
        # load_pickle("tts_models", "model")), which lets us drop the
        # silero pip package dependency entirely.
        from torch import package
        importer = package.PackageImporter(str(_LOCAL_MODEL_PATH))
        model = importer.load_pickle("tts_models", "model")
    else:
        try:
            from silero import silero_tts
        except ImportError as exc:
            raise RuntimeError(
                f"Silero model file not found at {_LOCAL_MODEL_PATH} and 'silero' package is not installed. "
                "Place v5_5_ru.pt into Subsystem/Models/silero/ or install the silero pip package."
            ) from exc
        model, _ = silero_tts(language="ru", speaker=_MODEL_ID)
    model.to(device)
    return model


def _dependency_errors() -> list[str]:
    errors: list[str] = []
    try:
        __import__("torch")
    except ImportError as exc:
        errors.append(f"torch: {exc}")
    if not _LOCAL_MODEL_PATH.exists():
        try:
            __import__("silero")
        except ImportError as exc:
            errors.append(
                f"silero model not at {_LOCAL_MODEL_PATH} and 'silero' pip package missing: {exc}"
            )
    return errors


def _to_wav(samples: list[float], sample_rate: int) -> bytes:
    pcm = bytearray()
    for sample in samples:
        value = max(-1.0, min(1.0, sample))
        pcm.extend(int(value * 32767).to_bytes(2, byteorder="little", signed=True))
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(pcm))
    return out.getvalue()


def _play_wav(wav_bytes: bytes, device: str = "") -> dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(wav_bytes)
            wav_path = handle.name
    except OSError as exc:
        return {"enabled": True, "ok": False, "error": f"tempfile: {exc}"}

    try:
        attempts = _playback_commands(wav_path, device or _PLAYBACK_DEVICE)
        if not attempts:
            return {"enabled": True, "ok": False, "error": "no_supported_player_found"}

        last: dict[str, Any] = {"enabled": True, "ok": False}
        for command in attempts:
            try:
                proc = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                last = {"enabled": True, "ok": False, "player": command[0], "error": str(exc)}
                continue
            stderr = proc.stderr.decode("utf-8", errors="replace")[-500:]
            if proc.returncode == 0:
                return {
                    "enabled": True,
                    "ok": True,
                    "player": command[0],
                    "returncode": 0,
                    "stderr": stderr,
                }
            last = {
                "enabled": True,
                "ok": False,
                "player": command[0],
                "returncode": proc.returncode,
                "stderr": stderr,
            }
        return last
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def _playback_commands(wav_path: str, device: str = "") -> list[list[str]]:
    dev = device or _PLAYBACK_DEVICE
    commands: list[list[str]] = []
    gst = shutil.which("gst-launch-1.0")
    # 1. PulseAudio via gst-launch (needs XDG_RUNTIME_DIR + PULSE_SERVER in systemd unit).
    if gst:
        commands.append([
            gst, "-q",
            "filesrc", f"location={wav_path}", "!",
            "wavparse", "!",
            "audioconvert", "!",
            "audioresample", "!",
            "pulsesink",
        ])
    # 2. PulseAudio via paplay (simpler, same requirement).
    if player := shutil.which("paplay"):
        commands.append([player, wav_path])
    # 3. Requested ALSA device.
    if gst:
        commands.append([
            gst, "-q",
            "filesrc", f"location={wav_path}", "!",
            "wavparse", "!",
            "audioconvert", "!",
            "audioresample", "!",
            "alsasink", f"device={dev}",
        ])
    if player := shutil.which("aplay"):
        commands.append([player, "-q", "-D", dev, wav_path])
    # 4. ALSA "default" fallback when the requested device differs.
    if dev != "default":
        if gst:
            commands.append([
                gst, "-q",
                "filesrc", f"location={wav_path}", "!",
                "wavparse", "!",
                "audioconvert", "!",
                "audioresample", "!",
                "alsasink", "device=default",
            ])
        if player := shutil.which("aplay"):
            commands.append([player, "-q", "-D", "default", wav_path])
    return commands


def main() -> None:
    import uvicorn

    host = os.environ.get("ADAM_TTS_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_TTS_PORT", "8090"))
    app_dir = str(Path(__file__).resolve().parents[1])
    uvicorn.run("Speech.TTS:app", host=host, port=port, reload=False, app_dir=app_dir)


if __name__ == "__main__":
    main()
