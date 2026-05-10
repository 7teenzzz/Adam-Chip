"""Runtime-настройки персоны Адама.

`Tuning.json` редактируется из WebUI и hot-reloadable.
Инфраструктура (камеры, MCU, endpoints LLM/ASR/TTS) — отдельно в Settings/Config.json.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Literal

from typing import Optional
from pydantic import BaseModel, Field, ValidationError, model_validator

from .config import PROJECT_ROOT

log = logging.getLogger(__name__)

DEFAULT_TUNING_PATH = PROJECT_ROOT / "Agent Adam Chip" / "Tuning.json"


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


class MemoryTuning(BaseModel):
    episodic: EpisodicTuning = Field(default_factory=EpisodicTuning)
    semantic: SemanticTuning = Field(default_factory=SemanticTuning)
    recent_injection: RecentInjectionTuning = Field(default_factory=RecentInjectionTuning)
    consolidator: ConsolidatorTuning = Field(default_factory=ConsolidatorTuning)


class EchoesTuning(BaseModel):
    enabled: bool = True
    global_cooldown_turns: int = Field(12, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.55, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
    matcher_type: Literal["tag", "embedding"] = "tag"


class ChineseTuning(BaseModel):
    enabled: bool = True
    global_cooldown_turns: int = Field(30, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.65, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
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
    volume: float = Field(1.0, ge=0, le=2.0)


class PromptTuning(BaseModel):
    history_turns: int = Field(8, ge=0, le=50)
    include_scene: bool = True
    include_sensors: bool = True


class DiagnosticsTuning(BaseModel):
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    metrics_enabled: bool = True
    trace_prompts: bool = False


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


# ---------- Store с hot-reload ----------


class TuningStore:
    """Singleton-обёртка над Tuning. Перечитывает файл при изменении mtime.

    Использование:
        store = TuningStore(path)
        cfg = store.current()       # Tuning instance
        store.apply_patch({...})    # частичное обновление + сохранение
        store.subscribe(callback)   # уведомления при перезагрузке
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_TUNING_PATH
        self._lock = threading.RLock()
        self._mtime: float = 0.0
        self._cache: Tuning = Tuning()  # дефолт пока не загружен
        self._listeners: list[callable] = []
        self._load_initial()

    def _load_initial(self) -> None:
        if not self.path.exists():
            log.warning("Tuning file not found at %s, using defaults", self.path)
            return
        try:
            self._reload_locked()
        except Exception as exc:  # pragma: no cover
            log.error("failed to load tuning: %s", exc, exc_info=True)

    def _reload_locked(self) -> Optional["Tuning"]:
        """Reload from disk if mtime changed. Returns new Tuning if listeners should fire, else None."""
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        if stat.st_mtime == self._mtime and self._cache:
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("tuning: cannot parse %s: %s", self.path, exc)
            return None
        raw.pop("_meta", None)
        try:
            new_cache = Tuning.model_validate(raw)
        except ValidationError as exc:
            log.error("tuning: validation failed, keeping previous cache: %s", exc)
            return None
        prev = self._cache
        self._cache = new_cache
        self._mtime = stat.st_mtime
        return new_cache if prev != new_cache else None

    def current(self) -> "Tuning":
        """Возвращает актуальный Tuning, перечитывая файл если он изменился."""
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
        """Применяет частичное обновление, валидирует, сохраняет на диск.

        Patch — dict с произвольной глубиной (deep merge поверх текущего).
        Возвращает новый Tuning. Бросает ValidationError если patch некорректен.
        """
        with self._lock:
            self._reload_locked()
            current_dict = self._cache.model_dump()
            merged = _deep_merge(current_dict, patch)
            new_cache = Tuning.model_validate(merged)  # бросит если что-то не так
            self._save_locked(new_cache)
            self._cache = new_cache
            self._mtime = self.path.stat().st_mtime
            listeners = list(self._listeners)
        self._fire_listeners(new_cache, listeners)
        return new_cache

    def replace(self, full: dict[str, Any]) -> "Tuning":
        """Полная замена настроек (без deep merge). Для UI-формы Restore defaults / Import."""
        with self._lock:
            new_cache = Tuning.model_validate(full)
            self._save_locked(new_cache)
            self._cache = new_cache
            self._mtime = self.path.stat().st_mtime
            listeners = list(self._listeners)
        self._fire_listeners(new_cache, listeners)
        return new_cache

    def restore_defaults(self) -> Tuning:
        return self.replace(Tuning().model_dump())

    def _save_locked(self, tuning: Tuning) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = tuning.model_dump()
        # сохраним _meta из существующего файла если есть
        meta: dict[str, Any] = {}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as h:
                    meta = json.load(h).get("_meta", {})
            except Exception:
                pass
        out = {"_meta": meta, **payload} if meta else payload
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=2, ensure_ascii=False)

    def subscribe(self, callback) -> None:
        """callback(tuning: Tuning) вызывается при изменении настроек."""
        with self._lock:
            self._listeners.append(callback)

    def _fire_listeners(self, tuning: "Tuning", listeners: list) -> None:
        for cb in listeners:
            try:
                cb(tuning)
            except Exception as exc:  # pragma: no cover
                log.error("tuning listener failed: %s", exc, exc_info=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


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
