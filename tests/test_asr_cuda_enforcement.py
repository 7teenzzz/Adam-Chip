"""Unit tests for ASR_WhisperX CUDA enforcement logic.

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
        """Ensures language and download_root are forwarded to whisperx.load_model."""
        from Speech.ASR_WhisperX import _load_model, _LANGUAGE, _MODELS_DIR
        mock_wx = MagicMock()
        with patch.dict(sys.modules, {"torch": _torch_mock(cuda_available=True)}):
            _load_model(mock_wx, "small", "cuda", "float16")
        call_kwargs = mock_wx.load_model.call_args[1]
        assert call_kwargs["device"] == "cuda"
        assert call_kwargs["compute_type"] == "float16"
        assert call_kwargs["language"] == _LANGUAGE
        assert str(call_kwargs["download_root"]) == str(_MODELS_DIR)
