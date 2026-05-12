"""Local wake word detection — runs entirely on CPU, <5ms per 80ms frame."""
from __future__ import annotations

import struct
from typing import Any


class WakeWordEngine:
    def process_chunk(self, pcm_80ms: bytes) -> bool:
        raise NotImplementedError

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
            vad_threshold=vad_threshold,
        )
        self._model_name = list(self._oww.models.keys())[0]
        self._n_frames = self._oww.model_inputs[self._model_name]
        self._threshold = threshold
        self._debounce_hits = debounce_hits
        self._consecutive_hits = 0

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
        if score >= self._threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0
        if self._consecutive_hits >= self._debounce_hits:
            self._consecutive_hits = 0  # reset so re-trigger requires a full new debounce sequence
            return True
        return False

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
