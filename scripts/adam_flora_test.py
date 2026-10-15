#!/usr/bin/env python3
"""Interactive Flora animation tester.

Sends preset transitions to ESP32 via POST /api/flora/state.
States are re-read from System/Flora.json on every prompt —
new states added to the file appear immediately without restart.

Usage:
    python3 scripts/adam_flora_test.py
    python3 scripts/adam_flora_test.py --host 10.10.10.171
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

# No-proxy opener — v2ray intercepts urllib default opener (see CLAUDE.md)
_NO_PROXY = build_opener(ProxyHandler({}))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FLORA_JSON = PROJECT_ROOT / "System" / "Flora.json"
CONFIG_JSON = PROJECT_ROOT / "System" / "Config.json"


def load_host() -> str:
    try:
        with open(CONFIG_JSON) as f:
            cfg = json.load(f)
        url = cfg.get("mcu", {}).get("base_url", "http://10.10.10.171")
        return url.removeprefix("http://").removeprefix("https://").split("/")[0]
    except Exception:
        return "10.10.10.171"


def load_states() -> list[tuple[str, dict]]:
    with open(FLORA_JSON) as f:
        data = json.load(f)
    return list((data.get("states") or {}).items())


def send_state(host: str, state: str, timeout: float = 3.0) -> tuple[bool, str]:
    url = f"http://{host}/api/flora/state"
    payload = json.dumps({"state": state}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _NO_PROXY.open(req, timeout=timeout) as resp:
            return True, resp.read().decode(errors="replace").strip()
    except urllib.error.URLError as e:
        return False, str(e)


def _param_summary(cfg: dict) -> str:
    parts = []
    if "period_ms" in cfg:
        parts.append(f"period={cfg['period_ms']}ms")
    if "wave_period_ms" in cfg:
        parts.append(f"wave={cfg['wave_period_ms']}ms")
    if "peak_pct" in cfg:
        parts.append(f"peak={cfg['peak_pct']}%")
    if "base_pct" in cfg:
        parts.append(f"base={cfg['base_pct']}%")
    v = cfg.get("vibro")
    if v is True:
        parts.append("vibro")
    elif isinstance(v, str):
        parts.append(f"vibro={v}")
    if cfg.get("settle_to"):
        parts.append(f"→{cfg['settle_to']}")
    return "  " + ", ".join(parts) if parts else ""


def print_menu(states: list[tuple[str, dict]]) -> None:
    width = max(len(n) for n, _ in states)
    print()
    for i, (name, cfg) in enumerate(states, 1):
        summary = _param_summary(cfg)
        print(f"  {i:2d}.  {name:<{width}}{summary}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Flora animation tester (interactive)")
    parser.add_argument("--host", default=None, help="ESP32 host, e.g. 10.10.10.171")
    args = parser.parse_args()

    host = args.host or load_host()
    print(f"\nFlora tester  →  http://{host}/api/flora/state")
    print("Flora.json reloads on every prompt. Ctrl+C to quit.\n")

    while True:
        try:
            states = load_states()
        except Exception as e:
            print(f"[error] Flora.json: {e}")
            time.sleep(1)
            continue

        print_menu(states)

        try:
            raw = input(f"  Choose [1–{len(states)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not raw:
            continue

        if not raw.isdigit():
            print("  Not a number.\n")
            continue

        idx = int(raw) - 1
        if not (0 <= idx < len(states)):
            print(f"  Out of range (1–{len(states)}).\n")
            continue

        name = states[idx][0]
        print(f"  → {name} ...", end="  ", flush=True)
        t0 = time.monotonic()
        ok, body = send_state(host, name)
        ms = (time.monotonic() - t0) * 1000
        if ok:
            print(f"OK  ({ms:.0f}ms)  {body[:100]}")
        else:
            print(f"FAIL  {body}")
        print()


if __name__ == "__main__":
    main()
