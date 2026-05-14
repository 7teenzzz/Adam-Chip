from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "System" / "Config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "agent": {
        "name": "Adam Chip",
        "language": "ru-RU",
        "mode": "maintenance",
        "data_dir": "data/adam",
        "persona_paths": [
            "Agent Adam Chip/About/System.md",
            "Agent Adam Chip/About/Identity.md",
            "Agent Adam Chip/About/Lore.md",
            "Agent Adam Chip/About/Abilities.md",
        ],
        "history_turns": 8,
    },
    "power": {
        "required_mode_name": "MAXN",
        "required_mode_id": 0,
        "require_jetson_clocks": True,
        "enforce_in_exhibition": True,
    },
    "media": {
        "video": {
            "primary": "jetson_gstreamer",
            "gstreamer_pipeline": (
                "v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1 ! jpegdec ! "
                "videoconvert ! video/x-raw,format=RGB ! appsink name=adam_frames "
                "drop=true max-buffers=1 sync=false"
            ),
            "remote_rtsp_url": "",
            "preview_enabled": False,
            "esp_mjpeg_url": "",
            "esp_fail_threshold": 3,
            "esp_retry_interval_sec": 30.0,
        },
        "audio": {
            "input_device": "pulse",
            "output_device": "default",
            "sample_rate": 16000,
            "channels": 1,
            "frame_ms": 20,
            "vad_threshold": 650,
            "min_speech_ms": 280,
            "max_segment_ms": 9000,
            "mic_source": "local",
            "esp32_mic_profile": "inmp441_philips32_stereo",
            "esp_health": {
                "poll_interval_s": 60,
                "silence_threshold": 24,
                "ratio_threshold": 6.0,
                "clip_burst_threshold": 20,
                "restore_threshold_polls": 5,
            },
        },
        "scene_worker_enabled": True,
        "scene_interval_sec": 8,
        "scene_stale_after_sec": 20,
    },
    "services": {
        "llm": {
            "provider": "openai",
            "base_url": "http://127.0.0.1:8081/v1",
            "model": "gemma-4-E4B-it-UD-Q4_K_XL",
            "timeout_sec": 60,
            "temperature": 0.7,
            "max_tokens": 220,
        },
        "vlm": {
            "base_url": "http://127.0.0.1:8084",
            "model": "Efficient-Large-Model/VILA1.5-3b",
            "timeout_sec": 20,
            "max_new_tokens": 32,
        },
        "asr": {
            "provider": "whisperx",
            "base_url": "http://127.0.0.1:8095",
            "model": "medium",
            "language": "ru",
            "command_endpointing_ms": 1500,
            "reply_window_sec": 6.0,
            "reply_absolute_deadline_sec": 12.0,
            "sample_rate": 16000,
            "timeout_sec": 30,
            "wake_words": "адам",
            "wake_word_required": False,
        },
        "tts": {
            "provider": "silero",
            "base_url": "http://127.0.0.1:8082",
            "model": "v5_5_ru",
            "speaker": "eugene",
            "sample_rate": 48000,
            "timeout_sec": 20,
        },
    },
    "mcu": {
        "base_url": "http://192.168.0.171",
        "speaker_url": "http://192.168.0.171:81/speaker",
        "timeout_sec": 3,
        "idle_scene": "boot_idle",
        "allowed_scenes": ["boot_idle", "all_on", "alternating"],
        "channels": {"min": 0, "max": 15, "value_min": 0, "value_max": 4095},
    },
    "sounds": {
        "enabled": True,
        "success_path": "data/sounds/success.mp3",
        "local_output_device": "default",
        "esp_boot_note": "ESP boot sound is embedded in ESP firmware and played by ESP after speaker init",
    },
    "safety": {
        "motor_default_duration_ms": 900,
        "motor_max_duration_ms": 2500,
        "motor_cooldown_ms": 250,
        "half_duplex_mute": True,
    },
    "wake_word": {
        "engine": "openwakeword",
        "model_path": "data/wake_word/adam.onnx",
        "threshold": 0.5,
        "debounce_hits": 5,
        "vad_threshold": 0.5,
        "wake_silence_timeout_sec": 3.0,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


class Settings:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        config_path = Path(os.environ.get("ADAM_CONFIG", str(path or DEFAULT_CONFIG_PATH)))
        if not config_path.is_absolute():
            config_path = PROJECT_ROOT / config_path
        raw = copy.deepcopy(DEFAULT_CONFIG)
        if config_path.exists() and config_path.stat().st_size > 0:
            with config_path.open("r", encoding="utf-8") as handle:
                raw = _deep_merge(raw, json.load(handle))

        if value := os.environ.get("ADAM_DATA_DIR"):
            raw["agent"]["data_dir"] = value
        if value := os.environ.get("ADAM_MODE"):
            raw["agent"]["mode"] = value
        if value := os.environ.get("ESP_BASE_URL"):
            raw["mcu"]["base_url"] = value
        if value := os.environ.get("ESP_SPEAKER_URL"):
            raw["mcu"]["speaker_url"] = value
        if value := os.environ.get("ADAM_LLM_BASE_URL"):
            raw["services"]["llm"]["base_url"] = value
        if value := os.environ.get("ADAM_LLM_PROVIDER"):
            raw["services"]["llm"]["provider"] = value
        if value := os.environ.get("ADAM_LLM_MODEL"):
            raw["services"]["llm"]["model"] = value
        if value := os.environ.get("ADAM_TTS_BASE_URL"):
            raw["services"]["tts"]["base_url"] = value
        if value := os.environ.get("ADAM_ASR_HOST"):
            raw["services"]["asr"]["host"] = value
        if value := os.environ.get("ADAM_ASR_PORT"):
            raw["services"]["asr"]["port"] = int(value)
        if value := os.environ.get("ADAM_VLM_BASE_URL"):
            raw["services"]["vlm"]["base_url"] = value
        if value := os.environ.get("ADAM_VLM_MODEL"):
            raw["services"]["vlm"]["model"] = value
        if value := os.environ.get("ADAM_VIDEO_DEVICE"):
            raw["media"]["video"]["gstreamer_pipeline"] = str(raw["media"]["video"]["gstreamer_pipeline"]).replace(
                "device=/dev/video0",
                f"device={value}",
            )
        if value := os.environ.get("ADAM_AUDIO_INPUT_DEVICE"):
            raw["media"]["audio"]["input_device"] = value
        if value := os.environ.get("ADAM_AUDIO_OUTPUT_DEVICE"):
            raw["media"]["audio"]["output_device"] = value
            raw["sounds"]["local_output_device"] = value
        if value := os.environ.get("ADAM_SUCCESS_SOUND"):
            raw["sounds"]["success_path"] = value
        if value := os.environ.get("ADAM_SOUNDS_ENABLED"):
            raw["sounds"]["enabled"] = value.strip().lower() not in {"0", "false", "no", "off"}

        return cls(raw)

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})
        return value if isinstance(value, dict) else {}

    @property
    def data_dir(self) -> Path:
        return _resolve_path(str(self.section("agent").get("data_dir", "data/adam")))

    @property
    def persona_paths(self) -> list[Path]:
        paths = self.section("agent").get("persona_paths", [])
        return [_resolve_path(path) for path in paths]

    @property
    def mode(self) -> str:
        return str(self.section("agent").get("mode", "maintenance"))

    def to_public_dict(self) -> dict[str, Any]:
        public = copy.deepcopy(self.raw)
        return public

    def apply_patch(self, section_path: str, patch: dict[str, Any]) -> dict[str, Any]:
        if not section_path:
            raise ValueError("section_path is required")
        keys = [key for key in section_path.split(".") if key]
        if not keys:
            raise ValueError("section_path must reference at least one key")

        cursor: dict[str, Any] = self.raw
        for key in keys:
            existing = cursor.get(key)
            if not isinstance(existing, dict):
                existing = {}
                cursor[key] = existing
            cursor = existing
        merged = _deep_merge(cursor, patch)
        cursor.clear()
        cursor.update(merged)
        return copy.deepcopy(merged)

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(os.environ.get("ADAM_CONFIG", str(path or DEFAULT_CONFIG_PATH)))
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(self.raw, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
        os.replace(tmp, target)
        return target
