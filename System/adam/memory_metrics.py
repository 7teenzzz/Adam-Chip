"""Метрики пайплайна памяти Адама.

Пишет JSONL-лог событий памяти (инъекция эхо, запись эпизода, консолидация, поиск).
Используется для /api/memory/status и отладки. Не блокирует основной поток.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

_MAX_RECORDS = 1000  # rolling cap


class MemoryMetrics:
    """Thread-safe JSONL-логгер событий памяти.

    Файл: {data_dir}/memory/metrics.jsonl
    При каждом старте обрезается до последних _MAX_RECORDS записей.
    """

    def __init__(self, metrics_path: Path) -> None:
        self.path = metrics_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._trim_on_startup()

    # ----- public record methods -----

    def record_echo_injected(self, echo_id: str, score: float, matcher: str) -> None:
        self._write({
            "event": "echo_injected",
            "echo_id": echo_id,
            "score": round(score, 4),
            "matcher": matcher,
        })

    def record_echo_blocked(self, reason: str, pool: str = "echoes") -> None:
        self._write({"event": "echo_blocked", "reason": reason, "pool": pool})

    def record_episode_committed(self, episode_id: str, salience: float, triggered_by: str) -> None:
        self._write({
            "event": "episode_committed",
            "episode_id": episode_id,
            "salience": round(salience, 4),
            "triggered_by": triggered_by,
        })

    def record_consolidation(
        self,
        episodes_count: int,
        patch_keys: list[str],
        runtime_s: float,
        source: str,
    ) -> None:
        self._write({
            "event": "consolidation",
            "episodes_count": episodes_count,
            "patch_keys": patch_keys,
            "runtime_s": round(runtime_s, 2),
            "source": source,
        })

    def record_search_hit(self, query: str, results_count: int, method: str) -> None:
        self._write({
            "event": "search_hit",
            "query_len": len(query),
            "results_count": results_count,
            "method": method,
        })

    # ----- read -----

    def recent(self, hours: int = 24) -> list[dict[str, Any]]:
        """Возвращает записи за последние N часов."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result: list[dict[str, Any]] = []
        if not self.path.exists():
            return result
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ts_str = rec.get("ts", "")
                        if ts_str:
                            try:
                                if ts_str.endswith("Z"):
                                    ts_str = ts_str[:-1] + "+00:00"
                                ts = datetime.fromisoformat(ts_str)
                                if ts >= cutoff:
                                    result.append(rec)
                            except ValueError:
                                result.append(rec)
            except OSError:
                pass
        return result

    def summary(self, hours: int = 24) -> dict[str, Any]:
        """Сводка за последние hours часов для /api/memory/status."""
        records = self.recent(hours=hours)
        echo_inject = [r for r in records if r.get("event") == "echo_injected"]
        episodes = [r for r in records if r.get("event") == "episode_committed"]
        consolidations = [r for r in records if r.get("event") == "consolidation"]
        last_echo = echo_inject[-1] if echo_inject else None
        return {
            "echo_inject_count": len(echo_inject),
            "episodes_committed": len(episodes),
            "consolidations": len(consolidations),
            "last_echo": {
                "id": last_echo["echo_id"],
                "score": last_echo["score"],
                "ts": last_echo["ts"],
            } if last_echo else None,
        }

    # ----- internals -----

    def _write(self, data: dict[str, Any]) -> None:
        data["ts"] = _utc_now_iso()
        line = json.dumps(data, ensure_ascii=False)
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:
                log.warning("memory_metrics: write failed: %s", exc)

    def _trim_on_startup(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                lines = [l.rstrip("\n") for l in fh if l.strip()]
            if len(lines) > _MAX_RECORDS:
                lines = lines[-_MAX_RECORDS:]
                tmp = self.path.with_suffix(".tmp")
                with tmp.open("w", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
                tmp.replace(self.path)
        except OSError as exc:
            log.warning("memory_metrics: trim failed: %s", exc)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
