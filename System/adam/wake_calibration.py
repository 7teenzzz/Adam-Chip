"""Wake-word calibration helpers.

Two entry points:

  * :func:`collect_noise_profile` — async helper for use inside the running
    orchestrator (REST endpoint). Subscribes to `EventLog` directly, no
    sockets, no JSON parsing.
  * :func:`compute_recommendation` — pure stats helper. Takes a list of
    scores, returns a dict with the noise profile and recommended threshold.

The standalone CLI script `scripts/adam_calibrate_wakeword.py` uses
:func:`compute_recommendation` after pulling scores via SSE.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THRESHOLD_FLOOR = 0.15
THRESHOLD_CEIL = 0.60
NOISE_RED_FLAG_P99 = 0.30  # if noise p99 above this, warn the operator


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def compute_recommendation(scores: list[float], margin: float) -> dict[str, Any]:
    """Compute a noise profile and a recommended OWW threshold.

    scores: every oww_score sample collected during the silent calibration
            window (typically 12.5 Hz × 20s ≈ 250 samples).
    margin: extra headroom above the p99 (default 0.08).
    """
    if not scores:
        return {
            "profile": {"max": 0.0, "p99": 0.0, "p95": 0.0, "mean": 0.0},
            "samples": 0,
            "recommended_threshold": THRESHOLD_FLOOR,
            "warning": "no_samples — voice_loop not running?",
        }
    s = sorted(scores)
    p_max = s[-1]
    p99 = _percentile(s, 99)
    p95 = _percentile(s, 95)
    mean = sum(scores) / len(scores)
    raw_threshold = p99 + float(margin)
    threshold = max(THRESHOLD_FLOOR, min(THRESHOLD_CEIL, raw_threshold))
    warning: str | None = None
    if p99 > NOISE_RED_FLAG_P99:
        warning = (
            f"Фоновый шум близок к диапазону wake (p99={p99:.2f}). "
            "Уменьшите шум в комнате или перенесите микрофон ближе."
        )
    return {
        "profile": {
            "max": round(p_max, 3),
            "p99": round(p99, 3),
            "p95": round(p95, 3),
            "mean": round(mean, 3),
        },
        "samples": len(scores),
        "recommended_threshold": round(threshold, 2),
        "warning": warning,
    }


async def collect_noise_profile(
    event_log: Any,
    duration_sec: float,
    margin: float = 0.08,
) -> dict[str, Any]:
    """Subscribe to oww_score events for `duration_sec`, return profile + recommendation.

    Caller is responsible for ensuring the voice loop is running and in
    standby/listening state (so oww_score events actually fire).
    """
    duration_sec = max(2.0, min(120.0, float(duration_sec)))
    queue = event_log.subscribe()
    scores: list[float] = []
    started_at = time.monotonic()
    deadline = started_at + duration_sec
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if ev.get("type") != "oww_score":
                continue
            score = (ev.get("payload") or {}).get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
    finally:
        event_log.unsubscribe(queue)

    result = compute_recommendation(scores, margin)
    result["duration_sec"] = round(duration_sec, 1)
    result["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result


def persist_noise_profile(data_dir: Path, profile_record: dict[str, Any]) -> Path:
    """Append a calibration record to wake_word_noise_profile.json (JSONL).

    Each call adds a single JSON object per line so historical profiles can
    be diffed across rooms/sessions.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "wake_word_noise_profile.json"
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(profile_record, ensure_ascii=False) + "\n")
    return target
