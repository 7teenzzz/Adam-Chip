---
phase: 42-webui-reorganization
plan: "07"
subsystem: WebUI
tags: [esp32, subsystem-page, diagnostics, metrics, pca9685, module-health]
dependency_graph:
  requires: [01]
  provides: [system-esp32-page, diagnostics-split]
  affects:
    - System/WebUI/static/js/panels/metrics.js
    - System/WebUI/static/js/panels/system/esp32.js
    - System/WebUI/static/js/panels/diagnostics/metricsLogs.js
    - System/WebUI/static/js/panels/diagnostics/systemHealth.js
    - System/WebUI/static/js/panels/diagnostics/esp32Health.js
tech_stack:
  added: []
  patterns: [sub-tab-bar, addrRow, moduleGrid, renderFieldRow+fieldInput+saveConfigField, thin-wrapper-panel]
key_files:
  created:
    - System/WebUI/static/js/panels/system/esp32.js
    - System/WebUI/static/js/panels/diagnostics/metricsLogs.js
    - System/WebUI/static/js/panels/diagnostics/systemHealth.js
    - System/WebUI/static/js/panels/diagnostics/esp32Health.js
  modified:
    - System/WebUI/static/js/panels/metrics.js
decisions:
  - "esp32.js's mcu config card adds flora_timeout_sec alongside the existing settings.js SCHEMA fields (base_url/speaker_url/timeout_sec/idle_scene) — plan explicitly called for it and Config.json defines mcu.flora_timeout_sec=3"
  - "fieldInput/renderFieldRow/saveConfigField copied as a text/number/bool-only subset (no audiodevice/select/enum/textarea/csv_array variants) — esp32.js's mcu/safety/sounds fields don't need those types"
  - "Моторный слой reads channel bounds (min/max/value_min/value_max) from config.mcu.channels at render time instead of hardcoding 0-15/0-4095, so safety.Config changes are reflected"
  - "systemHealth.js renders power+services from /api/agent/status plus a 'Раздел в разработке / Содержимое появится в следующей фазе' placeholder card (D-13 deferred scope)"
  - "esp32Health.js copies moduleGrid/MODULE_ORDER/MODULE_LABELS/dot verbatim from subsystem.js per plan, including its pre-existing m?.ok/m?.error assumption — modules from /api/ui/status are plain booleans, so this card currently shows all rows as 'bad'; out of scope for this plan, same dead-path class as the 42-04 flora cards"
requirements-completed: [WEBUI-R02, WEBUI-R06]
metrics:
  duration_minutes: 35
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
  completed_date: "2026-06-14"
---

# Phase 42 Plan 07: ESP32 subsystem page + diagnostics split + prompts→metrics migration

**Adds the ESP32 subsystem page (`#/system/esp32`) with three sub-tabs (Общие настройки / Моторный слой / Сенсорный слой), splits the old diagnostics panel into `metricsLogs`/`systemHealth`/`esp32Health`, and migrates the `recent_episodic` inline list from `prompts.js` to `metrics.js`.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3
- **Files modified:** 5

## Accomplishments

- `metrics.js` gains `inlineList(items)` and renders `item.recent_episodic` under the injection badges in each prompt-turn card — same content that previously lived only in `prompts.js`.
- New `panels/system/esp32.js`: sub-tab bar (UI-SPEC §6 pattern) with three tabs:
  - **Общие настройки** — ESP32 address rows (base_url/speaker_url/camera/mic streams) from `/api/ui/status`, plus editable `card-grid` for `config.mcu` (base_url, speaker_url, timeout_sec, idle_scene, flora_timeout_sec), `config.safety` (half_duplex_mute, motor_default_duration_ms, motor_max_duration_ms, motor_cooldown_ms), `config.sounds` (enabled, success_path, local_output_device) — each field auto-saves via `saveConfigField` → `PATCH /api/config`.
  - **Моторный слой** — 16 PCA9685 channel rows (bounds read from `config.mcu.channels`), numeric input + "Применить" button → `POST /api/ui/pca/channel {channel, mode:"pwm", value}`.
  - **Сенсорный слой** — read-only camera/mic/light(TEMT6000)/PIR status rows from `/api/ui/status.modules`.
- New `panels/diagnostics/metricsLogs.js` — thin wrapper mounting `metrics.js` + `logs.js` into one panel with combined teardown.
- New `panels/diagnostics/systemHealth.js` — power gate (nvpmodel/jetson_clocks) + per-service health grid from `/api/agent/status`, plus a "Раздел в разработке / Содержимое появится в следующей фазе" placeholder card for deferred content (D-13).
- New `panels/diagnostics/esp32Health.js` — `moduleGrid`/`MODULE_ORDER`/`MODULE_LABELS`/`dot` copied verbatim from `subsystem.js`, rendering ESP32 module status from `/api/ui/status.modules`.

## Task Commits

1. **Task 1: metrics.js — migrate recent_episodic inline list from prompts.js** - `dbac540` (feat)
2. **Task 2: panels/system/esp32.js — ESP32 subsystem page with 3 sub-tabs** - `7482509` (feat)
3. **Task 3: panels/diagnostics/{metricsLogs,systemHealth,esp32Health}.js** - `2a7e251` (feat)

## Files Created/Modified

- `System/WebUI/static/js/panels/metrics.js` - added `inlineList(items)`; `promptTurnRow` now renders `item.recent_episodic` under the injection badges
- `System/WebUI/static/js/panels/system/esp32.js` (new) - ESP32 subsystem page, 3 sub-tabs (Общие настройки / Моторный слой / Сенсорный слой), 382 lines
- `System/WebUI/static/js/panels/diagnostics/metricsLogs.js` (new) - thin wrapper over `metrics.js` + `logs.js`
- `System/WebUI/static/js/panels/diagnostics/systemHealth.js` (new) - power/services health + deferred-content placeholder
- `System/WebUI/static/js/panels/diagnostics/esp32Health.js` (new) - `moduleGrid` ESP32 module-status card

## Decisions Made

- Added `flora_timeout_sec` to the mcu config card beyond the existing settings.js SCHEMA group, per the plan's explicit field list and `Config.json.mcu.flora_timeout_sec`.
- Wrote a minimal `fieldInput`/`renderFieldRow`/`saveConfigField` (text/number/bool only) inside `esp32.js` rather than importing the full `settings.js` versions, since the latter pulls in audio-device/voice/select/enum/textarea/csv_array branches not needed here and `settings.js` does not export these helpers.
- `esp32Health.js` keeps `moduleGrid`'s existing `m?.ok`/`m?.error` shape assumption (copied verbatim from `subsystem.js` as the plan requires), even though `/api/ui/status.modules` currently returns plain booleans rather than `{ok, error}` objects — this is a pre-existing dead-path issue shared with `subsystem.js` itself, out of scope for this plan.

## Deviations from Plan

None — plan executed exactly as written (Task 1 verified, then Tasks 2 and 3 written directly to match each task's verify command).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `#/system/esp32` is ready to be wired into the router/nav for Wave 4 (42-08 dead-code cleanup of `subsystem.js`, `scene.js`, `prompts.js`, and `router.js`/`main.js` updates).
- `#/diagnostics/*` three-panel split is ready for the same router wiring; old `subsystem.js`/`prompts.js` content this plan duplicated from can now be removed in 42-08 once the new panels are registered.
- Backlog item (not part of this plan, noted for 42-08 or later): `modules` shape mismatch between `/api/ui/status` (`_module_flags` returns plain booleans) and `moduleGrid`'s expected `{ok, error}` per-module objects — affects both `subsystem.js` and the new `esp32Health.js`.
