from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(path: str, needle: str) -> None:
    text = read_text(path)
    if needle not in text:
        raise AssertionError(f"{path}: missing {needle!r}")


def assert_regex(path: str, pattern: str) -> None:
    text = read_text(path)
    if not re.search(pattern, text):
        raise AssertionError(f"{path}: missing pattern {pattern!r}")


def no_duplicate_keys_object_pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    counts = Counter(key for key, _ in pairs)
    duplicates = [key for key, count in counts.items() if count > 1]
    if duplicates:
        raise AssertionError(f"duplicate JSON keys: {duplicates}")
    return dict(pairs)


def check_no_conflict_markers() -> None:
    for rel in [
        "System/WebUI/static/js/panels/chat.js",
        "System/WebUI/static/js/main.js",
        "System/Config.json",
        "System/Orchestrator.py",
        "System/adam/api_runtime.py",
        "Subsystem/AdamsServer/config/AdamsConfig.h",
        "ToDo.md",
    ]:
        text = read_text(rel)
        for marker in ("<<<<<<<", "=======", ">>>>>>>"):
            if marker in text:
                raise AssertionError(f"{rel}: unresolved merge marker {marker}")


def check_config() -> None:
    config = json.loads(
        read_text("System/Config.json"),
        object_pairs_hook=no_duplicate_keys_object_pairs_hook,
    )

    media = config["media"]
    services = config["services"]

    expected = {
        "media.audio.mic_source": media["audio"]["mic_source"] == "esp32",
        "media.video.esp_mjpeg_url": media["video"]["esp_mjpeg_url"] == "http://192.168.0.171:81/stream",
        "services.asr.model": services["asr"]["model"] == "small",
        "services.tts.sample_rate": services["tts"]["sample_rate"] == 24000,
        "services.tts.filler_enabled": services["tts"]["filler_enabled"] is True,
    }
    failed = [name for name, ok in expected.items() if not ok]
    if failed:
        raise AssertionError(f"unexpected config values: {failed}")


def check_orchestrator() -> None:
    for needle in [
        "_esp_mic_fallback",
        "esp32_mic_fallback_start",
        "esp32_mic_restored",
        "_run_local",
        "_make_stereo_reader",
        "enough_speech",
        "_apply_wav_speed",
        "_prewarm_filler",
        "turn_id",
    ]:
        assert_contains("System/Orchestrator.py", needle)


def check_webui() -> None:
    for needle in [
        "esp32_mic_fallback_start",
        "esp32_mic_restored",
        "SIDE_EVENTS",
    ]:
        assert_contains("System/WebUI/static/js/main.js", needle)

    for needle in [
        "vuCanvas",
        "drawVuMeter",
        "countdownTrack",
        "endpointing_started",
        "cameraSourceLabel",
    ]:
        assert_contains("System/WebUI/static/js/panels/chat.js", needle)


def check_api() -> None:
    assert_contains("System/adam/api_runtime.py", '@router.get("/api/audio/input_devices")')
    assert_contains("System/WebUI/static/js/panels/settings.js", "/api/audio/input_devices")


def check_firmware_config() -> None:
    assert_regex(
        "Subsystem/AdamsServer/config/AdamsConfig.h",
        r"kEthernetStaticIp\[4\]\s*=\s*\{192,\s*168,\s*0,\s*171\}",
    )
    assert_regex(
        "Subsystem/AdamsServer/config/AdamsConfig.h",
        r"kSpeakerRingBufferBytes\s*=\s*32768",
    )


def main() -> None:
    check_no_conflict_markers()
    check_config()
    check_orchestrator()
    check_webui()
    check_api()
    check_firmware_config()
    print("OK esp32 merge verification")


if __name__ == "__main__":
    main()
