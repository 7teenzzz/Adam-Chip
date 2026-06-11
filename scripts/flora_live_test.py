#!/usr/bin/env python3
"""Live technoflora preset test — cycles every flora state with a 5s hold.

Usage:
    PYTHONPATH=System .venv/bin/python scripts/flora_live_test.py [--hold 5]

Sends each preset to ESP32 in sequence so you can visually verify the
lighting/vibro behaviour for all states including the new Phase 1 emotion
presets (curious_a/b, calm_a/b).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))

from adam.config import Settings
from adam.device import MCUClient
from adam.flora import FloraController


# Ordered sequence: pipeline states first, then P2 emotion presets.
PRESET_ORDER = [
    ("breathe",     "покой / idle"),
    ("accent",      "детекция / wake-word"),
    ("attentive",   "слушание / listening  [vibro OFF]"),
    ("think_pulse", "раздумье / thinking"),
    ("wake_bloom",  "пробуждение (one-shot)"),
    ("curious_a",   "любопытство A  [P2, intensity≤0.65]"),
    ("curious_b",   "любопытство B  [P2, intensity>0.65]"),
    ("calm_a",      "спокойствие A  [P2]"),
    ("calm_b",      "спокойствие B  [P2]"),
]


async def _poll_channels(mcu: MCUClient) -> list[int] | None:
    """Read current PCA9685 channel values from ESP32 status endpoint."""
    try:
        import json as _json
        from adam.device import _NO_PROXY_OPENER  # type: ignore[attr-defined]
        with _NO_PROXY_OPENER.open(f"{mcu.base_url}/api/status", None, 3) as r:
            data = _json.loads(r.read())
        return data.get("pca9685", {}).get("channels", [None] * 16)
    except Exception:
        return None


async def main(hold_s: float) -> None:
    settings = Settings.load()
    flora_cfg = settings.section("flora")
    mcu_cfg   = settings.section("mcu")

    mcu  = MCUClient(mcu_cfg)
    ctrl = FloraController(flora_cfg, mcu, event_log=None)

    known_states: set[str] = set((flora_cfg.get("states") or {}).keys())
    known_states.update({"breathe", "accent", "attentive", "think_pulse", "wake_bloom", "external"})

    errors = 0
    print(f"\n=== Flora live test  ({hold_s:.0f}s per preset) ===")
    print(f"    ESP32: {mcu.base_url}\n")

    for preset, label in PRESET_ORDER:
        if preset not in known_states:
            print(f"  [SKIP] {preset:15s}  — not in config")
            continue

        print(f"  [{preset:15s}]  {label} ...", end="", flush=True)
        params = ctrl._build_params(preset)
        result = await mcu.set_flora_state(preset, params)
        if result.ok:
            # Sample channels 0.5s after transition to show actual brightness
            await asyncio.sleep(0.5)
            ch = await _poll_channels(mcu)
            if ch:
                light = ch[4:12]  # first 8 light channels
                avg = int(sum(light) / len(light)) if light else 0
                pct = round(avg / 4095 * 100)
                print(f"  ✓  duty≈{avg} ({pct}%)  (holding {hold_s:.0f}s)")
            else:
                print(f"  ✓  (holding {hold_s:.0f}s)")
        else:
            print(f"  ✗  MCU {result.status}: {result.error}")
            errors += 1
        await asyncio.sleep(hold_s - 0.5)

    # Return to breathe
    print("\n  Returning to breathe ...")
    await mcu.set_flora_state("breathe", ctrl._build_params("breathe"))
    print(f"Done.  {'All OK' if errors == 0 else f'{errors} errors'}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flora live preset cycle test")
    parser.add_argument("--hold", type=float, default=5.0, help="Seconds per preset (default 5)")
    args = parser.parse_args()
    asyncio.run(main(args.hold))
