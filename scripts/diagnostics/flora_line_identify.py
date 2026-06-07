#!/usr/bin/env python3
"""Technoflora line/channel identification helper (Phase 29 calibration).

Walks PCA9685 channels one by one. For each channel it:
  1. announces the channel number out loud via the Silero TTS service
     ("Линия ноль", "Линия один", ...), and
  2. drives ONLY that channel to a steady level and holds it (default 70%
     for 5 s; use --mode breathe for a pulse instead), all others off,

so the operator can watch/feel which physical lamp line (channels 0-10 light,
channels 11-14 vibro motors) corresponds to each logical channel index, and
write down the mapping.

Pure stdlib (urllib + math) — runs on Jetson, macOS, or Windows. No numpy.

ESP HTTP MUST bypass the system proxy: v2ray on the Jetson hijacks localhost/LAN
traffic via http_proxy env vars and leaks half-open sockets to ESP32:81, draining
its 4-slot pool. We therefore use a private ProxyHandler({}) opener (see
System/adam/device.py for the same pattern / CLAUDE.md gotcha).

Usage (from repo root):
    python scripts/diagnostics/flora_line_identify.py                 # channels 0-14
    python scripts/diagnostics/flora_line_identify.py --channels 0-10 # light only
    python scripts/diagnostics/flora_line_identify.py --channels 11-14 --no-tts
    python scripts/diagnostics/flora_line_identify.py --channels 0,3,7 --duration 6

Config (mcu.base_url, services.tts.base_url, channel range, flora.gamma) is read
from System/Config.json by default; override with --base-url / --tts-url.

NOTE: run with the orchestrator's flora controller idle (maintenance mode or the
orchestrator stopped), otherwise it will fight the script for the channels.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import URLError, HTTPError

# --- proxy-free opener (MANDATORY for ESP HTTP — see module docstring) ---------
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))

# --- Russian numerals 0..15 (enough for a 16-channel PCA9685) ------------------
_RU_NUM = [
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять", "одиннадцать", "двенадцать",
    "тринадцать", "четырнадцать", "пятнадцать",
]


def ru_number(n: int) -> str:
    return _RU_NUM[n] if 0 <= n < len(_RU_NUM) else str(n)


# --- config loading ------------------------------------------------------------
def _repo_root() -> str:
    # scripts/diagnostics/this.py -> repo root is two levels up
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_config() -> dict:
    path = os.path.join(_repo_root(), "System", "Config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        print(f"[warn] could not read {path}: {exc} — using built-in defaults")
        return {}


# --- HTTP helpers --------------------------------------------------------------
def _post_json(url: str, payload: dict, timeout: float) -> tuple[bool, str]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with _NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            return True, resp.read().decode("utf-8", "replace")[:200]
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, str(exc)


class Esp:
    def __init__(self, base_url: str, value_max: int, timeout: float) -> None:
        self.base = base_url.rstrip("/")
        self.value_max = value_max
        self.timeout = timeout

    def set_channel(self, ch: int, value: int) -> None:
        value = max(0, min(self.value_max, int(value)))
        ok, info = _post_json(
            f"{self.base}/api/pca9685/channel",
            {"channel": ch, "mode": "pwm", "value": value},
            self.timeout,
        )
        if not ok:
            print(f"[warn] set_channel({ch},{value}) failed: {info}")

    def all_off(self, channels: range | list[int]) -> None:
        updates = [{"channel": c, "mode": "pwm", "value": 0} for c in channels]
        ok, info = _post_json(
            f"{self.base}/api/pca9685/channels", {"updates": updates}, self.timeout
        )
        if not ok:  # fall back to per-channel if batch route is unavailable
            for c in channels:
                self.set_channel(c, 0)


def tts_say(tts_url: str, speaker: str, text: str, timeout: float) -> None:
    ok, info = _post_json(
        f"{tts_url.rstrip('/')}/speak", {"text": text, "speaker": speaker}, timeout
    )
    if not ok:
        print(f"[warn] TTS '{text}' failed: {info} (continuing without audio)")


# --- breathing pulse -----------------------------------------------------------
def breathe_channel(
    esp: Esp,
    ch: int,
    duration_s: float,
    period_s: float,
    fps: float,
    gamma: float,
    peak_frac: float,
) -> None:
    """Drive one channel with a gamma-corrected raised-cosine breath."""
    frame_dt = 1.0 / max(1.0, fps)
    t0 = time.monotonic()
    next_frame = t0
    while True:
        now = time.monotonic()
        elapsed = now - t0
        if elapsed >= duration_s:
            break
        # raised cosine 0..1, full breath every period_s
        level = 0.5 - 0.5 * math.cos(2.0 * math.pi * (elapsed / period_s))
        duty = int(round(esp.value_max * peak_frac * (level ** gamma)))
        esp.set_channel(ch, duty)
        next_frame += frame_dt
        sleep = next_frame - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)
    esp.set_channel(ch, 0)


def hold_channel(
    esp: Esp,
    ch: int,
    duration_s: float,
    level_frac: float,
    gamma: float,
) -> None:
    """Drive one channel to a steady gamma-corrected level and hold it."""
    duty = int(round(esp.value_max * (level_frac ** gamma)))
    esp.set_channel(ch, duty)
    time.sleep(max(0.0, duration_s))
    esp.set_channel(ch, 0)


# --- channel-spec parsing ------------------------------------------------------
def parse_channels(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main(argv: list[str]) -> int:
    cfg = load_config()
    mcu = cfg.get("mcu", {})
    tts = cfg.get("services", {}).get("tts", {})
    flora = cfg.get("flora", {})
    value_max = int(mcu.get("channels", {}).get("value_max", 4095))

    ap = argparse.ArgumentParser(description="Identify technoflora PCA9685 lines.")
    ap.add_argument("--channels", default="0-14",
                    help="channels to walk, e.g. '0-14' or '0,3,7' (default 0-14)")
    ap.add_argument("--base-url", default=mcu.get("base_url", "http://10.10.10.171"),
                    help="ESP32 base URL (default from Config mcu.base_url)")
    ap.add_argument("--tts-url", default=tts.get("base_url", "http://127.0.0.1:8082"),
                    help="TTS service base URL (default from Config services.tts.base_url)")
    ap.add_argument("--speaker", default=tts.get("speaker", "eugene"))
    ap.add_argument("--mode", choices=["hold", "breathe"], default="hold",
                    help="hold = steady level for --duration (default); breathe = pulsing")
    ap.add_argument("--duration", type=float, default=5.0,
                    help="seconds the line stays active per channel (default 5)")
    ap.add_argument("--level", type=float, default=70.0,
                    help="steady brightness %% (gamma-corrected) in hold mode (default 70)")
    ap.add_argument("--period", type=float, default=0.6,
                    help="breath period in seconds for --mode breathe (default 0.6)")
    ap.add_argument("--fps", type=float, default=20.0,
                    help="frame rate of PWM updates (default 20; ESP HTTP ceiling ~15-20)")
    ap.add_argument("--gap", type=float, default=1.0,
                    help="pause in seconds between channels (default 1)")
    ap.add_argument("--peak", type=float, default=100.0,
                    help="peak duty as %% of value_max (default 100)")
    ap.add_argument("--gamma", type=float, default=float(flora.get("gamma", 2.2)))
    ap.add_argument("--esp-timeout", type=float, default=2.0)
    ap.add_argument("--tts-timeout", type=float, default=20.0)
    ap.add_argument("--no-tts", action="store_true", help="skip spoken announcements")
    args = ap.parse_args(argv)

    channels = [c for c in parse_channels(args.channels) if 0 <= c <= 15]
    if not channels:
        print("No valid channels in --channels.")
        return 2

    esp = Esp(args.base_url, value_max, args.esp_timeout)
    peak_frac = max(0.0, min(1.0, args.peak / 100.0))
    level_frac = max(0.0, min(1.0, args.level / 100.0))
    hold_duty = int(round(value_max * (level_frac ** args.gamma)))

    def cleanup(*_a) -> None:
        print("\n[cleanup] all channels off")
        esp.all_off(range(0, 16))
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, cleanup)

    print("=" * 60)
    print("Technoflora line identification")
    print(f"  ESP:      {args.base_url}")
    print(f"  TTS:      {'(disabled)' if args.no_tts else args.tts_url} speaker={args.speaker}")
    print(f"  channels: {channels}")
    if args.mode == "hold":
        print(f"  mode:     HOLD steady {args.level}% (duty {hold_duty}/{value_max}, "
              f"gamma {args.gamma}) for {args.duration}s per line")
    else:
        print(f"  mode:     BREATHE period={args.period}s peak={args.peak}% "
              f"gamma={args.gamma} for {args.duration}s per line")
    print("  channels 0-10 = light (watch lamps), 11-14 = vibro (feel motors)")
    print("  >>> run with the orchestrator's flora controller idle <<<")
    print("=" * 60)

    esp.all_off(range(0, 16))
    time.sleep(0.3)

    for ch in channels:
        word = ru_number(ch)
        print(f"\n--- channel {ch}  ('Линия {word}') ---")
        esp.all_off(range(0, 16))
        if not args.no_tts:
            tts_say(args.tts_url, args.speaker, f"Линия {word}", args.tts_timeout)
            time.sleep(0.3)
        if args.mode == "hold":
            hold_channel(esp, ch, args.duration, level_frac, args.gamma)
        else:
            breathe_channel(esp, ch, args.duration, args.period,
                            args.fps, args.gamma, peak_frac)
        esp.set_channel(ch, 0)
        time.sleep(args.gap)

    esp.all_off(range(0, 16))
    print("\nDone. All channels off. Write down: channel index -> physical line.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
