"""Runtime-настройки персоны Адама.

Раньше эти параметры жили в `Agent Adam Chip/Tuning.json` — отдельный файл с
hot-reload по mtime. В рамках миграции на single-source-of-truth все параметры
переехали в `System/Config.json` (секция `tuning`). Этот модуль сохраняет
pydantic-модели и API `TuningStore`, но backing store теперь — `Settings`,
читающий Config.json. Внешние импорты (`from .tuning import ...`) не меняются.
"""
from __future__ import annotations

import copy
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError, model_validator

from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, Settings

log = logging.getLogger(__name__)


# ---------- Pydantic-модели ----------


class EpisodicWeights(BaseModel):
    introduced_name: float = Field(0.30, ge=0, le=1)
    duration: float = Field(0.20, ge=0, le=1)
    themes: float = Field(0.15, ge=0, le=1)
    tone: float = Field(0.15, ge=0, le=1)
    echoes_used: float = Field(0.10, ge=0, le=1)
    new_question: float = Field(0.10, ge=0, le=1)

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "EpisodicWeights":
        total = (
            self.introduced_name + self.duration + self.themes
            + self.tone + self.echoes_used + self.new_question
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"EpisodicWeights must sum to 1.0 ± 0.01, got {total:.4f}")
        return self


class EpisodicTuning(BaseModel):
    enabled: bool = True
    salience_threshold: float = Field(0.4, ge=0, le=1)
    decay_days: int = Field(14, ge=1, le=365)
    duration_normalize_seconds: int = Field(300, ge=30)
    weights: EpisodicWeights = Field(default_factory=EpisodicWeights)
    highlights_max_per_episode: int = Field(6, ge=1, le=50)
    recurring_min_visits: int = Field(2, ge=2, le=20)
    recurring_lookup_days: int = Field(90, ge=7, le=365)


class SemanticTuning(BaseModel):
    enabled: bool = True
    max_chars: int = Field(4000, ge=200, le=20000)


class RecentInjectionTuning(BaseModel):
    enabled: bool = True
    limit: int = Field(2, ge=0, le=10)
    strategy: Literal["by_name", "by_theme", "by_name_or_theme"] = "by_name"
    max_age_days: int = Field(30, ge=1, le=365)


class ConsolidatorTuning(BaseModel):
    enabled: bool = True
    model: Optional[str] = None
    window_start: str = "03:00"
    window_end: str = "05:00"
    max_episodes_per_run: int = Field(200, ge=1)
    temperature: float = Field(0.3, ge=0, le=2)
    max_runtime_minutes: int = Field(30, ge=1, le=240)
    retry_on_invalid_patch: bool = False
    gate_log_max_days: int = Field(30, ge=1, le=365)
    instant_threshold: float = Field(0.75, ge=0, le=1)


class MemoryTuning(BaseModel):
    episodic: EpisodicTuning = Field(default_factory=EpisodicTuning)
    semantic: SemanticTuning = Field(default_factory=SemanticTuning)
    recent_injection: RecentInjectionTuning = Field(default_factory=RecentInjectionTuning)
    consolidator: ConsolidatorTuning = Field(default_factory=ConsolidatorTuning)
    theme_clusters: Dict[str, List[str]] = Field(default_factory=dict)


class EchoesTuning(BaseModel):
    enabled: bool = True
    global_cooldown_turns: int = Field(12, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.55, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
    matcher_type: Literal["tag", "tfidf"] = "tag"
    score_boost: float = Field(0.2, ge=0, le=1)
    tag_short_cutoff: int = Field(3, ge=1, le=10)
    default_entry_weight: float = Field(0.5, ge=0, le=1)


class ChineseTuning(BaseModel):
    enabled: bool = True
    global_cooldown_turns: int = Field(30, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.65, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
    matcher_type: Literal["tag", "tfidf"] = "tag"
    score_boost: float = Field(0.2, ge=0, le=1)
    tag_short_cutoff: int = Field(3, ge=1, le=10)
    default_entry_weight: float = Field(0.5, ge=0, le=1)
    audio_mode: Literal[
        "prerendered_only",
        "prerendered_with_text_fallback",
        "text_only",
    ] = "prerendered_with_text_fallback"


class SessionTuning(BaseModel):
    end_strategy: Literal[
        "vad_silence",
        "face_lost",
        "combined",
        "idle_with_grace",
        "event_signal",
    ] = "combined"
    vad_silence_seconds: int = Field(60, ge=5)
    face_lost_seconds: int = Field(15, ge=2)
    grace_message: str = "вы там?"


class SceneDirectorTuning(BaseModel):
    enabled: bool = True
    sustain_seconds: int = Field(8, ge=1)
    cooldown_between_changes_seconds: int = Field(5, ge=0)
    hysteresis_seconds: int = Field(15, ge=0)
    override_priority_scenes: list[str] = Field(default_factory=lambda: ["unease"])


class LLMTuning(BaseModel):
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(200, ge=10, le=2000)
    response_word_target: int = Field(30, ge=5, le=200)


class VoiceTuning(BaseModel):
    speaker: str = "eugene"
    speed_multiplier: float = Field(1.0, ge=0.5, le=2.0)
    volume: float = Field(0.5, ge=0, le=1.0)


class PromptTuning(BaseModel):
    history_turns: int = Field(8, ge=0, le=50)
    include_scene: bool = True
    include_sensors: bool = True


class DiagnosticsTuning(BaseModel):
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    metrics_enabled: bool = True
    trace_prompts: bool = False
    # Phase 11 lag-source diagnostic — emits ~200 mic_lag_diag_chunk events
    # per post-TTS turn while True. Use scripts/diag_lag_source.py to analyse.
    trace_post_tts_lag: bool = False


class Tuning(BaseModel):
    """Корневая модель runtime-настроек персоны."""

    memory: MemoryTuning = Field(default_factory=MemoryTuning)
    echoes: EchoesTuning = Field(default_factory=EchoesTuning)
    chinese: ChineseTuning = Field(default_factory=ChineseTuning)
    session: SessionTuning = Field(default_factory=SessionTuning)
    scene_director: SceneDirectorTuning = Field(default_factory=SceneDirectorTuning)
    llm: LLMTuning = Field(default_factory=LLMTuning)
    voice: VoiceTuning = Field(default_factory=VoiceTuning)
    prompt: PromptTuning = Field(default_factory=PromptTuning)
    diagnostics: DiagnosticsTuning = Field(default_factory=DiagnosticsTuning)


# ---------- Store с hot-reload (теперь поверх Config.json) ----------


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class TuningStore:
    """Singleton-обёртка над Tuning, читает секцию `tuning` из Config.json.

    Использование (без изменений по сравнению с прошлой версией):
        store = TuningStore()         # path-аргумент проигнорирован
        cfg = store.current()         # Tuning instance
        store.apply_patch({...})      # частичное обновление + сохранение
        store.subscribe(callback)     # уведомления при перезагрузке

    Hot-reload: poll'ит mtime Config.json. Если файл изменился извне
    (например, ручной редактирующий) — кэш перечитывается на следующем
    вызове .current().
    """

    def __init__(self, path: Path | None = None) -> None:
        # path-аргумент сохраняется только ради обратной совместимости
        # с вызовами из Engineering/consolidator.py и тестов. Реально
        # читаем/пишем в Config.json — единый источник истины.
        if path is not None:
            log.debug("TuningStore: ignoring legacy path=%s (using Config.json)", path)
        self._lock = threading.RLock()
        self._mtime: float = 0.0
        self._cache: Tuning = Tuning()
        self._listeners: list = []
        self._load_initial()

    @property
    def path(self) -> Path:
        """Возвращает путь к backing-store (Config.json) — для обратной совместимости."""
        return DEFAULT_CONFIG_PATH

    def _load_initial(self) -> None:
        try:
            self._reload_locked()
        except Exception as exc:  # pragma: no cover
            log.error("failed to initial-load tuning from config: %s", exc, exc_info=True)

    def _reload_locked(self) -> Optional["Tuning"]:
        """Reload from Config.json if mtime changed. Returns new Tuning if changed."""
        try:
            stat = DEFAULT_CONFIG_PATH.stat()
        except FileNotFoundError:
            return None
        if stat.st_mtime == self._mtime and self._cache:
            return None
        try:
            settings = Settings.load()
            raw_tuning = settings.section("tuning")
        except Exception as exc:
            log.error("tuning: cannot load Settings: %s", exc)
            return None
        try:
            new_cache = Tuning.model_validate(raw_tuning)
        except ValidationError as exc:
            log.error("tuning: validation failed, keeping previous cache: %s", exc)
            return None
        prev = self._cache
        self._cache = new_cache
        self._mtime = stat.st_mtime
        return new_cache if prev != new_cache else None

    def current(self) -> "Tuning":
        """Возвращает актуальный Tuning, перечитывая Config.json если он изменился."""
        with self._lock:
            changed = self._reload_locked()
            snap = self._cache
            listeners = list(self._listeners) if changed else []
        for cb in listeners:
            try:
                cb(changed)
            except Exception as exc:
                log.error("tuning listener failed: %s", exc, exc_info=True)
        return snap

    def apply_patch(self, patch: dict[str, Any]) -> "Tuning":
        """Частичное обновление: deep-merge поверх текущего, валидация, save в Config.json."""
        with self._lock:
            self._reload_locked()
            current_dict = self._cache.model_dump()
            merged = _deep_merge(current_dict, patch)
            new_cache = Tuning.model_validate(merged)
            self._persist_locked(new_cache)
            self._cache = new_cache
            try:
                self._mtime = DEFAULT_CONFIG_PATH.stat().st_mtime
            except FileNotFoundError:
                pass
            listeners = list(self._listeners)
        self._fire_listeners(new_cache, listeners)
        return new_cache

    def replace(self, full: dict[str, Any]) -> "Tuning":
        """Полная замена tuning-секции (без deep merge)."""
        with self._lock:
            new_cache = Tuning.model_validate(full)
            self._persist_locked(new_cache)
            self._cache = new_cache
            try:
                self._mtime = DEFAULT_CONFIG_PATH.stat().st_mtime
            except FileNotFoundError:
                pass
            listeners = list(self._listeners)
        self._fire_listeners(new_cache, listeners)
        return new_cache

    def restore_defaults(self) -> Tuning:
        return self.replace(Tuning().model_dump())

    def _persist_locked(self, tuning: Tuning) -> None:
        """Save tuning section into Config.json via Settings."""
        settings = Settings.load()
        payload = tuning.model_dump()
        # Полная замена секции tuning: сначала очищаем, потом мерджим.
        settings.raw["tuning"] = copy.deepcopy(payload)
        settings.save()

    def subscribe(self, callback) -> None:
        with self._lock:
            self._listeners.append(callback)

    def _fire_listeners(self, tuning: "Tuning", listeners: list) -> None:
        for cb in listeners:
            try:
                cb(tuning)
            except Exception as exc:  # pragma: no cover
                log.error("tuning listener failed: %s", exc, exc_info=True)


# ---------- Глобальный экземпляр ----------

_GLOBAL: TuningStore | None = None


def get_store(path: Path | None = None) -> TuningStore:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = TuningStore(path)
    return _GLOBAL


def reset_store() -> None:
    """Только для тестов."""
    global _GLOBAL
    _GLOBAL = None


# Legacy alias — раньше код мог ссылаться на DEFAULT_TUNING_PATH; теперь это
# просто путь к Config.json. Оставлен для обратной совместимости тестов.
DEFAULT_TUNING_PATH = DEFAULT_CONFIG_PATH
