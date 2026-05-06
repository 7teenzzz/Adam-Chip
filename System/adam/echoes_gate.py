"""Gate для пулов Echoes / Chinese.

Парсит файлы пула (`About/Echoes.md`, `About/Chinese_lines.md`),
держит in-memory состояние (turn-counter, отображение last-use),
выбирает 0 или 1 фрагмент per turn по cooldown + mood + thematic match.

LLM не решает «уместно ли» — gate отдаёт уже отфильтрованного кандидата.
"""
from __future__ import annotations

import logging
import random
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from .memory import EpisodicMemory
from .tuning import ChineseTuning, EchoesTuning

log = logging.getLogger(__name__)


# ---------- модель пула ----------


@dataclass
class EchoEntry:
    id: str
    tags: list[str]
    weight: float
    mood_block: list[str]
    body: str
    audio_id: Optional[str] = None
    ru_hint: Optional[str] = None
    pool: str = "echoes"  # "echoes" | "chinese"


@dataclass
class InjectedEcho:
    """То, что gate возвращает оркестратору для инжекта в prompt."""

    entry: EchoEntry
    score: float
    matched_tags: list[str] = field(default_factory=list)

    @property
    def hint_text(self) -> str:
        """Сформировать строку для prompt."""
        if self.entry.pool == "chinese":
            return f"[сейчас можешь вставить короткую китайскую фразу: «{self.entry.body.strip()}»]"
        return (
            f"[сейчас можешь упомянуть, если уместно: «{self.entry.body.strip()}»]"
        )


# ---------- парсер ----------


_FENCE_RE = re.compile(r"^```yaml\s*$", re.IGNORECASE)
_FENCE_END = "```"


def parse_echoes_file(path: Path, *, pool: str = "echoes") -> list[EchoEntry]:
    """Парсит .md-файл с блоками ```yaml --- frontmatter --- ``` + текст после.

    Возвращает список EchoEntry. Невалидные блоки пропускаются с предупреждением.
    """
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    return _parse_text(raw, pool=pool, source=str(path))


def _parse_text(text: str, *, pool: str, source: str = "") -> list[EchoEntry]:
    lines = text.splitlines()
    i = 0
    out: list[EchoEntry] = []
    while i < len(lines):
        line = lines[i]
        if not _FENCE_RE.match(line):
            i += 1
            continue
        # начало yaml-блока
        i += 1
        yaml_lines: list[str] = []
        while i < len(lines) and not lines[i].strip().startswith(_FENCE_END):
            yaml_lines.append(lines[i])
            i += 1
        # пропустим закрывающий ```
        if i < len(lines):
            i += 1
        # очистим обрамляющие ---
        if yaml_lines and yaml_lines[0].strip() == "---":
            yaml_lines = yaml_lines[1:]
        if yaml_lines and yaml_lines[-1].strip() == "---":
            yaml_lines = yaml_lines[:-1]
        try:
            meta = yaml.safe_load("\n".join(yaml_lines)) or {}
        except yaml.YAMLError as exc:
            log.warning("echoes_gate: bad yaml at %s: %s", source, exc)
            continue
        if not isinstance(meta, dict):
            log.warning("echoes_gate: yaml is not a dict at %s", source)
            continue
        # тело — строки до следующего ```yaml или EOF
        body_lines: list[str] = []
        while i < len(lines) and not _FENCE_RE.match(lines[i]):
            body_lines.append(lines[i])
            i += 1
        body = _clean_body(body_lines)
        if not body:
            log.warning("echoes_gate: empty body for id=%s", meta.get("id"))
            continue
        try:
            entry = EchoEntry(
                id=str(meta["id"]),
                tags=[str(t).lower() for t in (meta.get("tags") or [])],
                weight=float(meta.get("weight", 0.5)),
                mood_block=[str(m).lower() for m in (meta.get("mood_block") or [])],
                body=body,
                audio_id=meta.get("audio_id"),
                ru_hint=meta.get("ru_hint"),
                pool=pool,
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("echoes_gate: bad entry %r: %s", meta, exc)
            continue
        out.append(entry)
    return out


def _clean_body(lines: list[str]) -> str:
    # выбросим разделители и пустые в начале/конце
    while lines and lines[0].strip() in ("", "---"):
        lines = lines[1:]
    while lines and lines[-1].strip() in ("", "---"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


# ---------- gate ----------


class EchoGate:
    """Singleton-инстанс, который дёргается из оркестратора каждый turn."""

    def __init__(
        self,
        *,
        pool_path: Path,
        memory: EpisodicMemory,
        pool: str = "echoes",
        rng: Optional[random.Random] = None,
    ) -> None:
        self.pool_path = Path(pool_path)
        self.memory = memory
        self.pool = pool
        self._rng = rng or random.Random()
        self._lock = threading.RLock()
        self._mtime: float = 0.0
        self._entries: list[EchoEntry] = []
        self._turn_counter: int = 0
        self._last_use_turn: int = -10_000  # никогда не использовалось
        self.reload()

    # ----- public API -----

    def reload(self) -> int:
        """Перечитать файл если изменился. Возвращает число загруженных entries."""
        with self._lock:
            try:
                mtime = self.pool_path.stat().st_mtime
            except FileNotFoundError:
                self._entries = []
                self._mtime = 0.0
                return 0
            if mtime == self._mtime and self._entries:
                return len(self._entries)
            self._entries = parse_echoes_file(self.pool_path, pool=self.pool)
            self._mtime = mtime
            log.info("echoes_gate[%s]: loaded %d entries", self.pool, len(self._entries))
            return len(self._entries)

    def maybe_inject(
        self,
        *,
        transcript: str,
        mood: str,
        adam_state: str,
        tuning: EchoesTuning | ChineseTuning,
        now: Optional[datetime] = None,
    ) -> Optional[InjectedEcho]:
        """Главная точка вызова. None или InjectedEcho.

        Side-effect: при инжекте — увеличивает turn-counter и записывает used.
        Если просто пересчитать turn-counter без инжекта (например мы уже знаем что не инжектим
        по другой причине) — используй note_turn().
        """
        with self._lock:
            self._turn_counter += 1
            if not tuning.enabled:
                return None
            if not self._entries:
                self.reload()
            if not self._entries:
                return None

            # global cooldown
            since_last = self._turn_counter - self._last_use_turn
            if since_last < tuning.global_cooldown_turns:
                return None

            # candidates
            now = now or datetime.now(timezone.utc)
            cooldown_cutoff = now - timedelta(days=self._cooldown_days(tuning))
            recent_uses = self.memory.all_recent_uses(pool=self.pool, since=cooldown_cutoff)

            candidates: list[tuple[EchoEntry, float, list[str]]] = []
            for entry in self._entries:
                if mood in entry.mood_block:
                    continue
                if entry.id in recent_uses:
                    continue
                score, matched = self._score_match(entry, transcript)
                if score >= tuning.match_threshold:
                    candidates.append((entry, score, matched))

            if not candidates:
                return None

            candidates.sort(key=lambda c: c[1], reverse=True)
            top, score, matched = candidates[0]
            effective_weight = max(0.0, min(1.0, top.weight * tuning.weight_multiplier))
            if self._rng.random() > effective_weight:
                return None

            self.memory.record_echo_used(top.id, pool=self.pool)
            self._last_use_turn = self._turn_counter
            return InjectedEcho(entry=top, score=score, matched_tags=matched)

    def note_turn(self) -> None:
        """Просто увеличить счётчик turn'ов без попытки инжекта.

        Используется когда оркестратор не вызывает `maybe_inject` (например, во время повторного запуска).
        """
        with self._lock:
            self._turn_counter += 1

    @property
    def entries(self) -> list[EchoEntry]:
        with self._lock:
            return list(self._entries)

    @property
    def turn_counter(self) -> int:
        with self._lock:
            return self._turn_counter

    # ----- internal -----

    def _cooldown_days(self, tuning: EchoesTuning | ChineseTuning) -> int:
        if isinstance(tuning, EchoesTuning):
            return tuning.per_echo_cooldown_days
        # для chinese нет per-echo days в tuning — используем то же что глобально
        # (можно расширить в Tuning.json при необходимости)
        return 7

    def _score_match(self, entry: EchoEntry, transcript: str) -> tuple[float, list[str]]:
        """Tag-based матч: считаем сколько тегов entry присутствуют в transcript.

        Возвращает (score, matched_tags). Score нормализован к [0..1] относительно числа тегов entry.
        """
        if not entry.tags:
            return 0.0, []
        normalized = transcript.lower()
        matched: list[str] = []
        for tag in entry.tags:
            tag_lower = tag.lower()
            # простой substring-match с учётом границ слов для коротких тегов
            if len(tag_lower) <= 3:
                # короткие — только как полное слово
                pattern = rf"\b{re.escape(tag_lower)}\b"
                if re.search(pattern, normalized):
                    matched.append(tag)
            else:
                if tag_lower in normalized:
                    matched.append(tag)
        if not matched:
            return 0.0, []
        score = min(1.0, len(matched) / max(1, len(entry.tags)) + 0.2)
        return score, matched
