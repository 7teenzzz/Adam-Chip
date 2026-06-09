#!/usr/bin/env python3
"""ASR Calibration Analyzer for Adam Chip voice pipeline.

Reads data/adam/events.jsonl, joins asr_request (pcm_ms) with asr_result,
computes WER against a reference phrase, and prints a calibration table.

Usage:
    python3 scripts/asr_calibration_analyzer.py --last 20
    python3 scripts/asr_calibration_analyzer.py --last 30 --reference "ты здесь это тест три сестры шуршали в тишине"
    python3 scripts/asr_calibration_analyzer.py --last 50 --hours 6 --show-empty
    python3 scripts/asr_calibration_analyzer.py --sessions
    python3 scripts/asr_calibration_analyzer.py --word-errors --reference "три сестры шуршали"

No external dependencies — stdlib only (json, difflib, datetime, argparse).
"""

import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_EVENTS_PATH = Path(__file__).parent.parent / "data" / "adam" / "events.jsonl"
DEFAULT_REFERENCE = "ты здесь это тест три сестры шуршали в тишине"


def _normalize(text: str) -> str:
    """Strip punctuation, lowercase, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^а-яёa-z0-9 ]", " ", text)
    return " ".join(text.split())


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate via difflib (edit-distance style, 0.0–1.0).

    Uses 1 - (matching tokens / max(len_ref, len_hyp)).
    Returns 1.0 for empty hypothesis, 0.0 for empty reference.
    """
    if not reference.strip():
        return 0.0
    ref_w = _normalize(reference).split()
    hyp_w = _normalize(hypothesis).split() if hypothesis.strip() else []
    if not hyp_w:
        return 1.0
    matcher = difflib.SequenceMatcher(None, ref_w, hyp_w)
    matches = sum(t.size for t in matcher.get_matching_blocks())
    denom = max(len(ref_w), len(hyp_w))
    return round(1.0 - matches / denom, 3) if denom else 0.0


def _parse_ts(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_records(events_path: Path) -> list[dict]:
    """Read events.jsonl, join asr_request + asr_result by turn_id.

    Returns list of dicts: ts, turn_id, pcm_ms, asr_ms, empty, raw.
    Sorted by timestamp ascending.
    """
    all_ev: list[dict] = []

    with open(events_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = e.get("type", "")
            if t in ("asr_result", "asr_request"):
                all_ev.append(e)

    all_ev.sort(key=lambda e: e.get("ts", ""))

    req_map: dict[str, dict] = {}
    records: list[dict] = []

    for e in all_ev:
        etype = e["type"]
        tid = e.get("turn_id")
        payload = e.get("payload", {})

        if etype == "asr_request":
            req_map[tid] = payload
        elif etype == "asr_result":
            req_payload = req_map.get(tid, {})
            records.append(
                {
                    "ts": e.get("ts", ""),
                    "turn_id": tid,
                    "pcm_ms": req_payload.get("pcm_ms"),
                    "asr_ms": payload.get("asr_ms"),
                    "empty": payload.get("empty", True),
                    "raw": payload.get("raw", ""),
                }
            )

    return records


def filter_recent(records: list[dict], hours: float) -> list[dict]:
    if not records or hours <= 0:
        return records
    last_ts = _parse_ts(records[-1]["ts"])
    cutoff = last_ts - timedelta(hours=hours)
    return [r for r in records if _parse_ts(r["ts"]) >= cutoff]


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def compute_stats(records: list[dict], reference: str) -> dict:
    total = len(records)
    empty = sum(1 for r in records if r["empty"])
    non_empty = [r for r in records if not r["empty"]]
    pcm_vals = [r["pcm_ms"] for r in records if r["pcm_ms"] is not None]
    ne_pcm = [r["pcm_ms"] for r in non_empty if r["pcm_ms"] is not None]
    asr_ms_vals = [r["asr_ms"] for r in records if r["asr_ms"] is not None]

    wers = [wer(reference, r["raw"]) for r in non_empty] if non_empty else []

    return {
        "total": total,
        "empty": empty,
        "empty_rate": round(empty / total, 3) if total else 0.0,
        "non_empty": len(non_empty),
        "avg_pcm_ms": round(sum(pcm_vals) / len(pcm_vals)) if pcm_vals else 0,
        "avg_pcm_ms_ne": round(sum(ne_pcm) / len(ne_pcm)) if ne_pcm else 0,
        "max_pcm_ms": max(pcm_vals) if pcm_vals else 0,
        "long_clips_gt10s": sum(1 for v in pcm_vals if v > 10_000),
        "avg_asr_ms": round(sum(asr_ms_vals) / len(asr_ms_vals)) if asr_ms_vals else 0,
        "avg_wer": round(sum(wers) / len(wers), 3) if wers else None,
        "min_wer": round(min(wers), 3) if wers else None,
        "max_wer": round(max(wers), 3) if wers else None,
    }


# ---------------------------------------------------------------------------
# Session grouping
# ---------------------------------------------------------------------------

def split_sessions(records: list[dict], gap_minutes: float = 5.0) -> list[list[dict]]:
    """Split records into sessions where gap > gap_minutes between events."""
    sessions: list[list[dict]] = []
    cur: list[dict] = []
    prev_ts: datetime | None = None

    for r in records:
        ts = _parse_ts(r["ts"])
        if prev_ts and (ts - prev_ts).total_seconds() > gap_minutes * 60:
            sessions.append(cur)
            cur = []
        cur.append(r)
        prev_ts = ts

    if cur:
        sessions.append(cur)
    return sessions


# ---------------------------------------------------------------------------
# Word-level error analysis
# ---------------------------------------------------------------------------

def word_error_analysis(records: list[dict], reference: str) -> dict:
    ref_words = _normalize(reference).split()
    hit: Counter = Counter()
    miss: Counter = Counter()
    sub: Counter = Counter()

    for r in records:
        if r["empty"]:
            continue
        hyp_w = _normalize(r["raw"]).split()
        matcher = difflib.SequenceMatcher(None, ref_words, hyp_w)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for w in ref_words[i1:i2]:
                    hit[w] += 1
            elif tag == "replace":
                for w in ref_words[i1:i2]:
                    miss[w] += 1
                for hw in hyp_w[j1:j2]:
                    for rw in ref_words[i1:i2]:
                        sub[(rw, hw)] += 1
            elif tag == "delete":
                for w in ref_words[i1:i2]:
                    miss[w] += 1

    return {"ref_words": ref_words, "hit": hit, "miss": miss, "sub": sub}


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

COL_W = {
    "ts": 20,
    "pcm_ms": 8,
    "asr_ms": 8,
    "empty": 6,
    "wer": 6,
    "text": 60,
}


def fmt_ts(ts_str: str) -> str:
    # show date+time without timezone suffix, truncated
    try:
        dt = _parse_ts(ts_str)
        return dt.strftime("%m-%d %H:%M:%S")
    except Exception:
        return ts_str[-19:]


def fmt_num(val, fmt=".0f", fallback="?") -> str:
    if val is None:
        return fallback
    return format(val, fmt)


def print_table(records: list[dict], reference: str, show_empty: bool = False) -> None:
    """Print per-record calibration table."""
    w = COL_W
    header = (
        f"{'Timestamp':<{w['ts']}} "
        f"{'pcm_ms':>{w['pcm_ms']}} "
        f"{'asr_ms':>{w['asr_ms']}} "
        f"{'empty':>{w['empty']}} "
        f"{'WER':>{w['wer']}}  "
        f"{'Transcription'}"
    )
    print(header)
    print("-" * (sum(w.values()) + 10))

    for r in records:
        if r["empty"] and not show_empty:
            continue
        ts = fmt_ts(r["ts"])
        pcm = fmt_num(r["pcm_ms"])
        asr = fmt_num(r["asr_ms"], ".1f")
        empty_flag = "YES" if r["empty"] else "no"
        w_val = wer(reference, r["raw"])
        wer_str = f"{w_val:.2f}" if not r["empty"] else "  —  "
        text = r["raw"][:w["text"]] if r["raw"] else ""
        print(
            f"{ts:<{w['ts']}} "
            f"{pcm:>{w['pcm_ms']}} "
            f"{asr:>{w['asr_ms']}} "
            f"{empty_flag:>{w['empty']}} "
            f"{wer_str:>{w['wer']}}  "
            f"{text}"
        )


def print_stats(stats: dict, reference: str) -> None:
    print()
    print("=" * 55)
    print("SUMMARY STATISTICS")
    print("=" * 55)
    print(f"  Total records      : {stats['total']}")
    print(f"  Non-empty          : {stats['non_empty']}")
    print(f"  Empty rate         : {100*stats['empty_rate']:.1f}%  ({stats['empty']}/{stats['total']})")
    print(f"  Avg pcm_ms (all)   : {stats['avg_pcm_ms']} ms")
    print(f"  Avg pcm_ms (ne)    : {stats['avg_pcm_ms_ne']} ms")
    print(f"  Max pcm_ms         : {stats['max_pcm_ms']} ms")
    print(f"  Clips > 10s        : {stats['long_clips_gt10s']}  ← high = rms_threshold too aggressive")
    print(f"  Avg ASR latency    : {stats['avg_asr_ms']} ms")
    if stats["avg_wer"] is not None:
        print(f"  Avg WER            : {stats['avg_wer']:.2f}  (ref: \"{reference[:40]}\")")
        print(f"  WER min/max        : {stats['min_wer']:.2f} / {stats['max_wer']:.2f}")
    else:
        print("  WER                : N/A (no non-empty results)")
    print("=" * 55)


def print_sessions_table(sessions: list[list[dict]], reference: str) -> None:
    hdr = (
        f"{'Session start':<20} {'N':>4} {'empty%':>7} {'avg_pcm':>9} "
        f"{'long>10s':>9} {'avg_WER':>8}  first_text"
    )
    print(hdr)
    print("-" * 110)
    for s in sessions:
        start = fmt_ts(s[0]["ts"])
        total = len(s)
        empty = sum(1 for r in s if r["empty"])
        non_empty = [r for r in s if not r["empty"]]
        ep = 100 * empty // total if total else 0
        pcm_vals = [r["pcm_ms"] for r in s if r["pcm_ms"] is not None]
        avg_pcm = round(sum(pcm_vals) / len(pcm_vals)) if pcm_vals else 0
        long = sum(1 for v in pcm_vals if v > 10_000)
        wers = [wer(reference, r["raw"]) for r in non_empty]
        avg_w = f"{sum(wers)/len(wers):.2f}" if wers else "  —  "
        sample = non_empty[0]["raw"][:50] if non_empty else "(all empty)"
        print(
            f"{start:<20} {total:>4} {ep:>6}% {avg_pcm:>9} "
            f"{long:>9} {avg_w:>8}  {sample}"
        )


def print_word_errors(analysis: dict, top_n: int = 15) -> None:
    ref_words = analysis["ref_words"]
    hit = analysis["hit"]
    miss = analysis["miss"]
    sub = analysis["sub"]

    print()
    print("WORD ACCURACY (reference words only, non-empty transcriptions):")
    print(f"  {'word':<14} {'hits':>5} {'miss':>5} {'acc':>8}  diagnosis")
    print("  " + "-" * 55)
    for w in ref_words:
        h = hit[w]
        m = miss[w]
        total = h + m
        if total == 0:
            acc_str = "  N/A"
            diag = "never tested"
        else:
            acc = 100 * h // total
            acc_str = f"{acc:>3}%"
            if acc >= 80:
                diag = "OK"
            elif acc >= 50:
                diag = "fair — review acoustic conditions"
            elif acc >= 20:
                diag = "poor — common substitution or deletion"
            else:
                diag = "critical — ASR cannot reliably decode this word"
        print(f"  {w:<14} {h:>5} {m:>5} {acc_str:>8}  {diag}")

    print()
    print(f"TOP {top_n} SUBSTITUTIONS (reference_word -> hypothesis_word):")
    for (rw, hw), count in sub.most_common(top_n):
        print(f"  {rw!r:<14} -> {hw!r}: {count}x")


def print_pcm_distribution(records: list[dict]) -> None:
    empty_pcm = [r["pcm_ms"] for r in records if r["empty"] and r["pcm_ms"] is not None]
    ne_pcm = [r["pcm_ms"] for r in records if not r["empty"] and r["pcm_ms"] is not None]

    def bucket(vals):
        b = Counter()
        for v in vals:
            if v < 2_000:
                b["<2s"] += 1
            elif v < 5_000:
                b["2-5s"] += 1
            elif v < 10_000:
                b["5-10s"] += 1
            else:
                b[">10s"] += 1
        return b

    print()
    print("PCM DURATION DISTRIBUTION:")
    print(f"  {'bucket':<8} {'empty':>8} {'non-empty':>10}  diagnosis")
    print("  " + "-" * 50)
    eb = bucket(empty_pcm)
    nb = bucket(ne_pcm)
    for key in ["<2s", "2-5s", "5-10s", ">10s"]:
        ev = eb[key]
        nv = nb[key]
        diag = ""
        if key == "<2s" and ev > 5:
            diag = "← vad fires too eagerly or speech too short"
        if key == ">10s" and ev > 3:
            diag = "← rms_threshold too high — segments not splitting"
        print(f"  {key:<8} {ev:>8} {nv:>10}  {diag}")

    if empty_pcm:
        avg = sum(empty_pcm) / len(empty_pcm)
        print(f"\n  Empty  avg_pcm: {avg:.0f}ms  min: {min(empty_pcm)}  max: {max(empty_pcm)}")
    if ne_pcm:
        avg = sum(ne_pcm) / len(ne_pcm)
        print(f"  NonEmp avg_pcm: {avg:.0f}ms  min: {min(ne_pcm)}  max: {max(ne_pcm)}")


def print_scenario_matrix(sessions: list[list[dict]], reference: str) -> None:
    """Print the calibration scenario matrix."""
    print()
    print("CALIBRATION SCENARIO MATRIX")
    print("-" * 120)
    print(
        f"{'Scenario/Session':<22} | {'rms_thr':>7} | {'wake_req':>8} | "
        f"{'N':>4} | {'pcm_ms':>7} | {'empty%':>7} | {'WER_approx':>10} | Notes"
    )
    print("-" * 120)

    # rms_threshold and wake_req come from Config, not events — mark as from config
    for i, s in enumerate(sessions):
        start = fmt_ts(s[0]["ts"])
        total = len(s)
        empty = sum(1 for r in s if r["empty"])
        ne = [r for r in s if not r["empty"]]
        ep = 100 * empty // total if total else 0
        pcm_vals = [r["pcm_ms"] for r in s if r["pcm_ms"] is not None]
        avg_pcm = round(sum(pcm_vals) / len(pcm_vals)) if pcm_vals else 0
        wers = [wer(reference, r["raw"]) for r in ne]
        avg_wer_str = f"{sum(wers)/len(wers):.2f}" if wers else "N/A"
        long = sum(1 for v in pcm_vals if v > 10_000)

        notes = []
        if ep >= 80:
            notes.append("high empty → check logprob/vad_onset")
        if long > 3:
            notes.append(f"{long} clips>10s → rms_thr may be too high")
        if wers and sum(wers) / len(wers) > 0.7:
            notes.append("WER>0.7 → acoustic/model issue")
        note_str = "; ".join(notes) if notes else "OK"

        # rms_thr is not in events, so we note it's from config
        print(
            f"session {i+1:02d}  {start:<12} | {'(cfg)':>7} | {'(cfg)':>8} | "
            f"{total:>4} | {avg_pcm:>7} | {ep:>6}% | {avg_wer_str:>10} | {note_str}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASR calibration analyzer for Adam Chip voice pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/asr_calibration_analyzer.py --last 20
  python3 scripts/asr_calibration_analyzer.py --last 30 --reference "три сестры шуршали"
  python3 scripts/asr_calibration_analyzer.py --last 50 --show-empty
  python3 scripts/asr_calibration_analyzer.py --hours 6 --sessions
  python3 scripts/asr_calibration_analyzer.py --word-errors
  python3 scripts/asr_calibration_analyzer.py --pcm-dist --hours 24
""",
    )
    parser.add_argument(
        "--events",
        default=str(DEFAULT_EVENTS_PATH),
        help="Path to events.jsonl (default: data/adam/events.jsonl)",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=20,
        metavar="N",
        help="Show last N asr_result records (default: 20)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=0.0,
        metavar="H",
        help="Limit to last H hours of data (default: no limit, uses --last)",
    )
    parser.add_argument(
        "--reference",
        default=DEFAULT_REFERENCE,
        metavar="PHRASE",
        help=f'Reference phrase for WER (default: "{DEFAULT_REFERENCE}")',
    )
    parser.add_argument(
        "--show-empty",
        action="store_true",
        help="Include empty (no transcription) rows in the table",
    )
    parser.add_argument(
        "--sessions",
        action="store_true",
        help="Show session-grouped table (5min gap between sessions)",
    )
    parser.add_argument(
        "--session-gap",
        type=float,
        default=5.0,
        metavar="MIN",
        help="Session gap in minutes (default: 5)",
    )
    parser.add_argument(
        "--word-errors",
        action="store_true",
        help="Show per-word accuracy and top substitutions",
    )
    parser.add_argument(
        "--pcm-dist",
        action="store_true",
        help="Show pcm_ms duration distribution for empty vs non-empty",
    )
    parser.add_argument(
        "--scenario-matrix",
        action="store_true",
        help="Print calibration scenario matrix across sessions",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enable all analysis modes (sessions + word-errors + pcm-dist + scenario-matrix)",
    )

    args = parser.parse_args()

    # Load
    events_path = Path(args.events)
    if not events_path.exists():
        print(f"ERROR: events file not found: {events_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading events from: {events_path}", file=sys.stderr)
    all_records = load_records(events_path)
    print(f"Total asr_result records: {len(all_records)}", file=sys.stderr)

    # Filter by hours or last N
    if args.hours > 0:
        records = filter_recent(all_records, args.hours)
        print(
            f"Filtered to last {args.hours}h: {len(records)} records", file=sys.stderr
        )
    else:
        records = all_records[-args.last :]
        print(f"Using last {len(records)} records", file=sys.stderr)

    if not records:
        print("No records to analyze.", file=sys.stderr)
        sys.exit(0)

    reference = args.reference
    sessions = split_sessions(records, gap_minutes=args.session_gap)

    # --- Main table ---
    print()
    print(f"ASR CALIBRATION TABLE  (reference: \"{reference[:60]}\")")
    print()
    print_table(records, reference, show_empty=args.show_empty)

    # --- Stats ---
    stats = compute_stats(records, reference)
    print_stats(stats, reference)

    # --- Optional views ---
    do_sessions = args.sessions or args.all
    do_word = args.word_errors or args.all
    do_pcm = args.pcm_dist or args.all
    do_matrix = args.scenario_matrix or args.all

    if do_sessions:
        print()
        print(f"SESSION TABLE  ({len(sessions)} sessions, gap={args.session_gap}min)")
        print()
        print_sessions_table(sessions, reference)

    if do_word:
        analysis = word_error_analysis(records, reference)
        print_word_errors(analysis)

    if do_pcm:
        print_pcm_distribution(records)

    if do_matrix:
        print_scenario_matrix(sessions, reference)


if __name__ == "__main__":
    main()
