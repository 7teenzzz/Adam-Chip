---
phase: 42-webui-reorganization
plan: "05"
subsystem: WebUI
tags: [audio, video, audioAndVideo, card-full, wake-word, scene-worker]
dependency_graph:
  requires: [01]
  provides: [audio-video-merged-page]
  affects: [System/WebUI/static/js/panels/system/audioAndVideo.js, System/WebUI/static/js/panels/audioInput.js]
tech_stack:
  added: []
  patterns: [field-grid, disposables-teardown, card-grid]
key_files:
  created:
    - System/WebUI/static/js/panels/system/audioAndVideo.js
  modified:
    - System/WebUI/static/js/panels/audioInput.js
decisions:
  - "Card order: Видео (merged Видеопоток+Камера) → Микрофон и VAD → OWW · Wake word → Тайминги пайплайна → Silence calibration → audioInput's 5 cards (Volume, EQ, OWW meter, Monitor, Presets)"
  - "Volume card ('Громкость входа') uses plain 'card' class (no card-full) per D-15/WEBUI-R07; EQ/OWW meter/Monitor/Presets keep card-full (legitimate canvas widgets)"
  - "wake-word threshold field lives only in the OWW · Wake word config-schema card; audioInput's own OWW calibration card does not duplicate it"
  - "All SSE/_dispose widgets (EQ, OWW meter, Monitor) registered into a single disposables[] array drained on teardown (T-42-09)"
requirements-completed: [WEBUI-R02]
metrics:
  duration_minutes: 30
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  completed_date: "2026-06-14"
---

# Phase 42 Plan 05: Аудио и видео — объединённая страница (3.1)

**Merged audioInput.js (5 calibration cards) with settings.js audio/video field-groups into one `#/system/audio` page, fixed the card-full bug on the Volume card, and de-duplicated wake-word threshold + Видеопоток/Камера cards.**

## Performance
- **Duration:** ~30 min
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments
- `System/WebUI/static/js/panels/audioInput.js`: Volume card ("Громкость входа") class changed from `card card-full` to `card` — normal width (D-15/WEBUI-R07). Cards 2-5 (EQ, OWW meter, Monitor, Presets) untouched, still `card-full`.
- New `System/WebUI/static/js/panels/system/audioAndVideo.js` (1240 lines), exporting `mount(target)` → teardown:
  - Config-schema cards: Видео (merged Видеопоток+Камера — `media.video`), Микрофон и VAD (`media.audio`), OWW · Wake word (`wake_word`, incl. `buildWakeWordExtras()` canvas), Тайминги голосового пайплайна (`services.asr`), Воркер описания сцены (`media.scene_*`), Silence calibration (`buildSilenceCalibExtras`).
  - All 5 audioInput.js cards migrated verbatim: Volume (no card-full), Graphic EQ, OWW threshold/score meter, Monitor, Presets CRUD (D-05) — all card-full except Volume.
  - `saveConfigField`/`renderFieldRow`/`getNested`/`setNested` copied verbatim from settings.js.
  - SSE/_dispose widgets (EQ, OWW meter, Monitor) registered in `disposables[]`, drained on teardown.

## Task Commits
1. **Task 1: audioInput.js — remove card-full from volume card** - `1aa9db7` (fix)
2. **Task 2: panels/system/audioAndVideo.js — merged Audio+Video page** - `6b2af55` (feat)

## Files Created/Modified
- `System/WebUI/static/js/panels/audioInput.js` - Volume card class `card card-full` → `card`
- `System/WebUI/static/js/panels/system/audioAndVideo.js` (new, 1240 lines) - merged Аудио и видео page (3.1)

## Decisions Made
- Card ordering left to discretion (D-02): Видео → Микрофон и VAD → OWW · Wake word → Тайминги пайплайна → Silence calibration → audioInput's Volume/EQ/OWW meter/Monitor/Presets.
- wake-word `threshold` field kept in exactly one place (OWW · Wake word config-schema card); verified via grep — single occurrence.
- Видеопоток + Камера consolidated into a single "Видео" card reading/writing `media.video` (no duplicate card).

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `#/system/audio` is fully functional; old `audioInput.js` route remains in ROUTES until Wave 4 (42-08) dead-code cleanup removes it along with `settings.js`.
- `node --check` passes on the new file; `field-grid`, `media.video`, `media.audio`, `wake_word` all present.

---
*Phase: 42-webui-reorganization*
*Completed: 2026-06-14*
