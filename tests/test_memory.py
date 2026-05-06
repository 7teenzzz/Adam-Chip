"""Unit-тесты для slience, echoes_gate, decay и tuning.

Запуск: PYTHONPATH=System .venv/bin/python -m unittest tests.test_memory -v
(или просто .venv/bin/python -m unittest discover tests).
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make System importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))

from adam.echoes_gate import EchoGate, _parse_text  # noqa: E402
from adam.episodic import (  # noqa: E402
    Episode,
    SessionAccumulator,
    salience_score,
    should_record,
)
from adam.memory import EpisodicMemory  # noqa: E402
from adam.tuning import (  # noqa: E402
    EchoesTuning,
    EpisodicTuning,
    EpisodicWeights,
    Tuning,
    TuningStore,
    reset_store,
)


# ---------- Salience ----------


class SalienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weights = EpisodicWeights()

    def _score(self, **overrides) -> float:
        from adam.episodic import VisitorInfo
        kwargs = dict(
            visitor=VisitorInfo(),
            themes=[],
            tone="neutral",
            duration_s=0,
            echoes_used=[],
            chinese_used=[],
            has_new_question=False,
            weights=self.weights,
            duration_normalize_seconds=300,
        )
        kwargs.update(overrides)
        return salience_score(**kwargs)

    def test_empty_session_low(self) -> None:
        self.assertLess(self._score(), 0.05)

    def test_introduced_name_alone_above_threshold(self) -> None:
        from adam.episodic import VisitorInfo
        score = self._score(visitor=VisitorInfo(introduced_name="Михаил"))
        self.assertGreaterEqual(score, 0.30)

    def test_clamped_to_one(self) -> None:
        from adam.episodic import VisitorInfo
        score = self._score(
            visitor=VisitorInfo(introduced_name="A"),
            themes=["a", "b", "c", "d", "e"],
            tone="hostile",
            duration_s=600,
            echoes_used=["e1"],
            has_new_question=True,
        )
        self.assertLessEqual(score, 1.0)
        self.assertGreater(score, 0.9)

    def test_should_record_threshold(self) -> None:
        acc = SessionAccumulator()
        acc.set_tone("neutral")
        ep = acc.finalize(
            end_ts=acc.ts_start + timedelta(seconds=10),
            weights=self.weights,
            duration_normalize_seconds=300,
        )
        self.assertFalse(should_record(ep, acc, EpisodicTuning()))

    def test_should_record_name_overrides_threshold(self) -> None:
        acc = SessionAccumulator()
        acc.set_visitor_name("Анна")
        ep = acc.finalize(
            end_ts=acc.ts_start + timedelta(seconds=5),
            weights=self.weights,
            duration_normalize_seconds=300,
        )
        # имя есть → пишем даже при низком salience и короткой длительности
        self.assertTrue(should_record(ep, acc, EpisodicTuning()))

    def test_should_record_pinned_overrides(self) -> None:
        acc = SessionAccumulator()
        acc.pin()
        ep = acc.finalize(
            end_ts=acc.ts_start + timedelta(seconds=2),
            weights=self.weights,
            duration_normalize_seconds=300,
        )
        self.assertTrue(should_record(ep, acc, EpisodicTuning()))


# ---------- EpisodicMemory ----------


class EpisodicMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.em = EpisodicMemory(Path(self.tmp.name))
        self.weights = EpisodicWeights()

    def _make(self, name: str | None, *, days_ago: int = 0, themes=None, pinned=False) -> Episode:
        acc = SessionAccumulator()
        if name:
            acc.set_visitor_name(name)
        for t in themes or []:
            acc.note_theme(t)
        acc.set_tone("curious")
        acc.note_turn("visitor", "вопрос")
        acc.ts_start = datetime.now(timezone.utc) - timedelta(days=days_ago)
        if pinned:
            acc.pin()
        return acc.finalize(
            end_ts=acc.ts_start + timedelta(seconds=120),
            weights=self.weights,
            duration_normalize_seconds=300,
        )

    def test_commit_and_query_by_name(self) -> None:
        for ep in [
            self._make("Михаил", days_ago=4, themes=["память"]),
            self._make("Анна", days_ago=3, themes=["Тесей"]),
            self._make("Михаил", days_ago=1, themes=["технофлора"]),
        ]:
            self.em.commit_episode(ep)
        result = self.em.query_by_name("Михаил", limit=3)
        self.assertEqual(len(result), 2)
        # Сортировка по recency
        self.assertGreater(result[0].ts_end, result[1].ts_end)

    def test_query_by_name_empty_returns_empty(self) -> None:
        self.assertEqual(self.em.query_by_name(""), [])

    def test_decay_drops_old_unpinned(self) -> None:
        old_ep = self._make("Старый", days_ago=20)
        new_ep = self._make("Новый", days_ago=2)
        pinned_old = self._make("Pin", days_ago=30, pinned=True)
        for ep in (old_ep, new_ep, pinned_old):
            self.em.commit_episode(ep)
        stats = self.em.decay(decay_days=14)
        self.assertEqual(stats["dropped"], 1)
        self.assertEqual(stats["kept"], 2)
        # старый удалён, pinned остался
        names = {ep.visitor.introduced_name for ep in self.em.iter_episodes()}
        self.assertEqual(names, {"Новый", "Pin"})

    def test_decay_drops_consolidated_earlier(self) -> None:
        # consolidated удаляется через cutoff - 1 день
        ep = self._make("X", days_ago=14)
        self.em.commit_episode(ep)
        self.em.mark_consolidated([ep.id])
        stats = self.em.decay(decay_days=14)
        self.assertEqual(stats["dropped"], 1)

    def test_record_and_last_use(self) -> None:
        self.em.record_echo_used("echo_07")
        self.em.record_echo_used("echo_03")
        self.em.record_echo_used("echo_07")
        last = self.em.last_use("echo_07")
        self.assertIsNotNone(last)
        all_uses = self.em.all_recent_uses()
        self.assertIn("echo_07", all_uses)
        self.assertIn("echo_03", all_uses)

    def test_semantic_roundtrip(self) -> None:
        text = "## Постоянные посетители\n- **Михаил**: память."
        self.em.write_semantic(text)
        self.assertEqual(self.em.read_semantic(), text)


# ---------- EchoesGate ----------


SAMPLE_ECHOES = """
```yaml
---
id: echo_test_a
tags: [коридор, свет]
weight: 1.0
mood_block: [hostile]
---
```
длинный коридор с лампами через одну.

```yaml
---
id: echo_test_b
tags: [кухня, чайник, тепло]
weight: 1.0
mood_block: []
---
```
кухня с включённым чайником.
"""


class EchoesGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pool_path = Path(self.tmp.name) / "Echoes.md"
        self.pool_path.write_text(SAMPLE_ECHOES, encoding="utf-8")
        self.em = EpisodicMemory(Path(self.tmp.name))
        self.gate = EchoGate(
            pool_path=self.pool_path,
            memory=self.em,
            pool="echoes",
            rng=random.Random(0),
        )
        self.tuning = EchoesTuning(
            global_cooldown_turns=2,
            per_echo_cooldown_days=1,
            match_threshold=0.4,
            weight_multiplier=1.0,
        )

    def test_parse_two_entries(self) -> None:
        self.assertEqual(len(self.gate.entries), 2)
        ids = {e.id for e in self.gate.entries}
        self.assertEqual(ids, {"echo_test_a", "echo_test_b"})

    def test_match_and_inject(self) -> None:
        injected = self.gate.maybe_inject(
            transcript="расскажи про коридор и свет",
            mood="neutral", adam_state="Ac-Or",
            tuning=self.tuning,
        )
        self.assertIsNotNone(injected)
        self.assertEqual(injected.entry.id, "echo_test_a")

    def test_global_cooldown(self) -> None:
        self.gate.maybe_inject(
            transcript="коридор и свет",
            mood="neutral", adam_state="Ac-Or",
            tuning=self.tuning,
        )
        # сразу после инжекта — cooldown активен
        r2 = self.gate.maybe_inject(
            transcript="коридор и свет",
            mood="neutral", adam_state="Ac-Or",
            tuning=self.tuning,
        )
        self.assertIsNone(r2)

    def test_mood_block(self) -> None:
        r = self.gate.maybe_inject(
            transcript="коридор",
            mood="hostile",  # echo_test_a заблокирован
            adam_state="Ac-Ch",
            tuning=self.tuning,
        )
        # echo_b не заблокирован, но не матчит "коридор"
        self.assertIsNone(r)

    def test_disabled_returns_none(self) -> None:
        tuning = EchoesTuning(enabled=False)
        r = self.gate.maybe_inject(
            transcript="коридор",
            mood="neutral", adam_state="Ac-Or",
            tuning=tuning,
        )
        self.assertIsNone(r)


# ---------- TuningStore ----------


class TuningStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        reset_store()
        path = Path(self.tmp.name) / "Tuning.json"
        path.write_text(json.dumps({}), encoding="utf-8")
        self.store = TuningStore(path)

    def test_defaults_load(self) -> None:
        cfg = self.store.current()
        self.assertIsInstance(cfg, Tuning)
        self.assertEqual(cfg.echoes.global_cooldown_turns, 12)

    def test_apply_patch_merges_deeply(self) -> None:
        new = self.store.apply_patch({"echoes": {"global_cooldown_turns": 99}})
        self.assertEqual(new.echoes.global_cooldown_turns, 99)
        self.assertEqual(new.memory.episodic.decay_days, 14)  # сохранено
        # на диске тоже
        on_disk = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["echoes"]["global_cooldown_turns"], 99)

    def test_invalid_patch_raises(self) -> None:
        with self.assertRaises(Exception):
            self.store.apply_patch({"echoes": {"global_cooldown_turns": "abc"}})

    def test_restore_defaults(self) -> None:
        self.store.apply_patch({"echoes": {"global_cooldown_turns": 99}})
        restored = self.store.restore_defaults()
        self.assertEqual(restored.echoes.global_cooldown_turns, 12)


# ---------- consolidator.apply_patch ----------


class ConsolidatorMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        # Импорт тут чтобы не падало если запускают только подмножество
        sys.path.insert(0, str(ROOT / "Engineering"))
        import importlib
        self.consolidator = importlib.import_module("consolidator")

    def test_apply_patch_add(self) -> None:
        text = "## Постоянные посетители\n- **Аня**: давний друг."
        new = self.consolidator.apply_patch(
            text,
            {"add": [{"section": "Постоянные посетители", "entry": "- **Иван**: новенький."}]},
        )
        self.assertIn("Иван", new)
        self.assertIn("Аня", new)

    def test_apply_patch_update(self) -> None:
        text = "## Опорные факты\n- Куратор Иван."
        new = self.consolidator.apply_patch(
            text,
            {"update": [{"section": "Опорные факты", "match": "Куратор", "new": "- Куратор экспозиции — Анна."}]},
        )
        self.assertIn("Анна", new)
        self.assertNotIn("Куратор Иван", new)

    def test_apply_patch_deprecate(self) -> None:
        text = "## Нерешённые загадки\n- Странный шум по вечерам.\n- Где-то протекает."
        new = self.consolidator.apply_patch(
            text,
            {"deprecate": [{"section": "Нерешённые загадки", "match": "шум"}]},
        )
        self.assertNotIn("шум", new)
        self.assertIn("протекает", new)

    def test_validate_patch(self) -> None:
        valid = {"add": [{"section": "X", "entry": "y"}], "pin_episodes": ["abc"]}
        self.assertTrue(self.consolidator.validate_patch(valid))
        bad = {"add": "not a list"}
        self.assertFalse(self.consolidator.validate_patch(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
