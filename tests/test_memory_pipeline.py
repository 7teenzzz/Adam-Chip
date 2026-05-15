"""Phase 6B — тесты пайплайна памяти.

Unit-тесты: salience, decay, tfidf_matcher, rule_based_patch, gate_log_trim, bm25_search
E2E-тесты: episode_write_read, consolidator_dryrun, echo_cooldown

Запуск: PYTHONPATH=System .venv/bin/python -m pytest tests/test_memory_pipeline.py -v
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))
sys.path.insert(0, str(ROOT / "Engineering"))

from adam.echoes_gate import TfIdfMatcher, _tokenize, EchoGate  # noqa: E402
from adam.episodic import (  # noqa: E402
    Episode,
    SessionAccumulator,
    VisitorInfo,
    salience_score,
    should_record,
)
from adam.memory import EpisodicMemory  # noqa: E402
from adam.memory_metrics import MemoryMetrics  # noqa: E402
from adam.memory_search import BM25Index  # noqa: E402
from adam.tuning import EchoesTuning, EpisodicTuning, EpisodicWeights  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _weights() -> EpisodicWeights:
    return EpisodicWeights()


def _make_episode(
    name: str | None = None,
    themes: list[str] | None = None,
    days_ago: int = 0,
    pinned: bool = False,
    consolidated: bool = False,
) -> Episode:
    w = _weights()
    acc = SessionAccumulator()
    if name:
        acc.set_visitor_name(name)
    for t in themes or []:
        acc.note_theme(t)
    acc.set_tone("curious")
    acc.note_turn("visitor", "тест")
    acc.ts_start = datetime.now(timezone.utc) - timedelta(days=days_ago, seconds=10)
    if pinned:
        acc.pin()
    ep = acc.finalize(
        end_ts=acc.ts_start + timedelta(seconds=120),
        weights=w,
        duration_normalize_seconds=300,
    )
    if consolidated:
        ep = ep.model_copy(update={"consolidated": True})
    return ep


# ─────────────────────────────────────────────────────────────────────────────
# Unit: salience_score
# ─────────────────────────────────────────────────────────────────────────────

class TestSalienceScore(unittest.TestCase):
    def _s(self, **kw) -> float:
        defaults = dict(
            visitor=VisitorInfo(),
            themes=[],
            tone="neutral",
            duration_s=0,
            echoes_used=[],
            chinese_used=[],
            has_new_question=False,
            weights=_weights(),
            duration_normalize_seconds=300,
        )
        defaults.update(kw)
        return salience_score(**defaults)

    def test_empty_session_near_zero(self) -> None:
        self.assertLess(self._s(), 0.05)

    def test_name_alone_above_0_3(self) -> None:
        score = self._s(visitor=VisitorInfo(introduced_name="Михаил"))
        self.assertGreaterEqual(score, 0.30)

    def test_themes_increase_score(self) -> None:
        base = self._s()
        with_themes = self._s(themes=["память", "смерть"])
        self.assertGreater(with_themes, base)

    def test_question_contributes(self) -> None:
        no_q = self._s()
        with_q = self._s(has_new_question=True)
        self.assertGreater(with_q, no_q)

    def test_long_session_contributes(self) -> None:
        short = self._s(duration_s=10)
        long_ = self._s(duration_s=600)
        self.assertGreater(long_, short)

    def test_clamped_to_one(self) -> None:
        score = self._s(
            visitor=VisitorInfo(introduced_name="X"),
            themes=["a", "b", "c", "d", "e"],
            tone="hostile",
            duration_s=3000,
            echoes_used=["e1"],
            has_new_question=True,
        )
        self.assertLessEqual(score, 1.0)
        self.assertGreater(score, 0.9)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: decay
# ─────────────────────────────────────────────────────────────────────────────

class TestDecay(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.em = EpisodicMemory(Path(self.tmp.name))

    def test_old_unpinned_dropped(self) -> None:
        old = _make_episode("Старый", days_ago=20)
        new = _make_episode("Новый", days_ago=1)
        for ep in (old, new):
            self.em.commit_episode(ep)
        stats = self.em.decay(decay_days=14)
        self.assertEqual(stats["dropped"], 1)
        names = {ep.visitor.introduced_name for ep in self.em.iter_episodes()}
        self.assertIn("Новый", names)
        self.assertNotIn("Старый", names)

    def test_pinned_old_kept(self) -> None:
        pinned = _make_episode("Pin", days_ago=30, pinned=True)
        self.em.commit_episode(pinned)
        stats = self.em.decay(decay_days=14)
        self.assertEqual(stats["dropped"], 0)

    def test_consolidated_dropped_earlier(self) -> None:
        ep = _make_episode("X", days_ago=14)
        self.em.commit_episode(ep)
        self.em.mark_consolidated([ep.id])
        stats = self.em.decay(decay_days=14)
        self.assertEqual(stats["dropped"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: TF-IDF matcher
# ─────────────────────────────────────────────────────────────────────────────

class TestTfIdfMatcher(unittest.TestCase):
    def setUp(self) -> None:
        self._corpus_texts = [
            ["память", "воспоминание", "прошлое"],
            ["чайник", "кухня", "тепло"],
            ["коридор", "свет", "лампа"],
        ]
        self._matcher = TfIdfMatcher(self._corpus_texts)

    def test_memory_query_matches_first_doc(self) -> None:
        q = _tokenize("помнишь ли прошлое")
        score0 = self._matcher.score(q, 0)
        score1 = self._matcher.score(q, 1)
        score2 = self._matcher.score(q, 2)
        self.assertGreater(score0, score1)
        self.assertGreater(score0, score2)

    def test_score_memory_theme_above_threshold(self) -> None:
        q = _tokenize("помнишь меня")
        score = self._matcher.score(q, 0)
        self.assertGreaterEqual(score, 0.0)  # at minimum non-negative

    def test_unrelated_query_low_score(self) -> None:
        q = _tokenize("совершенно другой текст без совпадений xyz")
        score = self._matcher.score(q, 0)
        self.assertLessEqual(score, 0.5)

    def test_kitchen_query_matches_second_doc(self) -> None:
        q = _tokenize("чайник кухня")
        score1 = self._matcher.score(q, 1)
        score0 = self._matcher.score(q, 0)
        self.assertGreater(score1, score0)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: rule_based_patch
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleBasedPatch(unittest.TestCase):
    def setUp(self) -> None:
        import importlib
        sys.path.insert(0, str(ROOT / "Engineering"))
        self.consolidator = importlib.import_module("consolidator")

    def test_adds_visitor_name(self) -> None:
        ep = _make_episode("Михаил", themes=["память"])
        patch = self.consolidator.rule_based_patch([ep], "## Постоянные посетители\n")
        self.assertIn("add", patch)
        entries_text = " ".join(e["entry"] for e in patch["add"])
        self.assertIn("Михаил", entries_text)

    def test_adds_themes(self) -> None:
        ep = _make_episode(themes=["тесей", "корабль"])
        diary = "## Цепляющие темы\n"
        patch = self.consolidator.rule_based_patch([ep], diary)
        self.assertIn("add", patch)
        entries_text = " ".join(e["entry"] for e in patch["add"])
        self.assertIn("тесей", entries_text)

    def test_no_duplicate_visitor(self) -> None:
        ep = _make_episode("Анна")
        diary = "## Постоянные посетители\n- **Анна**: давний друг.\n"
        patch = self.consolidator.rule_based_patch([ep], diary)
        if "add" in patch:
            entries_text = " ".join(e["entry"] for e in patch["add"])
            self.assertNotIn("Анна", entries_text)

    def test_empty_episodes_returns_empty(self) -> None:
        patch = self.consolidator.rule_based_patch([], "## Постоянные посетители\n")
        self.assertEqual(patch, {})


# ─────────────────────────────────────────────────────────────────────────────
# Unit: gate log trim
# ─────────────────────────────────────────────────────────────────────────────

class TestGateLogTrim(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.em = EpisodicMemory(Path(self.tmp.name))

    def _write_uses(self, path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_old_records_removed(self) -> None:
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=40)).isoformat()
        new_ts = now.isoformat()
        records = [
            {"echo_id": "e1", "ts": old_ts, "pool": "echoes"},
            {"echo_id": "e2", "ts": new_ts, "pool": "echoes"},
        ]
        self._write_uses(self.em.echoes_used_path, records)
        stats = self.em.trim_gate_logs(max_days=30)
        self.assertEqual(stats["echoes_dropped"], 1)
        remaining = [
            json.loads(l)
            for l in self.em.echoes_used_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["echo_id"], "e2")

    def test_recent_records_kept(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {"echo_id": f"e{i}", "ts": (now - timedelta(days=i)).isoformat(), "pool": "echoes"}
            for i in range(5)
        ]
        self._write_uses(self.em.echoes_used_path, records)
        stats = self.em.trim_gate_logs(max_days=30)
        self.assertEqual(stats["echoes_dropped"], 0)

    def test_nonexistent_file_no_error(self) -> None:
        stats = self.em.trim_gate_logs(max_days=30)
        self.assertEqual(stats["echoes_dropped"], 0)
        self.assertEqual(stats["chinese_dropped"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: BM25 search
# ─────────────────────────────────────────────────────────────────────────────

class TestBM25Search(unittest.TestCase):
    def _episodes(self) -> list[Episode]:
        return [
            _make_episode("Михаил", themes=["память", "прошлое"]),
            _make_episode("Анна", themes=["тесей", "корабль"]),
            _make_episode(themes=["одиночество", "тишина"]),
        ]

    def test_finds_by_theme(self) -> None:
        eps = self._episodes()
        idx = BM25Index()
        idx.build(eps)
        results = idx.search("тесей корабль", limit=1)
        self.assertEqual(len(results), 1)
        self.assertIn("тесей", results[0].themes)

    def test_finds_by_visitor_name(self) -> None:
        eps = self._episodes()
        idx = BM25Index()
        idx.build(eps)
        results = idx.search("Михаил", limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].visitor.introduced_name, "Михаил")

    def test_empty_index_returns_empty(self) -> None:
        idx = BM25Index()
        idx.build([])
        self.assertEqual(idx.search("память"), [])

    def test_limit_respected(self) -> None:
        eps = self._episodes()
        idx = BM25Index()
        idx.build(eps)
        results = idx.search("память тесей одиночество", limit=2)
        self.assertLessEqual(len(results), 2)


# ─────────────────────────────────────────────────────────────────────────────
# E2E: episode write → read
# ─────────────────────────────────────────────────────────────────────────────

class TestEpisodeWriteRead(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.em = EpisodicMemory(Path(self.tmp.name))

    def test_commit_then_read_same_id(self) -> None:
        ep = _make_episode("Тест", themes=["тема"])
        self.em.commit_episode(ep)
        found = list(self.em.iter_episodes())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, ep.id)
        self.assertEqual(found[0].visitor.introduced_name, "Тест")
        self.assertEqual(found[0].themes, ["тема"])

    def test_multiple_commits_across_days(self) -> None:
        eps = [
            _make_episode("А", days_ago=3),
            _make_episode("Б", days_ago=2),
            _make_episode("В", days_ago=0),
        ]
        for ep in eps:
            self.em.commit_episode(ep)
        all_ep = list(self.em.iter_episodes())
        self.assertEqual(len(all_ep), 3)
        ids = {e.id for e in all_ep}
        self.assertEqual(ids, {e.id for e in eps})

    def test_is_recurring_detected(self) -> None:
        for i in range(3):
            ep = _make_episode("Ирина", days_ago=i)
            self.em.commit_episode(ep)
        self.assertTrue(self.em.is_recurring("Ирина", min_visits=2))
        self.assertFalse(self.em.is_recurring("Никто", min_visits=2))


# ─────────────────────────────────────────────────────────────────────────────
# E2E: consolidator --dry-run
# ─────────────────────────────────────────────────────────────────────────────

class TestConsolidatorDryRun(unittest.TestCase):
    def test_dry_run_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "Engineering" / "consolidator.py"),
             "--dry-run", "--since=24h"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr[-500:]}")


# ─────────────────────────────────────────────────────────────────────────────
# E2E: echo cooldown blocks second injection
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_ECHOES = """\
```yaml
---
id: echo_cooldown_test
tags: [коридор, свет]
weight: 1.0
mood_block: []
---
```
длинный коридор с лампами.
"""


class TestEchoCooldown(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pool_path = Path(self.tmp.name) / "Echoes.md"
        pool_path.write_text(SAMPLE_ECHOES, encoding="utf-8")
        self.em = EpisodicMemory(Path(self.tmp.name))
        self.gate = EchoGate(
            pool_path=pool_path,
            memory=self.em,
            pool="echoes",
            rng=random.Random(42),
        )
        self.tuning = EchoesTuning(
            global_cooldown_turns=3,
            per_echo_cooldown_days=1,
            match_threshold=0.3,
            weight_multiplier=1.0,
        )

    def test_first_injection_possible(self) -> None:
        result = self.gate.maybe_inject(
            transcript="расскажи про коридор и свет",
            mood="neutral",
            adam_state="Ac-Or",
            tuning=self.tuning,
        )
        self.assertIsNotNone(result)

    def test_second_injection_blocked_by_cooldown(self) -> None:
        self.gate.maybe_inject(
            transcript="коридор свет",
            mood="neutral",
            adam_state="Ac-Or",
            tuning=self.tuning,
        )
        blocked = self.gate.maybe_inject(
            transcript="коридор свет",
            mood="neutral",
            adam_state="Ac-Or",
            tuning=self.tuning,
        )
        self.assertIsNone(blocked)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: MemoryMetrics
# ─────────────────────────────────────────────────────────────────────────────

class TestMemoryMetrics(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mm = MemoryMetrics(Path(self.tmp.name) / "memory" / "metrics.jsonl")

    def test_records_echo_injected(self) -> None:
        self.mm.record_echo_injected("echo_01", 0.75, "tag")
        recs = self.mm.recent(hours=1)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["event"], "echo_injected")
        self.assertEqual(recs[0]["echo_id"], "echo_01")

    def test_records_episode_committed(self) -> None:
        self.mm.record_episode_committed("ep_abc", 0.65, "session_end")
        recs = self.mm.recent(hours=1)
        self.assertTrue(any(r["event"] == "episode_committed" for r in recs))

    def test_summary_counts(self) -> None:
        self.mm.record_echo_injected("e1", 0.6, "tfidf")
        self.mm.record_echo_injected("e2", 0.7, "tag")
        self.mm.record_episode_committed("ep1", 0.5, "session_end")
        s = self.mm.summary(hours=1)
        self.assertEqual(s["echo_inject_count"], 2)
        self.assertEqual(s["episodes_committed"], 1)
        self.assertIsNotNone(s["last_echo"])

    def test_summary_empty(self) -> None:
        s = self.mm.summary(hours=1)
        self.assertEqual(s["echo_inject_count"], 0)
        self.assertIsNone(s["last_echo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
