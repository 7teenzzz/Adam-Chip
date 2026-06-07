---
phase: 29-technoflora-reactions
plan: 02
subsystem: infra
tags: [config, flora, technoflora, pca9685, gamma, rms, pytest, config-first]

# Dependency graph
requires:
  - phase: 29-technoflora-reactions (plan 01)
    provides: firmware FloraModule channel masks + gamma defaults (AdamsConfig.h) — structural counterpart to this Config section
provides:
  - Top-level `flora` config section in Config.json (channels, gamma, crossfade, speech RMS params, vibro policy, 5 state presets)
  - Mirrored `flora` default in DEFAULT_CONFIG so settings.section("flora") always returns sane values
  - Full Config.schema.json documentation of every flora numeric (English descriptions + defaults)
  - tests/test_flora.py — Wave 0 test scaffold with test_flora_config active + 3 skip stubs + _make_sine_wav helper
affects: [29-03 (FloraController event mapping), 29-04 (RMS speech sync)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Plain top-level config section (flora) read via settings.section() — NOT pydantic tuning"
    - "Wave 0 single-home test file: active test + skip stubs reserving names for later plans"

key-files:
  created:
    - tests/test_flora.py
    - .planning/phases/29-technoflora-reactions/deferred-items.md
  modified:
    - System/Config.json
    - System/Config.schema.json
    - System/adam/config.py

key-decisions:
  - "flora is a plain section (settings.section('flora')), not pydantic tuning — RESEARCH Pitfall 6"
  - "Mirror flora into DEFAULT_CONFIG so the section has a code-level default independent of Config.json"
  - "test_flora_config is GREEN immediately because the config section is its artifact (config-validation, not new runtime behavior)"

patterns-established:
  - "Config-First flora: every flora number lives in Config.json + Config.schema.json (D-13), nothing hardcoded"
  - "Wave 0 test scaffold: stable test names now (test_event_mapping/test_vibro_silent_listening/test_rms_envelope) filled by plans 03/04"

requirements-completed: [FLORA-05]

# Metrics
duration: 12min
completed: 2026-06-04
---

# Phase 29 Plan 02: Config-First Flora Section Summary

**Top-level `flora` config section (channel masks light 0-10 / vibro 11-14, gamma 2.2, crossfade, speech RMS duties, vibro silent-states, 5 state presets) in Config.json + DEFAULT_CONFIG + fully documented in Config.schema.json, with the Wave 0 pytest scaffold (test_flora_config green, 3 stubs reserved).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-04T20:00:00Z (approx)
- **Completed:** 2026-06-04
- **Tasks:** 2
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments
- Added the Config-First `flora` section (FLORA-05) — the Jetson-side source of truth for the technoflora animation engine.
- Channel masks D-02 (light [0..10], vibro [11,12,13,14]), gamma 2.2 (D-13), crossfade 200ms (D-09), speech RMS params base/peak 25/90 (D-08) + HDMI offset + frame interval + spark probability (D-07), vibro intensity 30% restrained with silent_states ["attentive"] (D-11/D-12), and start defaults for all 5 presets (breathe / accent / attentive / think_pulse / wake_bloom).
- Mirrored the same section into DEFAULT_CONFIG (config.py) so `settings.section("flora")` returns defaults even without Config.json.
- Documented every flora numeric in Config.schema.json with English descriptions + defaults, matching the existing mcu/media.audio convention; noted the firmware-side AdamsConfig.h duplication.
- Created tests/test_flora.py as the single Wave 0 home: `test_flora_config` active and green; `test_event_mapping` (FLORA-03), `test_vibro_silent_listening` (FLORA-06), `test_rms_envelope` (FLORA-04) reserved as skip stubs; `_make_sine_wav` stdlib helper for plan 04.

## Task Commits

Each task was committed atomically:

1. **Task 1: flora section in Config.json + DEFAULT_CONFIG + schema** - `77af3fb` (feat)
2. **Task 2: Wave 0 test scaffold tests/test_flora.py + test_flora_config** - `4256019` (test)

_Note: Task 2 is TDD-tagged but config-validation only — the behavior under test (the flora section) is Task 1's artifact, so the test went GREEN on first run (no separate RED commit; documented under TDD Gate Compliance below)._

## Files Created/Modified
- `System/Config.json` - Added top-level `flora` section after `mcu`.
- `System/adam/config.py` - Mirrored `flora` into DEFAULT_CONFIG for code-level default.
- `System/Config.schema.json` - Documented the full `flora` schema (gamma, crossfade, speech.*, vibro.*, states.*).
- `tests/test_flora.py` - Wave 0 scaffold: test_flora_config + 3 skip stubs + _make_sine_wav.
- `.planning/phases/29-technoflora-reactions/deferred-items.md` - Logged 1 pre-existing out-of-scope test failure + audioop deprecation.

## Decisions Made
- **Plain section, not pydantic tuning** (RESEARCH Pitfall 6): flora params are infrastructure/calibration, same tier as `mcu`/`services`/`safety`; read via `settings.section("flora")`.
- **DEFAULT_CONFIG mirror**: gives a code-level default so the section is robust even if Config.json lacks it.
- **Insertion point**: placed `flora` after `mcu` (the closest structural analog — both are PCA9685/channel-oriented sections).
- **Test import style**: `sys.path.insert(ROOT/"System")` like tests/test_memory.py, so the test runs on Windows without depending solely on PYTHONPATH.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

Task 2 carried `tdd="true"`. Per the TDD fail-fast rule, the test was expected to pass once the config section existed. Because FLORA-05 is a **config-validation** requirement (assert the parsed section's shape/defaults) and the section is the artifact of Task 1, `test_flora_config` passed on first run — there is no behavior code to drive RED→GREEN. This is the documented config-only exemption (no non-test source file is under test by `test_flora_config`). The 3 sibling stubs (FLORA-03/04/06) are skips that plans 03/04 turn into real RED→GREEN cycles. No gate violation.

## Issues Encountered
- Full-suite run surfaced one **pre-existing, unrelated** failure: `tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip` (`AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`). Verified unrelated to this plan (memory-module API drift; this plan touched only config + flora test). Logged to deferred-items.md; NOT fixed (out of scope). All other 98 tests pass; flora tests: 1 passed, 3 skipped.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (FloraController event layer, FLORA-03/06) can read `settings.section("flora")` for channel masks, presets, and vibro silent_states; `test_event_mapping` and `test_vibro_silent_listening` names are reserved and ready to fill.
- Plan 04 (RMS speech sync, FLORA-04) has `flora.speech.*` params (frame_interval_ms, hdmi_latency_offset_ms, base/peak duties, spark_probability) and the `_make_sine_wav` helper + `test_rms_envelope` stub ready.

## Self-Check: PASSED

All created/modified files exist on disk; both task commits (`77af3fb`, `4256019`) present in git history.

---
*Phase: 29-technoflora-reactions*
*Completed: 2026-06-04*
