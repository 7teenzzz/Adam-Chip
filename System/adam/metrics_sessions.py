"""Per-session metrics log.

Append-only JSONL at ``<data_dir>/metrics_sessions.jsonl``. One record per
closed dialogue session with turn count, duration, visitor name, salience,
themes, and episode commit result.

Consumed by MetricsDashboard for M9 (dialog length) and session-level
aggregates. Written by Orchestrator._commit_session_locked.
"""

from __future__ import annotations

import json
import statistics
import threading
from collections import deque
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import utc_now
from .metrics import _tail_lines


class SessionsLog:
    def __init__(self, data_dir: Path, memory_limit: int = 200) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "metrics_sessions.jsonl"
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=memory_limit)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._hydrate()

    def _hydrate(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = _tail_lines(self.path, self._recent.maxlen or 200)
        except OSError:
            return
        for line in lines:
            try:
                self._recent.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": str(uuid4()), "ts": utc_now(), **record}
        encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(encoded + "\n")
            self._recent.append(entry)
        return entry

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock:
            return list(self._recent)[-limit:]

    def stats(self, limit: int = 100) -> dict[str, Any]:
        sessions = self.tail(limit)
        if not sessions:
            return {"count": 0, "turn_count": None, "duration_s": None,
                    "named_visitor_rate": None, "episode_commit_rate": None}
        counts = [s["turn_count"] for s in sessions if s.get("turn_count")]
        durations = [s["duration_s"] for s in sessions if s.get("duration_s")]
        named = [s for s in sessions if s.get("visitor_name")]
        committed = [s for s in sessions if s.get("episode_committed")]
        return {
            "count": len(sessions),
            "turn_count": {
                "min": min(counts) if counts else None,
                "avg": round(statistics.mean(counts), 1) if counts else None,
                "median": statistics.median(counts) if counts else None,
                "max": max(counts) if counts else None,
                "n": len(counts),
            },
            "duration_s": {
                "avg": round(statistics.mean(durations), 0) if durations else None,
                "n": len(durations),
            },
            "named_visitor_rate": round(len(named) / len(sessions), 3),
            "episode_commit_rate": round(len(committed) / len(sessions), 3),
        }
