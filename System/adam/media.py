from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MediaStatus:
    video_primary: str
    video_ready: bool
    video_device: str
    video_detail: str
    audio_input_ready: bool
    audio_output_ready: bool
    audio_input_device: str
    audio_output_device: str
    audio_detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "video": {
                "primary": self.video_primary,
                "ready": self.video_ready,
                "device": self.video_device,
                "detail": self.video_detail,
            },
            "audio": {
                "input_ready": self.audio_input_ready,
                "output_ready": self.audio_output_ready,
                "input_device": self.audio_input_device,
                "output_device": self.audio_output_device,
                "detail": self.audio_detail,
            },
        }


def _run(command: list[str], timeout: float = 2.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


class MediaHealth:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def check(self) -> MediaStatus:
        video = self.config.get("video", {})
        audio = self.config.get("audio", {})
        video_primary = str(video.get("primary", "jetson_gstreamer"))
        pipeline = str(video.get("gstreamer_pipeline", ""))
        remote_rtsp_url = str(video.get("remote_rtsp_url", ""))
        input_device = str(audio.get("input_device", "default"))
        output_device = str(audio.get("output_device", "default"))

        if video_primary == "remote_rtsp":
            video_ready = bool(remote_rtsp_url)
            video_device = remote_rtsp_url
            video_detail = remote_rtsp_url or "remote_rtsp_url is not configured"
        else:
            device = (
                str(video.get("video_device", "")).strip()
                or self._extract_v4l2_device(pipeline)
                or "/dev/video0"
            )
            video_device = device
            video_ready = Path(device).exists()
            video_detail = f"{device} exists" if video_ready else f"{device} not found"

        arecord = shutil.which("arecord")
        aplay = shutil.which("aplay")
        audio_input_ready = False
        audio_output_ready = False
        audio_details: list[str] = []

        if arecord:
            code, out = _run([arecord, "-l"])
            audio_input_ready = code == 0 and "card" in out.lower()
            if input_device != "default":
                audio_input_ready = audio_input_ready and self._alsa_device_available(out, input_device)
            audio_details.append("arecord ok" if audio_input_ready else out[:300])
        else:
            audio_details.append("arecord not installed")

        if aplay:
            code, out = _run([aplay, "-l"])
            audio_output_ready = code == 0 and "card" in out.lower()
            if output_device != "default":
                audio_output_ready = audio_output_ready and self._alsa_device_available(out, output_device)
            audio_details.append("aplay ok" if audio_output_ready else out[:300])
        else:
            audio_details.append("aplay not installed")

        return MediaStatus(
            video_primary=video_primary,
            video_ready=video_ready,
            video_device=video_device,
            video_detail=video_detail,
            audio_input_ready=audio_input_ready,
            audio_output_ready=audio_output_ready,
            audio_input_device=input_device,
            audio_output_device=output_device,
            audio_detail="; ".join(audio_details),
        )

    @staticmethod
    def _extract_v4l2_device(pipeline: str) -> str | None:
        marker = "device="
        if marker not in pipeline:
            return None
        tail = pipeline.split(marker, 1)[1]
        return tail.split(" ", 1)[0].strip() or None

    @staticmethod
    def _alsa_device_available(device_list: str, device: str) -> bool:
        if device.startswith("/"):
            return os.path.exists(device)
        if device.startswith("hw:"):
            parts = device[3:].split(",", 1)
            if len(parts) != 2:
                return False
            card, dev = parts[0].strip(), parts[1].strip()
            return f"card {card}:" in device_list and f"device {dev}:" in device_list
        return device in device_list
