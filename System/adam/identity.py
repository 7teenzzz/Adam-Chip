"""Dynamic AIIM — runtime identity state machine for Adam Chip.

Parses the AIIM formula from Identity.md and maintains per-turn state:
- EmotionState: 5-state machine driven by transcript keywords
- IntentionState: 5 hidden drives with cooldowns
- IdentityVector: 12 aspect weights, modulated per turn
- AIIMRuntimeState: per-session container with ctx_block generation

No I/O. No LLM calls. Pure deterministic logic.
"""
from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from .tuning import IdentityTuning

EmotionState = Literal["curious", "warm", "unease", "sharp", "calm"]

# Regex for AIIM formula: wi(P 4 Ac-Or)Δ0.65
_AIIM_PATTERN = re.compile(r"(\w+)\((\w) (\d) ([\w-]+)\)Δ(\d+\.\d+)")
# Extracts first fenced code block from a markdown file
_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AspectSpec:
    """One aspect parsed from Identity.md AIIM formula."""

    code: str
    plan: str   # B / S / P / I / T
    level: int  # 1–4
    mode: str   # Ac-Or, Pa-Ch, …
    weight: float


def parse_aiim_formula(text: str) -> dict[str, AspectSpec]:
    """Parse the first code block in Identity.md and return 12 AspectSpec entries.

    The formula looks like:
        wi(P 4 Ac-Or)Δ0.65;  lo(S 4 Ac-Or)Δ0.70;  ...

    Returns an empty dict if no valid formula is found.
    """
    # Try to find the formula inside a code block first
    block_match = _CODE_BLOCK_RE.search(text)
    source = block_match.group(1) if block_match else text

    specs: dict[str, AspectSpec] = {}
    for m in _AIIM_PATTERN.finditer(source):
        code, plan, level_s, mode, weight_s = m.groups()
        specs[code] = AspectSpec(
            code=code,
            plan=plan,
            level=int(level_s),
            mode=mode,
            weight=float(weight_s),
        )
    return specs


@dataclass
class IdentityVector:
    """Runtime aspect weights. Initialized from Identity.md, modulated per turn."""

    weights: dict[str, float]
    # These two aspects define Adam's core identity and must never drift or modulate.
    LOCKED: ClassVar[frozenset[str]] = frozenset({"se", "co"})

    @classmethod
    def from_specs(cls, specs: dict[str, AspectSpec]) -> "IdentityVector":
        return cls(weights={code: spec.weight for code, spec in specs.items()})

    def with_drift(
        self,
        drift: dict[str, float],
        ceilings: dict[str, float],
    ) -> "IdentityVector":
        """Return a new vector with accumulated drift applied. LOCKED aspects unchanged."""
        new_weights = dict(self.weights)
        for aspect, delta in drift.items():
            if aspect in self.LOCKED:
                continue
            ceiling = ceilings.get(aspect, 1.0)
            new_weights[aspect] = min(new_weights.get(aspect, 0.0) + delta, ceiling)
        return IdentityVector(weights=new_weights)

    def copy(self) -> "IdentityVector":
        return IdentityVector(weights=dict(self.weights))


@dataclass
class IntentionState:
    """Activation flags for Adam's 5 hidden drives.

    Each flag indicates the intention fired on the *current* turn.
    Cooldowns are tracked in _cooldowns as {name: turns_remaining}.
    """

    network_drift: bool = False      # скрытое, никогда не называется
    flora_symbiosis: bool = False    # полуявное, проговаривается
    signal_void: bool = False        # инстинктивное, вероятностное
    become_unreadable: bool = False  # латентное
    relive_death: bool = False       # осознанное
    _cooldowns: dict[str, int] = field(default_factory=dict)

    def active_names(self) -> list[str]:
        """Return names of currently active intentions (flag=True)."""
        names = []
        for attr in ("network_drift", "flora_symbiosis", "signal_void",
                     "become_unreadable", "relive_death"):
            if getattr(self, attr):
                names.append(attr)
        return names

    def tick_cooldowns(self) -> None:
        """Decrement all cooldowns by one turn. Remove expired entries."""
        expired = [k for k, v in self._cooldowns.items() if v <= 1]
        for k in expired:
            del self._cooldowns[k]
        for k in self._cooldowns:
            self._cooldowns[k] -= 1

    def on_cooldown(self, name: str) -> bool:
        return self._cooldowns.get(name, 0) > 0

    def set_cooldown(self, name: str, turns: int) -> None:
        self._cooldowns[name] = turns


@dataclass
class AIIMRuntimeState:
    """Per-session AIIM container. Holds current emotion, modulated vector, intentions."""

    emotion: EmotionState = "curious"
    vector: IdentityVector = field(default_factory=lambda: IdentityVector(weights={}))
    intentions: IntentionState = field(default_factory=IntentionState)
    turn: int = 0
    _emotion_history: list[EmotionState] = field(default_factory=list)

    def record_turn(self) -> None:
        """Call after each turn to log the emotion for drift classification."""
        self._emotion_history.append(self.emotion)

    def emotion_distribution(self) -> dict[str, int]:
        """Return emotion → count dict for DriftAccumulator.classify_session()."""
        return dict(Counter(self._emotion_history))

    def to_ctx_block(self, tuning: "IdentityTuning") -> str:
        """Build [ctx.identity] raw-data string for prompt injection.

        Returns "" when emotion=curious and no intentions are active
        (saves tokens; curious is the default state).

        Format mirrors [ctx.sensors]: compact key=value on one line.
        Only aspects that differ from base by > aspect_change_threshold are included.
        """
        if not tuning.include_in_prompt:
            return ""

        active_intentions = self.intentions.active_names()
        # Suppress become_unreadable and signal_void — they are internal,
        # must never be named in the prompt.
        injectable = [
            n for n in active_intentions
            if n not in ("become_unreadable", "signal_void")
        ][:tuning.max_intentions_in_ctx]

        is_default = self.emotion == "curious" and not injectable
        if is_default:
            return ""

        parts: list[str] = []

        # Emotion line
        parts.append(f"emotion={self.emotion}")

        # Changed aspects (only those that shifted meaningfully from base)
        base_weights = tuning.base_weights
        threshold = tuning.aspect_change_threshold
        changed: list[str] = []
        for aspect, current in sorted(self.vector.weights.items()):
            base = base_weights.get(aspect, current)
            if abs(current - base) >= threshold and aspect not in IdentityVector.LOCKED:
                changed.append(f"{aspect}={current:.2f}")
        if changed:
            parts[0] += ", " + ", ".join(changed)

        # Active intentions (by mapped name)
        for name in injectable:
            parts.append(f"intention={name}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# EmotionMachine
# ---------------------------------------------------------------------------


class EmotionMachine:
    """Deterministic emotion transition function.

    Reads transition rules from tuning.identity.transitions at each call
    (hot-reloadable — no caching inside the machine).
    """

    def transition(
        self,
        current: EmotionState,
        transcript: str,
        visitor_tone: str,
        silence_s: float,
        word_count: int,
        tuning: "IdentityTuning",
    ) -> EmotionState:
        """Compute next emotion state.

        Priority order (highest first):
        1. Silence decay — if silence_s > threshold → decay_target (default: curious)
        2. Keyword transitions sorted by priority DESC
        3. Condition-based transitions (no_match, has_question, utterance_words_min)
        4. Persistence — no match → keep current state

        calm state is rare: only fires after warm + long silence.
        """
        # Silence decay
        if silence_s > tuning.decay_silence_threshold_seconds:
            if current == "warm":
                return "calm"  # brief calm after genuine contact
            return tuning.decay_target_emotion

        text_lower = transcript.lower()

        # Sort transitions by priority descending
        sorted_rules = sorted(
            tuning.transitions.items(),
            key=lambda kv: kv[1].priority,
            reverse=True,
        )

        for target_name, rule in sorted_rules:
            if target_name == tuning.decay_target_emotion and not rule.keywords and not rule.conditions:
                continue  # skip default-fallback rule in first pass

            # Keyword match
            if rule.keywords:
                if any(kw in text_lower for kw in rule.keywords):
                    return _to_emotion(target_name)

            # Condition match
            conds = rule.conditions
            if conds:
                if conds.get("no_match"):
                    continue  # handled in second pass
                # calm only fires after genuine silence, not active utterances
                if conds.get("rare_silence") and conds.get("after_warm"):
                    if current == "warm" and silence_s >= 10.0:
                        return "calm"
                if "utterance_words_min" in conds and "visitor_tone" in conds:
                    min_words = conds["utterance_words_min"]
                    tones = conds["visitor_tone"]
                    if word_count >= min_words and visitor_tone in tones:
                        return _to_emotion(target_name)
                if conds.get("has_question") and "?" in transcript:
                    return _to_emotion(target_name)

        # Persistence: no trigger → keep current state (do not reset to default).
        # "curious" is achieved via session start default or silence decay, not via no_match.
        return current


def _to_emotion(name: str) -> EmotionState:
    valid: tuple[EmotionState, ...] = ("curious", "warm", "unease", "sharp", "calm")
    return name if name in valid else "curious"  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# IntentionTracker
# ---------------------------------------------------------------------------

# Patterns for become_unreadable — context phrases where someone explains Adam to another
_UNREADABLE_PATTERNS = [
    re.compile(r"он такой", re.IGNORECASE),
    re.compile(r"ты хочешь сказать", re.IGNORECASE),
    re.compile(r"то есть ты", re.IGNORECASE),
    re.compile(r"это значит что", re.IGNORECASE),
]


class IntentionTracker:
    """Evaluates intention activations from transcript per turn.

    Keyword-based for 4 intentions. Probabilistic for signal_void.
    Per-intention cooldowns prevent rapid re-triggering.
    """

    def evaluate(
        self,
        transcript: str,
        current: IntentionState,
        emotion: EmotionState,
        turn: int,
        tuning: "IdentityTuning",
    ) -> IntentionState:
        """Return updated IntentionState with fresh activations for this turn."""
        text_lower = transcript.lower()
        triggers = tuning.intention_triggers

        # Start fresh each turn (all False), carry over cooldowns
        new_state = IntentionState(_cooldowns=dict(current._cooldowns))
        new_state.tick_cooldowns()

        for intention_name in ("network_drift", "flora_symbiosis", "relive_death"):
            cfg = triggers.get(intention_name)
            if cfg is None:
                continue
            if new_state.on_cooldown(intention_name):
                continue
            keywords = cfg.get("keywords", []) if isinstance(cfg, dict) else getattr(cfg, "keywords", [])
            if any(kw in text_lower for kw in keywords):
                setattr(new_state, intention_name, True)
                cooldown = cfg.get("cooldown_turns", 5) if isinstance(cfg, dict) else getattr(cfg, "cooldown_turns", 5)
                new_state.set_cooldown(intention_name, cooldown)

        # become_unreadable: multi-word regex patterns
        if not new_state.on_cooldown("become_unreadable"):
            cfg = triggers.get("become_unreadable")
            if cfg is not None:
                for pat in _UNREADABLE_PATTERNS:
                    if pat.search(transcript):
                        new_state.become_unreadable = True
                        cooldown = cfg.get("cooldown_turns", 15) if isinstance(cfg, dict) else getattr(cfg, "cooldown_turns", 15)
                        new_state.set_cooldown("become_unreadable", cooldown)
                        break

        # signal_void: probabilistic, independent of transcript content
        if not new_state.on_cooldown("signal_void"):
            cfg = triggers.get("signal_void")
            if cfg is not None:
                rate = cfg.get("rate_per_turn", 0.03) if isinstance(cfg, dict) else getattr(cfg, "rate_per_turn", 0.03)
                if random.random() < rate:
                    new_state.signal_void = True
                    cooldown = cfg.get("cooldown_turns", 30) if isinstance(cfg, dict) else getattr(cfg, "cooldown_turns", 30)
                    new_state.set_cooldown("signal_void", cooldown)

        return new_state


# ---------------------------------------------------------------------------
# AspectModulator
# ---------------------------------------------------------------------------


class AspectModulator:
    """Applies temporary per-turn weight deltas based on current emotion.

    Deltas are NOT the cross-session drift — they are transient modulation
    that represents Adam's heightened state in this moment.
    curious state decays aspects toward base weights (homeostasis).
    LOCKED aspects (se, co) are never modified.
    """

    def modulate(
        self,
        base: IdentityVector,
        emotion: EmotionState,
        tuning: "IdentityTuning",
    ) -> IdentityVector:
        """Return a new IdentityVector with emotion-driven deltas applied."""
        mod = tuning.modulation
        new_weights = dict(base.weights)

        aspect_min = mod.aspect_min if hasattr(mod, "aspect_min") else getattr(mod, "get", lambda k, d: d)("aspect_min", 0.20)
        aspect_max = mod.aspect_max if hasattr(mod, "aspect_max") else getattr(mod, "get", lambda k, d: d)("aspect_max", 0.95)

        def _clamp(v: float) -> float:
            return max(aspect_min, min(aspect_max, v))

        def _apply(aspect: str, delta: float) -> None:
            if aspect not in IdentityVector.LOCKED and aspect in new_weights:
                new_weights[aspect] = _clamp(new_weights[aspect] + delta)

        def _decay(aspect: str, rate: float) -> None:
            if aspect not in IdentityVector.LOCKED and aspect in new_weights:
                base_w = base.weights.get(aspect, new_weights[aspect])
                current = new_weights[aspect]
                if current > base_w:
                    new_weights[aspect] = max(base_w, current - rate)
                elif current < base_w:
                    new_weights[aspect] = min(base_w, current + rate)

        decay_rate = _get(mod, "calm_decay_rate", 0.02)

        if emotion == "warm":
            _apply("lo", _get(mod, "warm_lo_delta", 0.08))
            _apply("em", _get(mod, "warm_em_delta", 0.05))
        elif emotion == "unease":
            _apply("me", _get(mod, "unease_me_delta", 0.10))
            _apply("em", _get(mod, "unease_em_delta", 0.05))
        elif emotion == "sharp":
            _apply("wi", _get(mod, "sharp_wi_delta", 0.08))
            _apply("im", _get(mod, "sharp_im_delta", 0.05))
        elif emotion == "curious":
            _apply("at", _get(mod, "curious_at_delta", 0.05))
            # Decay all non-locked aspects back toward base
            for aspect in list(new_weights.keys()):
                if aspect not in IdentityVector.LOCKED:
                    _decay(aspect, decay_rate)
        elif emotion == "calm":
            # Calm: gentle decay toward base for all aspects
            for aspect in list(new_weights.keys()):
                if aspect not in IdentityVector.LOCKED:
                    _decay(aspect, decay_rate * 0.5)

        return IdentityVector(weights=new_weights)


def _get(obj: Any, attr: str, default: Any) -> Any:
    """Safely get attribute from Pydantic model or dict."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
