#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import subprocess
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
_SAMPLE_RATE = 48000
_MODEL_ID = "v5_5_ru"
_DEFAULT_SPEAKER = "eugene"
_PLAYBACK_ENABLED = os.environ.get("ADAM_TTS_PLAYBACK", "1") != "0"
_PLAYBACK_DEVICE = os.environ.get("ADAM_TTS_OUTPUT_DEVICE", "default")


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
        "dependency_errors": dependency_errors,
    }


@app.post("/speak")
async def speak(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    speaker = str(payload.get("speaker", _DEFAULT_SPEAKER)).strip() or _DEFAULT_SPEAKER
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        audio = synthesize(text, speaker)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    wav_bytes = _to_wav(audio, _SAMPLE_RATE)
    playback = _play_wav(wav_bytes) if _PLAYBACK_ENABLED else {"enabled": False}
    playback_ok = bool(playback.get("ok", True)) if playback.get("enabled", True) else True
    return {
        "ok": playback_ok,
        "speaker": speaker,
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
    try:
        from silero import silero_tts
    except ImportError as exc:
        raise RuntimeError(
            "Install NVIDIA Jetson-compatible PyTorch first, then install Silero with: "
            "python3 -m pip install --no-deps 'silero>=0.5.0'"
        ) from exc
    model, _ = silero_tts(language="ru", speaker=_MODEL_ID)
    return model


def _dependency_errors() -> list[str]:
    errors: list[str] = []
    for module in ("torch", "silero"):
        try:
            __import__(module)
        except ImportError as exc:
            errors.append(f"{module}: {exc}")
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


def _play_wav(wav_bytes: bytes) -> dict[str, Any]:
    command = ["aplay", "-q", "-D", _PLAYBACK_DEVICE]
    try:
        proc = subprocess.run(command, input=wav_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"enabled": True, "ok": False, "error": str(exc)}
    return {
        "enabled": True,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr": proc.stderr.decode("utf-8", errors="replace")[-500:],
    }


def main() -> None:
    import uvicorn

    host = os.environ.get("ADAM_TTS_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_TTS_PORT", "8090"))
    app_dir = str(Path(__file__).resolve().parents[1])
    uvicorn.run("Speech.TTS:app", host=host, port=port, reload=False, app_dir=app_dir)


if __name__ == "__main__":
    main()
