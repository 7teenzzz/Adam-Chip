---
phase: 34
wave: 2
status: done
completed: 2026-06-09
---

# Phase 34 Wave 2 — ASR Hallucination Root-Cause Fixes

## Goal achieved

Addressed ASR hallucinations at the root cause (near-silence audio triggering WhisperX) rather than only expanding pattern lists.

## Changes made

### 1. Config.json + Config.schema.json
- `vad_onset`: 0.1 → 0.2 (primary root-cause fix — 0.1 was too sensitive, triggered on room noise)
- Added `asr_pre_send_min_rms: 200` — pre-send RMS gate, skips ASR entirely on near-silent PCM

### 2. System/Orchestrator.py
- RMS gate in `_transcribe_and_dispatch`: computes RMS of PCM before ASR call; if < `asr_pre_send_min_rms`, emits `asr_skipped_silent` event and returns without calling ASR
- Uses stdlib `struct` (numpy not imported in Orchestrator)
- `_is_hallucination` guard preserved (from previous wave): pattern check after transcription

### 3. System/Speech/ASR_WhisperX.py
- Added `_NO_SPEECH_THRESHOLD = 0.85` (env: `ADAM_ASR_NO_SPEECH_THRESHOLD`)
- Added `_COMPRESSION_RATIO_MIN = 1.1` (env: `ADAM_ASR_COMPRESSION_RATIO_MIN`)
- Applied both filters in `_transcribe_audio` segment loop after avg_logprob check
- Safe `.get()` fallbacks (0.0 / 999.0) — filters never fire if fields absent

### 4. compose.yaml
- `ADAM_ASR_VAD_ONSET` default: `0.1` → `0.2`

## Defense layers (in order of application)

1. **vad_onset=0.2** — Silero VAD less likely to trigger on room hum/noise (root cause)
2. **RMS gate** — Skip ASR entirely if PCM is near-silent (pre-call, Orchestrator)
3. **no_speech_prob** — Discard segments where Whisper is ≥85% sure there's no speech
4. **compression_ratio** — Discard extremely template-like sequences (hallucination signature)
5. **Pattern guard** — Last resort: 47 known YouTube/subtitle phrases blocked in both ASR_WhisperX.py and Orchestrator

## Required action (human)

Docker rebuild needed for ASR_WhisperX.py code changes:
```bash
docker compose build adam-asr-whisperx && docker compose up -d adam-asr-whisperx
```

vad_onset change in compose.yaml also requires container restart (included in rebuild).

## Reference

Root cause identified via git bisect: commit 9da07f92 (vad_onset=0.3, no hallucinations) vs commit cb93798 (vad_onset=0.1 via compose.yaml, hallucinations appear).

Pattern expansion alone cannot catch template hallucinations — they have HIGH avg_logprob (~-0.3) because the phrases are memorized YouTube training data.
