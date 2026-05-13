"""WhisperX ASR microservice — CUDA-optimized speech recognition for Jetson Orin.

Endpoints:
  GET  /health     — service health check
  POST /transcribe — WAV bytes → {"ok": true, "transcript": "..."}

Run: python -m Speech.ASR_WhisperX
"""
from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, Request, Response

_MODEL_SIZE = os.environ.get("ADAM_ASR_WHISPERX_MODEL", "medium")
_LANGUAGE = os.environ.get("ADAM_ASR_LANGUAGE", "ru")
_DEVICE = os.environ.get("ADAM_ASR_DEVICE", "cuda")
_COMPUTE_TYPE = os.environ.get("ADAM_ASR_COMPUTE_TYPE", "float16")
_SAMPLE_RATE = int(os.environ.get("ADAM_ASR_SAMPLE_RATE", "16000"))

_MODELS_DIR = Path(os.environ.get("ADAM_MODELS_DIR", "Subsystem/Models"))

_MODEL: Any = None
_ACTUAL_MODEL_SIZE: str = _MODEL_SIZE  # updated after load to reflect OOM fallback
_ACTUAL_DEVICE: str = _DEVICE          # updated after load to reflect CUDA→CPU fallback
_MODEL_LOCK = threading.Lock()         # prevents concurrent load_model() calls → OOM on Jetson


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


def _verify_cuda_available() -> None:
    """Raise RuntimeError if CUDA is not available — called before model load."""
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError(
            f"CUDA requested but torch.cuda.is_available() == False "
            f"(torch CUDA version: {torch.version.cuda})"
        )


def _load_model_with_fallback(whisperx: Any, model_size: str, device: str, compute_type: str) -> tuple[Any, str]:
    """Load whisperx model, falling back to CPU if ctranslate2 lacks CUDA support."""
    if device == "cuda":
        _verify_cuda_available()
    try:
        model = whisperx.load_model(
            model_size,
            device=device,
            compute_type=compute_type,
            language=_LANGUAGE,
            download_root=str(_MODELS_DIR),
        )
        return model, device
    except Exception as exc:
        exc_str = str(exc)
        if device == "cuda" and ("CUDA" in exc_str or "cuda" in exc_str.lower() or "CTranslate2" in exc_str):
            # ctranslate2 installed without CUDA support (common on Jetson with pip wheels)
            import logging as _logging
            _logging.getLogger("adam.asr").error(
                "ctranslate2 CUDA unavailable (%s) — falling back to CPU float32", exc_str[:120]
            )
            model = whisperx.load_model(
                model_size,
                device="cpu",
                compute_type="float32",
                language=_LANGUAGE,
                download_root=str(_MODELS_DIR),
            )
            return model, "cpu"
        raise


def _get_model() -> Any:
    global _MODEL, _ACTUAL_MODEL_SIZE, _ACTUAL_DEVICE
    # Fast path — avoid lock on every transcribe call
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        # Re-check inside lock — another thread may have loaded while we waited
        if _MODEL is not None:
            return _MODEL

        import whisperx

        device = _resolve_device()
        compute_type = _resolve_compute_type(device)
        model_size = _resolve_model_size()
        _ACTUAL_MODEL_SIZE = model_size

        # language is a top-level param of load_model(), NOT inside asr_options.
        # asr_options feeds into TranscriptionOptions (beam search params only).
        # Silero VAD is used automatically in whisperx >= 3.x via the internal vad pipeline;
        # pyannote is NOT needed and no HuggingFace token is required for transcription.
        _MODEL, _ACTUAL_DEVICE = _load_model_with_fallback(whisperx, model_size, device, compute_type)
    return _MODEL


def _transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe a numpy array (float32, 16kHz) directly — used for warmup and internal calls."""
    model = _get_model()
    result = model.transcribe(audio, language=_LANGUAGE, batch_size=1)
    parts = []
    for seg in result.get("segments", []):
        # avg_logprob: lower = worse quality. -0.5 is a good threshold for Russian.
        # NOTE: whisperx uses avg_logprob (NOT no_speech_prob which is faster-whisper only)
        if seg.get("avg_logprob", -1.0) < -0.5:
            continue
        text = seg.get("text", "").strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _wav_bytes_to_numpy(wav_bytes: bytes) -> np.ndarray:
    """Decode WAV bytes to float32 numpy array at 16kHz without requiring ffmpeg.

    whisperx.load_audio() requires ffmpeg even for WAV files. Since the orchestrator
    always sends 16kHz S16_LE mono WAV from arecord, we bypass ffmpeg entirely.
    Resamples with scipy if the rate differs from 16kHz.
    """
    import io
    import wave

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width == 2:
        audio_int = np.frombuffer(frames, dtype=np.int16)
        audio = audio_int.astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio_int = np.frombuffer(frames, dtype=np.int32)
        audio = audio_int.astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported sample_width={sample_width}")

    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    if frame_rate != _SAMPLE_RATE:
        from scipy.signal import resample_poly
        import math
        g = math.gcd(frame_rate, _SAMPLE_RATE)
        audio = resample_poly(audio, _SAMPLE_RATE // g, frame_rate // g).astype(np.float32)

    return audio


def _transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes. Uses pure-Python WAV decoder to avoid ffmpeg dependency."""
    audio = _wav_bytes_to_numpy(wav_bytes)
    return _transcribe_audio(audio)


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
        "model": _ACTUAL_MODEL_SIZE,  # reflects OOM fallback (may differ from _MODEL_SIZE env)
        "model_requested": _MODEL_SIZE,
        "language": _LANGUAGE,
        "device": _ACTUAL_DEVICE,          # reflects CUDA→CPU fallback
        "device_requested": _resolve_device(),
        "compute_type": _resolve_compute_type(_ACTUAL_DEVICE),
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
