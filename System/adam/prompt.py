from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


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
        sensor_text = self._format_sensors(sensors or {})
        recent_block = self._format_recent(recent_episodic or [])

        # System prompt is the full persona loaded from files (System.md first).
        # Apply word-count substitution here so tuning can override the target.
        system = _with_word_target(persona, response_word_target)

        # Dynamic per-turn context injected as a prefix to the current user message.
        # Changes every turn (scene, sensors, memory) — kept out of the cached system block.
        ctx_parts: list[str] = []
        if semantic_text.strip():
            ctx_parts.append(f"Что я знаю о посетителях и контексте:\n{semantic_text.strip()}")
        if recent_block:
            ctx_parts.append(recent_block)
        if include_scene:
            scenes = [s for s in (recent_scenes or []) if s]
            if len(scenes) > 1:
                numbered = "\n".join(f"  [{i + 1}] {s}" for i, s in enumerate(scenes))
                ctx_parts.append(f"Что я вижу (от раннего к позднему):\n{numbered}")
            else:
                latest = scenes[0] if scenes else scene_cache
                ctx_parts.append(f"Что я вижу:\n{latest or 'Визуальный канал не отвечает.'}")
        if include_sensors:
            ctx_parts.append(sensor_text)
        if echo_hint:
            ctx_parts.append(echo_hint.strip())

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        turns_limit = history_turns if history_turns is not None else self.history_turns
        for turn in dialogue_history[-turns_limit:]:
            role = "assistant" if turn.get("speaker") == "adam" else "user"
            messages.append({"role": role, "content": str(turn.get("text", ""))})

        ctx_prefix = "\n\n".join(ctx_parts)
        user_content = f"{ctx_prefix}\n\n{transcript}" if ctx_prefix else transcript
        messages.append({"role": "user", "content": user_content})
        return messages

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

    @staticmethod
    def _format_sensors(sensors: dict[str, Any]) -> str:
        if not sensors:
            return "Мои сенсорные органы не отвечают — отключены или сломаны."
        parts = ", ".join(f"{key}={value}" for key, value in sorted(sensors.items()))
        return f"Что я ощущаю: {parts}"

    @staticmethod
    def _format_recent(items: list[str]) -> str:
        items = [s.strip() for s in items if s and s.strip()]
        if not items:
            return ""
        joined = "; ".join(items)
        return f"[прошлые встречи: {joined}]"


def _with_word_target(base: str, target: Optional[int]) -> str:
    """Подменяем число '~30 слов' если задан другой target из tuning."""
    if not target or target == 30:
        return base
    return base.replace("~30 слов", f"~{target} слов")
