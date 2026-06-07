"""Unit tests for ASR_WhisperX CUDA enforcement and transcription filter logic.

Verifies that:
  1. _verify_cuda_available raises immediately when CUDA is absent.
  2. _load_model propagates CUDA errors — no silent CPU fallback.
  3. _load_model does NOT retry with device='cpu' after a CUDA failure.
  4. _load_model succeeds and returns the model object on happy path.

No whisperx or live CUDA required — torch and whisperx are mocked.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def _torch_mock(cuda_available: bool = True, total_memory_gb: float = 16.0) -> MagicMock:
    m = MagicMock(name="torch")
    m.cuda.is_available.return_value = cuda_available
    m.version.cuda = "12.6" if cuda_available else None
    props = MagicMock()
    props.total_memory = int(total_memory_gb * 1024 ** 3)
    m.cuda.get_device_properties.return_value = props
    return m


# ─── _verify_cuda_available ──────────────────────────────────────────────────

class TestVerifyCudaAvailable:
    """Behaviour of the CUDA pre-check before model load."""

    def test_raises_when_torch_reports_no_cuda(self):
        from Speech.ASR_WhisperX import _verify_cuda_available
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=False)}):
            with pytest.raises(RuntimeError, match="CUDA requested"):
                _verify_cuda_available()

    def test_passes_silently_when_cuda_available(self):
        from Speech.ASR_WhisperX import _verify_cuda_available
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            _verify_cuda_available()  # must not raise


# ─── _load_model ─────────────────────────────────────────────────────────────

class TestLoadModel:
    """_load_model must propagate failures and never retry on CPU."""

    def test_raises_on_ctranslate2_cpu_only_wheel(self):
        """The exact error seen in production (pip wheel, no CUDA) must propagate."""
        from Speech.ASR_WhisperX import _load_model
        mock_wx = MagicMock()
        mock_wx.load_model.side_effect = RuntimeError(
            "This CTranslate2 package was not compiled with CUDA support"
        )
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            with pytest.raises(RuntimeError, match="CTranslate2"):
                _load_model(mock_wx, "small", "cuda", "float16")

    def test_no_cpu_retry_after_cuda_failure(self):
        """load_model must be called exactly once — no silent retry with device='cpu'."""
        from Speech.ASR_WhisperX import _load_model
        mock_wx = MagicMock()
        mock_wx.load_model.side_effect = RuntimeError(
            "This CTranslate2 package was not compiled with CUDA support"
        )
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            with pytest.raises(RuntimeError):
                _load_model(mock_wx, "small", "cuda", "float16")

        assert mock_wx.load_model.call_count == 1, "must not retry with CPU"
        assert mock_wx.load_model.call_args[1]["device"] == "cuda"

    def test_generic_non_cuda_error_propagates(self):
        """Non-CUDA errors (OOM, file not found) must also propagate unchanged."""
        from Speech.ASR_WhisperX import _load_model
        mock_wx = MagicMock()
        mock_wx.load_model.side_effect = FileNotFoundError("model weights not found")
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            with pytest.raises(FileNotFoundError):
                _load_model(mock_wx, "small", "cuda", "float16")

    def test_succeeds_and_returns_model_object(self):
        """Happy path: returns the model object from whisperx.load_model."""
        from Speech.ASR_WhisperX import _load_model
        mock_wx = MagicMock()
        fake_model = object()
        mock_wx.load_model.return_value = fake_model
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            result = _load_model(mock_wx, "small", "cuda", "float16")
        assert result is fake_model

    def test_called_with_correct_params(self):
        """Ensures language, download_root and vad_options are forwarded to whisperx.load_model."""
        from Speech.ASR_WhisperX import _load_model, _LANGUAGE, _MODELS_DIR, _VAD_ONSET, _VAD_OFFSET
        mock_wx = MagicMock()
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            _load_model(mock_wx, "small", "cuda", "float16")
        call_kwargs = mock_wx.load_model.call_args[1]
        assert call_kwargs["device"] == "cuda"
        assert call_kwargs["compute_type"] == "float16"
        assert call_kwargs["language"] == _LANGUAGE
        assert str(call_kwargs["download_root"]) == str(_MODELS_DIR)
        assert call_kwargs["vad_options"] == {"vad_onset": _VAD_ONSET, "vad_offset": _VAD_OFFSET}
        # vad_onset must be below whisperX default 0.500 — tuned for ESP32 INMP441 mic
        assert _VAD_ONSET < 0.500
        assert _VAD_OFFSET < 0.363


# ─── _transcribe_audio segment filter ────────────────────────────────────────

class TestTranscribeAudioFilter:
    """Segment filtering in _transcribe_audio must not drop valid speech."""

    def _call(self, segments: list[dict]) -> str:
        """Call _transcribe_audio with a mocked model returning given segments."""
        import numpy as np
        from unittest.mock import patch as _patch
        from Speech.ASR_WhisperX import _transcribe_audio

        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"segments": segments}

        with _patch("Speech.ASR_WhisperX._MODEL", fake_model):
            audio = np.zeros(16000, dtype=np.float32)
            return _transcribe_audio(audio)

    def test_good_segment_returned(self):
        result = self._call([{"text": "привет", "avg_logprob": -0.3}])
        assert result == "привет"

    def test_low_confidence_segment_dropped(self):
        result = self._call([{"text": "шум", "avg_logprob": -1.5}])
        assert result == ""

    def test_missing_avg_logprob_not_dropped(self):
        """Bug fix: segment without avg_logprob key must NOT be silently dropped."""
        result = self._call([{"text": "адам"}])
        assert result == "адам"

    def test_multiple_segments_filtered_correctly(self):
        segments = [
            {"text": "адам", "avg_logprob": -0.4},
            {"text": "мусор", "avg_logprob": -1.2},
            {"text": "привет", "avg_logprob": -0.6},
        ]
        result = self._call(segments)
        assert "адам" in result
        assert "мусор" not in result
        assert "привет" in result

    def test_empty_segments_returns_empty_string(self):
        result = self._call([])
        assert result == ""
