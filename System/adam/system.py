from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any


# Managed systemd services. Key = short name used in API, value = unit name.
ADAM_SERVICES: dict[str, str] = {
    "llm": "adam-llm.service",
    "tts": "adam-tts-silero.service",
    "asr": "adam-asr-whisper.service",
}


@dataclass
class CommandStatus:
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "detail": self.detail}


def docker_health() -> CommandStatus:
    docker = shutil.which("docker")
    if docker is None:
        return CommandStatus(False, "docker not installed")
    try:
        proc = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandStatus(False, str(exc))
    detail = proc.stdout.strip()
    return CommandStatus(proc.returncode == 0, detail or "docker info returned no version")


def _systemctl(*args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )


def service_status(unit: str) -> dict[str, Any]:
    """Return {active, enabled, detail} for a systemd unit."""
    try:
        active_proc = _systemctl("is-active", unit)
        active = active_proc.stdout.strip()
        enabled_proc = _systemctl("is-enabled", unit)
        enabled = enabled_proc.stdout.strip()
        return {
            "active": active == "active",
            "state": active,
            "enabled": enabled in ("enabled", "static"),
            "detail": active,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"active": False, "state": "error", "enabled": False, "detail": str(exc)}


def service_action(unit: str, action: str) -> CommandStatus:
    """Start or stop a systemd unit via sudo -n (requires NOPASSWD sudoers)."""
    if action not in ("start", "stop", "restart"):
        return CommandStatus(False, f"unknown action: {action}")
    try:
        proc = subprocess.run(
            ["sudo", "-n", "systemctl", action, unit],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        detail = proc.stdout.strip() or f"systemctl {action} {unit}"
        return CommandStatus(proc.returncode == 0, detail)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandStatus(False, str(exc))


def all_services_status() -> dict[str, dict[str, Any]]:
    return {name: service_status(unit) for name, unit in ADAM_SERVICES.items()}


def gate_summary(items: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    for key, value in items.items():
        ok = False
        if isinstance(value, dict):
            ok = bool(value.get("ok"))
        else:
            ok = bool(getattr(value, "ok", False))
        if not ok:
            failed.append(key)
    return {"ok": not failed, "failed": failed}
