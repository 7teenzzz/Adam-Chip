from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal


Mood = Literal["neutral", "curious", "warm", "irritated", "silent"]
ActionKind = Literal["no_action", "scene", "channel"]


@dataclass
class Action:
    kind: ActionKind
    mood: Mood = "neutral"
    scene: str | None = None
    channel: int | None = None
    value: int | None = None
    duration_ms: int = 0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mood": self.mood,
            "scene": self.scene,
            "channel": self.channel,
            "value": self.value,
            "duration_ms": self.duration_ms,
            "reason": self.reason,
        }


class ActionLayer:
    def __init__(self, mcu_config: dict[str, Any], safety_config: dict[str, Any]) -> None:
        self.allowed_scenes = set(mcu_config.get("allowed_scenes", ["boot_idle"]))
        channels = mcu_config.get("channels", {})
        self.channel_min = int(channels.get("min", 0))
        self.channel_max = int(channels.get("max", 15))
        self.value_min = int(channels.get("value_min", 0))
        self.value_max = int(channels.get("value_max", 4095))
        self.default_duration_ms = int(safety_config.get("motor_default_duration_ms", 900))
        self.max_duration_ms = int(safety_config.get("motor_max_duration_ms", 2500))
        self.cooldown_ms = int(safety_config.get("motor_cooldown_ms", 250))
        self._last_action_at = 0.0

    def infer(self, reply_text: str, context: dict[str, Any] | None = None) -> Action:
        text = reply_text.lower()
        context = context or {}
        if not reply_text.strip():
            return Action(kind="no_action", mood="silent", reason="empty_reply")
        if self._cooling_down():
            return Action(kind="no_action", mood="neutral", reason="cooldown")

        if any(word in text for word in ("рад", "интересно", "вижу", "привет")):
            return self.validate({"kind": "scene", "mood": "warm", "scene": "alternating", "reason": "warm_reply"})
        if any(word in text for word in ("нет", "осторож", "не могу", "не стоит")):
            return self.validate({"kind": "scene", "mood": "irritated", "scene": "boot_idle", "reason": "boundary_reply"})

        sensors = context.get("sensors", {})
        if isinstance(sensors, dict) and sensors.get("motion"):
            return self.validate({"kind": "scene", "mood": "curious", "scene": "alternating", "reason": "motion"})

        return Action(kind="no_action", mood="neutral", reason="no_trigger")

    def validate(self, payload: dict[str, Any]) -> Action:
        if self._cooling_down():
            return Action(kind="no_action", mood="neutral", reason="cooldown")

        kind = str(payload.get("kind", "no_action"))
        mood = self._mood(payload.get("mood", "neutral"))
        reason = str(payload.get("reason", ""))
        duration_ms = max(0, min(self.max_duration_ms, int(payload.get("duration_ms", self.default_duration_ms))))

        if kind == "scene":
            scene = str(payload.get("scene", ""))
            if scene not in self.allowed_scenes:
                return Action(kind="no_action", mood=mood, reason=f"scene_not_allowed:{scene}")
            self._mark_action()
            return Action(kind="scene", mood=mood, scene=scene, duration_ms=duration_ms, reason=reason)

        if kind == "channel":
            try:
                channel = int(payload.get("channel"))
                value = int(payload.get("value"))
            except (TypeError, ValueError):
                return Action(kind="no_action", mood=mood, reason="invalid_channel_payload")
            channel = max(self.channel_min, min(self.channel_max, channel))
            value = max(self.value_min, min(self.value_max, value))
            self._mark_action()
            return Action(kind="channel", mood=mood, channel=channel, value=value, duration_ms=duration_ms, reason=reason)

        return Action(kind="no_action", mood=mood, reason=reason or "no_action")

    def _cooling_down(self) -> bool:
        elapsed_ms = (time.monotonic() - self._last_action_at) * 1000
        return elapsed_ms < self.cooldown_ms

    def _mark_action(self) -> None:
        self._last_action_at = time.monotonic()

    @staticmethod
    def _mood(value: Any) -> Mood:
        if value in {"neutral", "curious", "warm", "irritated", "silent"}:
            return value
        return "neutral"
