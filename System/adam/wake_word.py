"""Local wake word detection — runs entirely on CPU, <5ms per 80ms frame."""
from __future__ import annotations

import struct
from typing import Any


class WakeWordEngine:
    def process_chunk(self, pcm_80ms: bytes) -> bool:
        raise NotImplementedError

    def reset(self) -> None:
        # Default: no-op. Engines that maintain an internal audio buffer
        # across predict() calls (e.g. openWakeWord) override this to flush
        # the buffer with silence so a paused-then-resumed engine doesn't
        # score stale audio.
        pass

    def close(self) -> None:
        pass


class OpenWakeWordEngine(WakeWordEngine):
    """Uses adam.onnx directly with built-in Silero VAD.

    Debounced: requires N consecutive positive detections to avoid false triggers.
    openWakeWord's vad_threshold filters non-speech before the wake word model runs.
    """

    def __init__(
        self,
        model_path: str,
        threshold: float,
        debounce_hits: int,
        vad_threshold: float = 0.5,
    ) -> None:
        import numpy as np
        import openwakeword

        self._np = np
        self._oww = openwakeword.Model(
            wakeword_models=[model_path],
            inference_framework="onnx",  # adam.onnx requires onnxruntime, not tflite
            vad_threshold=vad_threshold,
        )
        self._model_name = list(self._oww.models.keys())[0]
        self._n_frames = self._oww.model_inputs[self._model_name]
        self._threshold = threshold
        self._debounce_hits = debounce_hits
        self._consecutive_hits = 0
        self.last_score: float = 0.0

        # Flush the model's initial ring-buffer with silence so it reflects a
        # real "no audio" baseline before any real audio arrives.
        silence = np.zeros(1280, dtype=np.int16)
        for _ in range(20):
            self._oww.predict(silence)

    def process_chunk(self, pcm_80ms: bytes) -> bool:
        np = self._np
        audio = np.frombuffer(pcm_80ms, dtype=np.int16)
        prediction = self._oww.predict(audio)
        score = prediction.get(self._model_name, 0)
        self.last_score = float(score)
        if score >= self._threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0
        if self._consecutive_hits >= self._debounce_hits:
            self._consecutive_hits = 0  # reset so re-trigger requires a full new debounce sequence
            return True
        return False

    def reset(self) -> None:
        # Flush the model's internal ~1.5s mel-spectrogram ring buffer with
        # silence. Required after the engine was paused (reply / no_reply /
        # boot_warmup states skip process_chunk) — otherwise the first
        # predict() on resume evaluates [stale ~1.5s][new 80ms] and the
        # stale tail (often containing the previous wake word + speech)
        # produces a false-positive score of 0.78-0.79 ~400 ms after
        # standby entry. Mirrors the silence-prime in __init__.
        silence = self._np.zeros(1280, dtype=self._np.int16)
        for _ in range(20):
            self._oww.predict(silence)
        self._consecutive_hits = 0
        self.last_score = 0.0

    # Live tuning — invoked by /api/wake_word/sensitivity PATCH. Clamp to safe
    # ranges and reset the debounce counter so the new threshold cannot "ride"
    # an already-accumulated hit streak from the previous setting.
    def set_threshold(self, threshold: float) -> None:
        self._threshold = max(0.0, min(1.0, float(threshold)))
        self._consecutive_hits = 0

    def set_debounce_hits(self, hits: int) -> None:
        self._debounce_hits = max(1, int(hits))
        self._consecutive_hits = 0

    @property
    def sensitivity(self) -> dict[str, Any]:
        return {
            "threshold": self._threshold,
            "debounce_hits": self._debounce_hits,
            "vad_threshold": getattr(self._oww, "vad_threshold", 0),
            "last_score": self.last_score,
            "consecutive_hits": self._consecutive_hits,
        }

    def close(self) -> None:
        pass


class PorcupineEngine(WakeWordEngine):
    """Picovoice Porcupine detector — requires a .ppn file and API key."""

    def __init__(self, keyword_path: str, access_key: str, sensitivity: float = 0.7) -> None:
        import pvporcupine

        self._porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
            sensitivities=[sensitivity],
        )

    def process_chunk(self, pcm_80ms: bytes) -> bool:
        n = self._porcupine.frame_length
        samples = struct.unpack_from(f"{n}h", pcm_80ms[: n * 2])
        return self._porcupine.process(samples) >= 0

    def close(self) -> None:
        self._porcupine.delete()


def create_engine(config: dict[str, Any]) -> WakeWordEngine | None:
    """Build from config. engine="openwakeword" → OpenWakeWordEngine with built-in VAD."""
    engine = str(config.get("engine", "none")).lower()
    if engine == "openwakeword":
        from pathlib import Path
        from adam.config import PROJECT_ROOT

        raw = str(config.get("model_path", "data/wake_word/adam.onnx"))
        p = Path(raw)
        model_path = str(p if p.is_absolute() else PROJECT_ROOT / p)
        if not Path(model_path).exists():
            return None  # model not yet trained — fall back to None
        return OpenWakeWordEngine(
            model_path=model_path,
            threshold=float(config.get("threshold", 0.5)),
            debounce_hits=int(config.get("debounce_hits", 5)),
            vad_threshold=float(config.get("vad_threshold", 0.5)),
        )
    if engine == "porcupine":
        return PorcupineEngine(
            keyword_path=str(config.get("keyword_path", "")),
            access_key=str(config.get("access_key", "")),
            sensitivity=float(config.get("sensitivity", 0.7)),
        )
    return None  # engine="none" → no wake word detection
