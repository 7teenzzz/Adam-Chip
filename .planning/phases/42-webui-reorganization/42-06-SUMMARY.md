---
phase: 42-webui-reorganization
plan: "06"
subsystem: WebUI
tags: [services, models, card-grid, vlm, dead-code-removal]
dependency_graph:
  requires: [01]
  provides: [services-models-merged-page]
  affects: [System/WebUI/static/js/panels/system/servicesModels.js]
tech_stack:
  added: []
  patterns: [card-grid, field-grid, field-wide, disposables-teardown, SERVICE_META]
key_files:
  created:
    - System/WebUI/static/js/panels/system/servicesModels.js
  modified: []
decisions:
  - "SERVICE_META covers llm/tts/asr/vlm (adam-vlm.service, :8051) — dead VILA1.5-3b card (buildVlmCard, /api/live_vlm/*) fully removed, not just hidden"
  - "Invalid fields dropped from SCHEMA: keep_alive (LLM), riva (ASR provider option), reply_absolute_deadline_sec (ASR); duplicate vad_onset/vad_offset entries de-duplicated to one each; stale VLM hint :8084 corrected to :8051"
  - "Model cards rendered below the service-card grid under a 'Модели и параметры' caption — mount() fetches /api/config + /api/tuning via Promise.allSettled and calls buildModelCards(config, tuning), appending the returned card-grid into a dedicated container with its own loading/error states"
  - "Service refresh (setInterval 5000ms, serviceCards.refresh()) and model-card load (one-shot on mount) are independent — model fields don't need 5s polling"
requirements-completed: [WEBUI-R02, WEBUI-R04]
metrics:
  duration_minutes: 25
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
  completed_date: "2026-06-14"
---

# Phase 42 Plan 06: Сервисы и модели — объединённая страница (3.2)

**Merged services.js (systemd service management for llm/tts/asr/vlm) with models.js + settings.js LLM/TTS/ASR/VLM field cards into one `#/system/services` page, removed the dead VILA1.5-3b Docker card and invalid config fields, added adam-vlm.service to SERVICE_META, and fixed the stale :8084 VLM hint to :8051.**

## Performance
- **Duration:** ~25 min
- **Tasks:** 2/2
- **Files modified:** 1 (new file)

## Accomplishments
- New `System/WebUI/static/js/panels/system/servicesModels.js` (487 lines), exporting `mount(target)` → teardown:
  - `SERVICE_META` for llm/tts/asr/vlm, each rendered via `buildServiceCard(name, meta)` with start/stop/restart buttons, `dot()` status indicator, refreshed every 5s.
  - Dead `buildVlmCard()` (Docker VILA1.5-3b, `/api/live_vlm/*`) removed entirely.
  - `SCHEMA` of 9 config/tuning field-card groups: Агент, LLM·инфраструктура, LLM·runtime, Сборка промта, Голос runtime, TTS·Silero, TTS·Филлер, ASR·WhisperX, VLM·описание сцены.
  - Invalid fields removed: `keep_alive`, `riva` ASR provider option, `reply_absolute_deadline_sec`; duplicate `vad_onset`/`vad_offset` collapsed to single entries; VLM hint corrected `:8084` → `:8051`.
  - `mount()` fetches `/api/config` + `/api/tuning` via `Promise.allSettled`, then calls `buildModelCards(config, tuning)` and appends the resulting `card-grid` below the service cards under a "Модели и параметры" caption, with its own loading/error states (separate from the 5s service-refresh loop).

## Task Commits
1. **Task 1: services panel — buildServiceCard for llm/tts/asr/vlm, remove dead VILA card** - `8dba04e` (feat)
2. **Task 2: render model field cards (SCHEMA groups) + fetch config/tuning in mount()** - `36236d0` (feat)

## Files Created/Modified
- `System/WebUI/static/js/panels/system/servicesModels.js` (new, 487 lines) - merged Сервисы и модели page (3.2)

## Decisions Made
- Model cards live in a separate container below the service-card grid, populated by a one-shot async fetch in `mount()` — kept independent from the 5s `refreshAll()` service-status polling since config/tuning fields don't need that cadence.
- adam-vlm.service added to `SERVICE_META` alongside llm/tts/asr, replacing the old Docker-based VILA card.

## Deviations from Plan
None — plan executed exactly as written. (Task 2 was initially written without wiring `mount()` to `buildModelCards()`/config-tuning fetch; this was caught during verification and fixed before commit.)

## Issues Encountered
- `node --check` on this ES module fails directly (`Cannot use import statement outside a module` under Node 18 CommonJS default) — verified via a `.mjs` copy instead. Same caveat applies to all other panel files; not specific to this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `#/system/services` is fully functional; old `services.js`/`models.js` routes remain in ROUTES until Wave 4 (42-08) dead-code cleanup.
- Verification command from the plan passes: `node --check` (via .mjs copy) ok, contains `8051`, contains `services.llm|tts|asr|vlm`, no `keep_alive`/`reply_absolute_deadline_sec`/`8084`/`riva`.

---
*Phase: 42-webui-reorganization*
*Completed: 2026-06-14*
