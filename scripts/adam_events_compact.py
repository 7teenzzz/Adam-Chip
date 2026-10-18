#!/usr/bin/env python3
"""Compact an existing events.jsonl with the same disk policy EventLog uses live.

Applies Config.json `events` (jsonl_sample + jsonl_dedupe_window_sec) through
adam.events.JsonlWritePolicy, so offline and live rules can never diverge.
Run with the orchestrator STOPPED — the file is replaced in place.

    PYTHONPATH=System .venv/bin/python scripts/adam_events_compact.py            # data/adam/events.jsonl
    PYTHONPATH=System .venv/bin/python scripts/adam_events_compact.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "System"))

from adam.events import EVENTS_DEFAULTS, JsonlWritePolicy  # noqa: E402

_TYPE_MARK = '"type": "'


def _line_type(line: str) -> str | None:
    # Records are written with sort_keys=True, so "type" is the last key —
    # read it from the tail without parsing the whole JSON line.
    i = line.rfind(_TYPE_MARK)
    if i < 0:
        return None
    j = line.find('"', i + len(_TYPE_MARK))
    return line[i + len(_TYPE_MARK):j] if j > 0 else None


def _ts_sec(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "System" / "Config.json"))
    ap.add_argument("--file", default=None, help="events.jsonl path (default: <agent.data_dir>/events.jsonl)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = {**EVENTS_DEFAULTS, **config.get("events", {})}
    src = Path(args.file) if args.file else Path(config["agent"]["data_dir"]) / "events.jsonl"
    dst = src.with_name(src.name + ".compacting")

    policy = JsonlWritePolicy(cfg)
    sample = policy._sample  # read-only use: fast path for types never written
    dropped: Counter[str] = Counter()
    kept = 0
    out = None if args.dry_run else dst.open("w", encoding="utf-8")
    try:
        with src.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                etype = _line_type(line)
                if etype is not None and sample.get(etype, 1) == 0:
                    dropped[etype] += 1
                    continue
                if etype is not None and sample.get(etype, 1) > 1:
                    write, suppressed = policy.decide({"type": etype}, 0.0)
                    record = None
                else:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        dropped["<invalid>"] += 1
                        continue
                    write, suppressed = policy.decide(record, _ts_sec(str(record.get("ts", ""))))
                if not write:
                    dropped[etype or "<untyped>"] += 1
                    continue
                kept += 1
                if out is None:
                    continue
                if record is not None and suppressed:
                    record["suppressed_since_last"] = record.get("suppressed_since_last", 0) + suppressed
                    out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                else:
                    out.write(line if line.endswith("\n") else line + "\n")
    finally:
        if out is not None:
            out.close()

    before = src.stat().st_size
    print(f"kept {kept} lines, dropped {sum(dropped.values())}")
    for etype, n in dropped.most_common(10):
        print(f"  - {etype}: {n}")
    if args.dry_run:
        return 0
    after = dst.stat().st_size
    os.replace(dst, src)
    print(f"{src}: {before / 2**20:.0f} MB -> {after / 2**20:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
