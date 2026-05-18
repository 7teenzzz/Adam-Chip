---
phase: 07-esp32-mic-pipeline-refactor-micreader-keep-alive
plan: 01
subsystem: config
tags: [config, asr, mic-reader, retry, backoff]
requires: []
provides:
  - "services.asr.disable_local_fallback (runtime knob)"
  - "services.asr.esp_open_timeout_sec (runtime knob)"
  - "services.asr.esp_probe_after_fails (runtime knob)"
  - "services.asr.esp_retry_backoff_sec (runtime knob)"
affects:
  - "07-02 MicReader implementation reads these via settings.section('services').get('asr', {})"
  - "rebuild_clients PATCH services.asr — triggers MicReader.apply_config()"
tech-stack:
  added: []
  patterns: ["Config-First (every numeric tuning lives in Config.json + schema)"]
key-files:
  modified:
    - System/Config.json
    - System/Config.schema.json
  created: []
decisions:
  - "Keys appended at end of services.asr (preserves existing key order — pure addition diff)"
  - "Schema descriptions explain rationale (per CLAUDE.md Config-First convention)"
metrics:
  duration: "~5 min"
  completed: 2026-05-16
---

# Phase 7 Plan 01: MicReader retry/probe config keys — Summary

Added 4 new keys to `services.asr` in `Config.json` with full schema documentation in `Config.schema.json`. These keys drive MicReader (plan 07-02) retry/backoff/probe behavior, replacing the previously hardcoded constants in `Orchestrator._run_esp32`.

## Keys Added

| Key | Default | Range | Purpose (D-ref) |
|-----|---------|-------|-----------------|
| `disable_local_fallback` | `true` | bool | D-16: MicReader never falls back to local ALSA mic; ESP32 INMP441 is exhibition contract |
| `esp_open_timeout_sec` | `8` | 1–60 | D-18: per-attempt timeout for `_NO_PROXY_OPENER.open(:81)` — replaces legacy hardcoded 30 |
| `esp_probe_after_fails` | `2` | 0–20 | D-19: probe `:80 /api/status` before retrying `:81` after N consecutive fails |
| `esp_retry_backoff_sec` | `[2, 4, 8, 15]` | array of numbers | D-20: exponential backoff between retries; last value reused indefinitely |

## Verification Results

All 4 acceptance criteria passed:

1. `Config.json` JSON-valid: OK
2. `Config.schema.json` JSON-valid: OK
3. Config defaults match D-16..D-20 exactly: OK
4. Schema entries have `type`/`description`/`default` (+ `minimum`/`maximum`/`items` where applicable): OK

Diff is **pure addition** — no existing keys were reordered or modified:
- `System/Config.json`: +5 / -1 (only the trailing comma added to `reply_window_expired_action`)
- `System/Config.schema.json`: +25 / -0

## Deviations from Plan

None — plan executed exactly as written.

Note on insertion position: the plan's task-1 prose said "insert after `silence_rms_threshold`", but the current `services.asr` object in `Config.json` has `silence_rms_threshold` mid-block (line 92) and `reply_window_expired_action` at the end (line 99). To satisfy the plan's own acceptance criterion *"no other services.asr keys lost or reordered (diff shows pure addition)"*, the new keys were appended at the end of the block (after `reply_window_expired_action`). This is the only valid interpretation; placing them after `silence_rms_threshold` would force reordering 7 existing keys.

## Commit

- `5e242c4` — feat(07-01): add MicReader retry/probe config keys

## Downstream Hooks

Plan 07-02 (MicReader implementation) will read these keys via:
```python
asr_cfg = settings.section("services").get("asr", {})
disable_local = asr_cfg.get("disable_local_fallback", True)
open_timeout = int(asr_cfg.get("esp_open_timeout_sec", 8))
probe_after = int(asr_cfg.get("esp_probe_after_fails", 2))
backoff = list(asr_cfg.get("esp_retry_backoff_sec", [2, 4, 8, 15]))
```

`rebuild_clients` (on PATCH `/api/config`) will trigger `MicReader.apply_config()` to honour live edits without restart.

## Self-Check: PASSED

- `System/Config.json` — FOUND, JSON-valid, contains all 4 keys with correct defaults
- `System/Config.schema.json` — FOUND, JSON-valid, contains all 4 schema entries with descriptions
- Commit `5e242c4` — FOUND in `git log --oneline`
