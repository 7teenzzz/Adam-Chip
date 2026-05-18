#!/usr/bin/env python3
"""Phase 8 hang diagnostic: проверка heartbeat-cadence в events.jsonl.

Использование:

    # Анализ последних N минут (snapshot mode)
    python3 scripts/adam_test_reply_hang.py --last-minutes 5

    # Live tail — печатает новые heartbeat events с пометкой OK/WARN/ERROR
    python3 scripts/adam_test_reply_hang.py --follow

    # Кастомный путь к events.jsonl и пороги
    python3 scripts/adam_test_reply_hang.py --events-file /path/to/events.jsonl --error-gap-sec 30

Exit codes:
    0 — OK (heartbeat-cadence в пределах нормы, max gap <= warn-gap-sec)
    1 — ERROR (обнаружен gap >= error-gap-sec, voice_loop вероятно завис)
    2 — events.jsonl не найден или пуст

Скрипт читает только локальный файл — не требует FastAPI/HTTP. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

# Default location for events.jsonl (override via --events-file or $ADAM_EVENTS).
# Matches agent.data_dir in Config.json. CWD-relative for dev; absolute if env set.
_DEFAULT_EVENTS_PATH = Path(
    os.environ.get("ADAM_EVENTS", "data/adam/events.jsonl")
)


def _parse_ts(raw: Any) -> datetime | None:
    """Parse event timestamp; tolerates ISO8601 with 'Z' or numeric epoch."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    if isinstance(raw, str):
        # Normalise trailing Z to +00:00 for fromisoformat.
        s = raw.rstrip("Z")
        if raw.endswith("Z"):
            s = s + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def read_events(path: Path, last_minutes: int | None = None) -> Iterator[dict[str, Any]]:
    """Stream events from JSONL file; optionally filter by recency window."""
    cutoff: datetime | None = None
    if last_minutes is not None and last_minutes > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=last_minutes)
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cutoff is not None:
                ts = _parse_ts(obj.get("ts") or obj.get("timestamp"))
                if ts is not None and ts < cutoff:
                    continue
            yield obj


def analyze_heartbeats(
    events: list[dict[str, Any]],
    warn_gap_sec: float,
    error_gap_sec: float,
) -> dict[str, Any]:
    """Compute gaps between consecutive voice_loop_heartbeat events.

    Returns dict with:
        heartbeats: total count
        max_gap_sec: largest gap observed
        gaps: list of (gap_sec, prev_event, next_event) tuples
        warn_count, error_count: how many gaps crossed each threshold
        last_state_change: most recent voice_state_change before the worst gap
    """
    heartbeats = [e for e in events if e.get("type") == "voice_loop_heartbeat"]
    state_changes = [e for e in events if e.get("type") == "voice_state_change"]

    gaps: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    prev: dict[str, Any] | None = None
    for hb in heartbeats:
        if prev is not None:
            # Prefer payload.uptime_sec (perf_counter relative); fall back to wallclock ts.
            uptime_prev = (prev.get("payload") or {}).get("uptime_sec")
            uptime_next = (hb.get("payload") or {}).get("uptime_sec")
            if isinstance(uptime_prev, (int, float)) and isinstance(uptime_next, (int, float)):
                gap = float(uptime_next) - float(uptime_prev)
            else:
                t1 = _parse_ts(prev.get("ts") or prev.get("timestamp"))
                t2 = _parse_ts(hb.get("ts") or hb.get("timestamp"))
                gap = (t2 - t1).total_seconds() if t1 and t2 else 0.0
            if gap > 0:
                gaps.append((gap, prev, hb))
        prev = hb

    max_gap = max((g for g, _, _ in gaps), default=0.0)
    warn_count = sum(1 for g, _, _ in gaps if g >= warn_gap_sec)
    error_count = sum(1 for g, _, _ in gaps if g >= error_gap_sec)

    last_state_change: dict[str, Any] | None = None
    if gaps and error_count > 0:
        # Find the worst gap and the state_change just before it.
        worst_gap_event = max(gaps, key=lambda g: g[0])[1]
        worst_ts = _parse_ts(worst_gap_event.get("ts") or worst_gap_event.get("timestamp"))
        if worst_ts is not None:
            for sc in reversed(state_changes):
                sc_ts = _parse_ts(sc.get("ts") or sc.get("timestamp"))
                if sc_ts is not None and sc_ts <= worst_ts:
                    last_state_change = sc
                    break

    return {
        "heartbeats": len(heartbeats),
        "state_changes": len(state_changes),
        "max_gap_sec": max_gap,
        "gaps": gaps,
        "warn_count": warn_count,
        "error_count": error_count,
        "last_state_change": last_state_change,
    }


def report(result: dict[str, Any], warn_gap: float, error_gap: float) -> int:
    """Print human-readable report, return exit code."""
    hb = result["heartbeats"]
    if hb == 0:
        print("ERROR: ни одного voice_loop_heartbeat event не найдено.", file=sys.stderr)
        print("       Возможно: оркестратор не работал, или Phase 8 фикс ещё не задеплоен.", file=sys.stderr)
        return 1

    max_gap = result["max_gap_sec"]
    if result["error_count"] > 0:
        print(f"ERROR: gap {max_gap:.1f} sec — voice_loop appears frozen "
              f"(порог ERROR = {error_gap} sec)")
        lsc = result.get("last_state_change")
        if lsc:
            p = lsc.get("payload") or {}
            print(f"       Последний voice_state_change перед gap: "
                  f"{p.get('from')} → {p.get('to')} (reason={p.get('reason')!r})")
        print(f"       Heartbeats: {hb}, state_changes: {result['state_changes']}, "
              f"warn-gaps: {result['warn_count']}, error-gaps: {result['error_count']}")
        return 1
    elif result["warn_count"] > 0:
        print(f"WARN: max gap {max_gap:.1f} sec (норма ≤ {warn_gap} sec); "
              f"транзиентные stalls={result['warn_count']}.")
        print(f"      Heartbeats: {hb}, state_changes: {result['state_changes']}.")
        return 0
    else:
        print(f"OK: {hb} heartbeats, max gap {max_gap:.1f} sec (норма ≤ {warn_gap} sec).")
        return 0


def follow_mode(path: Path, warn_gap: float, error_gap: float) -> int:
    """Live tail: print each new heartbeat with OK/WARN/ERROR label; never exits cleanly (Ctrl+C)."""
    print(f"Follow mode: {path}. Ctrl+C для остановки.")
    if not path.exists():
        print(f"ERROR: {path} не найден.", file=sys.stderr)
        return 2
    prev_uptime: float | None = None
    pos = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            fh.seek(0, 2)  # tail-from-end
            pos = fh.tell()
            while True:
                fh.seek(pos)
                line = fh.readline()
                if not line:
                    time.sleep(2.0)
                    continue
                pos = fh.tell()
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "voice_loop_heartbeat":
                    continue
                p = obj.get("payload") or {}
                uptime = p.get("uptime_sec")
                state = p.get("state")
                if prev_uptime is not None and isinstance(uptime, (int, float)):
                    gap = float(uptime) - prev_uptime
                    label = "OK" if gap < warn_gap else ("WARN" if gap < error_gap else "ERROR")
                    print(f"[{label}] gap={gap:.1f}s state={state} uptime={uptime:.1f}s "
                          f"iter={p.get('iter')}")
                else:
                    print(f"[OK]   first heartbeat state={state} uptime={uptime}")
                if isinstance(uptime, (int, float)):
                    prev_uptime = float(uptime)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Phase 8 hang diagnostic — анализирует voice_loop_heartbeat events.jsonl.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--events-file",
        type=Path,
        default=_DEFAULT_EVENTS_PATH,
        help=f"Путь к events.jsonl (default: {_DEFAULT_EVENTS_PATH}; "
        f"или env ADAM_EVENTS)",
    )
    ap.add_argument(
        "--last-minutes",
        type=int,
        default=5,
        help="Анализировать только последние N минут (default: 5)",
    )
    ap.add_argument(
        "--follow",
        action="store_true",
        help="Live tail — печатать новые heartbeat events с пометками (Ctrl+C для выхода)",
    )
    ap.add_argument(
        "--warn-gap-sec",
        type=float,
        default=6.0,
        help="Gap >= этого = WARN (default: 6.0 — heartbeat-period 5s + 1s slack)",
    )
    ap.add_argument(
        "--error-gap-sec",
        type=float,
        default=30.0,
        help="Gap >= этого = ERROR / loop probably frozen (default: 30.0)",
    )
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = ap.parse_args(argv)

    path: Path = args.events_file
    if not path.exists():
        print(f"ERROR: events file не найден: {path}", file=sys.stderr)
        print("       Проверь agent.data_dir в Config.json или установи ADAM_EVENTS.", file=sys.stderr)
        return 2

    if args.follow:
        return follow_mode(path, args.warn_gap_sec, args.error_gap_sec)

    events = list(read_events(path, last_minutes=args.last_minutes))
    if not events:
        print(f"ERROR: за последние {args.last_minutes} мин нет events в {path}", file=sys.stderr)
        return 2

    result = analyze_heartbeats(events, args.warn_gap_sec, args.error_gap_sec)
    if args.verbose:
        print(f"Total events read: {len(events)}")
        print(f"Heartbeats: {result['heartbeats']}; state_changes: {result['state_changes']}")
    return report(result, args.warn_gap_sec, args.error_gap_sec)


if __name__ == "__main__":
    sys.exit(main())
