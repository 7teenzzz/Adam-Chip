#!/usr/bin/env python3
"""Analyse post-TTS lag source from events.jsonl.

Reads recent turns from data/adam/events.jsonl, extracts mic_lag_diag_chunk
sequences (enable via `tuning.diagnostics.trace_post_tts_lag=true`), and
prints the RMS envelope so we can pinpoint when the audio actually goes
silent after `tts_finished` / `mic_unmuted`.

Interpretation rules
--------------------
Each diag window starts when mic_unmuted fires (origin=post_transcribe).
We emit one event per ~20 ms frame. The RMS column shows audio level.

Expected envelopes by lag source:

  ALSA HDMI buffer drain (~50–300 ms):
    rms HIGH (TTS) for first 100–300 ms, then SHARP drop to silence.
    Cause: aplay exited but HDMI hardware buffer kept playing.

  Room acoustic reverb (~200–800 ms):
    rms moderate (echo) for first 200–800 ms, decay curve.
    Cause: speaker→mic acoustic path with room reflections.

  ESP32 firmware FIFO (~1500–2500 ms):
    rms HIGH for the entire 1500–2500 ms span, then SHARP cliff to silence.
    Cause: ESP32 buffered N seconds of mic audio internally, delivering
    audio captured BEFORE mute_unmute was set on Jetson.

  User speech (real response):
    rms low for first few hundred ms, then ramps up when user starts speaking.
    Cause: user reacting to Adam.

  Mixed (real-world):
    sharp HIGH→cliff with a second voiced bump = ESP32 FIFO drain followed
    by user response.

Usage
-----
    PYTHONPATH=System python3 scripts/diag_lag_source.py [N_LAST_DIAG_WINDOWS]

Output: per-window RMS profile + summary statistics.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def parse_events(path: Path, n_windows: int) -> list[dict]:
    """Walk the events log backwards, collect last N diag windows."""
    windows: list[dict] = []
    current: dict | None = None
    # Read whole file in chunks is fine — for production scale use tac/tail.
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            t = ev.get("type", "")
            p = ev.get("payload", {})
            ts = ev.get("ts", "")
            if t == "mic_lag_diag_started":
                current = {
                    "started_ts": ts,
                    "origin": p.get("origin", ""),
                    "chunks": [],
                }
            elif t == "mic_lag_diag_chunk" and current is not None:
                current["chunks"].append({
                    "offset_ms": p.get("t_offset_ms", 0),
                    "rms": p.get("rms", 0),
                    "muted": p.get("muted", False),
                    "discarded": p.get("discarded", False),
                })
            elif t == "mic_lag_diag_finished" and current is not None:
                current["finished_ts"] = ts
                windows.append(current)
                current = None
                if len(windows) > n_windows * 4:
                    # Keep growing — we want the LAST N. Trim periodically.
                    windows = windows[-n_windows * 2 :]
    return windows[-n_windows:]


def render_window(w: dict, idx: int, total: int) -> None:
    chunks = w["chunks"]
    if not chunks:
        print(f"  window #{idx + 1}/{total}: EMPTY")
        return
    rmss = [c["rms"] for c in chunks]
    rms_max = max(rmss) or 1
    duration_ms = chunks[-1]["offset_ms"] if chunks else 0
    print(
        f"  window #{idx + 1}/{total} "
        f"started={w['started_ts']} "
        f"origin={w['origin']} "
        f"duration={duration_ms} ms "
        f"chunks={len(chunks)} "
        f"max_rms={rms_max}"
    )
    # Print histogram bar per ~100 ms bucket.
    buckets: dict[int, list[int]] = defaultdict(list)
    for c in chunks:
        buckets[c["offset_ms"] // 100].append(c["rms"])
    bar_w = 50
    for bucket_idx in sorted(buckets.keys()):
        avg = sum(buckets[bucket_idx]) / len(buckets[bucket_idx])
        bar_n = max(1, int(avg / rms_max * bar_w)) if avg > 0 else 0
        flag = ""
        # Mark discarded vs queued by majority vote in bucket
        sample = chunks[
            min(len(chunks) - 1,
                next(i for i, c in enumerate(chunks) if c["offset_ms"] // 100 == bucket_idx))
        ]
        if sample["discarded"]:
            flag = "D"  # discarded by post-tts discard window
        elif sample["muted"]:
            flag = "M"  # somehow still muted
        else:
            flag = "Q"  # queued to consumer (will reach VAD)
        bar = "█" * bar_n + "·" * (bar_w - bar_n)
        print(f"    +{bucket_idx*100:>4d}-{bucket_idx*100+99} ms [{flag}] {bar} rms={int(avg):>5d}")
    # Detect cliff: find biggest drop between consecutive 100ms buckets.
    sorted_keys = sorted(buckets.keys())
    if len(sorted_keys) >= 2:
        max_drop = 0
        cliff_at = None
        for i in range(1, len(sorted_keys)):
            prev = sum(buckets[sorted_keys[i - 1]]) / len(buckets[sorted_keys[i - 1]])
            curr = sum(buckets[sorted_keys[i]]) / len(buckets[sorted_keys[i]])
            drop = prev - curr
            if drop > max_drop:
                max_drop = drop
                cliff_at = sorted_keys[i] * 100
        if cliff_at is not None:
            print(
                f"    → biggest drop: -{int(max_drop)} rms at +{cliff_at} ms "
                f"(audio went quiet here)"
            )


def main(argv: list[str]) -> int:
    n_windows = int(argv[1]) if len(argv) > 1 else 5
    log = Path("data/adam/events.jsonl")
    if not log.exists():
        print(f"events.jsonl not found at {log}", file=sys.stderr)
        return 1
    print(f"Reading last {n_windows} mic_lag_diag windows from {log}…")
    windows = parse_events(log, n_windows)
    print(f"Found {len(windows)} window(s).")
    if not windows:
        print()
        print("No data. Enable:")
        print('  curl --noproxy "*" -X PATCH http://127.0.0.1:8080/api/config \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"tuning":{"diagnostics":{"trace_post_tts_lag":true}}}\'')
        print("Then run a few turns and re-run this script.")
        return 0
    print()
    print("Legend: [D]=discarded(post-tts window), [Q]=queued to consumer, [M]=still muted")
    print()
    for i, w in enumerate(windows):
        render_window(w, i, len(windows))
        print()
    print("Interpretation cheatsheet (see file header for details):")
    print("  Cliff at +50-300 ms     → ALSA HDMI buffer drain")
    print("  Cliff at +200-800 ms    → Room acoustic reverb")
    print("  Cliff at +1500-2500 ms  → ESP32 firmware FIFO ← MOST LIKELY ROOT CAUSE")
    print("  Rising envelope, late   → real user speech")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
