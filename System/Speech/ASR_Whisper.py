#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import threading
import wave
from pathlib import Path
from typing import Any

# Clear all proxy env vars before importing HF libraries. huggingface_hub uses httpx
# which doesn't support SOCKS5 without httpx[socks], and any proxy (including HTTP)
# may block or delay the HF auth check, freezing the asyncio event loop on first import.
for _var in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
    os.environ.pop(_var, None)

# Disable HF hub network access — all models are cached locally.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Project-local model storage. faster-whisper's WhisperModel(download_root=...)
# overrides the HuggingFace cache; HF_HOME below is also set so huggingface_hub
# probes (used internally by faster-whisper) hit the project cache first.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODELS_DIR = _PROJECT_ROOT / "Subsystem" / "Models"
_MODELS_DIR = Path(os.environ.get("ADAM_MODELS_DIR", str(_DEFAULT_MODELS_DIR)))
_HF_HOME = Path(os.environ.get("HF_HOME", str(_MODELS_DIR / "hf")))
os.environ.setdefault("HF_HOME", str(_HF_HOME))
os.environ.setdefault("HF_HUB_CACHE", str(_HF_HOME / "hub"))

try:
    from contextlib import asynccontextmanager
    import asyncio
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import Response
except ImportError as exc:  # pragma: no cover
    raise SystemExit("FastAPI is required: python3 -m pip install fastapi uvicorn") from exc


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await asyncio.to_thread(_get_model)
    # Warm up when provider=whisper: run a silent frame through the model so the first
    # real request is fast. When provider=speaches, _warmup_asr() in Orchestrator handles it.
    _silence = _pcm_to_wav(b"\x00" * _SAMPLE_RATE, _SAMPLE_RATE)
    await asyncio.to_thread(_transcribe, _silence)
    yield


app = FastAPI(title="Adam Chip Whisper ASR", version="0.1.0", lifespan=_lifespan)

_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_MODEL_SIZE = os.environ.get("ADAM_ASR_WHISPER_MODEL", "medium")
_LANGUAGE = os.environ.get("ADAM_ASR_LANGUAGE", "ru")
_DEVICE = os.environ.get("ADAM_ASR_DEVICE", "auto")
_COMPUTE_TYPE = os.environ.get("ADAM_ASR_COMPUTE_TYPE", "auto")
_SAMPLE_RATE = int(os.environ.get("ADAM_ASR_SAMPLE_RATE", "16000"))


@app.get("/health")
async def health(response: Response) -> dict[str, Any]:
    dependency_errors = _dependency_errors()
    ok = not dependency_errors
    if not ok:
        response.status_code = 503
    return {
        "ok": ok,
        "provider": "faster-whisper",
        "model_loaded": _MODEL is not None,
        "model": _MODEL_SIZE,
        "language": _LANGUAGE,
        "device": _resolve_device(),
        "dependency_errors": dependency_errors,
    }


@app.post("/transcribe")
async def transcribe(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="audio body is required")

    if "audio/wav" in content_type or "audio/x-wav" in content_type:
        wav_bytes = body
    else:
        # Assume raw PCM — wrap it
        wav_bytes = _pcm_to_wav(body, _SAMPLE_RATE)

    try:
        transcript = _transcribe(wav_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"ok": True, "transcript": transcript, "language": _LANGUAGE}


def _transcribe(wav_bytes: bytes) -> str:
    model = _get_model()
    audio_file = io.BytesIO(wav_bytes)
    segments, _info = model.transcribe(
        audio_file,
        language=_LANGUAGE,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    parts: list[str] = []
    for seg in segments:
        if seg.no_speech_prob > 0.6:
            continue  # reject noise / hallucinated segment
        text = seg.text.strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _get_model() -> Any:
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            _MODEL = _load_model()
    return _MODEL


def _load_model() -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper not installed. Run: .venv/bin/pip install faster-whisper"
        ) from exc
    device = _resolve_device()
    compute_type = _resolve_compute_type(device)
    return WhisperModel(
        _MODEL_SIZE,
        device=device,
        compute_type=compute_type,
        download_root=str(_HF_HOME / "hub"),
    )


def _resolve_device() -> str:
    if _DEVICE != "auto":
        return _DEVICE
    try:
        import ctranslate2
        # CTranslate2 (used by faster-whisper) may not have CUDA support compiled
        # Check if the device is actually available, not just if torch.cuda exists
        if hasattr(ctranslate2.Device, "CUDA"):
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _resolve_compute_type(device: str) -> str:
    if _COMPUTE_TYPE != "auto":
        return _COMPUTE_TYPE
    return "float16" if device == "cuda" else "int8"


def _dependency_errors() -> list[str]:
    errors: list[str] = []
    for module in ("faster_whisper",):
        try:
            __import__(module)
        except ImportError as exc:
            errors.append(f"{module}: {exc}")
    return errors


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return out.getvalue()


def main() -> None:
    import uvicorn

    host = os.environ.get("ADAM_ASR_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_ASR_PORT", "8095"))
    app_dir = str(Path(__file__).resolve().parents[1])
    uvicorn.run("Speech.ASR_Whisper:app", host=host, port=port, reload=False, app_dir=app_dir)


if __name__ == "__main__":
    main()
