"""Unit-тесты для VLMClient: _build_prompt (delta context) и CJK rejection без retry.

Запуск: PYTHONPATH=System .venv/bin/python -m unittest tests.test_vlm_delta_prompt -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "System"))

from adam.inference import VLMClient, _VLM_DEFAULT_PROMPT


class TestVLMBuildPrompt(unittest.TestCase):

    def _client(self, prompt: str = _VLM_DEFAULT_PROMPT) -> VLMClient:
        return VLMClient({"prompt": prompt, "base_url": "http://127.0.0.1:8084"})

    def test_no_prev_returns_base_prompt(self) -> None:
        client = self._client()
        result = client._build_prompt("")
        self.assertEqual(result, _VLM_DEFAULT_PROMPT)
        self.assertNotIn("Previous observation", result)

    def test_none_equiv_prev_returns_base_prompt(self) -> None:
        client = self._client()
        result = client._build_prompt("   ")
        self.assertEqual(result, _VLM_DEFAULT_PROMPT)

    def test_with_prev_includes_previous_observation(self) -> None:
        client = self._client()
        result = client._build_prompt("Scene: 1 person. Engagement: watching.")
        self.assertIn("Previous observation:", result)
        self.assertIn("Scene: 1 person. Engagement: watching.", result)

    def test_with_prev_includes_base_prompt(self) -> None:
        client = self._client()
        result = client._build_prompt("Scene: 1 person. Engagement: watching.")
        self.assertIn(_VLM_DEFAULT_PROMPT, result)

    def test_with_prev_includes_change_instruction(self) -> None:
        client = self._client()
        result = client._build_prompt("Scene: empty room. Engagement: none.")
        self.assertIn("Report what changed", result)

    def test_prev_stripped(self) -> None:
        client = self._client()
        result = client._build_prompt("  Scene: 1 person.  ")
        self.assertIn('"Scene: 1 person."', result)


class TestVLMCJKRejectionNoRetry(unittest.TestCase):
    """CJK detection should reject immediately without retry (single _call_vlm invocation)."""

    def _client(self) -> VLMClient:
        return VLMClient({"prompt": _VLM_DEFAULT_PROMPT, "base_url": "http://127.0.0.1:8084"})

    def test_cjk_output_raises_runtime_error(self) -> None:
        client = self._client()
        chinese_text = "这是一段中文描述，场景中有几个人站立。"
        with patch.object(client, "_call_vlm", return_value=chinese_text) as mock_call:
            with self.assertRaises(RuntimeError) as ctx:
                client._describe_jpeg_sync(b"\xff\xd8\xff" + b"\x00" * 100)
            self.assertIn("cjk", str(ctx.exception).lower())
            # Exactly ONE _call_vlm invocation — no retry
            mock_call.assert_called_once()

    def test_good_english_output_passes(self) -> None:
        client = self._client()
        good_text = "Scene: 1 person near installation. Engagement: watching."
        with patch.object(client, "_call_vlm", return_value=good_text):
            result = client._describe_jpeg_sync(b"\xff\xd8\xff" + b"\x00" * 100)
            self.assertEqual(result, good_text)

    def test_empty_output_raises_runtime_error(self) -> None:
        client = self._client()
        with patch.object(client, "_call_vlm", return_value=""):
            with self.assertRaises(RuntimeError) as ctx:
                client._describe_jpeg_sync(b"\xff\xd8\xff" + b"\x00" * 100)
            self.assertIn("no scene description", str(ctx.exception))

    def test_empty_jpeg_raises(self) -> None:
        client = self._client()
        with self.assertRaises(RuntimeError) as ctx:
            client._describe_jpeg_sync(b"")
        self.assertIn("empty scene snapshot", str(ctx.exception))


class TestPromptContextDedup(unittest.TestCase):
    """Tests for consecutive scene deduplication in PromptBuilder._build_context_body."""

    def _build(self, recent_scenes: list[str]) -> str:
        from adam.prompt import PromptBuilder
        return PromptBuilder._build_context_body(
            sensors={},
            semantic_text="",
            recent_episodic=[],
            recent_scenes=recent_scenes,
            scene_cache="",
            include_scene=True,
            include_sensors=False,
        )

    def test_three_identical_become_one(self) -> None:
        result = self._build(["Scene: A. Engagement: none."] * 3)
        self.assertEqual(result.count("Scene: A"), 1)

    def test_two_identical_become_one(self) -> None:
        result = self._build(["Scene: A.", "Scene: A."])
        self.assertEqual(result.count("Scene: A"), 1)

    def test_mixed_consecutive_deduped(self) -> None:
        result = self._build(["A", "A", "B"])
        self.assertIn("[1]", result)
        self.assertIn("[2]", result)
        self.assertNotIn("[3]", result)

    def test_alternating_all_kept(self) -> None:
        result = self._build(["A", "B", "A"])
        self.assertIn("[1]", result)
        self.assertIn("[2]", result)
        self.assertIn("[3]", result)

    def test_single_scene_no_numbering(self) -> None:
        result = self._build(["Scene: 1 person."])
        self.assertNotIn("[1]", result)
        self.assertIn("Scene: 1 person.", result)


if __name__ == "__main__":
    unittest.main()
