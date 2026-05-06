from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from .episodic import Episode
from .events import utc_now

log = logging.getLogger(__name__)


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


# ---------- Episodic & Semantic memory ----------


_EPISODE_DATE_FMT = "%Y-%m-%d"


class EpisodicMemory:
    """Persistence-слой для эпизодической памяти + semantic markdown + gate-логи.

    Не выдаёт салиенс/аккумуляцию — это в episodic.SessionAccumulator.
    Здесь только I/O: запись эпизодов, чтение, retrieval, декей.
    """

    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir) / "memory"
        self.episodes_dir = self.root / "episodes"
        self.semantic_path = self.root / "semantic.md"
        self.echoes_used_path = self.root / "echoes_used.jsonl"
        self.chinese_used_path = self.root / "chinese_used.jsonl"
        self.state_path = self.root / "consolidator_state.json"
        self.consolidator_log = self.root / "consolidator.log"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ----- write -----

    def commit_episode(self, episode: Episode) -> Path:
        """Append одного эпизода в jsonl за день ts_end."""
        date_str = episode.ts_end.astimezone(timezone.utc).strftime(_EPISODE_DATE_FMT)
        path = self.episodes_dir / f"{date_str}.jsonl"
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(episode.to_dict(), ensure_ascii=False) + "\n")
        return path

    # ----- read -----

    def iter_episodes(self) -> Iterator[Episode]:
        """Идёт по всем jsonl, отдаёт Episode по одному."""
        for path in sorted(self.episodes_dir.glob("*.jsonl")):
            yield from self._iter_jsonl(path)

    def iter_episodes_since(self, since: datetime) -> Iterator[Episode]:
        cutoff_date = since.astimezone(timezone.utc).strftime(_EPISODE_DATE_FMT)
        for path in sorted(self.episodes_dir.glob("*.jsonl")):
            if path.stem < cutoff_date:
                # дата файла раньше cutoff — пропускаем целиком
                continue
            for ep in self._iter_jsonl(path):
                if ep.ts_end >= since:
                    yield ep

    def query_by_name(self, name: str, limit: int = 2) -> list[Episode]:
        if not name:
            return []
        target = name.strip().lower()
        matches: list[Episode] = []
        for ep in self.iter_episodes():
            stored = (ep.visitor.introduced_name or "").strip().lower()
            if stored and stored == target:
                matches.append(ep)
        matches.sort(key=lambda e: e.ts_end, reverse=True)
        return matches[: max(0, limit)]

    def read_semantic(self) -> str:
        if not self.semantic_path.exists():
            return ""
        return self.semantic_path.read_text(encoding="utf-8")

    def write_semantic(self, text: str) -> None:
        self.semantic_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.semantic_path.write_text(text, encoding="utf-8")

    # ----- gate use logs -----

    def record_echo_used(self, echo_id: str, pool: str = "echoes") -> None:
        path = self._gate_log_path(pool)
        record = {"id": echo_id, "ts": utc_now(), "pool": pool}
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def last_use(self, echo_id: str, pool: str = "echoes") -> Optional[datetime]:
        path = self._gate_log_path(pool)
        if not path.exists():
            return None
        last: Optional[datetime] = None
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("id") != echo_id:
                    continue
                ts = _parse_ts(rec.get("ts"))
                if ts and (last is None or ts > last):
                    last = ts
        return last

    def all_recent_uses(
        self, pool: str = "echoes", *, since: Optional[datetime] = None
    ) -> dict[str, datetime]:
        """Возвращает {id: last_ts} для быстрого cooldown lookup."""
        path = self._gate_log_path(pool)
        if not path.exists():
            return {}
        result: dict[str, datetime] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = rec.get("id")
                ts = _parse_ts(rec.get("ts"))
                if not rid or ts is None:
                    continue
                if since is not None and ts < since:
                    continue
                prev = result.get(rid)
                if prev is None or ts > prev:
                    result[rid] = ts
        return result

    # ----- decay & flags -----

    def mark_consolidated(self, episode_ids: Iterable[str]) -> int:
        """Помечает эпизоды consolidated=True. Возвращает кол-во затронутых."""
        ids = set(episode_ids)
        if not ids:
            return 0
        return self._rewrite_with(lambda ep: _set_flag(ep, "consolidated", True) if ep.id in ids else ep)

    def pin_episodes(self, episode_ids: Iterable[str]) -> int:
        ids = set(episode_ids)
        if not ids:
            return 0
        return self._rewrite_with(lambda ep: _set_flag(ep, "pinned", True) if ep.id in ids else ep)

    def decay(self, now: Optional[datetime] = None, *, decay_days: int = 14) -> dict[str, int]:
        """Удаляет старые записи. Возвращает stats {dropped, kept, files_removed}.

        Логика:
          - pinned: никогда не удаляются.
          - consolidated: удаляются раньше — после 1 дня жизни (информация уже в semantic).
          - все остальные: удаляются по достижении decay_days возраста.
        """
        now = now or datetime.now(timezone.utc)
        regular_cutoff = now - timedelta(days=decay_days)
        consolidated_cutoff = now - timedelta(days=1)

        dropped = 0
        kept = 0
        files_removed = 0
        with self._lock:
            for path in sorted(self.episodes_dir.glob("*.jsonl")):
                survivors: list[dict[str, Any]] = []
                for ep in self._iter_jsonl(path):
                    if ep.pinned:
                        survivors.append(ep.to_dict())
                        kept += 1
                        continue
                    if ep.consolidated and ep.ts_end <= consolidated_cutoff:
                        dropped += 1
                        continue
                    if ep.ts_end <= regular_cutoff:
                        dropped += 1
                        continue
                    survivors.append(ep.to_dict())
                    kept += 1
                if not survivors:
                    path.unlink(missing_ok=True)
                    files_removed += 1
                else:
                    self._rewrite_jsonl(path, survivors)
        return {"dropped": dropped, "kept": kept, "files_removed": files_removed}

    # ----- consolidator state -----

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    # ----- helpers -----

    def _gate_log_path(self, pool: str) -> Path:
        if pool == "chinese":
            return self.chinese_used_path
        return self.echoes_used_path

    def _iter_jsonl(self, path: Path) -> Iterator[Episode]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError as exc:
                        log.warning("bad jsonl in %s: %s", path, exc)
                        continue
                    try:
                        yield Episode.from_dict(raw)
                    except (KeyError, ValueError) as exc:
                        log.warning("bad episode in %s: %s", path, exc)
        except FileNotFoundError:
            return

    def _rewrite_jsonl(self, path: Path, records: list[dict[str, Any]]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for rec in records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tmp.replace(path)

    def _rewrite_with(self, transform) -> int:
        """Применяет transform(ep) -> ep ко всем записям. Возвращает кол-во изменённых."""
        changed = 0
        with self._lock:
            for path in sorted(self.episodes_dir.glob("*.jsonl")):
                rebuilt: list[dict[str, Any]] = []
                touched_in_file = 0
                for ep in self._iter_jsonl(path):
                    new_ep = transform(ep)
                    if new_ep is not ep:
                        touched_in_file += 1
                    rebuilt.append(new_ep.to_dict())
                if touched_in_file:
                    self._rewrite_jsonl(path, rebuilt)
                    changed += touched_in_file
        return changed


def _set_flag(episode: Episode, attr: str, value: bool) -> Episode:
    """Возвращает мутированный Episode (обновляет атрибут). Возвращает новый объект если изменилось."""
    if getattr(episode, attr) == value:
        return episode
    setattr(episode, attr, value)
    return Episode(
        id=episode.id,
        ts_start=episode.ts_start,
        ts_end=episode.ts_end,
        duration_s=episode.duration_s,
        session_id=episode.session_id,
        visitor=episode.visitor,
        themes=episode.themes,
        salience=episode.salience,
        tone_visitor=episode.tone_visitor,
        adam_state=episode.adam_state,
        highlights=episode.highlights,
        echoes_used=episode.echoes_used,
        chinese_used=episode.chinese_used,
        scene_changes=episode.scene_changes,
        pinned=episode.pinned,
        consolidated=episode.consolidated,
    )


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
