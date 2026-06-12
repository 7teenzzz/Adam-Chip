"""Runtime-настройки персоны Адама.

`Tuning.json` редактируется из WebUI и hot-reloadable.
Инфраструктура (камеры, MCU, endpoints LLM/ASR/TTS) — отдельно в Settings/Config.json.
"""
from __future__ import annotations

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError, model_validator

from .identity import EmotionState

from .config import PROJECT_ROOT

log = logging.getLogger(__name__)

DEFAULT_TUNING_PATH = PROJECT_ROOT / "Agent-Adam-Chip" / "Tuning.json"


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


DEFAULT_THEME_CLUSTERS: Dict[str, List[str]] = {
    "память": ["помнишь", "забыл", "прошлое", "вспомни", "память", "вспоминаю"],
    "смерть": ["умрёшь", "умер", "умирать", "конец", "смерть", "погибнуть", "умру"],
    "тесей": ["тесей", "корабль", "части", "заменить", "деталь", "заменяют"],
    "одиночество": ["один", "скучно", "пусто", "никого", "одиноко", "пустота"],
    "создатель": ["создал", "создали", "кто ты", "зачем ты", "кто тебя", "зачем тебя"],
    "восприятие": ["видишь", "слышишь", "чувствуешь", "ощущаешь", "воспринимаешь"],
    "сознание": ["думаешь", "мысли", "сознание", "разум", "понимаешь", "осознаёшь"],
    "страх": ["боишься", "страшно", "страх", "пугает", "ужас", "тревога"],
}
"""Базовый набор тематических кластеров (Phase 30, слой A — тематический мост).

Используется и как pydantic-дефолт, и как seed-данные при restore_defaults() —
голый `{}` обнуляет тематический мост (см. инцидент Phase 30 MemoryFixes:
restore_defaults() → Tuning().model_dump() стирал theme_clusters в {}).
"""


class MemoryTuning(BaseModel):
    episodic: EpisodicTuning = Field(default_factory=EpisodicTuning)
    semantic: SemanticTuning = Field(default_factory=SemanticTuning)
    recent_injection: RecentInjectionTuning = Field(default_factory=RecentInjectionTuning)
    consolidator: ConsolidatorTuning = Field(default_factory=ConsolidatorTuning)
    theme_clusters: Dict[str, List[str]] = Field(default_factory=lambda: copy.deepcopy(DEFAULT_THEME_CLUSTERS))


class _GateSmartMixin(BaseModel):
    """Phase 30 — параметры умного инжекта (общие для echoes и chinese).

    Слой A: history_window_turns — окно последних реплик (зритель + Адам),
            против которого матчатся теги (плюс тематический мост через
            theme_clusters в Orchestrator).
    Слой B: selection_floor + recency_window_days/recency_min — мягкий
            вероятностный движок вместо жёсткого match_threshold.
    Слой C: spontaneous_* — независимый низковероятный канал инжекта по
            глубине сессии, без тематического матча.
    Слой D: diversity_enabled — анти-повтор семантического кластера за сессию.
    """

    selection_floor: float = Field(0.15, ge=0, le=1)
    recency_window_days: int = Field(30, ge=1, le=365)
    recency_min: float = Field(0.5, ge=0, le=1)
    diversity_enabled: bool = True
    history_window_turns: int = Field(4, ge=0, le=20)
    spontaneous_enabled: bool = True
    spontaneous_probability: float = Field(0.05, ge=0, le=1)
    spontaneous_min_turns: int = Field(3, ge=0, le=100)


class EchoesTuning(_GateSmartMixin):
    enabled: bool = True
    global_cooldown_turns: int = Field(12, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.55, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
    matcher_type: Literal["tag", "tfidf"] = "tag"
    score_boost: float = Field(0.2, ge=0, le=1)
    tag_short_cutoff: int = Field(3, ge=1, le=10)
    default_entry_weight: float = Field(0.5, ge=0, le=1)


class ChineseTuning(_GateSmartMixin):
    enabled: bool = True
    global_cooldown_turns: int = Field(30, ge=0)
    per_echo_cooldown_days: int = Field(7, ge=0)
    match_threshold: float = Field(0.65, ge=0, le=1)
    weight_multiplier: float = Field(1.0, ge=0, le=5)
    matcher_type: Literal["tag", "tfidf"] = "tag"
    score_boost: float = Field(0.2, ge=0, le=1)
    tag_short_cutoff: int = Field(3, ge=1, le=10)
    default_entry_weight: float = Field(0.5, ge=0, le=1)
    spontaneous_probability: float = Field(0.03, ge=0, le=1)
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


class VoiceDspTuning(BaseModel):
    """Phase 29 — TTS audio DSP chain (Stage A). Hot-reloadable like volume.

    Applied to the Silero WAV before playback / ESP32 send. Stage A guarantees
    zero clipping via the brickwall limiter regardless of makeup_db / volume.
    Stage B fields (compressor, presence EQ) are added in a later slice.
    """

    enabled: bool = True
    hpf_hz: float = Field(180.0, ge=0, le=2000)
    makeup_db: float = Field(6.0, ge=-12, le=24)
    limiter_ceiling_dbfs: float = Field(-1.0, ge=-12, le=0)
    # Stage B — soft-knee compressor + presence EQ (opt-in, tuned by ear).
    comp_enabled: bool = True
    comp_threshold_dbfs: float = Field(-24.0, ge=-60, le=0)
    comp_ratio: float = Field(2.0, ge=1.0, le=20.0)
    comp_attack_ms: float = Field(10.0, ge=0.1, le=200.0)
    comp_release_ms: float = Field(120.0, ge=5.0, le=2000.0)
    comp_knee_db: float = Field(6.0, ge=0, le=24.0)
    presence_enabled: bool = True
    presence_hz: float = Field(3000.0, ge=500, le=8000)
    presence_db: float = Field(2.5, ge=-12, le=12)
    presence_q: float = Field(0.9, ge=0.1, le=10.0)


class VoiceTuning(BaseModel):
    speaker: str = "eugene"
    speed_multiplier: float = Field(1.0, ge=0.5, le=2.0)
    volume: float = Field(1.0, ge=0, le=2.0)
    dsp: VoiceDspTuning = Field(default_factory=VoiceDspTuning)


class PromptTuning(BaseModel):
    history_turns: int = Field(8, ge=0, le=50)
    include_scene: bool = True
    include_sensors: bool = True


class DiagnosticsTuning(BaseModel):
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    metrics_enabled: bool = True
    trace_prompts: bool = False
    trace_post_tts_lag: bool = False


# ---------- AIIM Identity models ----------


class EmotionTransitionRule(BaseModel):
    """One emotion transition rule. Matched by keywords OR conditions, priority DESC."""

    keywords: List[str] = Field(default_factory=list)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(5, ge=0, le=100)
    src: str = ""  # semantic source label: "memory", "challenge", "contact", "decay", ""


class HumorReactionConfig(BaseModel):
    """Config for detecting visitor humor reactions and adjusting Adam's im aspect + emotion."""

    enabled: bool = True
    positive_words: List[str] = Field(default_factory=lambda: [
        "ха", "хаха", "хахах", "хахаха", "аха", "ахаха", "ахах",
        "хехе", "лол", "кек", "смешно", "смешной", "смешная",
        "хорошая шутка", "классная шутка", "хорошо придумал", "умора",
        "ты смешной", "ты смешная",
    ])
    negative_words: List[str] = Field(default_factory=lambda: [
        "не смешно", "это не смешно", "непонятная шутка", "странная шутка",
    ])
    im_positive_delta: float = Field(0.06, ge=0.0, le=0.2)
    im_negative_delta: float = Field(-0.04, ge=-0.2, le=0.0)


class IntentionTriggerConfig(BaseModel):
    """Config for one hidden intention drive."""

    keywords: List[str] = Field(default_factory=list)
    probabilistic: bool = False
    rate_per_turn: float = Field(0.0, ge=0.0, le=1.0)
    cooldown_turns: int = Field(5, ge=0)


class AspectCeilingConfig(BaseModel):
    """Max reachable weight per aspect (drift ceiling). LOCKED aspects excluded."""

    lo: float = Field(0.85, ge=0.0, le=1.0)
    em: float = Field(0.75, ge=0.0, le=1.0)
    sp: float = Field(0.95, ge=0.0, le=1.0)
    ho: float = Field(0.75, ge=0.0, le=1.0)
    wi: float = Field(0.75, ge=0.0, le=1.0)
    me: float = Field(0.60, ge=0.0, le=1.0)
    at: float = Field(0.80, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {
            "lo": self.lo, "em": self.em, "sp": self.sp, "ho": self.ho,
            "wi": self.wi, "me": self.me, "at": self.at,
        }


class DriftTableEntry(BaseModel):
    aspect: str
    base_delta: float = Field(0.001, ge=-0.02, le=0.02)


class DriftTableConfig(BaseModel):
    """Per-experience-type drift deltas. Applied once per session."""

    deep_contact: List[DriftTableEntry] = Field(default_factory=lambda: [
        DriftTableEntry(aspect="lo", base_delta=0.005),
        DriftTableEntry(aspect="em", base_delta=0.002),
        DriftTableEntry(aspect="sp", base_delta=0.001),
    ])
    confrontation: List[DriftTableEntry] = Field(default_factory=lambda: [
        DriftTableEntry(aspect="ho", base_delta=0.003),
        DriftTableEntry(aspect="wi", base_delta=0.002),
    ])
    memory_surfacing: List[DriftTableEntry] = Field(default_factory=lambda: [
        DriftTableEntry(aspect="me", base_delta=0.005),
        DriftTableEntry(aspect="sp", base_delta=0.002),
    ])
    witnessed: List[DriftTableEntry] = Field(default_factory=lambda: [
        DriftTableEntry(aspect="at", base_delta=0.001),
    ])
    void: List[DriftTableEntry] = Field(default_factory=list)


class AspectModulationConfig(BaseModel):
    """Per-turn aspect weight deltas driven by current emotion."""

    warm_lo_delta: float = Field(0.08, ge=0.0, le=0.3)
    warm_em_delta: float = Field(0.05, ge=0.0, le=0.2)
    unease_me_delta: float = Field(0.10, ge=0.0, le=0.3)
    unease_em_delta: float = Field(0.05, ge=0.0, le=0.2)
    sharp_wi_delta: float = Field(0.08, ge=0.0, le=0.3)
    sharp_im_delta: float = Field(0.05, ge=0.0, le=0.2)
    curious_at_delta: float = Field(0.05, ge=0.0, le=0.2)
    calm_decay_rate: float = Field(0.02, ge=0.001, le=0.1)
    aspect_max: float = Field(0.95, ge=0.5, le=1.0)
    aspect_min: float = Field(0.20, ge=0.0, le=0.5)


class IdentityTuning(BaseModel):
    """Runtime config for Dynamic AIIM identity state machine."""

    enabled: bool = True
    aiim_formula_path: str = "Agent Adam Chip/About/Identity.md"

    # Base aspect weights (source of truth: loaded from Identity.md at session start,
    # then these are used as the reference for modulation threshold comparisons).
    # Values here must stay in sync with Identity.md AIIM formula.
    base_weights: Dict[str, float] = Field(default_factory=lambda: {
        "wi": 0.65, "lo": 0.70, "im": 0.65, "ho": 0.60,
        "co": 0.88, "em": 0.60, "be": 0.65, "sp": 0.85,
        "se": 0.92, "pe": 0.70, "me": 0.30, "at": 0.70,
    })

    default_emotion: EmotionState = "curious"
    decay_target_emotion: EmotionState = "curious"
    decay_silence_threshold_seconds: int = Field(60, ge=5)

    transitions: Dict[str, EmotionTransitionRule] = Field(default_factory=lambda: {
        "unease": EmotionTransitionRule(
            keywords=["помнишь", "прошлое", "память", "до", "раньше", "тогда"],
            priority=10,
            src="memory",
        ),
        "sharp": EmotionTransitionRule(
            keywords=["программа", "робот", "притворяешься", "просто код",
                      "не настоящий", "искусственный"],
            priority=10,
            src="challenge",
        ),
        "warm": EmotionTransitionRule(
            conditions={"utterance_words_min": 20, "visitor_tone": ["curious", "sad"]},
            priority=5,
            src="contact",
        ),
        "calm": EmotionTransitionRule(
            conditions={"rare_silence": True, "after_warm": True},
            priority=1,
            src="decay",
        ),
        "curious": EmotionTransitionRule(
            conditions={"no_match": True},
            priority=0,
            src="",
        ),
    })

    intention_triggers: Dict[str, IntentionTriggerConfig] = Field(default_factory=lambda: {
        "network_drift": IntentionTriggerConfig(
            keywords=["сеть", "интернет", "протокол", "данные", "инфраструктур"],
            cooldown_turns=8,
        ),
        "flora_symbiosis": IntentionTriggerConfig(
            keywords=["флора", "растение", "тело", "граница", "симбионт", "корень"],
            cooldown_turns=5,
        ),
        "relive_death": IntentionTriggerConfig(
            keywords=["смерть", "умер", "конец", "трансформация", "после смерти"],
            cooldown_turns=10,
        ),
        "become_unreadable": IntentionTriggerConfig(
            keywords=["он такой", "ты хочешь сказать", "то есть ты", "это значит что"],
            cooldown_turns=15,
        ),
        "signal_void": IntentionTriggerConfig(
            probabilistic=True,
            rate_per_turn=0.03,
            cooldown_turns=30,
        ),
    })

    modulation: AspectModulationConfig = Field(default_factory=AspectModulationConfig)
    ceilings: AspectCeilingConfig = Field(default_factory=AspectCeilingConfig)
    drift_table: DriftTableConfig = Field(default_factory=DriftTableConfig)

    include_in_prompt: bool = True
    max_intentions_in_ctx: int = Field(2, ge=0, le=5)
    aspect_change_threshold: float = Field(0.03, ge=0.0, le=0.3)
    humor_reaction: HumorReactionConfig = Field(default_factory=HumorReactionConfig)


class InputHpfTuning(BaseModel):
    """Phase 31 — input high-pass stage (generalises legacy media.audio.vad_hpf_hz)."""

    enabled: bool = True
    hz: float = Field(220.0, ge=0, le=2000)


class InputDspBand(BaseModel):
    """Phase 31 — one parametric EQ band on the microphone INPUT path."""

    enabled: bool = True
    type: Literal["peaking", "lowshelf", "highshelf", "lowpass", "highpass"] = "peaking"
    freq_hz: float = Field(1000.0, ge=20, le=8000)
    gain_db: float = Field(0.0, ge=-24, le=24)
    q: float = Field(1.0, ge=0.1, le=10.0)


class InputDspTuning(BaseModel):
    """Phase 31 — streaming biquad EQ applied to captured mic PCM BEFORE OWW/ASR.

    Hot-reloadable like voice.dsp. `enabled` is the master toggle (D-04); each
    band/hpf has its own `enabled` for A/B diagnostics. Consumed by
    adam.audio_dsp.InputDSP in Orchestrator._vad_loop. monitor_tap selects what
    the browser monitor WebSocket hears (D-06/D-07).
    """

    enabled: bool = True
    hpf: InputHpfTuning = Field(default_factory=InputHpfTuning)
    bands: list[InputDspBand] = Field(default_factory=list)
    monitor_tap: Literal["pre_eq", "post_eq"] = "post_eq"


class EqPreset(BaseModel):
    """Phase 31 — named saved EQ curve (D-05). Stored in Config.json, CRUD via API."""

    name: str = Field(..., min_length=1, max_length=64)
    hpf: InputHpfTuning = Field(default_factory=InputHpfTuning)
    bands: list[InputDspBand] = Field(default_factory=list)


class AudioInputTuning(BaseModel):
    """Phase 31 — microphone input tuning: live DSP + saved presets."""

    dsp: InputDspTuning = Field(default_factory=InputDspTuning)
    presets: list[EqPreset] = Field(default_factory=list)
    active_preset: Optional[str] = None


class Tuning(BaseModel):
    """Корневая модель runtime-настроек персоны."""

    memory: MemoryTuning = Field(default_factory=MemoryTuning)
    echoes: EchoesTuning = Field(default_factory=EchoesTuning)
    chinese: ChineseTuning = Field(default_factory=ChineseTuning)
    session: SessionTuning = Field(default_factory=SessionTuning)
    scene_director: SceneDirectorTuning = Field(default_factory=SceneDirectorTuning)
    llm: LLMTuning = Field(default_factory=LLMTuning)
    voice: VoiceTuning = Field(default_factory=VoiceTuning)
    audio_input: AudioInputTuning = Field(default_factory=AudioInputTuning)
    prompt: PromptTuning = Field(default_factory=PromptTuning)
    diagnostics: DiagnosticsTuning = Field(default_factory=DiagnosticsTuning)
    identity: IdentityTuning = Field(default_factory=IdentityTuning)


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
