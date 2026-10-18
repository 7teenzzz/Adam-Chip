"""EventLog disk policy: sampling, repeat dedupe, rotation, bounded tail."""
from __future__ import annotations

import json
from pathlib import Path

from adam.events import EventLog


def _disk(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_sample_zero_skips_disk_but_keeps_live(tmp_path: Path) -> None:
    log = EventLog(tmp_path, events_cfg={"jsonl_sample": {"oww_score": 0, "audio_level": 3}})
    for _ in range(6):
        log.append("oww_score", {"score": 0.1})
        log.append("audio_level", {"rms": 1})
    types = [e["type"] for e in _disk(log.path)]
    assert "oww_score" not in types
    assert types.count("audio_level") == 2
    assert len(log.tail(100)) == 12  # in-memory / SSE side unaffected


def test_identical_repeats_collapsed_with_count(tmp_path: Path) -> None:
    log = EventLog(tmp_path, events_cfg={"jsonl_dedupe_window_sec": 60})
    for _ in range(5):
        log.append("camera_error", {"error": "no device"})
    log.append("camera_error", {"error": "other"})
    log.append("asr_result", {"text": "привет"}, turn_id="t1")
    log.append("asr_result", {"text": "привет"}, turn_id="t2")  # different turn -> kept
    rows = _disk(log.path)
    cam = [r for r in rows if r["type"] == "camera_error"]
    assert [r["payload"]["error"] for r in cam] == ["no device", "other"]
    assert cam[1]["suppressed_since_last"] == 4
    assert len([r for r in rows if r["type"] == "asr_result"]) == 2


def test_rotation_keeps_backups(tmp_path: Path) -> None:
    log = EventLog(tmp_path, events_cfg={"jsonl_max_mb": 0.001, "jsonl_backups": 2})
    for i in range(200):
        log.append("tick", {"i": i, "pad": "x" * 50})
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["events.jsonl", "events.jsonl.1", "events.jsonl.2"]
    assert log.path.stat().st_size < 1100


def test_tail_reads_only_file_end(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for i in range(5000):
            handle.write(json.dumps({"id": str(i), "ts": "", "type": "x", "payload": {"i": i}}) + "\n")
    log = EventLog(tmp_path, events_cfg={"tail_read_kb": 64})
    out = log.tail(5)
    assert [e["payload"]["i"] for e in out] == [4995, 4996, 4997, 4998, 4999]


def test_legacy_audio_sampler_still_honoured(tmp_path: Path) -> None:
    log = EventLog(tmp_path, audio_cfg={"events_jsonl_sample_audio_level": 2})
    for _ in range(4):
        log.append("audio_level", {"rms": 1})
    assert len(_disk(log.path)) == 2
