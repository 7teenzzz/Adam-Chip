"""Episodic memory primitives для Адама.

`Episode` — одна запись на диалоговую сессию (не на turn).
`SessionAccumulator` — собирает highlights/themes/echoes за время сессии,
финализируется в Episode при закрытии сессии.
`salience_score()` — rule-based фильтр для записи (см. Memory_Schema.md).

Чистый код без I/O. Хранение и retrieval — в memory.py.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from .tuning import EpisodicTuning, EpisodicWeights

# Тон зрителя — ограниченный набор для детерминированной аналитики
ToneLiteral = str  # фактически: curious|hostile|sad|playful|neutral|confused
AdamStateLiteral = str  # Ac-Or | Pa-Or | Ac-Ch | Pa-Ch | unknown


# ---------- модели ----------


@dataclass
class Highlight:
    who: str  # "visitor" | "adam"
    text: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"who": self.who, "text": self.text, "reason": self.reason}


@dataclass
class VisitorInfo:
    introduced_name: Optional[str] = None
    estimated_count: int = 1
    recurring_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "introduced_name": self.introduced_name,
            "estimated_count": self.estimated_count,
            "recurring_signal": self.recurring_signal,
        }


@dataclass
class Episode:
    id: str
    ts_start: datetime
    ts_end: datetime
    duration_s: int
    session_id: str
    visitor: VisitorInfo
    themes: list[str]
    salience: float
    tone_visitor: str
    adam_state: str
    highlights: list[Highlight]
    echoes_used: list[str]
    chinese_used: list[str]
    scene_changes: list[str]
    pinned: bool = False
    consolidated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts_start": _to_iso(self.ts_start),
            "ts_end": _to_iso(self.ts_end),
            "duration_s": self.duration_s,
            "session_id": self.session_id,
            "visitor": self.visitor.to_dict(),
            "themes": list(self.themes),
            "salience": round(self.salience, 4),
            "tone_visitor": self.tone_visitor,
            "adam_state": self.adam_state,
            "highlights": [h.to_dict() for h in self.highlights],
            "echoes_used": list(self.echoes_used),
            "chinese_used": list(self.chinese_used),
            "scene_changes": list(self.scene_changes),
            "pinned": self.pinned,
            "consolidated": self.consolidated,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Episode":
        visitor_raw = raw.get("visitor") or {}
        return cls(
            id=raw["id"],
            ts_start=_from_iso(raw["ts_start"]),
            ts_end=_from_iso(raw["ts_end"]),
            duration_s=int(raw.get("duration_s", 0)),
            session_id=raw.get("session_id", ""),
            visitor=VisitorInfo(
                introduced_name=visitor_raw.get("introduced_name"),
                estimated_count=int(visitor_raw.get("estimated_count", 1)),
                recurring_signal=bool(visitor_raw.get("recurring_signal", False)),
            ),
            themes=list(raw.get("themes", [])),
            salience=float(raw.get("salience", 0.0)),
            tone_visitor=raw.get("tone_visitor", "neutral"),
            adam_state=raw.get("adam_state", "unknown"),
            highlights=[
                Highlight(who=h["who"], text=h["text"], reason=h.get("reason", ""))
                for h in raw.get("highlights", [])
            ],
            echoes_used=list(raw.get("echoes_used", [])),
            chinese_used=list(raw.get("chinese_used", [])),
            scene_changes=list(raw.get("scene_changes", [])),
            pinned=bool(raw.get("pinned", False)),
            consolidated=bool(raw.get("consolidated", False)),
        )


# ---------- accumulator ----------


@dataclass
class SessionAccumulator:
    """Растёт по ходу сессии, финализируется в Episode."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ts_end: Optional[datetime] = None
    visitor: VisitorInfo = field(default_factory=VisitorInfo)
    themes: list[str] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    echoes_used: list[str] = field(default_factory=list)
    chinese_used: list[str] = field(default_factory=list)
    scene_changes: list[str] = field(default_factory=list)
    tone_visitor: str = "neutral"
    adam_state: str = "unknown"
    pinned: bool = False
    _seen_questions: set[str] = field(default_factory=set)
    _has_new_question: bool = False
    _turn_count: int = 0

    def note_turn(self, who: str, text: str) -> None:
        self._turn_count += 1
        if who == "visitor" and "?" in text:
            sig = _question_signature(text)
            if sig and sig not in self._seen_questions:
                self._seen_questions.add(sig)
                # отметим — для salience веса new_question
                self._has_new_question = True

    def add_highlight(self, who: str, text: str, reason: str = "", *, max_count: int = 6) -> None:
        if len(self.highlights) >= max_count:
            return
        self.highlights.append(Highlight(who=who, text=text, reason=reason))

    def note_theme(self, theme: str) -> None:
        if theme and theme not in self.themes:
            self.themes.append(theme)

    def note_echo_used(self, echo_id: str) -> None:
        if echo_id and echo_id not in self.echoes_used:
            self.echoes_used.append(echo_id)

    def note_chinese_used(self, chinese_id: str) -> None:
        if chinese_id and chinese_id not in self.chinese_used:
            self.chinese_used.append(chinese_id)

    def note_scene_change(self, scene: str) -> None:
        if not self.scene_changes or self.scene_changes[-1] != scene:
            self.scene_changes.append(scene)

    def set_visitor_name(self, name: Optional[str]) -> None:
        self.visitor.introduced_name = name.strip() if name else None

    def set_visitor_count(self, count: int) -> None:
        self.visitor.estimated_count = max(1, int(count))

    def set_recurring(self, recurring: bool) -> None:
        self.visitor.recurring_signal = bool(recurring)

    def set_tone(self, tone: str) -> None:
        self.tone_visitor = tone

    def set_adam_state(self, state: str) -> None:
        self.adam_state = state

    def pin(self) -> None:
        self.pinned = True

    def has_new_question(self) -> bool:
        return self._has_new_question

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def finalize(
        self,
        end_ts: Optional[datetime] = None,
        *,
        weights: EpisodicWeights,
        duration_normalize_seconds: int,
    ) -> Episode:
        end = end_ts or datetime.now(timezone.utc)
        duration = max(0, int((end - self.ts_start).total_seconds()))
        salience = salience_score(
            visitor=self.visitor,
            themes=self.themes,
            tone=self.tone_visitor,
            duration_s=duration,
            echoes_used=self.echoes_used,
            chinese_used=self.chinese_used,
            has_new_question=self._has_new_question,
            weights=weights,
            duration_normalize_seconds=duration_normalize_seconds,
        )
        self.ts_end = end
        return Episode(
            id=uuid.uuid4().hex,
            ts_start=self.ts_start,
            ts_end=end,
            duration_s=duration,
            session_id=self.session_id,
            visitor=VisitorInfo(**self.visitor.__dict__),
            themes=list(self.themes),
            salience=salience,
            tone_visitor=self.tone_visitor,
            adam_state=self.adam_state,
            highlights=list(self.highlights),
            echoes_used=list(self.echoes_used),
            chinese_used=list(self.chinese_used),
            scene_changes=list(self.scene_changes),
            pinned=self.pinned,
            consolidated=False,
        )


# ---------- salience ----------


SALIENCE_TONE_BUCKET = {"hostile", "sad", "playful"}


def salience_score(
    *,
    visitor: VisitorInfo,
    themes: Iterable[str],
    tone: str,
    duration_s: int,
    echoes_used: Iterable[str],
    chinese_used: Iterable[str],
    has_new_question: bool,
    weights: EpisodicWeights,
    duration_normalize_seconds: int = 300,
) -> float:
    """Rule-based salience-формула из Memory_Schema.md.

    Возвращает float в [0..1].
    """
    themes_list = list(themes)
    echo_or_chinese = bool(list(echoes_used) or list(chinese_used))

    name_term = 1.0 if visitor.introduced_name else 0.0
    duration_norm = _clamp01(duration_s / max(1, duration_normalize_seconds))
    themes_term = min(len(set(themes_list)), 5) / 5
    tone_term = 1.0 if tone in SALIENCE_TONE_BUCKET else 0.0
    echo_term = 1.0 if echo_or_chinese else 0.0
    new_q_term = 1.0 if has_new_question else 0.0

    score = (
        weights.introduced_name * name_term
        + weights.duration * duration_norm
        + weights.themes * themes_term
        + weights.tone * tone_term
        + weights.echoes_used * echo_term
        + weights.new_question * new_q_term
    )
    return _clamp01(score)


def should_record(
    episode: Episode | None,
    accumulator: SessionAccumulator,
    tuning: EpisodicTuning,
) -> bool:
    """Триггер записи: salience >= threshold OR introduced_name OR pinned."""
    if not tuning.enabled:
        return False
    if accumulator.pinned:
        return True
    if accumulator.visitor.introduced_name:
        return True
    if episode is None:
        return False
    return episode.salience >= tuning.salience_threshold


# ---------- helpers ----------


_QUESTION_NORMALIZE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _question_signature(text: str) -> str:
    """Нормализованная сигнатура для дедупликации вопросов в рамках сессии."""
    normalized = _QUESTION_NORMALIZE.sub(" ", text.lower())
    tokens = [t for t in normalized.split() if len(t) > 2]
    return " ".join(sorted(tokens[:8]))


def _clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _from_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
