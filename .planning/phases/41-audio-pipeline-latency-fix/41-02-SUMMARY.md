---
phase: 41-audio-pipeline-latency-fix
plan: 02
status: complete
commit: 377e451
subsystem: audio/mic
tags: [pulse-audio, local-mic-reader, config, oww, orchestrator]
key-files:
  created:
    - System/adam/local_mic_reader.py
    - tests/test_local_mic_reader.py
  modified:
    - System/Config.json
    - System/Config.schema.json
    - System/Orchestrator.py
metrics:
  tests_added: 4
  tests_passed: 4
  config_keys_added: 2
---

## Plan 41-02: _find_pulse_source retry + OWW comment fix

### What was built

**Task 1 — APLF-02: retry-with-backoff in _find_pulse_source**

`LocalMicReader._find_pulse_source` now retries up to `pulse_source_retries` (default 3) times with `pulse_source_retry_delay_sec` (default 1.0s) between attempts before returning None. This eliminates the cold-start boot race where PipeWire/USB enumeration lagged behind orchestrator startup (3/7 starts failed on 2026-06-12).

Bug found during TDD: `self._event_log` was assigned AFTER `_find_pulse_source` was called, causing all `_emit` calls from `_find_pulse_source` to silently fail with AttributeError. Fixed by moving `self._event_log = event_log` to the top of `__init__`, before spectrum setup and PULSE_SOURCE resolution.

Config keys added to `System/Config.json` and `System/Config.schema.json` (under `media.audio`):
- `pulse_source_retries` (integer, default 3, min 1, max 10)
- `pulse_source_retry_delay_sec` (number, default 1.0, min 0.1, max 10.0)

Tests added to `tests/test_local_mic_reader.py`:
- `test_find_pulse_source_retries` — first call no-match, second matches; verifies one sleep called
- `test_find_pulse_source_immediate` — match on first call; verifies subprocess.run called exactly once, no sleep
- `test_find_pulse_source_all_fail_returns_none` — all attempts fail; verifies None returned and unresolved event emitted
- `test_no_hardcoded_retry_constants` — custom retries=5/delay=0.25 config respected (4 sleeps with 0.25s)

All 4 tests pass.

**Task 2 — APLF-03: finalize OWW-input decision**

Kept `self._ww_buf.append(_raw_chunk_for_monitor)` (raw pre-DSP audio for OWW) — no logic change.

Replaced incorrect inline comment claiming "220Hz HPF removes low-frequency fundamentals → score drops to 0.001". This causal claim was WRONG: the HPF was already active on 2026-06-08/09 when OWW scored 0.77. Correct rationale: raw full-spectrum input matches OWW training distribution; the score collapse root cause was PipeWire node.max-latency=1s (Phase 41 Plan 41-01). Orchestrator.py parses cleanly.

### Deviations

- Found that `self._event_log` ordering bug was also present in the ORIGINAL code (the error path `_emit("local_mic_pulse_source_error", ...)` on subprocess exception would also silently fail). Fixed as part of this task.

### Self-Check: PASSED

- `grep -c '_ww_buf.append(_raw_chunk_for_monitor)' System/Orchestrator.py` → 1 ✓
- `_raw_chunk_for_monitor = chunk` appears before `_input_dsp.process(chunk)` at line 1267 ✓
- `grep 'pulse_source_retries\|pulse_source_retry_delay_sec' Config.json Config.schema.json` → found in both ✓
- No hardcoded `range(3)` or `sleep(1.0)` literals in local_mic_reader.py ✓
- All 4 pytest tests pass ✓
- Orchestrator.py AST parses cleanly ✓
