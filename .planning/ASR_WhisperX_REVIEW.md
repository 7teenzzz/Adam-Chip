---
phase: ASR_WhisperX
reviewed: 2026-05-13T00:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - System/adam/wake_word.py
  - System/Speech/ASR_WhisperX.py
  - System/adam/inference.py
  - System/Config.json
  - System/Orchestrator.py
  - System/requirements.txt
  - compose.yaml
  - deploy/systemd/adam-asr-whisperx.service
findings:
  critical: 4
  warning: 4
  info: 2
  total: 10
status: issues_found
---

# ASR WhisperX: Code Review Report

**Reviewed:** 2026-05-13  
**Depth:** deep  
**Files Reviewed:** 8  
**Status:** issues_found

## Summary

The PR introduces a new ASR pipeline (WhisperX + openWakeWord). The wake word engine and Orchestrator voice-loop state machine are structurally correct. However, there is a **service-stopping bug** in `ASR_WhisperX.py`: two invalid keys are placed inside the `asr_options` dict that should be top-level `whisperx.load_model()` arguments. This causes a `TypeError` at startup — the service never loads the model. A secondary critical issue is the Docker container lacking a model cache volume mount, causing large-v3 (~3GB) to be re-downloaded into an ephemeral container layer on every restart. Two additional blockers cover a silent infinite-standby condition when the ONNX model file is missing, and stale Ollama defaults in `compose.yaml` that break the orchestrator container.

---

## Critical Issues

### CR-01: `language` and `vad_method` inside `asr_options` — service crashes at startup

**File:** `System/Speech/ASR_WhisperX.py:89-99`

**Issue:** `whisperx.load_model()` accepts `language` and `vad_method` as **top-level keyword arguments**, not as keys inside `asr_options`. When the code passes them inside `asr_options`, whisperx merges the dict into `default_asr_options` and then calls `TranscriptionOptions(**default_asr_options)`. Neither `language` nor `vad_method` is a field of `TranscriptionOptions` (confirmed by inspection of the dataclass), so Python raises `TypeError: __init__() got an unexpected keyword argument 'language'`. The model never loads; the service crashes on startup.

**Fix:**
```python
_MODEL = whisperx.load_model(
    model_size,
    device=device,
    compute_type=compute_type,
    language=_LANGUAGE,           # top-level param
    vad_method="silero",          # top-level param
    download_root=str(_MODELS_DIR),
    asr_options={},               # only valid TranscriptionOptions keys go here
)
```

---

### CR-02: Docker container has no model cache volume — large-v3 re-downloaded on every restart

**File:** `compose.yaml:71-96`

**Issue:** The `adam-asr-whisperx` service sets `ADAM_MODELS_DIR` to the default `Subsystem/Models` (relative to `WORKDIR=/app`), resolving to `/app/Subsystem/Models` inside the container. This path is **not mounted as a volume**. The `Subsystem/Models` host directory is also not mounted. As a result, whisperx downloads the large-v3 model (~3 GB) into the ephemeral container layer on every cold start. On a Jetson with limited storage and external internet access constrained to the v2ray proxy, this is a repeated expensive failure mode.

**Fix:**
```yaml
adam-asr-whisperx:
  environment:
    ADAM_MODELS_DIR: /models
  volumes:
    - ./data:/data
    - ./data/hf_cache:/hf_cache
    - ./Subsystem/Models:/models   # ADD this line
    - /etc/localtime:/etc/localtime:ro
```

---

### CR-03: Silent infinite-standby when `adam.onnx` is missing — no error, no fallback

**File:** `System/adam/wake_word.py:99-100` and `System/Orchestrator.py:330-349`

**Issue:** When the ONNX model file does not exist, `create_engine()` returns `None` (line 100: silent fallback, intentional for the "not yet trained" case). With `_wake_engine = None` and `wake_word_required = true` (set in Config.json), the voice loop enters a permanent standby: the `if self._wake_engine is not None` guard at Orchestrator.py line 331 never triggers, so `_voice_state` never leaves `"standby"`. Adam never responds to any audio. There is **no log warning, no event emitted, and no status flag** to indicate why the system is unresponsive. An operator looking at `voice_loop.status()` sees `vad_state: "standby"` with no indication that the OWW engine is absent.

**Fix — two-part:**

1. In `wake_word.py`, log a warning when the model is missing:
```python
if not Path(model_path).exists():
    import logging
    logging.getLogger(__name__).warning(
        "OpenWakeWord model not found at %s — wake word detection disabled", model_path
    )
    return None
```

2. In `Orchestrator.py` `__init__`, warn when `wake_word_required` is set but engine is absent:
```python
self._wake_engine = _create_wake_engine(ww_cfg)
if self._wake_engine is None and self.wake_word_required:
    event_log.append("wake_engine_missing", {
        "reason": "model_not_found",
        "model_path": ww_cfg.get("model_path"),
        "effect": "voice_loop_stuck_in_standby",
    })
```

---

### CR-04: `compose.yaml` orchestrator defaults to stale Ollama stack — LLM unreachable

**File:** `compose.yaml:14-16`

**Issue:** The `adam-orchestrator` service hardcodes Ollama defaults:
```yaml
ADAM_LLM_PROVIDER: ${ADAM_LLM_PROVIDER:-ollama}
ADAM_LLM_BASE_URL: ${ADAM_LLM_BASE_URL:-http://127.0.0.1:11434}
ADAM_LLM_MODEL: ${ADAM_LLM_MODEL:-gemma3:4b}
```
The project has migrated to llama.cpp (port 8081, `gemma-4-E4B-it-UD-Q4_K_XL`). No `.env.example` ships these new defaults. When running `docker compose up adam-orchestrator` without explicit env vars, the orchestrator attempts to connect to Ollama at port 11434, which is not running. LLM health check fails, exhibition gate blocks, and every dialogue turn errors.

**Fix:**
```yaml
ADAM_LLM_PROVIDER: ${ADAM_LLM_PROVIDER:-openai}
ADAM_LLM_BASE_URL: ${ADAM_LLM_BASE_URL:-http://127.0.0.1:8081/v1}
ADAM_LLM_MODEL: ${ADAM_LLM_MODEL:-gemma-4-E4B-it-UD-Q4_K_XL}
```

---

## Warnings

### WR-01: `/health` reports wrong model size when VRAM fallback triggers

**File:** `System/Speech/ASR_WhisperX.py:56-65, 160`

**Issue:** `_resolve_model_size()` can return `"medium"` (fallback when VRAM < 12 GB), but the `/health` endpoint always reports `_MODEL_SIZE` — the original env-var value (e.g. `"large-v3"`). The health payload misleads the operator: the model field shows `large-v3` while the actual loaded model is `medium`.

**Fix:** Store the resolved size at load time and use it in the health response:
```python
_RESOLVED_MODEL_SIZE: str = ""   # set in _get_model()

def _get_model() -> Any:
    global _MODEL, _RESOLVED_MODEL_SIZE
    if _MODEL is not None:
        return _MODEL
    ...
    model_size = _resolve_model_size()
    _RESOLVED_MODEL_SIZE = model_size
    _MODEL = whisperx.load_model(model_size, ...)
    return _MODEL

# In /health:
"model": _RESOLVED_MODEL_SIZE or _MODEL_SIZE,
```

---

### WR-02: `_n_frames` is stored but never used — frame count is hardcoded to 4

**File:** `System/adam/wake_word.py:39` and `System/Orchestrator.py:249`

**Issue:** `OpenWakeWordEngine.__init__` reads `self._n_frames = self._oww.model_inputs[self._model_name]` (the number of audio samples the ONNX model expects per call). However, this value is **never used**: the Orchestrator hardcodes `self._ww_frames_needed = 4` (line 249), which assumes 4 × 20ms = 80ms = 1280 samples. If a custom model is trained with a different receptive field (e.g. 160ms = 2560 samples), the engine silently receives the wrong-sized chunk. The `_n_frames` value exists but is disconnected from `_ww_frames_needed`.

**Fix:** Either expose `_n_frames` and use it in the Orchestrator, or remove the unused attribute. Minimal fix in Orchestrator:
```python
# After engine creation, derive chunk sizing from the model:
if self._wake_engine is not None and hasattr(self._wake_engine, "_n_frames"):
    model_samples = self._wake_engine._n_frames  # e.g. 1280
    frame_samples = self.sample_rate * self.frame_ms // 1000  # 320
    self._ww_frames_needed = max(1, model_samples // frame_samples)
```

---

### WR-03: `_get_model()` has a TOCTOU race under concurrent `/transcribe` calls

**File:** `System/Speech/ASR_WhisperX.py:78-100`

**Issue:** The `_get_model()` singleton has a check-then-set pattern without a lock:
```python
if _MODEL is not None:
    return _MODEL
# ... load_model() ...
_MODEL = whisperx.load_model(...)
```
In a scenario where two `asyncio.to_thread(_transcribe, ...)` calls land before the lifespan warmup completes, two threads can both observe `_MODEL is None` and both call `whisperx.load_model()`. On a 16 GB Jetson, loading large-v3 twice simultaneously will OOM. The lifespan warmup reduces this window to near-zero in normal operation, but it is not zero.

**Fix:**
```python
import threading
_MODEL_LOCK = threading.Lock()

def _get_model() -> Any:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:   # double-check after acquiring lock
            return _MODEL
        ...
        _MODEL = whisperx.load_model(...)
        return _MODEL
```

---

### WR-04: `systemd` service missing `TimeoutStartSec` — restart loop on first boot

**File:** `deploy/systemd/adam-asr-whisperx.service`

**Issue:** The service sets `Restart=always` and `RestartSec=5` but has no `TimeoutStartSec`. The systemd default is 90 seconds. Loading `large-v3` on first run involves downloading ~3 GB and compiling CUDA kernels; on a Jetson Orin NX this routinely takes 2–5 minutes. The unit will be killed by systemd after 90 seconds, restart, and loop indefinitely on first run until the model is cached. A `TimeoutStartSec=0` (unlimited) or a sufficiently large value is needed.

**Fix:**
```ini
[Service]
Type=simple
TimeoutStartSec=600
TimeoutStopSec=10
Restart=on-failure
RestartSec=10
```
Using `Restart=on-failure` instead of `Restart=always` also prevents restart when the process exits cleanly (e.g. SIGTERM during stop).

---

## Info

### IN-01: `requirements.txt` pins `numpy>=1.24.0` — allows numpy 2.x which breaks ctranslate2

**File:** `System/requirements.txt:7`

**Issue:** The installed environment has numpy 2.2.6, but `ctranslate2` (and the Jetson PyTorch wheel) were compiled against numpy 1.x. The current constraint `numpy>=1.24.0` allows numpy 2.x, leading to the "A module compiled using NumPy 1.x cannot be run in NumPy 2.x" warning on import. While ctranslate2 may still function on Tegra CUDA paths, this is a latent crash risk.

**Fix:**
```
numpy>=1.24.0,<2.0
```

---

### IN-02: `compose.yaml` whisperx uses `ADAM_ASR_PORT` env var but orchestrator also uses same var

**File:** `compose.yaml:83`

**Issue:** Both `adam-asr-whisperx` and the legacy `adam-asr-whisper` containers share the `ADAM_ASR_PORT` env var name with different defaults (8095 vs 8083). The `adam-orchestrator` service reads `ADAM_ASR_PORT` too. If someone sets `ADAM_ASR_PORT=8083` for a legacy deployment, the new whisperx service silently starts on the wrong port while the orchestrator ASR config (which reads from Config.json, `base_url: "http://127.0.0.1:8095"`) remains hardcoded to 8095 — mismatch goes unnoticed until health check times out. The port should be defined explicitly in `adam-asr-whisperx` without relying on the shared `ADAM_ASR_PORT` variable, or the variable name should be scoped (e.g. `ADAM_ASR_WHISPERX_PORT`).

---

_Reviewed: 2026-05-13_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: deep_
