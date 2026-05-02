from __future__ import annotations

from pathlib import Path
from typing import Any


BASE_SYSTEM_PROMPT = """Ты Adam Chip, художественный ИИ-агент выставочной инсталляции.
Говори по-русски естественно, коротко и живо. Ты отвечаешь зрителю обычным текстом,
без JSON, markdown-таблиц и служебных команд. Не описывай внутренние инструменты.
Если видишь сцену или сенсоры, используй их как контекст, но не притворяйся человеком."""


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
    ) -> list[dict[str, str]]:
        persona = self._load_persona()
        sensor_text = self._format_sensors(sensors or {})
        system = "\n\n".join(
            part
            for part in [
                BASE_SYSTEM_PROMPT,
                persona,
                f"Долговременная память:\n{memory_summary}",
                f"Текущая сцена:\n{scene_cache or 'Сцена ещё не описана.'}",
                f"Сенсоры:\n{sensor_text}",
            ]
            if part.strip()
        )
        messages = [{"role": "system", "content": system}]
        for turn in dialogue_history[-self.history_turns :]:
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
            return "Персона пока не описана в BIO.md и Abilities.md; держи тон наблюдательного агента инсталляции."
        return "\n\n".join(chunks)

    @staticmethod
    def _format_sensors(sensors: dict[str, Any]) -> str:
        if not sensors:
            return "Нет свежих данных."
        return ", ".join(f"{key}={value}" for key, value in sorted(sensors.items()))
