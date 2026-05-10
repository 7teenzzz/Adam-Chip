from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLog:
    def __init__(self, data_dir: Path, memory_limit: int = 500) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "events.jsonl"
        self._lock = threading.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=memory_limit)
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]] = []
        self._dropped_count: int = 0
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

    def append(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": str(uuid4()),
            "ts": utc_now(),
            "type": event_type,
            "payload": payload or {},
        }
        encoded = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
            self._recent.append(event)
            subscribers = list(self._subscribers)
        self._broadcast(subscribers, event)
        return event

    def tail(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            if len(self._recent) >= limit:
                return list(self._recent)[-limit:]

        if not self.path.exists():
            return []

        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

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
