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
    """Detects "адам" using a trained sklearn verifier on top of openWakeWord embeddings.

    The verifier is a LogisticRegression pipeline trained on Silero TTS synthetic data.
    The openWakeWord base model acts as a fixed audio feature extractor (onnxruntime, CPU).
    """

    # Require this many consecutive positive detections to avoid false triggers.
    # 3 × 80ms = 240ms — covers full "адам" utterance, filters one-frame noise.
    _DEBOUNCE_HITS = 3

    def __init__(self, verifier_path: str, threshold: float = 0.7) -> None:
        import pickle
        import numpy as np
        import openwakeword

        self._np = np
        self._oww = openwakeword.Model(inference_framework="onnx")
        self._model_name = list(self._oww.models.keys())[0]
        self._n_frames = self._oww.model_inputs[self._model_name]
        with open(verifier_path, "rb") as fh:
            self._verifier = pickle.load(fh)
        self._threshold = threshold
        self._consecutive_hits = 0

        # Flush the model's initial ring-buffer with silence so it reflects a
        # real "no audio" baseline before any real audio arrives.
        silence = np.zeros(1280, dtype=np.int16)
        for _ in range(20):
            self._oww.predict(silence)

    def process_chunk(self, pcm_80ms: bytes) -> bool:
        np = self._np
        audio = np.frombuffer(pcm_80ms, dtype=np.int16)
        self._oww.predict(audio)
        feats = self._oww.preprocessor.get_features(self._n_frames)
        if feats.shape[0] == 0:
            self._consecutive_hits = 0
            return False
        x = feats.flatten().reshape(1, -1)
        score = float(self._verifier.predict_proba(x)[0, 1])
        if score >= self._threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0
        if self._consecutive_hits >= self._DEBOUNCE_HITS:
            self._consecutive_hits = 0  # reset so re-trigger requires a full new debounce sequence
            return True
        return False


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
    """Build a WakeWordEngine from a config dict, or return None for fallback mode."""
    engine = str(config.get("engine", "none")).lower()
    if engine == "openwakeword":
        from pathlib import Path
        from adam.config import PROJECT_ROOT
        raw = str(config.get("verifier_path", "data/wake_word/adam_verifier.pkl"))
        p = Path(raw)
        verifier_path = str(p if p.is_absolute() else PROJECT_ROOT / p)
        return OpenWakeWordEngine(
            verifier_path=verifier_path,
            threshold=float(config.get("threshold", 0.7)),
        )
    if engine == "porcupine":
        return PorcupineEngine(
            keyword_path=str(config.get("keyword_path", "")),
            access_key=str(config.get("access_key", "")),
            sensitivity=float(config.get("sensitivity", 0.7)),
        )
    return None  # engine="none" → Whisper-based wake detection fallback
