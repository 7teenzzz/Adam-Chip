from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .events import utc_now


class MemoryStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "memory.sqlite3"
        self.notes_dir = data_dir / "notes"
        self.summaries_dir = data_dir / "summaries"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialogue_turns (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  speaker TEXT NOT NULL,
                  text TEXT NOT NULL,
                  meta_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  title TEXT NOT NULL,
                  body TEXT NOT NULL
                )
                """
            )

    def add_dialogue(self, speaker: str, text: str, meta_json: str = "{}") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO dialogue_turns(ts, speaker, text, meta_json) VALUES(?, ?, ?, ?)",
                (utc_now(), speaker, text, meta_json),
            )

    def recent_dialogue(self, limit: int = 8) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ts, speaker, text, meta_json
                FROM dialogue_turns
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_note(self, title: str, body: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO notes(ts, title, body) VALUES(?, ?, ?)",
                (utc_now(), title, body),
            )
            note_id = int(cursor.lastrowid)
        safe_title = "".join(ch for ch in title if ch.isalnum() or ch in (" ", "-", "_")).strip()
        filename = f"{note_id:04d}-{safe_title or 'note'}.md"
        (self.notes_dir / filename).write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
        return note_id

    def summary_text(self) -> str:
        summaries = sorted(self.summaries_dir.glob("*.md"))
        if not summaries:
            return "Долговременная память пока пуста."
        return "\n\n".join(path.read_text(encoding="utf-8").strip() for path in summaries[-3:])
