---
phase: 21A
plan: 04
subsystem: events-bus / disk-io
tags: [config-first, jsonl-growth-mitigation, sampler, sse-cadence-preserved]
dependency_graph:
  requires:
    - "21A-02 (Config schema scaffold — media.audio.spectrum_* keys provide the insertion anchor)"
  provides:
    - "Config key media.audio.events_jsonl_sample_audio_level (default 5)"
    - "EventLog writing-side sampler — disk write throttled per high-frequency event type"
  affects:
    - "data/adam/events.jsonl growth rate (~5× reduction at default config)"
    - "EventLog.__init__ signature (added audio_cfg kwarg, default None)"
    - "Orchestrator EventLog construction site"
tech_stack:
  added: []
  patterns:
    - "Config-First: integer knob in Config.json + Config.schema.json, code reads via settings.section()"
    - "Silent-skip pattern for disk write (no skipped-event emission — would defeat purpose)"
    - "Separation of concerns: writing path throttled, broadcast/in-memory path UNCHANGED"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/deferred-items.md"
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-04-SUMMARY.md"
  modified:
    - "System/Config.json"
    - "System/Config.schema.json"
    - "System/adam/events.py"
    - "System/Orchestrator.py"
decisions:
  - "Default value = 5 (RESEARCH §12 recommendation — reduces 36 MB/h → ~7 MB/h)"
  - "Sampler keyed by event type, currently only audio_level is throttled (extensible via _jsonl_write_counters map)"
  - "audio_cfg defaulted to None for test/legacy backwards-compat — tests using EventLog(data_dir) keep legacy 1:1 behavior"
  - "Silent skip (no diagnostic emission on every skipped write) — emitting would recurse and defeat the purpose"
  - "Counter increment is inside _lock for thread safety (EventLog is shared across asyncio + background threads)"
metrics:
  duration_minutes: 12
  completed_date: 2026-05-18
  tasks_completed: 2
  files_changed: 4
---

# Phase 21A Plan 04: events.jsonl writing-side sampler Summary

**One-liner:** Writing-side sampler in `EventLog.append()` throttles disk writes for high-frequency `audio_level` events (default 1-in-5) while keeping SSE broadcast and in-memory `_recent` deque at full cadence — mitigates the 36 MB/h jsonl growth flagged by RESEARCH §5/§12 without affecting frontend EQ widget responsiveness.

## Objective

Plan 21A introduces a 25 Hz spectrum-bands cadence on `audio_level` events with a 24-element `bands[]` payload. At baseline this would compound the existing events.jsonl growth (already 417 MB, growing ~36 MB/hour from audio_level alone). RESEARCH §12 recommended writing-side sampling as the cleaner of two options (vs. full log rotation, which is out of scope for this phase). CONTEXT D-04 accepted the recommendation.

This plan delivers exactly that — one new Config key + a small change in `events.py`.

## Tasks Completed

| Task | Name                                                                                       | Commit  | Files                                          |
| ---- | ------------------------------------------------------------------------------------------ | ------- | ---------------------------------------------- |
| 1    | Add Config key `events_jsonl_sample_audio_level` + schema entry                            | d97b5fb | System/Config.json, System/Config.schema.json  |
| 2    | Add writing-side sampler to `EventLog.append` + Orchestrator wiring + deferred-items log   | 1f7af0d | System/adam/events.py, System/Orchestrator.py, .planning/phases/21A-chat-eq-real-spectrum-fft/deferred-items.md |

## What Changed

### Config (Task 1)

- `System/Config.json` — added `media.audio.events_jsonl_sample_audio_level: 5` after the spectrum_color_red_at key added in Plan 02.
- `System/Config.schema.json` — added matching property entry: `type: integer`, `minimum: 1`, `maximum: 100`, `default: 5`, full English description covering the trade-off and the explicit guarantee that SSE cadence is unaffected.

Both files validate as JSON (verified by the inline `json.load()` check from the plan's verification block).

### EventLog (Task 2)

`System/adam/events.py`:

- `EventLog.__init__` gained a keyword-only `audio_cfg: dict[str, Any] | None = None` parameter. When None (test/legacy path), the sampler is effectively disabled (`_jsonl_sample_audio_level = 1`).
- Two new instance attributes:
  - `self._jsonl_sample_audio_level: int` — read from `audio_cfg["events_jsonl_sample_audio_level"]`, clamped to ≥1
  - `self._jsonl_write_counters: dict[str, int]` — per-event-type counter, keyed by event type
- `append()` decides `skip_file_write` before the `with self._lock:` block: increments the counter for `audio_level` events under the lock, skips the disk write when `counter % N != 0`. Both `_recent.append()` and the broadcast/`_enqueue` paths remain UNCHANGED and UNCONDITIONAL.

`System/Orchestrator.py`:

- The single EventLog construction site now passes `audio_cfg=settings.section("media").get("audio", {})`.

### Smoke verification (in-task, beyond pytest)

Ran 5 in-process scenarios against the actual `EventLog` class:

1. Default (no audio_cfg) → all 10 of 10 written to disk, all 10 in `_recent`.
2. Sampler=5 → 5 of 25 written to disk, all 25 in `_recent`. **Core acceptance.**
3. Non-audio_level events (e.g. `turn_started`) → always written (sampler is event-type-scoped).
4. Sampler=1 (explicit revert) → all 20 of 20 written.
5. Sampler=0 (invalid) → clamped to 1 by `max(1, int(...))`.

All five passed.

## Deviations from Plan

None — plan executed exactly as written.

## Pre-existing Issues (out of scope)

Two pytest failures were already on the baseline (verified via `git stash`) and are unrelated to this plan's changes. Logged in `.planning/phases/21A-chat-eq-real-spectrum-fft/deferred-items.md`:

1. `tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip` — `EpisodicMemory.write_semantic` not implemented; out-of-scope memory subsystem item.
2. `tests/test_mic_reader_spectrum.py::test_payload_shape` — asserts the Plan 03 deliverable (`bands[]` key in `audio_level` payload); will turn green once Plan 03 lands.

Excluding those two, the full pytest suite is green: **98 passed, 5 skipped, 2 deselected**.

## Verification

- `python -m json.tool` on both Config files: OK.
- `inspect.signature(EventLog.__init__)` contains `audio_cfg` kwarg: OK.
- `grep _jsonl_sample_audio_level System/adam/events.py`: matches at __init__ and append.
- `grep _jsonl_write_counters System/adam/events.py`: matches at __init__ and append.
- Smoke test (5 scenarios): all pass.
- Full pytest excluding two pre-existing failures: 98 passed, 5 skipped.

## Impact on Subsequent Plans

- **Plan 03** (FFT compute in `_emit_audio_level`) — already references the `bands[]` field that this sampler now throttles to disk. No coupling change needed; Plan 03 just adds the payload field.
- **Plan 05–07** (frontend wiring) — operate against the SSE stream which is at full cadence. No frontend code change required.
- **Operator** — can revert to legacy 1:1 logging by setting `media.audio.events_jsonl_sample_audio_level` to 1 in `Config.json` (no code change, hot-reload-friendly since EventLog reads it at construction; an Orchestrator restart applies the new value).

## Self-Check: PASSED

Files created/modified verified:

- `[ -f System/Config.json ]` — FOUND, contains `events_jsonl_sample_audio_level: 5`.
- `[ -f System/Config.schema.json ]` — FOUND, contains schema entry.
- `[ -f System/adam/events.py ]` — FOUND, modified.
- `[ -f System/Orchestrator.py ]` — FOUND, modified.
- `[ -f .planning/phases/21A-chat-eq-real-spectrum-fft/deferred-items.md ]` — FOUND.
- `[ -f .planning/phases/21A-chat-eq-real-spectrum-fft/21A-04-SUMMARY.md ]` — FOUND (this file).

Commits verified in git log:

- `d97b5fb` — Task 1 commit FOUND.
- `1f7af0d` — Task 2 commit FOUND.
