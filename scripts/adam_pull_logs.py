#!/usr/bin/env python3
"""Pull and display pipeline logs from Adam-Chip orchestrator.

Usage (from Windows dev machine on same LAN as Jetson):

    python scripts/adam_pull_logs.py --url http://192.168.0.X:8080 --last 5
    python scripts/adam_pull_logs.py --url http://192.168.0.X:8080 --follow --stage asr
    python scripts/adam_pull_logs.py --url http://192.168.0.X:8080 --last 3 --out json

Environment variable JETSON_URL overrides the default URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


STAGE_EVENTS: dict[str, list[str]] = {
    "oww":    ["wake_word_detected", "oww_score", "oww_ready"],
    "vad":    ["audio_level", "asr_partial", "mic_muted", "mic_unmuted"],
    "asr":    ["asr_request", "asr_result", "asr_final", "asr_wake_only"],
    "llm":    ["llm_thinking_started", "llm_thinking_finished", "llm_error", "viewer_transcript", "reply_sanitized"],
    "tts":    ["tts_started", "tts_finished"],
    "action": ["adam_reply"],
    "vlm":    ["scene_updated", "scene_stale"],
}

ALL_STAGE_TYPES: set[str] = {t for types in STAGE_EVENTS.values() for t in types}

COL_RESET  = "\033[0m"
COL_BOLD   = "\033[1m"
COL_DIM    = "\033[2m"
COL_GREEN  = "\033[32m"
COL_YELLOW = "\033[33m"
COL_CYAN   = "\033[36m"
COL_RED    = "\033[31m"
COL_BLUE   = "\033[34m"

_use_color = sys.stdout.isatty()


def c(code: str, text: str) -> str:
    return f"{code}{text}{COL_RESET}" if _use_color else text


def _fetch(url: str, timeout: int = 10) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}  ({url})", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Connection error: {exc}\nURL: {url}", file=sys.stderr)
        sys.exit(1)


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.strftime("%H:%M:%S")
    except Exception:
        return ts[:19] if ts else "?"


def _ms(val: Any) -> str:
    if val is None:
        return c(COL_DIM, "  —  ")
    return f"{int(val):>5} ms"


def _event_summary(evt: dict[str, Any], stage: str) -> str:
    t = evt.get("type", "")
    p = evt.get("payload", {})
    parts: list[str] = [c(COL_DIM, t)]
    if t == "asr_result":
        raw = p.get("raw", "")[:60]
        parts.append(f'"{raw}"' if raw else "(empty)")
        if p.get("asr_ms"):
            parts.append(f'{p["asr_ms"]} ms')
    elif t == "asr_final":
        text = p.get("text", "")[:60]
        parts.append(f'"{text}"')
    elif t in ("llm_thinking_started", "llm_thinking_finished"):
        pass
    elif t == "llm_error":
        parts.append(c(COL_RED, p.get("error", "")[:80]))
    elif t == "viewer_transcript":
        text = p.get("text", "")[:60]
        parts.append(f'"{text}"')
        if p.get("visitor_name"):
            parts.append(f'visitor={p["visitor_name"]}')
    elif t == "tts_started":
        text = p.get("text", "")[:40]
        if text and text != "(streaming)":
            parts.append(f'"{text}"')
    elif t == "tts_finished":
        ok = p.get("ok", True)
        parts.append(c(COL_GREEN, "ok") if ok else c(COL_RED, "degraded"))
    elif t == "adam_reply":
        text = p.get("text", "")[:60]
        parts.append(f'"{text}"')
        timings = p.get("timings", {})
        total = timings.get("total_ms")
        if total:
            parts.append(f"total={total} ms")
        action = p.get("action", {}).get("kind", "")
        if action and action != "no_action":
            parts.append(f"action={action}")
    elif t == "scene_updated":
        desc = str(p.get("text", p.get("description", "")))[:60]
        parts.append(f'"{desc}"')
    elif t == "wake_word_detected":
        score = p.get("score")
        if score is not None:
            parts.append(f"score={score:.3f}")
    return "  ".join(parts)


def print_turn(turn: dict[str, Any], stage_filter: str | None) -> None:
    tid = turn.get("turn_id") or "?"
    ts = _fmt_ts(turn.get("ts"))
    transcript = (turn.get("transcript") or "")[:80]
    reply = (turn.get("reply") or "")[:80]
    stages = turn.get("stages", {})
    meta = turn.get("meta", {})
    events = turn.get("events", [])

    header = c(COL_BOLD, f"TURN {tid}") + "  " + c(COL_DIM, ts)
    if meta.get("llm_error"):
        header += "  " + c(COL_RED, "[LLM ERROR]")
    if meta.get("voice_degraded"):
        header += "  " + c(COL_YELLOW, "[voice degraded]")
    print(header)
    print(f"  {c(COL_DIM, 'transcript')} : \"{transcript}\"")
    print(f"  {c(COL_DIM, 'reply')}      : \"{reply}\"")

    show_all = stage_filter in (None, "all")

    def show_stage(name: str, ms_key: str, color: str) -> None:
        if not show_all and stage_filter != name:
            return
        ms = stages.get(ms_key)
        stage_events = [e for e in events if e.get("type") in STAGE_EVENTS.get(name, [])]
        line = f"  {c(color, name.upper()):<25}{_ms(ms)}"
        if stage_events:
            summaries = [_event_summary(e, name) for e in stage_events]
            line += "  " + c(COL_DIM, " | ".join(summaries))
        print(line)

    show_stage("asr",    "asr_ms",   COL_CYAN)
    show_stage("llm",    "llm_ms",   COL_YELLOW)
    show_stage("tts",    "tts_ms",   COL_GREEN)
    show_stage("vlm",    "vlm_ms",   COL_BLUE)
    show_stage("action", "total_ms", COL_DIM)

    if show_all:
        total = stages.get("total_ms")
        ttfv  = stages.get("ttfv_ms")
        print(f"  {c(COL_BOLD, 'TOTAL'):<25}{_ms(total)}  ttfv={ttfv} ms")

    print()


def cmd_turns(base_url: str, args: argparse.Namespace) -> None:
    url = f"{base_url}/api/agent/turns?limit={args.last}"
    data = _fetch(url)
    turns = data.get("turns", [])
    if not turns:
        print("No turns found.")
        return

    if args.out == "json":
        print(json.dumps(turns, ensure_ascii=False, indent=2))
        return

    stage_filter = args.stage if args.stage and args.stage != "all" else None
    for turn in turns:
        print_turn(turn, stage_filter)


def cmd_follow(base_url: str, args: argparse.Namespace) -> None:
    url = f"{base_url}/api/agent/stream"
    stage_filter = args.stage if args.stage and args.stage != "all" else None

    print(f"Following live event stream from {base_url} (Ctrl+C to stop)...")
    print(f"Stage filter: {stage_filter or 'all'}\n")

    try:
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=None) as resp:
            buffer = ""
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    for line in block.splitlines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw:
                            continue
                        try:
                            evt = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        etype = evt.get("type", "")
                        if stage_filter:
                            allowed = STAGE_EVENTS.get(stage_filter, [])
                            if etype not in allowed:
                                continue
                        elif etype not in ALL_STAGE_TYPES:
                            continue
                        ts = _fmt_ts(evt.get("ts"))
                        tid = evt.get("turn_id", "")
                        tid_str = f"[{tid}] " if tid else ""
                        summary = _event_summary(evt, "")
                        print(f"{c(COL_DIM, ts)}  {c(COL_CYAN, tid_str)}{summary}")
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_status(base_url: str) -> None:
    data = _fetch(f"{base_url}/api/agent/status")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    default_url = os.environ.get("JETSON_URL", "http://127.0.0.1:8080")

    parser = argparse.ArgumentParser(
        description="Pull pipeline logs from Adam-Chip orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show last 5 turns (all stages)
  python scripts/adam_pull_logs.py --url http://192.168.0.171:8080 --last 5

  # Show only ASR stage for last 10 turns
  python scripts/adam_pull_logs.py --url http://192.168.0.171:8080 --last 10 --stage asr

  # Follow live stream, show only TTS events
  python scripts/adam_pull_logs.py --url http://192.168.0.171:8080 --follow --stage tts

  # Export last 20 turns as JSON
  python scripts/adam_pull_logs.py --url http://192.168.0.171:8080 --last 20 --out json

Set JETSON_URL env var to avoid repeating --url each time.
""",
    )
    parser.add_argument("--url", default=default_url, help="Orchestrator base URL (default: JETSON_URL env or http://127.0.0.1:8080)")
    parser.add_argument("--last", type=int, default=10, metavar="N", help="Last N turns to show (default: 10)")
    parser.add_argument("--stage", choices=list(STAGE_EVENTS.keys()) + ["all"], default="all", help="Filter output to pipeline stage")
    parser.add_argument("--follow", action="store_true", help="Tail live SSE event stream")
    parser.add_argument("--out", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--status", action="store_true", help="Show agent status and exit")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    if args.status:
        cmd_status(base_url)
        return

    if args.follow:
        cmd_follow(base_url, args)
    else:
        cmd_turns(base_url, args)


if __name__ == "__main__":
    main()
