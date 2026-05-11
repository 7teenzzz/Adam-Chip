from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class PowerStatus:
    ok: bool
    mode_ok: bool
    clocks_ok: bool | None
    mode_text: str
    clocks_text: str
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode_ok": self.mode_ok,
            "clocks_ok": self.clocks_ok,
            "mode_text": self.mode_text,
            "clocks_text": self.clocks_text,
            "errors": self.errors,
        }


def _run(command: list[str], timeout: float = 3.0) -> tuple[int, str]:
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


class PowerGate:
    def __init__(self, config: dict[str, Any]) -> None:
        self.required_name = str(config.get("required_mode_name", "MAXN"))
        self.required_id = int(config.get("required_mode_id", 0))
        self.require_clocks = bool(config.get("require_jetson_clocks", True))

    def check(self) -> PowerStatus:
        errors: list[str] = []
        _, mode_text = _run(["nvpmodel", "-q"])
        mode_ok = self.required_name in mode_text or f"\n{self.required_id}" in mode_text
        if not mode_ok:
            errors.append(f"required nvpmodel {self.required_name}({self.required_id}) is not active")

        clocks_ok: bool | None = None
        clocks_text = ""
        clocks_is_perm_error = False
        if self.require_clocks:
            code, clocks_text = _run(["sudo", "-n", "jetson_clocks", "--show"])
            if code == 0:
                lowered = clocks_text.lower()
                clocks_ok = "error:" not in lowered and "inactive" not in lowered
            else:
                clocks_is_perm_error = "root" in clocks_text.lower() or "permission" in clocks_text.lower()
                if clocks_is_perm_error:
                    clocks_ok = None
                    errors.append("jetson_clocks status requires root (warning only — add sudoers entry for exhibition)")
                else:
                    clocks_ok = False
                    errors.append("jetson_clocks status unavailable")

        clocks_blocking = self.require_clocks and clocks_ok is False
        return PowerStatus(
            ok=mode_ok and not clocks_blocking,
            mode_ok=mode_ok,
            clocks_ok=clocks_ok,
            mode_text=mode_text,
            clocks_text=clocks_text,
            errors=errors,
        )
