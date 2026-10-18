from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Fallbacks only for tests / missing Config.json section; production values
# live in Config.json `events` (Config-First).
EVENTS_DEFAULTS: dict[str, Any] = {
    "jsonl_sample": {},
    "jsonl_dedupe_window_sec": 0,
    "jsonl_max_mb": 0,
    "jsonl_backups": 0,
    "tail_read_kb": 2048,
}


class JsonlWritePolicy:
    """Decides which events reach events.jsonl (SSE and _recent always get all).

    - jsonl_sample[type] = 0 -> never written; N > 1 -> every Nth written.
    - Unsampled events whose (turn_id, payload) equal the previous written event
      of the same type are skipped while inside jsonl_dedupe_window_sec; the next
      written event of that type carries `suppressed_since_last` = skipped copies.
    Shared with scripts/adam_events_compact.py so live and offline rules match.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._sample = {str(k): max(0, int(v)) for k, v in (cfg.get("jsonl_sample") or {}).items()}
        self._window = float(cfg.get("jsonl_dedupe_window_sec") or 0)
        self._counters: dict[str, int] = {}
        # type -> [signature, written_at_sec, suppressed_count]
        self._last: dict[str, list[Any]] = {}

    def decide(self, event: dict[str, Any], now_sec: float) -> tuple[bool, int]:
        """Return (write_to_disk, suppressed_since_last)."""
        etype = str(event.get("type"))
        every = self._sample.get(etype, 1)
        if every == 0:
            return False, 0
        if every > 1:
            c = self._counters.get(etype, 0) + 1
            self._counters[etype] = c
            return c % every == 0, 0
        if self._window <= 0:
            return True, 0
        sig = json.dumps([event.get("turn_id"), event.get("payload")], ensure_ascii=False, sort_keys=True)
        last = self._last.get(etype)
        if last is not None and last[0] == sig and now_sec - last[1] < self._window:
            last[2] += 1
            return False, 0
        suppressed = last[2] if last is not None else 0
        self._last[etype] = [sig, now_sec, 0]
        return True, suppressed


class EventLog:
    def __init__(
        self,
        data_dir: Path,
        memory_limit: int = 500,
        *,
        audio_cfg: dict[str, Any] | None = None,
        events_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "events.jsonl"
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=memory_limit)
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]] = []
        self._dropped_count: int = 0
        cfg = {**EVENTS_DEFAULTS, **(events_cfg or {})}
        sample = dict(cfg.get("jsonl_sample") or {})
        # Deprecated media.audio.events_jsonl_sample_audio_level (Phase 21A-04) —
        # honoured only when events.jsonl_sample does not set audio_level.
        legacy = (audio_cfg or {}).get("events_jsonl_sample_audio_level")
        if legacy is not None and "audio_level" not in sample:
            sample["audio_level"] = max(1, int(legacy))
        cfg["jsonl_sample"] = sample
        self._policy = JsonlWritePolicy(cfg)
        self._max_bytes = int(float(cfg["jsonl_max_mb"]) * 1024 * 1024)
        self._backups = max(0, int(cfg["jsonl_backups"]))
        self._tail_read_bytes = max(64, int(cfg["tail_read_kb"])) * 1024
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._size = self.path.stat().st_size if self.path.exists() else 0

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

    def append(self, event_type: str, payload: dict[str, Any] | None = None, *, turn_id: str | None = None) -> dict[str, Any]:
        event: dict[str, Any] = {
            "id": str(uuid4()),
            "ts": utc_now(),
            "type": event_type,
            "payload": payload or {},
        }
        if turn_id:
            event["turn_id"] = turn_id

        # Only disk writes are filtered; SSE and _recent receive every event so the
        # live UI widgets (EQ, OWW meter) keep their full cadence.
        with self._lock:
            write, suppressed = self._policy.decide(event, time.time())
            if write:
                record = {**event, "suppressed_since_last": suppressed} if suppressed else event
                line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                with self.path.open("ab") as handle:
                    handle.write(line)
                self._size += len(line)
                if self._max_bytes and self._size >= self._max_bytes:
                    self._rotate()
            self._recent.append(event)
            subscribers = list(self._subscribers)
        self._broadcast(subscribers, event)
        return event

    def _rotate(self) -> None:
        """events.jsonl -> .1 -> .2 ... keeping jsonl_backups files. Caller holds _lock."""
        try:
            if self._backups == 0:
                self.path.unlink(missing_ok=True)
            else:
                for i in range(self._backups - 1, 0, -1):
                    src = self.path.with_name(f"{self.path.name}.{i}")
                    if src.exists():
                        src.replace(self.path.with_name(f"{self.path.name}.{i + 1}"))
                self.path.replace(self.path.with_name(f"{self.path.name}.1"))
        except OSError:
            return  # never let log rotation break the event bus
        self._size = 0

    def _read_tail_lines(self) -> list[str]:
        with self.path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - self._tail_read_bytes))
            chunk = handle.read()
        lines = chunk.decode("utf-8", errors="replace").splitlines()
        return lines[1:] if size > self._tail_read_bytes else lines  # first may be partial

    def tail(
        self,
        limit: int = 100,
        *,
        types: list[str] | None = None,
        turn_id: str | None = None,
        since_ms: float | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            source = list(self._recent)

        if not source and self.path.exists():
            lines = self._read_tail_lines()[-(limit * 10):]
            for line in lines:
                try:
                    source.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if types:
            type_set = set(types)
            source = [e for e in source if e.get("type") in type_set]
        if turn_id:
            source = [e for e in source if e.get("turn_id") == turn_id]
        if since_ms is not None:
            source = [e for e in source if _ts_to_ms(e.get("ts", "")) >= since_ms]

        return source[-limit:]

    def subscribe(self, max_queue: int = 200) -> asyncio.Queue[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue)
        with self._lock:
            self._subscribers.append((loop, queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers = [(loop, q) for loop, q in self._subscribers if q is not queue]

    def _broadcast(self, subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]], event: dict[str, Any]) -> None:
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(self._enqueue, queue, event)
            except RuntimeError:
                # Loop already closed — drop the subscriber on next sweep.
                self.unsubscribe(queue)

    def _enqueue(self, queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                with self._lock:
                    self._dropped_count += 1


def _ts_to_ms(ts: str) -> float:
    """Convert ISO-8601 timestamp string to Unix milliseconds, or 0.0 on error."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp() * 1000
    except Exception:
        return 0.0
