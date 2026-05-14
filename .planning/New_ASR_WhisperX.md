# Implementation Plan: New ASR Architecture (WhisperX + openWakeWord)

> **Branch:** `V_S002-New_ASR_WhisperX`
> **Target:** NVIDIA Jetson Orin NX Super 16GB, JetPack 6.2.2 (L4T 36.5.01, CUDA 12.6)
> **Goal:** Replace broken ASR module with WhisperX (CUDA) + rebuild wake word detection (CPU) with zero false positives

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Voice Loop Controller                        │
│                                                                     │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐  │
│  │ arecord  │───▶│ openWakeWord adam.onnx (with built-in VAD)   │  │
│  │ (mic in) │    │ VAD filters non-speech → OWW detects "Адам"  │  │
│  └──────────┘    └────────────────────┬─────────────────────────┘  │
│                                       │                             │
│                                  yes  │   no                        │
│                       ┌───────────────▼──────────────┐              │
│                       │ Wake detected!               │              │
│                       │ → listening mode             │              │
│                       └──────────────────────────────┘              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  listening → VAD accumulate → 1.5s silence → transcribe      │  │
│  │  → WhisperX (CUDA) → LLM → TTS → 4s reply window → standby  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Rebuild Wake Word Engine

### 1.1 Rewrite `System/adam/wake_word.py`

**Replace the entire file.** The new implementation:

- Removes the sklearn `LogisticRegression` verifier (`adam_verifier.pkl`)
- Uses the custom `adam.onnx` model directly via openWakeWord
- Uses openWakeWord's **built-in Silero VAD** (via `vad_threshold` parameter) — no custom pre-filter needed
- Maintains the same `WakeWordEngine` interface (`process_chunk() -> bool`)

**New architecture:**

```python
class WakeWordEngine:
    def process_chunk(self, pcm_80ms: bytes) -> bool: ...
    def close(self) -> None: ...

class OpenWakeWordEngine(WakeWordEngine):
    """Uses adam.onnx directly with built-in Silero VAD.
    Debounced: requires N consecutive positive detections."""

    def __init__(self, model_path: str, threshold: float, debounce_hits: int,
                 vad_threshold: float = 0.5) -> None:
        import numpy as np
        import openwakeword

        self._np = np
        # openWakeWord has built-in Silero VAD — no separate pre-filter needed
        self._oww = openwakeword.Model(
            wakeword_models=[model_path],
            vad_threshold=vad_threshold,  # Built-in VAD filters non-speech
        )
        self._model_name = list(self._oww.models.keys())[0]
        self._n_frames = self._oww.model_inputs[self._model_name]
        self._threshold = threshold
        self._debounce_hits = debounce_hits
        self._consecutive_hits = 0

        # Flush the model's initial ring-buffer with silence
        silence = np.zeros(1280, dtype=np.int16)
        for _ in range(20):
            self._oww.predict(silence)

    def process_chunk(self, pcm_80ms: bytes) -> bool:
        np = self._np
        audio = np.frombuffer(pcm_80ms, dtype=np.int16)
        prediction = self._oww.predict(audio)
        score = prediction.get(self._model_name, 0)
        if score >= self._threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0
        if self._consecutive_hits >= self._debounce_hits:
            self._consecutive_hits = 0  # reset for re-trigger
            return True
        return False

    def close(self) -> None:
        pass

def create_engine(config: dict) -> WakeWordEngine | None:
    """Build from config. engine="openwakeword" → OpenWakeWordEngine with built-in VAD."""
    engine = str(config.get("engine", "none")).lower()
    if engine == "openwakeword":
        from pathlib import Path
        from adam.config import PROJECT_ROOT
        raw = str(config.get("model_path", "data/wake_word/adam.onnx"))
        p = Path(raw)
        model_path = str(p if p.is_absolute() else PROJECT_ROOT / p)
        if not p.exists():
            return None  # model not yet trained — fall back to None
        return OpenWakeWordEngine(
            model_path=model_path,
            threshold=float(config.get("threshold", 0.5)),
            debounce_hits=int(config.get("debounce_hits", 5)),
            vad_threshold=float(config.get("vad_threshold", 0.5)),
        )
    return None  # engine="none" → no wake word detection
```

**Key implementation details:**

1. **Built-in Silero VAD:**
   - openWakeWord's `Model(vad_threshold=0.5)` already runs Silero VAD internally
   - Non-speech audio is filtered before reaching the wake word detector
   - This eliminates ~80-90% of false positives from non-speech noise
   - No need for a separate VAD pre-filter class

2. **openWakeWord with adam.onnx:**
   - Load `adam.onnx` via `openwakeword.Model(wakeword_models=[model_path])`
   - Use built-in model scoring (no external verifier)
   - Debounce: require **5 consecutive** positive hits (400ms of "адам")
   - Threshold: start at 0.5, tune based on real-world testing

3. **Config changes:**
   - `wake_word.engine`: `"openwakeword"` (unchanged)
   - `wake_word.model_path`: `"data/wake_word/adam.onnx"` (NEW — replaces `verifier_path`)
   - `wake_word.threshold`: `0.5` (adjusted for native OWW scoring)
   - `wake_word.debounce_hits`: `5` (NEW — 5 × 80ms = 400ms)
   - `wake_word.vad_threshold`: `0.5` (NEW — built-in Silero VAD threshold)
   - Remove `wake_word.verifier_path` (no longer needed)

### 1.2 Update `System/Config.json`

Update the `wake_word` section:

```json
"wake_word": {
    "engine": "openwakeword",
    "model_path": "data/wake_word/adam.onnx",
    "threshold": 0.5,
    "debounce_hits": 5,
    "vad_threshold": 0.5
}
```

Remove the old `verifier_path` key.

### 1.3 Update `System/Orchestrator.py` — VoiceLoopController

**No structural changes needed** to the voice loop state machine. The `VoiceLoopController` already:

- Uses `self._wake_engine = _create_wake_engine(ww_cfg)` — will get the new engine automatically
- Accumulates 80ms chunks in `self._ww_buf` and calls `process_chunk(pcm_80ms)` — interface unchanged
- Has guard window (`_STANDBY_GUARD_SEC`) after TTS — keep as-is
- Has debounce logic built into the engine — keep as-is

**Only change:** Ensure the config keys match the new `wake_word` section format.

### 1.4 Update `System/requirements.txt`

Ensure these dependencies are present:

```
openwakeword>=0.6.0
onnxruntime>=1.16.0
numpy>=1.24.0
```

Remove any references to `scikit-learn` or `pickle`-based verifier if they exist.

### 1.5 Add `.gitignore` entry for the model (if needed)

The `adam.onnx` model is ~1-2MB and should be committed to the repo. Ensure it's NOT in `.gitignore`.

If the model file is too large for git, consider using Git LFS:

```bash
git lfs install
git lfs track "data/wake_word/adam.onnx"
git add .gitattributes
```

---

## Phase 2: WhisperX ASR Service

### 2.1 Create `System/Speech/ASR_WhisperX.py`

New FastAPI microservice, replacing `ASR_Whisper.py`.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/transcribe` | Transcribe WAV audio → JSON `{"ok": true, "transcript": "..."}` |

**Model configuration:**

```python
_MODEL_SIZE = os.environ.get("ADAM_ASR_WHISPERX_MODEL", "large-v3")
_LANGUAGE = os.environ.get("ADAM_ASR_LANGUAGE", "ru")
_DEVICE = os.environ.get("ADAM_ASR_DEVICE", "cuda")
_COMPUTE_TYPE = os.environ.get("ADAM_ASR_COMPUTE_TYPE", "float16")
_SAMPLE_RATE = int(os.environ.get("ADAM_ASR_SAMPLE_RATE", "16000"))
```

**Model loading (in lifespan):**

```python
import whisperx
import torch

model = whisperx.load_model(
    _MODEL_SIZE,
    device=_DEVICE,
    compute_type=_COMPUTE_TYPE,
    download_root=str(_MODELS_DIR),
    asr_options={
        "language": _LANGUAGE,
        "vad_method": "silero",  # Use Silero VAD (no HF token needed)
        # Do NOT use "pyannote" — it requires a HuggingFace token and gated model access
    },
)
```

**Transcription logic:**

```python
def _transcribe(wav_bytes: bytes) -> str:
    import tempfile
    import numpy as np

    # whisperx.load_audio() requires a file path, NOT a file-like object.
    # Write WAV bytes to a temp file, then load it.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        audio = whisperx.load_audio(tmp_path)  # returns numpy array, float32, 16kHz
        result = model.transcribe(
            audio,
            language=_LANGUAGE,
            batch_size=1,          # Jetson Orin: single batch to avoid OOM
            # NOTE: VAD is configured at model load time via asr_options,
            # NOT at transcribe time. No vad_filter/vad_parameters here.
        )
        # Filter out low-confidence segments
        # WhisperX segments have 'avg_logprob' (NOT 'no_speech_prob')
        parts = []
        for seg in result.get("segments", []):
            # avg_logprob: lower = worse quality. -0.5 is a good threshold for Russian.
            if seg.get("avg_logprob", -1.0) < -0.5:
                continue
            text = seg.get("text", "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()
    finally:
        os.unlink(tmp_path)  # Always clean up temp file
```

**Key differences from current `ASR_Whisper.py`:**

| Aspect | Old (faster-whisper) | New (whisperx) |
|--------|---------------------|----------------|
| Import | `from faster_whisper import WhisperModel` | `import whisperx` |
| Audio input | `io.BytesIO(wav_bytes)` (file-like) | Temp file → `whisperx.load_audio(path)` (numpy) |
| VAD config | `vad_filter=True` in `transcribe()` | `vad_method="silero"` in `load_model()` |
| Output | `segments, info = model.transcribe(...)` | `result = model.transcribe(...)` (dict) |
| Quality filter | `seg.no_speech_prob` | `seg.avg_logprob` (different field!) |
| Warmup | Silent frame via `io.BytesIO` | Silent numpy array directly |

**Health endpoint:**

```python
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
```

**Dependency check:**

```python
def _dependency_errors() -> list[str]:
    errors = []
    for module in ("whisperx", "faster_whisper", "ctranslate2"):
        try:
            __import__(module)
        except ImportError as exc:
            errors.append(f"{module}: {exc}")
    return errors
```

### 2.2 Update `System/adam/inference.py`

Add `WhisperXASRClient` class. Since the API is identical to the current `WhisperASRClient` (both use `POST /transcribe` with WAV body, returning `{"transcript": "..."}`), you can:

**Option A (simplest):** Reuse the existing `WhisperASRClient` — no code changes needed if the endpoint contract is identical.

**Option B (explicit):** Add a new `WhisperXASRClient` class that:
- Has the same interface: `transcribe_pcm(pcm) -> str`, `health() -> ServiceHealth`
- Reports `provider: "whisperx"` in health checks
- Can be distinguished in logs/metrics

Update `create_asr_client()` to handle `provider: "whisperx"`:

```python
def create_asr_client(config: dict[str, Any]) -> WhisperASRClient | WhisperXASRClient | SpeachesASRClient:
    provider = str(config.get("provider", "whisper")).strip().lower()
    if provider == "speaches":
        return SpeachesASRClient(config)
    if provider == "whisperx":
        return WhisperXASRClient(config)  # or WhisperASRClient if reusing
    return WhisperASRClient(config)
```

### 2.3 Update `System/Config.json` — ASR section

```json
"services": {
    "asr": {
        "provider": "whisperx",
        "base_url": "http://127.0.0.1:8095",
        "model": "large-v3",
        "language": "ru",
        "command_endpointing_ms": 1500,
        "reply_window_sec": 4.0,
        "reply_absolute_deadline_sec": 12.0,
        "reply_noise_gate": 1000,
        "sample_rate": 16000,
        "timeout_sec": 30,
        "wake_words": "адам",
        "wake_word_required": true
    }
}
```

**Key config values explained:**

| Key | Value | Purpose |
|-----|-------|---------|
| `provider` | `"whisperx"` | Selects WhisperXASRClient |
| `base_url` | `http://127.0.0.1:8095` | ASR service port (changed from 8083) |
| `model` | `"large-v3"` | Best Russian accuracy. Use `"medium"` if OOM. |
| `command_endpointing_ms` | `1500` | 1.5s silence = end of utterance |
| `reply_window_sec` | `4.0` | Follow-up window after TTS response |
| `wake_words` | `"адам"` | Comma-separated wake words for text-level stripping |
| `wake_word_required` | `true` | Require wake word in transcript |

### 2.4 Update `compose.yaml`

Add/replace the ASR service:

```yaml
adam-asr-whisperx:
  build:
    context: .
    dockerfile: System/Dockerfile
  container_name: adam-asr-whisperx
  profiles:
    - speech-local
  network_mode: host
  restart: unless-stopped
  runtime: nvidia
  environment:
    PYTHONPATH: System
    ADAM_ASR_PORT: ${ADAM_ASR_PORT:-8095}
    ADAM_ASR_WHISPERX_MODEL: ${ADAM_ASR_WHISPERX_MODEL:-large-v3}
    ADAM_ASR_LANGUAGE: ${ADAM_ASR_LANGUAGE:-ru}
    ADAM_ASR_DEVICE: cuda
    ADAM_ASR_COMPUTE_TYPE: float16
    ADAM_ASR_SAMPLE_RATE: "16000"
    NVIDIA_DRIVER_CAPABILITIES: compute,utility
    HF_HOME: /hf_cache
    HF_HUB_CACHE: /hf_cache/hub
  command: ["python", "-m", "Speech.ASR_WhisperX"]
  volumes:
    - ./data:/data
    - ./data/hf_cache:/hf_cache
    - /etc/localtime:/etc/localtime:ro
```

**Note:** The volume `./data/hf_cache:/hf_cache` uses a directory that will be created on first run.
If `Subsystem/Models/hf` already contains cached models, change to:
```yaml
    - ./Subsystem/Models/hf:/hf_cache
```

Keep the old `adam-asr-whisper` and `adam-asr-speaches` services for backward compatibility but mark them as deprecated in comments.

### 2.5 Update `System/requirements.txt`

Add WhisperX dependencies:

```
# ASR — WhisperX (CUDA-optimized speech recognition)
whisperx>=3.1.0
faster-whisper>=1.0.0
ctranslate2>=4.0.0
# NOTE: pyannote.audio is NOT needed when using vad_method="silero"
# Only add it if you switch to vad_method="pyannote" (requires HF token)
```

### 2.6 Create `System/Speech/__init__.py`

Create an empty `__init__.py` file to make `Speech` a proper Python package:

```python
"""Speech services for Adam Chip — ASR and TTS microservices."""
```

Without this file, `python -m Speech.ASR_WhisperX` will fail with `ModuleNotFoundError`.

### 2.7 Add entry point to `ASR_WhisperX.py`

Add a `__main__` block at the end of the file so it can be run as a module:

```python
def main() -> None:
    import uvicorn

    host = os.environ.get("ADAM_ASR_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_ASR_PORT", "8095"))
    app_dir = str(Path(__file__).resolve().parents[1])
    uvicorn.run("Speech.ASR_WhisperX:app", host=host, port=port, reload=False, app_dir=app_dir)


if __name__ == "__main__":
    main()
```

### 2.8 Add model warmup to lifespan

The lifespan must warm up the model to absorb the cold-start penalty:

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    await asyncio.to_thread(_get_model)
    # Warmup: run a silent frame through the model
    warmup_audio = np.zeros(_SAMPLE_RATE, dtype=np.float32)  # 1 second of silence
    await asyncio.to_thread(_transcribe_audio, warmup_audio)
    yield
```

Add a helper function that accepts numpy array directly (bypassing temp file for warmup):

```python
def _transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe a numpy array (float32, 16kHz) directly."""
    result = model.transcribe(audio, language=_LANGUAGE, batch_size=1)
    parts = []
    for seg in result.get("segments", []):
        if seg.get("avg_logprob", -1.0) < -0.5:
            continue
        text = seg.get("text", "").strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()
```

### 2.9 Add OOM detection and fallback

On Jetson Orin NX 16GB, `large-v3` with float16 uses ~3-5GB. Add automatic fallback:

```python
def _resolve_compute_type(device: str) -> str:
    if _COMPUTE_TYPE != "auto":
        return _COMPUTE_TYPE
    if device != "cuda":
        return "float32"
    # Check available VRAM
    try:
        import torch
        free_mem = torch.cuda.get_device_properties(0).total_memory
        free_gb = free_mem / (1024 ** 3)
        if free_gb < 8:  # Less than 8GB total — use int8
            return "int8"
        return "float16"
    except Exception:
        return "float16"  # fallback
```

Also add a model size fallback in config:

```python
def _resolve_model_size() -> str:
    """Fall back to 'medium' if VRAM is limited."""
    try:
        import torch
        free_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if free_gb < 12:
            return "medium"  # safer for 16GB shared memory
    except Exception:
        pass
    return _MODEL_SIZE
```

### 2.10 Create systemd service file

```ini
[Unit]
Description=Adam Chip WhisperX ASR Service
After=network.target
Wants=network.target

[Service]
Type=simple
# REPLACE: i17jet → actual username on Jetson
# REPLACE: /home/i17jet/Agents/Adam-Chip → actual project path
User=i17jet
WorkingDirectory=/home/i17jet/Agents/Adam-Chip
Environment=PYTHONPATH=System
Environment=PATH=/home/i17jet/Agents/Adam-Chip/.venv/bin
Environment=ADAM_ASR_PORT=8095
Environment=ADAM_ASR_WHISPERX_MODEL=large-v3
Environment=ADAM_ASR_LANGUAGE=ru
Environment=ADAM_ASR_DEVICE=cuda
Environment=ADAM_ASR_COMPUTE_TYPE=float16
Environment=HF_HOME=/home/i17jet/Agents/Adam-Chip/data/hf_cache
ExecStart=/home/i17jet/Agents/Adam-Chip/.venv/bin/python -m Speech.ASR_WhisperX
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=adam-asr-whisperx

# GPU access
DeviceAllow=/dev/nvidia0 rw
DeviceAllow=/dev/nvidiactl rw

[Install]
WantedBy=multi-user.target
```

---

## Phase 3: Voice Loop Timing Adjustments

### 3.1 Update `VoiceLoopController` in `System/Orchestrator.py`

The voice loop state machine is already well-structured. Make these targeted adjustments:

#### 3.1.1 Add 3-second silence timeout after wake word detection

**Current behavior:** After wake word is detected, the loop enters `listening` state and starts accumulating speech frames. If the user says "Адам" and then stays silent, the loop waits indefinitely for speech.

**Required behavior:** If no speech is detected within 3 seconds of wake word → return to standby.

**Implementation:** Add a `_wake_detected_at` timestamp and check in the listening loop:

```python
# In __init__:
self._wake_detected_at: float = 0.0
self._wake_silence_timeout_sec: float = 3.0

# After wake word detected (in _run, standby section):
if self._wake_engine.process_chunk(pcm_80ms):
    event_log.append("wake_word_detected", {"engine": "openwakeword"})
    self._voice_state = "listening"
    self._wake_detected_at = time.perf_counter()
    speech_frames.clear()
    speech_ms = 0
    silence_ms = 0

# In listening section, before VAD accumulation:
if self._voice_state == "listening" and speech_ms == 0:
    elapsed = time.perf_counter() - self._wake_detected_at
    if elapsed >= self._wake_silence_timeout_sec:
        event_log.append("wake_silence_timeout", {
            "action": "standby",
            "elapsed_sec": round(elapsed, 1),
        })
        self._voice_state = "standby"
        self._standby_entry_time = time.perf_counter()
        self._ww_buf.clear()
        continue
```

#### 3.1.2 Verify endpointing is 1.5 seconds

Current config has `command_endpointing_ms: 1500` — this is correct (1.5s silence = end of utterance). No change needed, just verify it's loaded correctly:

```python
# In VoiceLoopController.__init__:
self._command_endpointing_ms = int(asr_cfg.get("command_endpointing_ms", 1500))
```

#### 3.1.3 Verify reply window is 4 seconds

Current config has `reply_window_sec: 4.0` — correct. No change needed.

#### 3.1.4 Ensure mic is off during processing

Current code already does `_stop_process()` before transcribing and restarts after — correct. No change needed.

### 3.2 Update `media.audio` section in `Config.json`

Ensure audio settings match the voice loop expectations:

```json
"media": {
    "audio": {
        "input_device": "pulse",
        "output_device": "default",
        "sample_rate": 16000,
        "channels": 1,
        "frame_ms": 20,
        "vad_threshold": 600,
        "min_speech_ms": 200,
        "max_segment_ms": 3000,
        "max_command_segment_ms": 15000,
        "normalize_factor": 8000
    }
}
```

---

## Phase 4: Integration & Backward Compatibility

### 4.1 Ensure `_rebuild_clients()` handles the new ASR provider

In `System/Orchestrator.py`, the `_rebuild_clients()` function already recreates the ASR client when `services.asr` is patched:

```python
if section_path.startswith("services.asr") or section_path == "services":
    asr = create_asr_client(services.get("asr", {}))
    voice_loop.asr_client = asr
    restarted.append("asr")
```

This will work automatically with the updated `create_asr_client()` that handles `provider: "whisperx"`.

### 4.2 Ensure health check endpoint reports correctly

The `/api/agent/status` endpoint calls `asr.health()` — the new `WhisperXASRClient` must return a compatible `ServiceHealth` object with `ok`, `detail`, `loading` fields.

### 4.3 Keep old ASR services as fallback

Do NOT delete `ASR_Whisper.py`. Keep it as a fallback option. Users can switch back by changing `provider` in Config.json:

```json
"asr": {
    "provider": "whisper",  // or "whisperx" or "speaches"
    ...
}
```

### 4.4 Event log compatibility

Ensure all existing event types are preserved:

| Event | When emitted | Must keep? |
|-------|-------------|------------|
| `voice_loop_started` | Voice loop start | Yes |
| `voice_loop_stopped` | Voice loop stop | Yes |
| `voice_loop_error` | Error in loop | Yes |
| `wake_word_detected` | Wake word trigger | Yes |
| `wake_silence_timeout` | NEW — 3s silence after wake | Yes (new) |
| `asr_partial` | Speech started | Yes |
| `asr_final` | Transcript ready | Yes |
| `asr_wake_only` | Only wake word in transcript | Yes |
| `asr_reply_window_open` | Reply window opened | Yes |
| `reply_window_expired` | Reply window closed | Yes |
| `warmup_asr` | ASR warmup | Yes |

---

## Phase 5: Testing & Validation

### 5.1 Smoke tests

Run these commands on the Jetson:

```bash
# 1. Check wake word model exists
ls -la data/wake_word/adam.onnx

# 2. Start ASR service
./.venv/bin/python -m Speech.ASR_WhisperX &
sleep 10  # wait for model load

# 3. Health check
curl -s http://127.0.0.1:8095/health | python3 -m json.tool

# 4. Test transcription with a WAV file
curl -s -X POST http://127.0.0.1:8095/transcribe \
  -H "Content-Type: audio/wav" \
  --data-binary @test_audio_ru.wav | python3 -m json.tool

# 5. Start orchestrator
PYTHONPATH=System ./.venv/bin/python System/Orchestrator.py

# 6. Check status
curl -s http://127.0.0.1:8080/api/agent/status | python3 -m json.tool

# 7. Check voice loop status
curl -s http://127.0.0.1:8080/api/agent/listen/status | python3 -m json.tool
```

### 5.2 Integration tests

1. **Wake word test:** Say "Адам" from 1-3 meters — should trigger within 400ms
2. **False positive test:** Play background music, talk normally for 10 minutes — should NOT trigger
3. **Silence timeout test:** Say "Адам" and stay silent — should return to standby after 3s
4. **Endpointing test:** Say "Адам, расскажи о себе" then pause 1.5s — should transcribe and respond
5. **Reply window test:** After response, immediately ask a follow-up — should process without wake word
6. **Reply window expiry:** After response, wait 5s then speak — should be ignored (back to standby)

### 5.3 Performance targets

| Metric | Target | How to measure |
|--------|--------|---------------|
| Wake word false positive rate | < 0.5/hour | Count `wake_word_detected` events in 2h of background noise |
| Wake word detection latency | < 500ms | Time from end of "Адам" to `wake_word_detected` event |
| ASR latency (CUDA) | < 3s for 10s utterance | `last_asr_ms` in `/api/agent/status` |
| End-to-end turn latency | < 10s | `total_ms` in dialogue turn response |
| Memory usage (ASR) | < 4GB VRAM | `tegrastats` or `nvidia-smi` |

---

## File Change Summary

| File | Action | Phase |
|------|--------|-------|
| `data/wake_word/adam.onnx` | **User creates** (Colab) | Phase 0 |
| `System/adam/wake_word.py` | **Rewrite** — OWW with built-in VAD | Phase 1 |
| `System/Config.json` | **Update** — wake_word + asr sections | Phase 1, 2 |
| `System/Orchestrator.py` | **Modify** — 3s wake silence timeout | Phase 3 |
| `System/adam/inference.py` | **Add** — WhisperXASRClient | Phase 2 |
| `System/Speech/__init__.py` | **Create** — package init | Phase 2 |
| `System/Speech/ASR_WhisperX.py` | **Create** — new ASR service | Phase 2 |
| `System/requirements.txt` | **Update** — whisperx deps | Phase 2 |
| `compose.yaml` | **Update** — add adam-asr-whisperx | Phase 2 |
| `deploy/systemd/adam-asr-whisperx.service` | **Create** | Phase 2 |
| `System/Speech/ASR_Whisper.py` | **Keep** (backward compat) | Phase 4 |

---

## Execution Order for Claude Code

1. **Verify** `data/wake_word/adam.onnx` exists — if not, stop and tell user to complete Phase 0
2. **Rewrite** `System/adam/wake_word.py` with openWakeWord + built-in VAD
3. **Update** `System/Config.json` — wake_word section
4. **Create** `System/Speech/__init__.py`
5. **Create** `System/Speech/ASR_WhisperX.py` (with warmup, OOM fallback, entry point)
6. **Update** `System/adam/inference.py` — add WhisperXASRClient
7. **Update** `System/Config.json` — asr section
8. **Update** `System/Orchestrator.py` — 3s wake silence timeout
9. **Update** `System/requirements.txt`
10. **Update** `compose.yaml`
11. **Create** `deploy/systemd/adam-asr-whisperx.service`
12. **Verify** backward compatibility — old providers still work
13. **Run** smoke tests (health checks)

---

## Critical Constraints

1. **DO NOT change API contracts** — all `/api/*` endpoints must work identically
2. **DO NOT change TTS, LLM, VLM** clients or services
3. **DO NOT change UI** — WebUI backend and frontend stay as-is
4. **DO NOT delete** `ASR_Whisper.py` — keep for fallback
5. **DO NOT change** the voice loop state machine structure — only add the 3s silence timeout
6. **Preserve all event log types** — UI and diagnostics depend on them
7. **Config.json patching via API** must still work — `_rebuild_clients()` must handle new provider
8. **Model file path** must be relative to `PROJECT_ROOT` — use `config.py` path resolution

---

## Audit History

This plan was audited by GSD plan-checker and the following issues were fixed:

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| E1 | CRITICAL | `whisperx.load_audio(io.BytesIO())` — accepts file path only | Use temp file + `os.unlink` in finally |
| E2 | CRITICAL | `vad_filter=True` in `transcribe()` — not a WhisperX param | VAD configured at `load_model()` via `asr_options` |
| E3 | CRITICAL | `seg.no_speech_prob` — field doesn't exist in WhisperX | Use `seg.avg_logprob` for quality filtering |
| E4 | LOGICAL | VAD param names from faster-whisper, not WhisperX | Use `vad_method="silero"` in `asr_options` |
| E5 | LOGICAL | Custom SileroVADPreFilter redundant — OWW has built-in VAD | Use `openwakeword.Model(vad_threshold=...)` |
| E6 | LOGICAL | Colab config variable names may differ; Russian TTS may not exist | Added warning to verify TTS availability first |
| E7 | INCONSISTENCY | Transcribe endpoint input handling changes | Temp file approach shown in code |
| E8 | INCONSISTENCY | Missing `PYTHONPATH=System` in compose.yaml and systemd | Added to both |
| E9 | INCONSISTENCY | Hardcoded user/paths in systemd | Added REPLACE comments |
| E10 | INCONSISTENCY | Volume `./Subsystem/Models/hf` may not exist | Changed to `./data/hf_cache` with note |
| E11 | MISSING | No `Speech/__init__.py` — module import fails | Added as step 2.6 |
| E12 | MISSING | No `__main__` entry point in ASR_WhisperX.py | Added `main()` function |
| E13 | MISSING | No warmup implementation | Added to lifespan + `_transcribe_audio()` |
| E14 | MISSING | No OOM detection/fallback | Added `_resolve_compute_type()` + `_resolve_model_size()` |
| E15 | MISSING | pyannote.audio requires HF token | Removed from deps; use `vad_method="silero"` |
