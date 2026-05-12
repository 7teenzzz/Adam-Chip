"""WhisperX ASR microservice — CUDA-optimized speech recognition for Jetson Orin.

Endpoints:
  GET  /health     — service health check
  POST /transcribe — WAV bytes → {"ok": true, "transcript": "..."}

Run: python -m Speech.ASR_WhisperX
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, Request, Response

_MODEL_SIZE = os.environ.get("ADAM_ASR_WHISPERX_MODEL", "large-v3")
_LANGUAGE = os.environ.get("ADAM_ASR_LANGUAGE", "ru")
_DEVICE = os.environ.get("ADAM_ASR_DEVICE", "cuda")
_COMPUTE_TYPE = os.environ.get("ADAM_ASR_COMPUTE_TYPE", "float16")
_SAMPLE_RATE = int(os.environ.get("ADAM_ASR_SAMPLE_RATE", "16000"))

_MODELS_DIR = Path(os.environ.get("ADAM_MODELS_DIR", "Subsystem/Models"))

_MODEL: Any = None


def _resolve_device() -> str:
    if _DEVICE != "auto":
        return _DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _resolve_compute_type(device: str) -> str:
    if _COMPUTE_TYPE != "auto":
        return _COMPUTE_TYPE
    if device != "cuda":
        return "float32"
    try:
        import torch
        free_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if free_gb < 8:
            return "int8"
        return "float16"
    except Exception:
        return "float16"


def _resolve_model_size() -> str:
    """Fall back to 'medium' if VRAM is limited (< 12GB total)."""
    try:
        import torch
        free_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if free_gb < 12:
            return "medium"
    except Exception:
        pass
    return _MODEL_SIZE


def _dependency_errors() -> list[str]:
    errors = []
    for module in ("whisperx", "faster_whisper", "ctranslate2"):
        try:
            __import__(module)
        except ImportError as exc:
            errors.append(f"{module}: {exc}")
    return errors


def _get_model() -> Any:
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    import whisperx

    device = _resolve_device()
    compute_type = _resolve_compute_type(device)
    model_size = _resolve_model_size()

    _MODEL = whisperx.load_model(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(_MODELS_DIR),
        asr_options={
            "language": _LANGUAGE,
            "vad_method": "silero",
            # Do NOT use "pyannote" — requires HuggingFace token and gated model access
        },
    )
    return _MODEL


def _transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe a numpy array (float32, 16kHz) directly — used for warmup and internal calls."""
    model = _get_model()
    result = model.transcribe(audio, language=_LANGUAGE, batch_size=1)
    parts = []
    for seg in result.get("segments", []):
        # avg_logprob: lower = worse quality. -0.5 is a good threshold for Russian.
        if seg.get("avg_logprob", -1.0) < -0.5:
            continue
        text = seg.get("text", "").strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes. Writes to temp file because whisperx.load_audio() requires a path."""
    import tempfile
    import whisperx

    # whisperx.load_audio() requires a file path, NOT a file-like object.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        audio = whisperx.load_audio(tmp_path)  # returns numpy float32 array at 16kHz
        return _transcribe_audio(audio)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await asyncio.to_thread(_get_model)
    # Warmup: run a silent frame through the model to absorb cold-start JIT penalty
    warmup_audio = np.zeros(_SAMPLE_RATE, dtype=np.float32)  # 1 second of silence
    await asyncio.to_thread(_transcribe_audio, warmup_audio)
    yield


app = FastAPI(title="Adam WhisperX ASR", lifespan=_lifespan)


@app.get("/health")
async def health(response: Response) -> dict:
    dependency_errors = _dependency_errors()
    ok = not dependency_errors and _MODEL is not None
    if not ok:
        response.status_code = 503
    return {
        "ok": ok,
        "provider": "whisperx",
        "model_loaded": _MODEL is not None,
        "model": _MODEL_SIZE,
        "language": _LANGUAGE,
        "device": _resolve_device(),
        "compute_type": _resolve_compute_type(_resolve_device()),
        "dependency_errors": dependency_errors,
    }


@app.post("/transcribe")
async def transcribe(request: Request) -> dict:
    wav_bytes = await request.body()
    if not wav_bytes:
        return {"ok": False, "transcript": "", "error": "empty body"}
    try:
        transcript = await asyncio.to_thread(_transcribe, wav_bytes)
        return {"ok": True, "transcript": transcript}
    except Exception as exc:
        return {"ok": False, "transcript": "", "error": str(exc)}


def main() -> None:
    import uvicorn

    host = os.environ.get("ADAM_ASR_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_ASR_PORT", "8095"))
    app_dir = str(Path(__file__).resolve().parents[1])
    uvicorn.run("Speech.ASR_WhisperX:app", host=host, port=port, reload=False, app_dir=app_dir)


if __name__ == "__main__":
    main()
