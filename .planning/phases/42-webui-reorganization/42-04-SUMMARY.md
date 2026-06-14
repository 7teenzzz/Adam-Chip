---
phase: 42-webui-reorganization
plan: "04"
subsystem: WebUI
tags: [flora, technoflora, flora-table, FloraStore, Flora.json]
dependency_graph:
  requires: [01]
  provides: [flora-states-table, flora-config-write-endpoint]
  affects: [System/WebUI/static/js/panels/flora.js, System/Orchestrator.py, System/WebUI/static/css/components.css]
tech_stack:
  added: []
  patterns: [flora-table-row, btn-icon-preview, post-flora-config-states]
key_files:
  created: []
  modified:
    - System/WebUI/static/js/panels/flora.js
    - System/Orchestrator.py
    - System/WebUI/static/css/components.css
decisions:
  - "GET /api/flora/config now also returns raw_states (live FloraStore states dict) — table rows read their initial values from here, not from the stale Config.json `flora` section"
  - "Global card (enabled/max_duty_pct/crossfade_ms), Речь and Вибро cards keep reading/writing via /api/config section=flora — out of scope for this plan, pre-existing dead-path issue unchanged (flagged for backlog)"
  - "hasBase = stateKey !== 'attentive' (simpler than old base_pct-presence heuristic)"
  - "peak_pct slider initValue clamped with Math.min(stateData.peak_pct ?? 50, 71) so values >71 in Flora.json don't overflow the max=71 slider"
requirements-completed: [WEBUI-R07]
metrics:
  duration_minutes: 25
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
  completed_date: "2026-06-14"
---

# Phase 42 Plan 04: Технофлора — states table + Flora.json write path

**Replaced the 5 per-state preset cards on #/flora with a single flora-table (D-11) and fixed the dead save path so state edits actually reach Flora.json/FloraStore.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments
- New `POST /api/flora/config { states: {...} }` endpoint deep-merges into Flora.json via `FloraStore.apply_patch` + `.save()`, with `ValidationError` → HTTP 400.
- `GET /api/flora/config` now also returns `raw_states` (live `current_dict()["states"]`).
- `flora.js` renders the 5 states (breathe/accent/attentive/think_pulse/wake_bloom) as one `<table class="flora-table">`: Состояние | База | Пик (≤71%) | Скорость (+ `.speed-label` real field name) | Вибро | Показать сейчас.
- `peak_pct` slider hard-capped at max=71 (T-42-07); attentive has no Base control and a disabled Вибро checkbox; think_pulse Вибро renders as a read-only "2×" badge (`double_pulse`).
- Both "Показать сейчас" (per-row) and "Сохранить все состояния" (table-wide) save through `POST /api/flora/config`, fixing Pitfall #4 (old code wrote to the dead `flora` section of Config.json via `/api/config`).

## Task Commits

1. **Task 1: Backend — POST /api/flora/config writes states into Flora.json** - `be293da` (feat)
2. **Task 2: flora.js — states table replaces 5 preset cards** - `9a73efe` (feat)

## Files Created/Modified
- `System/Orchestrator.py` - new `POST /api/flora/config` (states write, deep-merge + save); `GET /api/flora/config` now returns `raw_states`
- `System/WebUI/static/js/panels/flora.js` - `buildStateCard` → `buildStateRow`; states card-grid loop → `flora-table` + "Сохранить все состояния" button; mount() fetches `raw_states` from `/api/flora/config`
- `System/WebUI/static/css/components.css` - `.flora-table`, `.flora-table th/td`, `.speed-label`, `.flora-table input[type="range"]`

## Decisions Made
- Kept the existing `/api/config section=flora` read/write path for the Глобальные / Речь / Вибро / emotion_map / presets / sequences sections of the panel — only the 5-state table's read+write path was redirected to FloraStore, per the plan's `files_modified` scope (flora.js + Orchestrator.py) and the D-12 "don't touch presets/sequences/emotion_map" constraint. The global card's dead Config.json round-trip is a pre-existing issue, unchanged by this plan.
- `STATE_SPEED` / `STATE_LABELS` / `STATE_KEYS` / `makeSlider` / `makeToggle` kept verbatim as required.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `#/flora` states table is live and writes to Flora.json; ESP32 preview via `POST /api/flora/state` unchanged.
- Backlog item (not part of this plan): Глобальные/Речь/Вибро cards on `#/flora` still round-trip through the dead `Config.json` `flora` section via `/api/config` — a future cleanup phase could route these through `FloraStore` (the `FloraConfig` model already has `enabled`/`max_duty_pct`/`crossfade_ms`/`speech`/`vibro` top-level fields) and remove the stale `flora` key from `Config.json`/`Config.schema.json`.

---
*Phase: 42-webui-reorganization*
*Completed: 2026-06-14*
