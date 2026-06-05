---
phase: 21A
plan: 05
subsystem: System/WebUI/static/js/widgets / Wave 3 (frontend EQ)
tags: [equaliser, spectrum, sse, raf, color-gradient, dispose-leak]
dependency_graph:
  requires:
    - "21A-03 (Wave 2): backend MicReader emits payload.bands list[float] length 24 on audio_level events"
    - "21A-02 (Wave 1): Config.json media.audio.spectrum_color_yellow_at (0.6) and spectrum_color_red_at (0.85)"
  provides:
    - "wakeMeter.js renders 24 bars sourced DIRECTLY from ev.payload.bands — no smoothing, no decay, no wobble"
    - "colorForLevel(v, yellowAt, redAt) — piecewise green→yellow→red RGB blend, alpha = 0.35 + 0.65v"
    - "Idempotent dispose() with `disposed` flag; draw() early-returns when disposed (RAF-leak guard)"
    - "Mount-time non-blocking fetch /api/config that overrides per-instance colour thresholds"
  affects:
    - "21A-06: chat.js hint text + smoke-test of settings.js draggable wakeMeter — bars source/colour pattern is the contract"
    - "Operator UX: spectrum bars now show the same signal OWW/ASR hears (truth-by-construction)"
tech_stack:
  added: []
  patterns:
    - "Direct SSE-payload binding into a per-widget Float32Array — no intermediate decay buffer"
    - "Closure-local colour-ramp helpers (GREEN/YELLOW/RED constants, lerp, rgbBlend, colorForLevel) keep all rendering logic in one file"
    - "Defensive bands[] guard: Array.isArray(p.bands) && p.bands.length === N_BANDS — synthetic _level_emit_loop frames (which omit bands by design per 21A-03) leave the previous snapshot intact"
    - "Idempotent disposer pattern: boolean flag both gates the dispose body AND short-circuits the recurring RAF callback"
    - "Mount-time fetch /api/config with .catch(() => {}) — never blocks; defaults usable until network resolves"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-05-SUMMARY.md"
  modified:
    - "System/WebUI/static/js/widgets/wakeMeter.js"
decisions:
  - "Colour helpers placed at module level (above createWakeMeter factory) so they are not reallocated per-instance — they are pure functions of (v, yAt, rAt)"
  - "state.colorYellowAt/colorRedAt live on the state object (not module-level vars) so each widget instance can be tuned independently if a future panel wants different thresholds (e.g. an operator preview vs a public-display kiosk)"
  - "Mount-time fetch is fire-and-forget — failure is silent (defaults remain). Hot-reload of colour thresholds is OUT OF SCOPE (RESEARCH §7); a page refresh picks up new Config.json values"
  - "state.audioLevel assignment retained in audio_level handler even though the widget no longer renders it — chat.js/other panels may still read it during transitional rollout, and the cost is negligible"
  - "Floor strip (thin green rectangle row at the bottom) preserved from the legacy renderer — it gives the operator a visual baseline at silence, which the all-zeros bands[] case would otherwise leave totally blank"
  - "Per-bar threshold v < 0.01 short-circuit kept (was v < 0.008 with peaks) — at floor the bar contributes nothing visible; saves draw calls when most bands sit at the noise floor"
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 2
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 21A Plan 05: Wave 3 — Frontend EQ Refactor Summary

Wave 3 of Phase 21A — the chat-panel equaliser widget on `System/WebUI/static/js/widgets/wakeMeter.js` was rewritten to consume the real 24-band log-frequency spectrum that Plan 03 wired into `audio_level` SSE events. The widget no longer fakes a Gaussian-shaped spectrum from a scalar RMS value; every visible bar is now an honest, per-frame measurement.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| Closure-local `bands` Float32Array(24) on each widget instance | Latest spectrum snapshot — updated in place on each audio_level event that carries a valid bands[24] array. Missing/short arrays leave the previous snapshot intact. |
| Module-level `colorForLevel(v, yAt, rAt)` + `GREEN/YELLOW/RED/lerp/rgbBlend` helpers | Piecewise RGB blend: v∈[0, yAt] → green→yellow ramp, v∈[yAt, rAt] → yellow→red ramp, v≥rAt → solid red. Alpha = 0.35 + 0.65v so quiet bars stay subtle. |
| `state.colorYellowAt = 0.6` / `state.colorRedAt = 0.85` | Per-instance colour thresholds (defaults mirror Config.json). |
| Mount-time `fetch("/api/config")` overlay | Non-blocking; on success patches state.colorYellowAt/colorRedAt from `media.audio.spectrum_color_yellow_at` / `spectrum_color_red_at`. Silent on failure. |
| Rewritten `draw()` bars block | Floor strip + per-bar gradient render. No peak-hold, no decay, no wobble, no audioLevel×4 multiplier. Bars use `bands[i]` directly. |
| Extended `audio_level` handler | `if (Array.isArray(p.bands) && p.bands.length === N_BANDS) for (let i=0; i<N_BANDS; i++) bands[i] = +p.bands[i] || 0;` — defensive consumer. |
| `voice_loop_stopped` clears `bands.fill(0)` | Replaces the legacy `for (i...) peaks[i] = 0` loop. |
| `let disposed = false` flag + idempotent `dispose()` | Double-dispose is a no-op; unsub() wrapped in try/catch. |
| `draw()` early-return `if (disposed) return;` | First line of the function — fires BEFORE the recurring `requestAnimationFrame(draw)` reschedule, killing the SSE/RAF leak when panels swap mid-frame. |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | Replace EQ_SHAPE / peaks / wobble with direct bands[] consumption + color-by-level | `b239173` | All forbidden tokens (EQ_SHAPE, audioLevel*4, peaks[i]*0.87, Date.now()*0.0015) → 0 occurrences. `N_BANDS = 24`, `colorForLevel`, `Array.isArray(p.bands)` markers present. OWW score decay (`scoreDecay * 0.86`) and threshold (`setLineDash`, `rgba(240,184,74,…)`) paths untouched. ESM syntax clean. |
| 2 | Idempotent dispose() + guard draw() against post-dispose RAF re-entry | `4834ac9` | `let disposed = false` × 1, `if (disposed) return` × 2 (top of draw + top of dispose), `disposed = true` × 1 inside dispose body. External API `{ canvas, dispose, state }` unchanged. ESM syntax clean. |

## Verification

```bash
$ for t in "EQ_SHAPE" "audioLevel \* 4" "peaks\[i\] \* 0.87" "Date.now() \* 0.0015"; do
    grep -c "$t" System/WebUI/static/js/widgets/wakeMeter.js
  done
0
0
0
0

$ grep -nE "function colorForLevel|N_BANDS = 24|Array\.isArray\(p\.bands\)|let disposed = false|if \(disposed\) return|disposed = true|bands\.fill\(0\)" \
    System/WebUI/static/js/widgets/wakeMeter.js
23:const N_BANDS = 24;
40:function colorForLevel(v, yAt, rAt) {
134:  let disposed = false;
137:    if (disposed) return;
273:      if (Array.isArray(p.bands) && p.bands.length === N_BANDS) {
300:      bands.fill(0);
317:    if (disposed) return;
318:    disposed = true;

$ grep -nE "scoreDecay \* 0\.86|setLineDash|240,184,74" System/WebUI/static/js/widgets/wakeMeter.js
191:      state.scoreDecay = Math.max(state.score, state.scoreDecay * 0.86);
208:        ? "rgba(240,184,74,1.0)"
209:        : `rgba(240,184,74,${alpha.toFixed(2)})`;
211:      ctx.setLineDash([6, 4]);
216:      ctx.setLineDash([]);
221:        ctx.fillStyle = state.dragging ? "rgba(240,184,74,1.0)" : "rgba(240,184,74,0.92)";

$ node --input-type=module --check < System/WebUI/static/js/widgets/wakeMeter.js && echo ok
ok
```

All `<acceptance_criteria>` items from both tasks in the PLAN satisfied. OWW score path (cyan, decay 0.86) and threshold path (orange dashed, draggable handle) preserved exactly as before.

## Decisions Made

- **Colour helpers are module-level pure functions.** `lerp`, `rgbBlend`, `colorForLevel`, and the `GREEN/YELLOW/RED` constants live above the `createWakeMeter` factory. Two widget instances on one page (e.g. chat panel + settings panel) share the same allocations — there is no per-instance overhead.
- **`state.colorYellowAt`/`state.colorRedAt` live on the state object, not module-level.** Each widget instance owns its thresholds so future panels can have different ramps (operator dashboard vs public kiosk) without code changes.
- **Mount-time `/api/config` fetch is fire-and-forget.** Failure is silent — the 0.6 / 0.85 defaults remain. This means the widget starts rendering with sensible colours before the network resolves, and a missing/unreachable `/api/config` endpoint does not break the EQ.
- **`state.audioLevel` assignment kept.** Even though the widget no longer renders it, removing it would touch other panels mid-rollout. Keeping the assignment is one extra branch per audio_level event — negligible cost, useful safety net.
- **Floor strip preserved.** The thin green row at the bottom (`rgba(67,209,122,0.10)`) is a visual baseline; without it the all-zeros silence state would render a completely blank canvas, which reads as "broken" rather than "quiet". Cost: 24 fillRect calls per frame.
- **Bar-render short-circuit at `v < 0.01`.** Was `< 0.008` with peaks. Slightly higher cutoff because real spectrum data has more floor noise than the smoothed peak-hold version did; below 0.01 the bar is sub-pixel and we save the draw call.
- **`disposed` flag inside `draw()` guards BEFORE the RAF reschedule.** Placing the check as the first statement of draw() means a mid-flight RAF callback that fires after `cancelAnimationFrame(rafId)` returns immediately without enqueueing another frame. Without this, dispose() would race the RAF loop and one extra frame would always slip through (low-severity, but real).
- **`unsub()` wrapped in try/catch in dispose.** The SSE wrapper in `api.js` is defensive but if it ever throws (e.g. browser EventSource oddities on unload), we still need `disposed = true` to stick so a second dispose call is a no-op.

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Issues

- **Hot-reload of colour thresholds requires a page refresh.** RESEARCH §7 and the PLAN explicitly defer this — the mount-time fetch happens once. If an operator changes `spectrum_color_yellow_at` via `/api/config` PATCH while the chat panel is open, the new value takes effect after the next reload. Adding an SSE listener for `config_patched` events to live-update state.colorYellowAt/state.colorRedAt is a backlog item for Phase 21B.

## Self-Check: PASSED

- `System/WebUI/static/js/widgets/wakeMeter.js` modified — FOUND (`git diff --stat` shows changes vs base)
- Commit `b239173` — FOUND in `git log --oneline -5`
- Commit `4834ac9` — FOUND in `git log --oneline -5`
- All forbidden tokens (`EQ_SHAPE`, `audioLevel * 4`, `peaks[i] * 0.87`, `Date.now() * 0.0015`) — 0 occurrences (verified above)
- `N_BANDS = 24`, `function colorForLevel`, `Array.isArray(p.bands)` — all FOUND (verified above)
- `let disposed = false` × 1, `if (disposed) return` × 2, `disposed = true` × 1 — all match expected counts
- OWW score decay (`scoreDecay * 0.86`) — FOUND at line 191 (unchanged)
- Threshold dashed line (`setLineDash([6, 4])`) — FOUND at line 211 (unchanged)
- Threshold orange colour (`rgba(240,184,74,…)`) — FOUND (unchanged)
- ESM syntax — `node --input-type=module --check` exits 0
- `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-05-SUMMARY.md` — created by this run
