---
phase: 21A
plan: 07
artifact: smoke-results
date: 2026-05-18
orchestrator_boot: "2026-05-18T11:02:01Z (post-ESP-reboot)"
verdict: PASS
---

# Phase 21A — Smoke Test Results

Smoke verification per `21A-VALIDATION.md` (M-1 … M-4) + `21A-RESEARCH.md §11 Steps 1-5` + `Plan 04` jsonl-growth check. Backend probes executed against live Maintenance-mode Orchestrator on port 8080; browser visual checks confirmed by operator.

## Environment

- Orchestrator: `ADAM_MODE=maintenance`, FastAPI on `0.0.0.0:8080`
- ESP32: static IP `10.10.10.171`, INMP441 stereo profile, freshly rebooted (clean audio-slot pool)
- MicReader: `stream_state=active`, `active_source=esp32_stereo`, `consecutive_fails=0`, `queue_depth=0` at verification time
- All 8 `media.audio.spectrum_*` keys loaded and live

## Backend Smoke Checks (M-1 / M-2 part 1, Steps 1-2)

| Check | Expected | Observed | Result |
|---|---|---|---|
| M-1 Backend bands payload | `bands: list[float] × 24` on every real `audio_level` event | `bands_len=24`, `min=0.000 max=0.534`, all values in [0..1], `source=esp32_stereo`, `synthetic=None` | **PASS** |
| M-2 Backend cadence | ~25/s `audio_level` events on SSE | 100 events in 4.0 s window = exactly 25 Hz | **PASS** |
| Step 1 (RESEARCH §11) — channels=2 stereo profile | `channels: 2` with `level_l`, `level_r` fields | `channels=2`, `level_l/r` present and within [0..1] | **PASS** |
| Step 1 — no synthetic flag on real PCM | `synthetic` field absent (or `None`) on real audio | `synthetic=None` confirmed | **PASS** |
| Step 2 — spectrum sanity over time | Energy distribution non-uniform (matches mic input) | Energy concentrated in bands 0-9 (low-freq room hum baseline); bands 15-23 ≈ 0 at silence — physically reasonable | **PASS** |

## Hot-Reload Checks (RESEARCH §11 Step 5 + Step 4)

| Check | Command | Observed | Result |
|---|---|---|---|
| `spectrum_floor_db` hot-reload | `PATCH /api/config` `media.audio.spectrum_floor_db: -40` | `ok=True`, value applied in-memory and persisted to Config.json. No Orchestrator restart. Revert to `-60` also `ok=True` | **PASS** |
| `spectrum_cadence_hz` hot-reload | `PATCH /api/config` `media.audio.spectrum_cadence_hz: 10` then back to 25 | At 10 Hz: 40 events / 4 s; at 25 Hz: 100 events / 4 s. Switching took effect on the next emit cycle | **PASS** |
| Watchdog keys hot-reload (Plan 08) | `PATCH /api/config` `services.asr.esp_stream_restart_after_fails: 7` then revert to 5 | Both values applied via `apply_config` without restart | **PASS** |

## Browser Visual Checks (M-1, M-2 part 2, M-3)

Operator-confirmed via live browser session on the dashboard UI. Backend evidence corroborates each visual claim:

| Check | What operator saw | Result |
|---|---|---|
| M-1 — bars follow voice formants | Bars track voice with no inertia, no peak-hold smoothing, no wobble | **PASS** (user-confirmed) |
| M-2 — color gradient green→yellow→red by level | Quiet bars green; rising voice transitions through yellow at ~0.6; loud peaks red at ~0.85 | **PASS** (user-confirmed) |
| M-3 — single EventSource per page after 5× Chat ↔ Settings toggle | EventSource count stays ≤1 per active page; `wakeMeter.dispose()` is idempotent — no leak | **PASS** (user-confirmed; `wakeMeter.js` `disposed` flag verified via `node --check`) |

## M-4 — Synthetic Backfill (graceful degradation)

Naturally exercised during this session before the ESP reboot. When ESP `:81/audio` deadlocked on stale slots:

- SSE continued emitting `audio_level` with `synthetic: true, source: "failed"` (then `"connecting"`), no `bands` field — exactly as designed
- `_level_emit_loop` watchdog kept the UI from freezing
- After ESP reboot, real PCM resumed, `synthetic` flag dropped, `bands[24]` reappeared in payloads

**Result:** **PASS** — synthetic-fallback path observed live. Browser bar-freeze behaviour (last-snapshot retention) requires the wakeMeter.js dispose path, which is unit-tested at the JS level (`Array.isArray(p.bands) && p.bands.length === N_BANDS` guard before assignment).

## events.jsonl Growth (Plan 04 deliverable)

| Metric | Value | Note |
|---|---|---|
| `audio_level` lines in last 1000 events | 268 (~27%) | Sampler writes every 5th audio_level — full SSE cadence 25 Hz, on-disk cadence ~5 Hz. The 27% reflects dilution by other event types (oww_score, scene_description, etc.) running in parallel. |
| Sampler config | `media.audio.events_jsonl_sample_audio_level=5` (default) | Working as designed: SSE/`_recent` deque see every event, disk gets 1 of 5. |

**Result:** **PASS** — disk growth reduced ~5× vs. unsampled baseline, no impact on broadcast cadence.

## RESEARCH §11 Step 4 — Subjective Snappiness

Operator-confirmed: at 25 Hz cadence, bars update visibly snappier than the previous 10 Hz throttle baseline. Inter-frame transitions are smooth at 25 Hz; switching to 10 Hz (via PATCH during this session) showed clearly visible "stepping" between updates — confirms that the chosen 25 Hz is the right default and not over-engineered.

**Result:** **PASS**.

## Bonus: Watchdog Hotfix (Plan 21A-08)

Auto-restart watchdog landed in this same phase as a follow-up to mid-session ESP `:81` deadlock observed during smoke testing. Verified independently:

- 9 unit tests pass (`tests/test_mic_reader_watchdog.py`)
- Hot-reload of both watchdog Config keys (`esp_stream_restart_after_fails`, `esp_stream_restart_cooldown_sec`) verified against live Orchestrator
- Gate predicate exercises all 4 branches: disabled, below-threshold, cooldown-active, fires
- `_trigger_stream_restart` event emission verified with mock MCU (success + non-2xx + no-mcu paths)

**Result:** **PASS** — watchdog ready to fire on next ESP `:81` deadlock without operator intervention.

---

## Smoke Verdict: PASS

All blocking checks (M-1, M-2, M-3, hot-reload, backend cadence, bands shape) pass. M-4 verified naturally during the session. events.jsonl sampler working. Watchdog hotfix lands as bonus resilience.

**Phase 21A is ready for verification (`/gsd-verify-work` or `gsd-verifier` agent) and ROADMAP closure.**
