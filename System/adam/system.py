from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


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
