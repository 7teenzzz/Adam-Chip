---
phase: 21A
plan: 08
type: hotfix
wave: 6
depends_on: [03]
files_modified:
  - System/Config.json
  - System/Config.schema.json
  - System/adam/mic_reader.py
  - tests/test_mic_reader_watchdog.py
autonomous: true
requirements:
  - UI-EQ-RESILIENCE
must_haves:
  truths:
    - "After N consecutive `:81/audio` open failures, MicReader sends POST `:80/api/system/stream/restart` automatically — without operator intervention"
    - "Threshold N and cooldown between restart attempts are Config-driven (no hardcoded values)"
    - "Auto-restart only fires when probe of `:80/api/status` returns OK — otherwise ESP control plane is dead and restart wouldn't work"
    - "Cooldown prevents restart-loop: same restart cannot fire twice within `esp_stream_restart_cooldown_sec` seconds even if fails keep climbing"
    - "After successful restart trigger, `_consecutive_fails` resets to 0 — fresh retry cycle"
    - "Event `mic_reader_stream_restart_triggered` emitted with ok/status/error fields for diagnostics"
    - "Hot-reload of both new keys works via PATCH /api/config — no Orchestrator restart needed"
  artifacts:
    - path: "System/Config.json"
      provides: "Two new keys under services.asr — esp_stream_restart_after_fails (default 5), esp_stream_restart_cooldown_sec (default 120.0)"
      contains: "esp_stream_restart_after_fails"
    - path: "System/Config.schema.json"
      provides: "Schema documentation for both new keys"
      contains: "esp_stream_restart_cooldown_sec"
    - path: "System/adam/mic_reader.py"
      provides: "Auto-restart gate in `_run` + helper `_trigger_stream_restart`"
      contains: "_trigger_stream_restart"
    - path: "tests/test_mic_reader_watchdog.py"
      provides: "Unit tests for restart trigger threshold + cooldown"
      contains: "test_restart_fires_after_threshold, test_restart_respects_cooldown, test_restart_resets_fail_counter"
  key_links:
    - from: "MicReader._run"
      to: "MicReader._trigger_stream_restart"
      via: "method call when consecutive_fails >= esp_stream_restart_after_fails and cooldown elapsed"
      pattern: "self\\._trigger_stream_restart\\("
    - from: "MicReader._trigger_stream_restart"
      to: "Device.stream_restart"
      via: "POST :80/api/system/stream/restart through MCU client"
      pattern: "self\\._mcu\\.stream_restart\\("
---

<objective>
Mic stream auto-restart watchdog. Today when ESP32 firmware's :81 web-server deadlocks on stale audio sockets (4-slot limit per CLAUDE.md gotcha), MicReader retries `:81/audio` forever with backoff — but never breaks the deadlock. Operator must SSH in and POST `/api/system/stream/restart` by hand. This plan automates that step inside MicReader so the voice pipeline self-recovers within ~60 sec instead of indefinitely.

Triggers, scope, and bounds:
- Trigger: `_consecutive_fails >= esp_stream_restart_after_fails` (default 5) on `:81/audio` open
- Gate: ESP `:80/api/status` must be alive (probe via `_probe_esp_status` already in `_run`) — otherwise restart is wasted
- Cooldown: hard minimum of `esp_stream_restart_cooldown_sec` (default 120) between two consecutive restart triggers — prevents restart-loop while ESP firmware takes ~8-15 sec to bring `:81` server back up
- After restart: sleep 8 sec for ESP web-stack settle, reset `_consecutive_fails` to 0, loop back to `:81/audio` open
- Cost in steady-state (stream healthy): zero. The gate is checked only when fails >= threshold, which never happens when stream is open.
</objective>

<tasks>

### Task 1: Add 2 new Config keys + schema documentation

**Files:** `System/Config.json`, `System/Config.schema.json`

Add under `services.asr`:
```json
"esp_stream_restart_after_fails": 5,
"esp_stream_restart_cooldown_sec": 120.0
```

Schema descriptions must explain the watchdog semantics, default rationale, and ESP firmware 4-slot limit context.

**Verify:**
```bash
python3 -m json.tool < System/Config.json > /dev/null     # valid JSON
python3 -m json.tool < System/Config.schema.json > /dev/null
python3 -c "import json; assert 'esp_stream_restart_after_fails' in json.load(open('System/Config.json'))['services']['asr']"
```

### Task 2: Implement `_trigger_stream_restart` + auto-restart gate in `_run`

**Files:** `System/adam/mic_reader.py`

1. Read both keys in `__init__` from `asr_cfg`. Add state `_last_auto_restart_t: float = 0.0`.
2. Read both keys in `apply_config` (hot-reload).
3. Add helper `async def _trigger_stream_restart(self) -> bool` that calls `self._mcu.stream_restart()` and emits `mic_reader_stream_restart_triggered` event with `ok`, `status_code`, `consecutive_fails`, optional `error` fields.
4. In `_run`, after the existing probe gate (around line 962-976), add auto-restart gate:
   - Pre-condition: `_esp_stream_restart_after_fails > 0` (0 disables feature)
   - Trigger when: `_consecutive_fails >= _esp_stream_restart_after_fails` AND `(perf_counter() - _last_auto_restart_t) >= _esp_stream_restart_cooldown_sec`
   - On trigger: update `_last_auto_restart_t = perf_counter()`, await `_trigger_stream_restart()`, sleep 8 sec, on success reset `_consecutive_fails = 0`, `continue` outer loop
5. The gate runs ONLY after probe succeeded — that's already implicit because if probe fails the `continue` above runs first.

**Verify:**
```bash
grep -c "_trigger_stream_restart\|_last_auto_restart_t\|esp_stream_restart_after_fails" System/adam/mic_reader.py    # >= 6 occurrences
./.venv/bin/python -c "from System.adam.mic_reader import MicReader; print('import ok')"
```

### Task 3: Unit tests

**Files:** `tests/test_mic_reader_watchdog.py`

Tests:
- `test_restart_fires_after_threshold` — simulate 5 fails (set `_consecutive_fails`), call probe gate manually or run one `_run` iteration with stubbed MCU; assert `mcu.stream_restart` was called once.
- `test_restart_respects_cooldown` — fire restart once, simulate 5 more fails before cooldown elapsed, assert restart NOT called second time.
- `test_restart_resets_fail_counter` — after successful restart, `_consecutive_fails == 0`.
- `test_restart_disabled_when_threshold_zero` — when `esp_stream_restart_after_fails=0`, restart never fires regardless of fail count.

**Verify:**
```bash
./.venv/bin/python -m pytest tests/test_mic_reader_watchdog.py -x -q
```

All 4 tests pass.

</tasks>

<acceptance_criteria>
- [ ] Both Config keys present in Config.json (defaults 5 and 120.0) and Config.schema.json (with descriptions)
- [ ] `_trigger_stream_restart` method exists on MicReader and emits `mic_reader_stream_restart_triggered` event
- [ ] Auto-restart gate is invoked from `_run` AFTER the existing probe gate
- [ ] Cooldown enforced via `_last_auto_restart_t` instance state
- [ ] 4 unit tests in `tests/test_mic_reader_watchdog.py` pass
- [ ] Full pytest suite still green (no regression)
- [ ] PATCH `/api/config` with these keys triggers hot-reload (apply_config picks them up)
- [ ] In steady state (no fails) gate is never entered — zero perf cost
</acceptance_criteria>
