from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SoundResult:
    ok: bool
    target: str
    detail: str
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "target": self.target, "detail": self.detail, "error": self.error}


def play_local_sound(path: Path, output_device: str = "default", timeout: float = 20) -> SoundResult:
    if not path.exists():
        return SoundResult(False, "local", str(path), "file_not_found")

    command = _local_playback_command(path, output_device)
    if not command:
        return SoundResult(False, "local", str(path), "no_supported_player_found")

    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SoundResult(False, "local", " ".join(command), str(exc))

    stderr = proc.stderr.decode("utf-8", errors="replace")[-500:]
    return SoundResult(proc.returncode == 0, "local", " ".join(command), None if proc.returncode == 0 else stderr)


def _local_playback_command(path: Path, output_device: str) -> list[str] | None:
    suffix = path.suffix.lower()
    if suffix in {".mp3", ".wav", ".ogg", ".flac"}:
        if player := shutil.which("gst-play-1.0"):
            return [player, "--quiet", str(path)]
    if suffix == ".wav":
        if player := shutil.which("aplay"):
            return [player, "-q", "-D", output_device, str(path)]
        if player := shutil.which("paplay"):
            return [player, str(path)]
    return None
