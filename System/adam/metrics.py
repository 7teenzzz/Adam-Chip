"""Per-turn inference metrics log.

Append-only JSONL at ``<data_dir>/inference_metrics.jsonl``. One record per
completed dialogue turn with ASR / LLM / TTS latencies, transcript, reply,
model identifier, source channel, and voice-degradation flag.

Read access is exposed via a small in-memory tail buffer (the JSONL on disk
is the durable source; the buffer keeps the last N entries hot for the UI
without re-reading the whole file).
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


class MetricsLog:
    def __init__(self, data_dir: Path, memory_limit: int = 500) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "inference_metrics.jsonl"
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=memory_limit)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._hydrate()

    def _hydrate(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = _tail_lines(self.path, self._recent.maxlen or 500)
        except OSError:
            return
        for line in lines:
            try:
                self._recent.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "id": str(uuid4()),
            "ts": utc_now(),
            **record,
        }
        encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
            self._recent.append(entry)
        return entry

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            return list(self._recent)[-limit:]

    def summary(self, limit: int = 50) -> dict[str, Any]:
        recent = self.tail(limit)
        if not recent:
            return {"count": 0, "metrics": {}}
        out: dict[str, Any] = {"count": len(recent), "metrics": {}}
        for key in ("asr_ms", "llm_ms", "tts_ms", "total_ms"):
            values = [float(r[key]) for r in recent if r.get(key) is not None]
            if not values:
                out["metrics"][key] = None
                continue
            out["metrics"][key] = {
                "min": round(min(values), 1),
                "avg": round(statistics.mean(values), 1),
                "p95": round(_p95(values), 1),
                "max": round(max(values), 1),
                "n": len(values),
            }
        return out


def _tail_lines(path: Path, n: int, chunk_size: int = 8192) -> list[str]:
    """Read last *n* newline-delimited lines from *path* without loading the whole file."""
    with path.open("rb") as fh:
        fh.seek(0, 2)
        remaining = fh.tell()
        buf = b""
        lines: list[bytes] = []
        while remaining > 0 and len(lines) <= n:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            fh.seek(remaining)
            buf = fh.read(read_size) + buf
            lines = buf.split(b"\n")
        # First element may be an incomplete line if we didn't reach the start.
        if remaining > 0 and lines:
            lines = lines[1:]
    return [line.decode("utf-8", errors="replace") for line in lines[-n:] if line.strip()]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, int(round(0.95 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]
