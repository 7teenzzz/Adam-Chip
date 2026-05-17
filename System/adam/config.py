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
        "name": "Адам Чип",
        "language": "ru-RU",
        "mode": "maintenance",
        "data_dir": "data/adam",
        "persona_paths": [
            "Agent Adam Chip/About/System.md",
            "Agent Adam Chip/About/Identity.md",
            "Agent Adam Chip/About/Lore.md",
            "Agent Adam Chip/About/Abilities.md",
        ],
        "history_turns": 2,
        "prompt_trace_max": 50,
    },
    "power": {
        "required_mode_name": "MAXN",
        "required_mode_id": 0,
        "require_jetson_clocks": True,
        "enforce_in_exhibition": True,
    },
    "media": {
        "video": {
            "primary": "esp_mjpeg",
            "gstreamer_pipeline": (
                "v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1 ! jpegdec ! "
                "videoconvert ! video/x-raw,format=RGB ! appsink name=adam_frames "
                "drop=true max-buffers=1 sync=false"
            ),
            "remote_rtsp_url": "",
            "preview_enabled": True,
            "esp_mjpeg_url": "http://192.168.0.171:81/stream",
            "esp_fail_threshold": 3,
            "esp_retry_interval_sec": 30.0,
            "video_device": "/dev/video0",
            "camera_width": 640,
            "camera_height": 480,
            "camera_quality": 75,
            "camera_capture_interval_sec": 0.5,
        },
        "audio": {
            "input_device": "pulse",
            "output_device": "default",
            "sample_rate": 16000,
            "channels": 1,
            "frame_ms": 20,
            "vad_threshold": 650,
            "min_speech_ms": 200,
            "max_segment_ms": 9000,
            "mic_source": "esp32",
            "esp32_mic_profile": "inmp441_philips32_stereo",
            "esp_mic_fail_threshold": 3,
            "esp_mic_retry_interval_sec": 10.0,
            "esp_health": {
                "poll_interval_s": 60,
                "silence_threshold": 24,
                "ratio_threshold": 6.0,
                "clip_burst_threshold": 20,
                "restore_threshold_polls": 5,
            },
            "webrtc_vad_aggressiveness": 2,
            "max_command_segment_ms": 15000,
            "normalize_factor": 8000,
        },
        "scene_worker_enabled": True,
        "scene_interval_sec": 4,
        "scene_stale_after_sec": 8,
        "scene_buffer_maxlen": 8,
        "scene_context_count": 1,
    },
    "services": {
        "llm": {
            "provider": "openai",
            "base_url": "http://127.0.0.1:8081/v1",
            "model": "gemma-4-E4B-it-UD-Q4_K_XL",
            "timeout_sec": 60,
            "temperature": 0.7,
            "max_tokens": 40,
            "num_ctx": 8192,
        },
        "vlm": {
            "base_url": "http://127.0.0.1:8084",
            "model": "Efficient-Large-Model/VILA1.5-3b",
            "timeout_sec": 20,
            "max_new_tokens": 48,
            "prompt": "Describe the scene in one brief sentence: people, movements, notable objects. No Chinese characters.",
        },
        "asr": {
            "provider": "whisperx",
            "base_url": "http://127.0.0.1:8095",
            "model": "small",
            "language": "ru",
            "command_endpointing_ms": 1500,
            "reply_window_sec": 3.75,
            "reply_silence_timeout_sec": 4.0,
            "endpointing_debounce_frames": 5,
            "endpointing_voiced_debounce_frames": 3,
            "sample_rate": 16000,
            "timeout_sec": 30,
            "wake_words": "адам",
            "wake_word_required": True,
            "reply_window_expired_action": "standby",
        },
        "tts": {
            "provider": "silero",
            "base_url": "http://127.0.0.1:8082",
            "model": "v5_5_ru",
            "speaker": "eugene",
            "sample_rate": 24000,
            "timeout_sec": 20,
            "available_speakers": ["aidar", "baya", "kseniya", "xenia", "eugene", "random"],
            "output_target": "jetson_hdmi",
            "output_device": "plughw:1,3",
            "filler_enabled": True,
            "filler_phrase": "Хм...",
            "filler_delay_ms": 800,
            "filler_probability": 0.30,
        },
    },
    "mcu": {
        "base_url": "http://192.168.0.171",
        "speaker_url": "http://192.168.0.171:81/speaker",
        "timeout_sec": 1,
        "idle_scene": "boot_idle",
        "allowed_scenes": ["boot_idle", "all_on", "alternating"],
        "channels": {"min": 0, "max": 15, "value_min": 0, "value_max": 4095},
    },
    "sounds": {
        "enabled": True,
        "success_path": "data/sounds/success.wav",
        "local_output_device": "default",
        "esp_boot_note": "ESP boot sound is embedded in ESP firmware and played by ESP after speaker init",
        "error_path": "data/sounds/boot.wav",
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
        "threshold": 0.20,
        "debounce_hits": 2,
        "vad_threshold": 0,
        "wake_silence_timeout_sec": 3,
    },
    "tuning": {
        "memory": {
            "episodic": {
                "enabled": True,
                "salience_threshold": 0.4,
                "decay_days": 14,
                "duration_normalize_seconds": 300,
                "weights": {
                    "introduced_name": 0.3,
                    "duration": 0.2,
                    "themes": 0.15,
                    "tone": 0.15,
                    "echoes_used": 0.1,
                    "new_question": 0.1,
                },
                "highlights_max_per_episode": 6,
                "recurring_min_visits": 2,
                "recurring_lookup_days": 90,
            },
            "semantic": {"enabled": True, "max_chars": 2000},
            "recent_injection": {
                "enabled": True,
                "limit": 2,
                "strategy": "by_name",
                "max_age_days": 30,
            },
            "consolidator": {
                "enabled": True,
                "model": None,
                "window_start": "03:00",
                "window_end": "05:00",
                "max_episodes_per_run": 200,
                "temperature": 0.3,
                "max_runtime_minutes": 30,
                "retry_on_invalid_patch": False,
                "gate_log_max_days": 30,
                "instant_threshold": 0.75,
            },
            "theme_clusters": {},
        },
        "echoes": {
            "enabled": False,
            "global_cooldown_turns": 12,
            "per_echo_cooldown_days": 7,
            "match_threshold": 0.55,
            "weight_multiplier": 1.0,
            "matcher_type": "tag",
            "score_boost": 0.2,
            "tag_short_cutoff": 3,
            "default_entry_weight": 0.5,
        },
        "chinese": {
            "enabled": False,
            "global_cooldown_turns": 30,
            "per_echo_cooldown_days": 7,
            "match_threshold": 0.65,
            "weight_multiplier": 1.0,
            "matcher_type": "tag",
            "score_boost": 0.2,
            "tag_short_cutoff": 3,
            "default_entry_weight": 0.5,
            "audio_mode": "prerendered_with_text_fallback",
        },
        "session": {
            "end_strategy": "combined",
            "vad_silence_seconds": 60,
            "face_lost_seconds": 15,
            "grace_message": "вы там?",
        },
        "scene_director": {
            "enabled": True,
            "sustain_seconds": 8,
            "cooldown_between_changes_seconds": 5,
            "hysteresis_seconds": 15,
            "override_priority_scenes": ["unease"],
        },
        "llm": {
            "temperature": 0.7,
            "max_tokens": 100,
            "response_word_target": 14,
        },
        "voice": {
            "speaker": "eugene",
            "speed_multiplier": 1.1,
            "volume": 0.5,
        },
        "prompt": {
            "history_turns": 4,
            "include_scene": True,
            "include_sensors": True,
        },
        "diagnostics": {
            "log_level": "info",
            "metrics_enabled": True,
            "trace_prompts": False,
        },
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

        # Only deployment-specific overrides — Config.json is the primary source
        # for all service config (LLM, TTS, ASR, VLM, MCU).
        if value := os.environ.get("ADAM_DATA_DIR"):
            raw["agent"]["data_dir"] = value
        if value := os.environ.get("ADAM_MODE"):
            raw["agent"]["mode"] = value
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
