from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional


# Tag-style markers for internal context. Deliberately non-narrative so the model
# does not parrot them as a speech pattern (см. инцидент 2026-05-14: модель
# зеркалила "Что я вижу:" / "Что я ощущаю:" в каждом ответе).
_CTX_HEADER = (
    "[INTERNAL_CONTEXT — служебные данные, НЕ ОЗВУЧИВАТЬ, НЕ ЦИТИРОВАТЬ.\n"
    "Используй для понимания мира. Никогда не начинай ответ с тегов или их содержимого.]"
)

# Vision-header / sensors-header / generic noise patterns. Splitting them lets
# the state machine know which block we are entering when we see one.
_VISION_HEADER_RE = re.compile(r"^\s*что\s+я\s+вижу\s*[:—\-–]", re.IGNORECASE)
_SENSORS_HEADER_RE = re.compile(r"^\s*что\s+я\s+ощущаю\s*[:—\-–]", re.IGNORECASE)
_OTHER_NOISE_PATTERNS = [
    re.compile(r"^\s*визуальн\w+\s+канал\b", re.IGNORECASE),
    re.compile(r"^\s*сенсорн\w+\s+канал\b", re.IGNORECASE),
    re.compile(r"^\s*сенсоры?\s+молч\w+", re.IGNORECASE),
    re.compile(r"^\s*мои\s+сенсоры?\b", re.IGNORECASE),
    re.compile(r"^\s*канал\s+зрени[ея]\b", re.IGNORECASE),
]


def _is_vision_header(s: str) -> bool:
    return bool(s and _VISION_HEADER_RE.search(s))


def _is_sensors_header(s: str) -> bool:
    return bool(s and _SENSORS_HEADER_RE.search(s))


def _is_other_noise(s: str) -> bool:
    if not s:
        return False
    return any(p.search(s) for p in _OTHER_NOISE_PATTERNS)


def is_leading_noise(sentence: str) -> bool:
    """True if sentence is a leaked system-context echo (vision/sensors header)."""
    if not sentence or not sentence.strip():
        return False
    return _is_vision_header(sentence) or _is_sensors_header(sentence) or _is_other_noise(sentence)


class LeadingNoiseFilter:
    """Stateful filter for streaming sentences.

    Detects and strips the LLM's "system-info report preamble" that sometimes
    leaks into the start of a reply. The preamble has a recurring structure:

        Что я вижу: ... [N continuation sentences] ...
        Что я ощущаю: ... [continuation] ...
        <real answer>

    The state machine:
      init      - no noise seen yet; pass through.
      in_vision - inside vision block; drop everything until we see a
                  sensors header (→ in_sensors) or budget exhausted (→ content).
      in_sensors - inside sensors block; drop one block sentence, then the
                   first non-noise sentence becomes content.
      content   - everything passes through.

    Budgets prevent infinite dropping if the model never emits a sensors
    header — after MAX_VISION_DROP sentences in a vision block we treat the
    next non-noise sentence as content.
    """

    MAX_VISION_DROP = 6
    MAX_SENSORS_DROP = 4

    def __init__(self) -> None:
        self._state = "init"
        self._vision_dropped = 0
        self._sensors_dropped = 0
        self._dropped: list[str] = []

    def accept(self, sentence: str) -> Optional[str]:
        s = sentence.strip() if sentence else ""
        if not s:
            return None
        if self._state == "content":
            return sentence

        # Headers always switch state and drop, regardless of current state.
        if _is_vision_header(s):
            self._state = "in_vision"
            self._vision_dropped = 1
            self._dropped.append(sentence)
            return None
        if _is_sensors_header(s):
            self._state = "in_sensors"
            self._sensors_dropped = 1
            self._dropped.append(sentence)
            return None
        if _is_other_noise(s) and self._state != "content":
            self._dropped.append(sentence)
            return None

        # Non-noise sentence: behaviour depends on state.
        if self._state == "in_vision":
            if self._vision_dropped < self.MAX_VISION_DROP:
                self._vision_dropped += 1
                self._dropped.append(sentence)
                return None
            self._state = "content"
            return sentence
        if self._state == "in_sensors":
            # First non-noise after sensors block IS the real answer.
            self._state = "content"
            return sentence
        # state == "init"
        self._state = "content"
        return sentence

    @property
    def dropped(self) -> list[str]:
        return list(self._dropped)


def sanitize_reply(text: str) -> tuple[str, list[str]]:
    """Strip leading system-info echo lines from a full reply.

    Returns (cleaned_text, dropped_sentences). Splits on sentence boundaries
    and feeds through LeadingNoiseFilter. Stable: idempotent if applied twice.
    """
    if not text:
        return text, []
    # Mild split: keep punctuation with each chunk.
    pieces = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    f = LeadingNoiseFilter()
    kept: list[str] = []
    for p in pieces:
        out = f.accept(p)
        if out is not None:
            kept.append(out)
    cleaned = " ".join(s.strip() for s in kept if s.strip())
    # If nothing survived (rare; model emitted ONLY system-info), fall back to
    # raw text minus the first sentence's leading prefix, so we still speak
    # *something* instead of nothing. The action layer can still parse it.
    if not cleaned:
        return text.strip(), f.dropped
    return cleaned, f.dropped


class PromptBuilder:
    def __init__(self, persona_paths: list[Path], history_turns: int = 8) -> None:
        self.persona_paths = persona_paths
        self.history_turns = history_turns
        # Persona cache: (mtime_sum, text). Reloaded only when files change on disk.
        self._persona_cache: tuple[float, str] = (0.0, "")

    def build_messages(
        self,
        transcript: str,
        dialogue_history: list[dict[str, Any]],
        scene_cache: str,
        sensors: dict[str, Any] | None = None,
        *,
        semantic_text: str = "",
        recent_episodic: list[str] | None = None,
        recent_scenes: list[str] | None = None,
        echo_hint: Optional[str] = None,
        history_turns: Optional[int] = None,
        include_scene: bool = True,
        include_sensors: bool = True,
        response_word_target: Optional[int] = None,
    ) -> list[dict[str, str]]:
        persona = self._load_persona()
        # Apply word-count substitution here so tuning can override the target.
        system = _with_word_target(persona, response_word_target)

        # Dynamic per-turn context goes into a SECOND system message with
        # tag-style markers — the model is far less likely to echo "[ctx.vision]"
        # than the natural-language "Что я вижу:". This separates "what the model
        # knows" from "what the user said".
        ctx_body = self._build_context_body(
            sensors=sensors or {},
            semantic_text=semantic_text,
            recent_episodic=recent_episodic or [],
            recent_scenes=recent_scenes or [],
            scene_cache=scene_cache,
            include_scene=include_scene,
            include_sensors=include_sensors,
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if ctx_body:
            messages.append({"role": "system", "content": f"{_CTX_HEADER}\n{ctx_body}"})

        turns_limit = history_turns if history_turns is not None else self.history_turns
        for turn in dialogue_history[-turns_limit:]:
            role = "assistant" if turn.get("speaker") == "adam" else "user"
            messages.append({"role": role, "content": str(turn.get("text", ""))})

        # User message is just the transcript. Echo hint (if any) is kept here
        # because it is a per-turn nudge tied directly to *this* utterance, not
        # background context — but we wrap it in a neutral marker so it does
        # not look like dialogue from the user.
        if echo_hint and echo_hint.strip():
            user_content = f"[hint] {echo_hint.strip()}\n\n{transcript}"
        else:
            user_content = transcript
        messages.append({"role": "user", "content": user_content})
        return messages

    @staticmethod
    def _build_context_body(
        *,
        sensors: dict[str, Any],
        semantic_text: str,
        recent_episodic: list[str],
        recent_scenes: list[str],
        scene_cache: str,
        include_scene: bool,
        include_sensors: bool,
    ) -> str:
        parts: list[str] = []

        if semantic_text.strip():
            parts.append(f"[ctx.memory]\n{semantic_text.strip()}")

        recent = [s.strip() for s in recent_episodic if s and s.strip()]
        if recent:
            parts.append("[ctx.recent_visitors]\n" + "; ".join(recent))

        if include_scene:
            scenes = [s for s in recent_scenes if s]
            # Deduplicate consecutive identical descriptions (static scene protection).
            deduped: list[str] = []
            for s in scenes:
                if not deduped or s != deduped[-1]:
                    deduped.append(s)
            scenes = deduped
            if len(scenes) > 1:
                numbered = "\n".join(f"  [{i + 1}] {s}" for i, s in enumerate(scenes))
                parts.append(f"[ctx.vision]\n{numbered}")
            else:
                latest = scenes[0] if scenes else scene_cache
                parts.append(f"[ctx.vision]\n{latest or '(visual channel offline)'}")

        if include_sensors:
            if sensors:
                joined = ", ".join(f"{k}={v}" for k, v in sorted(sensors.items()))
                parts.append(f"[ctx.sensors]\n{joined}")
            else:
                parts.append("[ctx.sensors]\n(sensors offline)")

        return "\n\n".join(parts)

    def _load_persona(self) -> str:
        # Compute combined mtime so we reload only when a persona file actually changes.
        mtime_sum = sum(
            p.stat().st_mtime for p in self.persona_paths if p.exists()
        )
        if mtime_sum == self._persona_cache[0]:
            return self._persona_cache[1]
        chunks: list[str] = []
        for path in self.persona_paths:
            if path.exists() and path.stat().st_size > 0:
                chunks.append(path.read_text(encoding="utf-8").strip())
        text = "\n\n".join(chunks) if chunks else ""
        self._persona_cache = (mtime_sum, text)
        return text


def _with_word_target(base: str, target: Optional[int]) -> str:
    """Подменяем число '~30 слов' если задан другой target из tuning."""
    if not target or target == 30:
        return base
    return base.replace("~30 слов", f"~{target} слов")
