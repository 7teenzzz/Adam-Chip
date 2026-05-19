#!/usr/bin/env python3
"""Diploma research metrics aggregator.

Reads inference_metrics.jsonl and memory/metrics.jsonl from the Jetson data
directory and prints tables ready for Chapter 3.4 of the diploma.

Usage on Jetson (or via SSH):
    python3 scripts/adam_diploma_metrics.py --data /home/i17jet/Agents/Adam-Chip/data/adam

Usage on Windows dev machine (reads files copied from Jetson):
    python scripts/adam_diploma_metrics.py --data C:/path/to/data/adam

Outputs (all to stdout, --out json for raw JSON):
  1. Latency summary  : ASR / LLM / TTS / total  min/avg/p95/max across all turns
  2. Per-session table: id, turns, duration_s, avg_total_ms, lmrr, ri
  3. LMRR summary     : search_hit events per session vs turn count
  4. RI summary       : average pairwise Jaccard of word bigrams per session
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _parse_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------

def _latency_stats(turns: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("asr_ms", "llm_ms", "tts_ms", "total_ms"):
        vals = [float(t[key]) for t in turns if t.get(key) is not None]
        if not vals:
            out[key] = None
            continue
        sorted_v = sorted(vals)
        p95_idx = max(0, min(len(sorted_v) - 1, int(round(0.95 * (len(sorted_v) - 1)))))
        out[key] = {
            "n":   len(vals),
            "min": round(min(vals)),
            "avg": round(statistics.mean(vals)),
            "p95": round(sorted_v[p95_idx]),
            "max": round(max(vals)),
        }
    return out


# ---------------------------------------------------------------------------
# RI — Repetition Index (avg pairwise Jaccard on word bigrams per session)
# ---------------------------------------------------------------------------

def _bigrams(text: str) -> set[tuple[str, str]]:
    words = text.lower().split()
    if len(words) < 2:
        return set()
    return {(words[i], words[i + 1]) for i in range(len(words) - 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _session_ri(replies: list[str]) -> float:
    """Average pairwise Jaccard of word bigrams across all reply pairs."""
    bgs = [_bigrams(r) for r in replies if r.strip()]
    if len(bgs) < 2:
        return 0.0
    pairs: list[float] = []
    for i in range(len(bgs)):
        for j in range(i + 1, len(bgs)):
            pairs.append(_jaccard(bgs[i], bgs[j]))
    return round(statistics.mean(pairs), 4) if pairs else 0.0


# ---------------------------------------------------------------------------
# Session assembly
# ---------------------------------------------------------------------------

def _build_sessions(
    turns: list[dict], memory_records: list[dict]
) -> list[dict[str, Any]]:
    by_session: dict[str, list[dict]] = defaultdict(list)
    for t in turns:
        sid = t.get("session_id") or "unknown"
        by_session[sid].append(t)

    # search_hit count per session — memory records don't carry session_id directly,
    # so we attribute them by timestamp proximity: if a search_hit falls within
    # the [first_turn_ts, last_turn_ts] window of a session, it belongs there.
    session_windows: list[tuple[str, datetime, datetime]] = []
    for sid, ts_list in by_session.items():
        tss = [_parse_ts(t.get("ts", "")) for t in ts_list]
        tss = [x for x in tss if x]
        if tss:
            session_windows.append((sid, min(tss), max(tss)))

    search_hits_per_session: dict[str, int] = defaultdict(int)
    for rec in memory_records:
        if rec.get("event") != "search_hit":
            continue
        ts = _parse_ts(rec.get("ts", ""))
        if not ts:
            continue
        for sid, t_min, t_max in session_windows:
            if t_min <= ts <= t_max:
                search_hits_per_session[sid] += 1
                break

    sessions: list[dict[str, Any]] = []
    for sid, ts_list in sorted(by_session.items(),
                               key=lambda kv: (kv[1][0].get("ts", "") or "")):
        tss = [_parse_ts(t.get("ts", "")) for t in ts_list]
        tss_clean = [x for x in tss if x]
        duration_s = 0
        if len(tss_clean) >= 2:
            duration_s = int((max(tss_clean) - min(tss_clean)).total_seconds())

        replies = [t.get("reply", "") or "" for t in ts_list]
        total_vals = [float(t["total_ms"]) for t in ts_list if t.get("total_ms") is not None]
        n_turns = len(ts_list)
        search_hits = search_hits_per_session.get(sid, 0)

        sessions.append({
            "session_id":  sid[:16],
            "turns":       n_turns,
            "duration_s":  duration_s,
            "avg_total_ms": round(statistics.mean(total_vals)) if total_vals else None,
            "search_hits": search_hits,
            "lmrr": round(search_hits / n_turns, 3) if n_turns else 0.0,
            "ri":   _session_ri(replies),
        })
    return sessions


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

COL_W = 14

def _row(*cells: Any) -> str:
    return "  ".join(str(c).ljust(COL_W) for c in cells)


def _print_latency(stats: dict[str, Any]) -> None:
    print("\n=== Задержки по стадиям (мс) ===\n")
    print(_row("Стадия", "N", "min", "avg", "p95", "max"))
    print(_row(*(["-" * 10] * 6)))
    labels = {"asr_ms": "ASR", "llm_ms": "LLM", "tts_ms": "TTS", "total_ms": "Total"}
    for key, label in labels.items():
        s = stats.get(key)
        if not s:
            print(_row(label, "—", "—", "—", "—", "—"))
        else:
            print(_row(label, s["n"], s["min"], s["avg"], s["p95"], s["max"]))


def _print_sessions(sessions: list[dict]) -> None:
    print("\n=== Сессии ===\n")
    print(_row("session_id", "turns", "duration_s", "avg_ms", "search_hits", "LMRR", "RI"))
    print(_row(*(["-" * 10] * 7)))
    for s in sessions:
        print(_row(
            s["session_id"],
            s["turns"],
            s["duration_s"],
            s["avg_total_ms"] if s["avg_total_ms"] is not None else "—",
            s["search_hits"],
            s["lmrr"],
            s["ri"],
        ))


def _print_lmrr_summary(sessions: list[dict]) -> None:
    lmrr_vals = [s["lmrr"] for s in sessions if s["turns"] > 0]
    if not lmrr_vals:
        return
    print("\n=== LMRR (частота обращений к долгосрочной памяти) ===\n")
    print(f"  Сессий: {len(lmrr_vals)}")
    print(f"  avg: {round(statistics.mean(lmrr_vals), 3)}")
    print(f"  min: {round(min(lmrr_vals), 3)}")
    print(f"  max: {round(max(lmrr_vals), 3)}")


def _print_ri_summary(sessions: list[dict]) -> None:
    ri_vals = [s["ri"] for s in sessions if s["turns"] >= 2]
    if not ri_vals:
        return
    print("\n=== RI (индекс повторяемости, Jaccard биграмм) ===\n")
    print(f"  Сессий с ≥2 репликами: {len(ri_vals)}")
    print(f"  avg: {round(statistics.mean(ri_vals), 4)}")
    print(f"  min: {round(min(ri_vals), 4)}")
    print(f"  max: {round(max(ri_vals), 4)}")
    print("  Интерпретация: 0.0 = нет повторов, 1.0 = идентичные реплики")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Adam Chip diploma metrics aggregator")
    parser.add_argument(
        "--data",
        default="/home/i17jet/Agents/Adam-Chip/data/adam",
        help="Path to adam data directory (contains inference_metrics.jsonl)",
    )
    parser.add_argument(
        "--out",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=0,
        help="Limit to last N turns (0 = all)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data)
    turns_path = data_dir / "inference_metrics.jsonl"
    memory_path = data_dir / "memory" / "metrics.jsonl"

    turns = _load_jsonl(turns_path)
    memory_records = _load_jsonl(memory_path)

    if not turns:
        print(f"[ERROR] Нет данных в {turns_path}", file=sys.stderr)
        sys.exit(1)

    if args.last > 0:
        turns = turns[-args.last:]

    print(f"\nВсего turn'ов: {len(turns)}")
    print(f"Событий памяти: {len(memory_records)}")

    lat_stats = _latency_stats(turns)
    sessions = _build_sessions(turns, memory_records)

    if args.out == "json":
        print(json.dumps({
            "latency": lat_stats,
            "sessions": sessions,
        }, ensure_ascii=False, indent=2))
        return

    _print_latency(lat_stats)
    _print_sessions(sessions)
    _print_lmrr_summary(sessions)
    _print_ri_summary(sessions)
    print()


if __name__ == "__main__":
    main()
