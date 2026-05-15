"""Unit-тесты для SceneDescriptionBuffer — exact-match deduplication.

Запуск: PYTHONPATH=System .venv/bin/python -m unittest tests.test_scene_buffer_dedup -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "System"))

from adam.camera import SceneDescriptionBuffer


class TestSceneDescriptionBufferDedup(unittest.TestCase):

    def test_push_duplicate_skipped(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("Scene: 1 person. Engagement: watching.")
        buf.push("Scene: 1 person. Engagement: watching.")
        self.assertEqual(buf.recent(5), ["Scene: 1 person. Engagement: watching."])

    def test_push_different_passes(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("Scene: empty room. Engagement: none.")
        buf.push("Scene: 1 person near installation. Engagement: approaching.")
        result = buf.recent(5)
        self.assertEqual(len(result), 2)
        self.assertIn("empty room", result[0])
        self.assertIn("approaching", result[1])

    def test_push_returns_true_on_new(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        self.assertTrue(buf.push("Scene: 1 person. Engagement: watching."))

    def test_push_returns_false_on_duplicate(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("Scene: 1 person. Engagement: watching.")
        self.assertFalse(buf.push("Scene: 1 person. Engagement: watching."))

    def test_push_empty_returns_false(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        self.assertFalse(buf.push(""))
        self.assertFalse(buf.push("   "))
        self.assertEqual(len(buf), 0)

    def test_push_whitespace_stripped_for_dedup(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("Scene: 1 person.")
        self.assertFalse(buf.push("  Scene: 1 person.  "))

    def test_alternating_all_pass(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("A")
        buf.push("B")
        buf.push("A")
        self.assertEqual(buf.recent(5), ["A", "B", "A"])

    def test_many_duplicates_then_new(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        for _ in range(5):
            buf.push("Scene: empty room. Engagement: none.")
        buf.push("Scene: 2 people. Engagement: watching.")
        result = buf.recent(5)
        self.assertEqual(len(result), 2)

    def test_buffer_maxlen_respected(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=3)
        for i in range(5):
            buf.push(f"Scene: {i} people.")
        self.assertEqual(len(buf), 3)

    def test_latest_after_duplicates(self) -> None:
        buf = SceneDescriptionBuffer(maxlen=8)
        buf.push("Scene: A. Engagement: none.")
        buf.push("Scene: A. Engagement: none.")
        self.assertEqual(buf.latest(), "Scene: A. Engagement: none.")


if __name__ == "__main__":
    unittest.main()
