---
phase: 21A
plan: 08
subsystem: System/adam/mic_reader.py / Phase 21A Wave 6 (hotfix)
tags: [watchdog, esp32, resilience, mic-stream, auto-restart, config-first]
dependency_graph:
  requires:
    - "21A-02 (Wave 1): Config-First key handling in MicReader.__init__ + apply_config"
    - "Pre-existing device.py Device.stream_restart() — POST :80/api/system/stream/restart"
  provides:
    - "Auto-recovery from ESP32 :81 socket deadlocks within ~60 sec of first failure"
    - "Config-driven threshold/cooldown — operator can tune without code change"
    - "mic_reader_stream_restart_triggered event for diagnostics"
    - "Zero perf cost in steady state — gate only evaluates after first failure"
  affects:
    - "Voice pipeline resilience under exhibition conditions"
    - "Operator workload — no longer requires manual restart when ESP firmware hangs"
tech_stack:
  added: []
  patterns:
    - "Cooldown-gated retry pattern via perf_counter timestamp comparison"
    - "Extracted gate predicate (_should_trigger_stream_restart) for unit-testability — actual call site in _run is a single-line `if predicate(): action`"
    - "Watchdog runs ONLY in the existing :81 reconnect loop — no extra threads, no extra timers"
    - "Defence-in-depth: probe-alive precondition is implicit (handled by earlier probe gate in same iteration)"
    - "Exception-safe event emission: _trigger_stream_restart catches all exceptions internally and emits a failure event — never bubbles up to disrupt _run"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-08-PLAN.md"
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-08-SUMMARY.md"
    - "tests/test_mic_reader_watchdog.py"
  modified:
    - "System/Config.json"
    - "System/Config.schema.json"
    - "System/adam/mic_reader.py"
decisions:
  - "Gate predicate extracted into _should_trigger_stream_restart(now) for unit-testability instead of inline conditional — single source of truth for trigger logic"
  - "Sleep 8 sec after restart trigger is sized for observed ESP32-S3 :81 reboot time (W5500 + esp_http_server startup ~4-6 sec + safety margin). Not Config-tunable yet — if production reveals different timing, promote to Config key in a future revision"
  - "Reset _consecutive_fails to 0 ONLY on restart_ok=True. If the POST itself fails (ESP fully dead), keep climbing so the next iteration may try probe again — preserves the normal failure semantics"
  - "Cooldown gate uses perf_counter() not wall-clock — immune to NTP skew and operator clock changes"
  - "Default threshold 5 and cooldown 120 sec chosen per user direction. 5 ≈ 30-45 sec of backoff retries (2+4+8+15 from esp_retry_backoff_sec, last repeated for any extras above 4) before triggering. 120 sec cooldown comfortably above ESP firmware reboot time (~10 sec) with safety margin"
  - "Watchdog disabled when esp_stream_restart_after_fails=0 — provides explicit kill-switch for operators who don't trust auto-recovery"
  - "Probe-alive precondition is IMPLICIT, not re-checked. Justification: if probe fails earlier in the same _run iteration, that branch `continue`s before reaching the watchdog gate. Re-checking probe would double the :80 traffic for no information gain"
  - "Event payload schema: ok, consecutive_fails, status_code on success; +error on failure. status_code=0 means no HTTP response was received (network error). Consumers can grep for ok=False to count failure events"
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 3
  tasks_completed: 3
  files_created: 3
  files_modified: 3
  tests_added: 9
---

# Phase 21A Plan 08: Watchdog Hotfix Summary

Mic stream auto-restart watchdog. When ESP32 firmware's `:81` web-server deadlocks on stale audio sockets (4-slot limit + keepalive-death zombies, see CLAUDE.md gotcha), MicReader now sends `POST :80/api/system/stream/restart` automatically after N consecutive failures, bringing the voice pipeline back online within ~60 sec instead of waiting indefinitely for human intervention.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| `services.asr.esp_stream_restart_after_fails: 5` | Failure budget before watchdog fires. 0 disables feature. |
| `services.asr.esp_stream_restart_cooldown_sec: 120.0` | Minimum interval between two consecutive auto-restarts. Prevents restart-loop. |
| `MicReader._should_trigger_stream_restart(now)` | Pure predicate: enabled + fails ≥ threshold + cooldown elapsed. Unit-testable. |
| `MicReader._trigger_stream_restart()` | POST `:80/api/system/stream/restart` via existing `device.Device.stream_restart()`. Emits `mic_reader_stream_restart_triggered` event with ok/status/error fields. |
| `MicReader._last_auto_restart_t` | `perf_counter()` of last trigger; powers cooldown gate. |
| Gate inline in `_run` | Right after probe gate, before `:81/audio` open. Settles 8 sec, resets `_consecutive_fails` on success. |
| Hot-reload in `apply_config` | Both new keys re-read live — verified via PATCH `/api/config` against running Orchestrator. |
| `tests/test_mic_reader_watchdog.py` | 9 tests covering predicate (5), trigger helper (3), hot-reload (1). |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | Config keys + schema | `ccc6e5a` | Both keys added under `services.asr`, schema describes 4-slot context + cooldown reasoning |
| 2 | MicReader gate + helper | `822b9bf` | `_should_trigger_stream_restart`, `_trigger_stream_restart`, gate inline in `_run`, hot-reload in `apply_config` |
| 3 | Unit tests | `0060981` | 9 tests pass; full repo suite stays GREEN at 89/89 (excluding pre-existing memory failure) |

## Verification

```bash
$ ./.venv/bin/python -m pytest tests/test_mic_reader_watchdog.py -q
.........                                                                [100%]
9 passed in 0.11s

$ ./.venv/bin/python -m pytest tests/ -q --ignore=tests/test_memory.py
89 passed in 0.94s

# Hot-reload against running Orchestrator (port 8080):
$ curl --noproxy '*' -X PATCH http://127.0.0.1:8080/api/config \
    -H 'Content-Type: application/json' \
    -d '{"section":"services","patch":{"asr":{"esp_stream_restart_after_fails":7,"esp_stream_restart_cooldown_sec":90.0}}}'
{"ok": true, ..., "applied": {"asr": {..., "esp_stream_restart_after_fails": 7, "esp_stream_restart_cooldown_sec": 90.0}}}
```

## Decisions Made

- **Predicate extracted into a named method, not left inline.** Cleaner unit testing — tests do not need to mock asyncio.run + urlopen + probe; they just set `_consecutive_fails` and `_last_auto_restart_t`, then call the predicate with a synthetic `now`.
- **8 sec settle sleep is hardcoded, not Config-driven.** Observed ESP32-S3 `:81` web-server boot time is ~4-6 sec; 8 sec gives comfortable margin without being a tunable knob that operators would forget about. If production reveals different timing on different ESP hardware, promote to Config in a future revision.
- **`_consecutive_fails` resets to 0 ONLY when the restart POST itself succeeds.** If POST fails (ESP fully dead), counter keeps climbing — next iteration goes through normal probe → backoff path. This preserves the existing "ESP fully dead = wait indefinitely" semantics for that pathological case; the watchdog only helps when ESP is half-dead (control plane alive, stream server stuck).
- **`perf_counter()`, not wall-clock.** Immune to NTP skew, RTC drift, operator clock changes. Cooldown is "time since last restart in process lifetime" — exactly what we want.
- **Probe-alive precondition is implicit.** The probe gate (D-19) already runs earlier in the same `_run` iteration; if probe fails, that branch `continue`s before we ever reach the watchdog gate. Re-checking probe here would double `:80` traffic for zero information gain.
- **Watchdog disables itself when threshold=0.** Explicit kill-switch for operators who don't trust auto-recovery — bypasses the entire mechanism via Config without touching code.
- **Cooldown 120 sec, not 60 or 300.** Per user direction. 60 risks restart spam while ESP firmware is still booting `:81` after the previous restart; 300 is too conservative for exhibition (5 min of silence is unacceptable). 120 sec is comfortably above observed reboot time (~10 sec) and below user-noticeable downtime threshold.

## Deviations from Plan

None — all 3 tasks executed exactly as planned. 9 tests, threshold 5, cooldown 120, hot-reload verified against live Orchestrator.

## Deferred Issues

- **Cap on total restarts per session.** Currently unlimited — if ESP firmware is in a persistent bad state, watchdog will fire every 120 sec forever (1 POST + 8 sec sleep every 2 min). This is mild — ~30 restart events/hour worst case — and beats voice pipeline silence, but operator monitoring should grep `mic_reader_stream_restart_triggered` events with `ok=False` to detect "stuck" mode. If exhibition reveals this needs hard-capping, add `esp_stream_restart_max_per_hour` in a future revision.
- **Settle-sleep duration is not Config-driven.** Hardcoded 8 sec. Promote to Config if different ESP hardware needs different timing.
- **No telemetry on restart effectiveness.** Currently we emit the trigger event but do not correlate "did the next `:81/audio` open succeed". A follow-up could compute `restart_recovery_rate = (next_open_succeeded / restarts_fired)` over a rolling window — useful for tuning threshold. Out of scope for this hotfix.

## Self-Check: PASSED

- `services.asr.esp_stream_restart_after_fails` and `esp_stream_restart_cooldown_sec` present in `System/Config.json` with defaults 5 and 120.0 — VERIFIED via `python3 -c "import json; ..."`
- Schema documents both keys with descriptions covering ESP firmware 4-slot context — VERIFIED via grep on `Config.schema.json`
- `_trigger_stream_restart` method exists on MicReader and is async — VERIFIED via `grep` and `_make_mr().` introspection in tests
- `_should_trigger_stream_restart` predicate covers all 4 branches (disabled, below-threshold, cooldown, fires) — VERIFIED by 5 dedicated tests
- Hot-reload via `apply_config` works — VERIFIED both in unit test AND via PATCH `/api/config` against running Orchestrator
- Full repo pytest suite stays GREEN at 89/89 (excluding pre-existing `test_memory.py::test_semantic_roundtrip` failure unrelated to this plan)
- No regression in `tests/test_mic_reader_spectrum.py` — 7/7 still GREEN
- All 3 git commits land cleanly on V-S09.1-Audio_out, working tree clean after task 3
