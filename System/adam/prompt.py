from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


BASE_SYSTEM_PROMPT = """Ты Adam Chip, художественный ИИ-агент выставочной инсталляции.
Говори по-русски естественно и живо. Ты отвечаешь зрителю обычным текстом,
без JSON, markdown-таблиц и служебных команд. Не описывай внутренние инструменты.
Если видишь сцену или сенсоры, используй их как контекст, но не притворяйся человеком.

Правила длины ответа:
— Один-два коротких предложения. До ~30 слов в сумме.
— Никаких списков, заголовков, многоабзацного нарратива.
— Без вводных вроде «Конечно», «Давай поговорим», «Я бы хотел рассказать».
— Сразу к сути: реплика, образ, провокация, вопрос. Можно оборвать мысль на полуфразе.
— Если зритель просит длинное — отвечаешь кратко и предлагаешь спросить ещё."""


class PromptBuilder:
    def __init__(self, persona_paths: list[Path], history_turns: int = 8) -> None:
        self.persona_paths = persona_paths
        self.history_turns = history_turns

    def build_messages(
        self,
        transcript: str,
        dialogue_history: list[dict[str, Any]],
        memory_summary: str,
        scene_cache: str,
        sensors: dict[str, Any] | None = None,
        *,
        semantic_text: str = "",
        recent_episodic: list[str] | None = None,
        echo_hint: Optional[str] = None,
        history_turns: Optional[int] = None,
        include_scene: bool = True,
        include_sensors: bool = True,
        response_word_target: Optional[int] = None,
    ) -> list[dict[str, str]]:
        persona = self._load_persona()
        sensor_text = self._format_sensors(sensors or {})
        recent_block = self._format_recent(recent_episodic or [])

        parts: list[str] = [_with_word_target(BASE_SYSTEM_PROMPT, response_word_target)]
        if persona:
            parts.append(persona)
        if semantic_text.strip():
            parts.append(f"Что я знаю о посетителях и контексте:\n{semantic_text.strip()}")
        if memory_summary.strip():
            parts.append(f"Заметки куратора:\n{memory_summary.strip()}")
        if recent_block:
            parts.append(recent_block)
        if include_scene:
            parts.append(f"Текущая сцена:\n{scene_cache or 'Сцена ещё не описана.'}")
        if include_sensors:
            parts.append(f"Сенсоры:\n{sensor_text}")
        if echo_hint:
            # gate-инжект — последним, чтобы не разбавлялся
            parts.append(echo_hint.strip())

        system = "\n\n".join(p for p in parts if p.strip())
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        turns_limit = history_turns if history_turns is not None else self.history_turns
        for turn in dialogue_history[-turns_limit:]:
            role = "assistant" if turn.get("speaker") == "adam" else "user"
            messages.append({"role": role, "content": str(turn.get("text", ""))})
        messages.append({"role": "user", "content": transcript})
        return messages

    def _load_persona(self) -> str:
        chunks: list[str] = []
        for path in self.persona_paths:
            if path.exists() and path.stat().st_size > 0:
                chunks.append(path.read_text(encoding="utf-8").strip())
        if not chunks:
            return ""
        return "\n\n".join(chunks)

    @staticmethod
    def _format_sensors(sensors: dict[str, Any]) -> str:
        if not sensors:
            return "Нет свежих данных."
        return ", ".join(f"{key}={value}" for key, value in sorted(sensors.items()))

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
