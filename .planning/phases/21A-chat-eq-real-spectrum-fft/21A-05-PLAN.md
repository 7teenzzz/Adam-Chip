---
phase: 21A
plan: 05
type: execute
wave: 3
depends_on: [03]
files_modified:
  - System/WebUI/static/js/widgets/wakeMeter.js
autonomous: true
requirements:
  - UI-EQ-03
  - UI-EQ-04
  - UI-EQ-05
must_haves:
  truths:
    - "wakeMeter renders 24 bars sourced directly from the latest audio_level event's bands[] array — no peak-hold, no decay, no wobble, no EQ_SHAPE"
    - "Each bar color is computed from its own level via a green→yellow→red gradient using configurable thresholds (yellow_at=0.6, red_at=0.85 defaults)"
    - "OWW score (cyan, decay 0.86) and threshold (orange dashed) rendering paths are UNCHANGED — same code that was there before"
    - "dispose() is idempotent: calling it twice does not throw; subsequent RAF frames are guarded by a `disposed` flag and abort cleanly"
    - "When audio_level arrives WITHOUT a valid bands[24] array (e.g. synthetic backfill, network glitch), the widget keeps the last good snapshot — bars do not flash to zero"
  artifacts:
    - path: "System/WebUI/static/js/widgets/wakeMeter.js"
      provides: "Refactored bar-rendering loop, color function, idempotent dispose"
      contains: "function colorForLevel"
  key_links:
    - from: "wakeMeter.js bars[] state"
      to: "ev.payload.bands array"
      via: "guarded assignment on audio_level handler"
      pattern: "Array\\.isArray\\(p\\.bands\\) && p\\.bands\\.length"
    - from: "wakeMeter.js dispose()"
      to: "unsub() + cancelAnimationFrame"
      via: "disposed boolean flag"
      pattern: "disposed = true"
---

<objective>
Refactor wakeMeter.js to consume the real `bands[24]` data emitted by Plan 03's backend. Delete EQ_SHAPE, audioLevel×4 magic, sin-wobble, peaks-decay. Render 24 bars sourced directly from the latest SSE snapshot, color each by its own level via piecewise RGB green→yellow→red. Make dispose() idempotent and guard draw() against post-dispose RAF execution. Preserve OWW score (cyan) and threshold (orange dashed) overlays exactly as today.

Purpose: UI-EQ-03 (honest render), UI-EQ-04 (color gradient), UI-EQ-05 (SSE leak fix). Frontend half of the phase.
Output: One JS file refactored. Plan 06 then updates chat.js hint text + smoke-tests settings.js draggable.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@System/WebUI/static/js/widgets/wakeMeter.js
@System/WebUI/static/js/api.js
@System/WebUI/static/js/panels/chat.js

<interfaces>
Current shape (wakeMeter.js — for context):
  - createWakeMeter({ draggable, height }) returns { canvas, dispose, state }
  - BAR_N = some constant (likely 24 or 32 already) — verify; bars[] state will be N_BANDS=24
  - peaks Float32Array (current decay buffer) → DELETED
  - EQ_SHAPE Float32Array (current illusion) → DELETED
  - draw() function at ~line 100-140 → rewritten
  - audio_level handler at ~line 214-255 → bands[] consumed; existing state-tracking (pipelineReady) preserved
  - oww_score handler at ~line 243-249 → UNCHANGED
  - wake_sensitivity_updated handler at ~line 250-254 → UNCHANGED
  - voice_loop_started / voice_state_change / voice_loop_stopped handlers → UNCHANGED
  - dispose() at ~line 258-262 → made idempotent

New state in widget closure:
  const N_BANDS = 24;
  const bands = new Float32Array(N_BANDS);  // last snapshot; default 0
  let disposed = false;

New module-level color helper (or in-closure — choose the shorter path):
  const GREEN  = [67, 209, 122];
  const YELLOW = [234, 200, 80];
  const RED    = [220, 80, 80];
  function lerp(a, b, t) { return a + (b - a) * t; }
  function rgbBlend(c1, c2, t) { return [lerp(c1[0],c2[0],t), lerp(c1[1],c2[1],t), lerp(c1[2],c2[2],t)]; }
  function colorForLevel(v, yAt, rAt) {
    let rgb;
    if (v <= yAt)       rgb = rgbBlend(GREEN, YELLOW, v / Math.max(0.001, yAt));
    else if (v >= rAt)  rgb = RED;
    else                rgb = rgbBlend(YELLOW, RED, (v - yAt) / Math.max(0.001, rAt - yAt));
    const a = 0.35 + v * 0.65;
    return `rgba(${rgb[0]|0},${rgb[1]|0},${rgb[2]|0},${a.toFixed(2)})`;
  }

Color thresholds are sourced ONCE at mount from /api/config (existing endpoint per RESEARCH §9). Fall back to 0.6 / 0.85 if fetch fails.
Live hot-reload of color thresholds is OUT OF SCOPE for this plan (RESEARCH §7 "RAF behavior" + Open Question 3); a page refresh picks up new values.

Items to DELETE (D-13):
  - EQ_SHAPE constant
  - peaks Float32Array allocation
  - peaks[i] * 0.87 decay math
  - sin(Date.now() * 0.0015 + i * 0.85) wobble
  - audioLevel * 4.0 multiplier

Items to PRESERVE (D-12):
  - OWW score draw path (cyan horizontal line, decay 0.86)
  - threshold draw path (orange dashed line)
  - draggable threshold handling (when draggable=true)
  - state.score / state.threshold / state.dragging / state.engineReady fields
  - state.pipelineReady gating (audio_level state field → standby/listening/reply flips ready)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Replace EQ_SHAPE / peaks / wobble with direct bands[] consumption + color-by-level</name>
  <read_first>
    - System/WebUI/static/js/widgets/wakeMeter.js entire file (it is &lt;300 lines)
    - 21A-RESEARCH.md §7 "Frontend: 24-Bar Gradient with No Smoothing" — has the verbatim draw/handler/color code
    - 21A-RESEARCH.md §8 "SSE Leak Fix" — for Task 2 reference (this task does NOT touch dispose)
    - 21A-CONTEXT.md D-10 (no smoothing), D-11 (color), D-12 (preserve OWW/threshold), D-13 (delete-list)
    - System/WebUI/static/js/api.js subscribeEvents shape
  </read_first>
  <files>System/WebUI/static/js/widgets/wakeMeter.js</files>
  <behavior>
    - The widget renders exactly N_BANDS = 24 bars whose heights are state.bands[i] * (h - 3) — no scaling, no decay
    - Bar colors come from colorForLevel(bands[i], state.colorYellowAt, state.colorRedAt) with defaults 0.6 / 0.85
    - On audio_level event handler: if Array.isArray(p.bands) && p.bands.length === N_BANDS, copy values into bands[]; otherwise leave bands[] unchanged (preserves last snapshot per Pitfall 4 in RESEARCH)
    - On voice_loop_stopped: zero out bands[] (existing zero-out for audioLevel/peaks remains semantically the same)
    - OWW score line and threshold line are drawn by the SAME existing code; no changes to that section
    - At mount, fetch /api/config once; populate state.colorYellowAt / state.colorRedAt from response.media.audio.spectrum_color_yellow_at / spectrum_color_red_at; on failure, defaults 0.6 / 0.85 remain
  </behavior>
  <action>
    1. Open wakeMeter.js. Locate and DELETE the following:
       - The `EQ_SHAPE` Float32Array constant (~line 21)
       - The `const peaks = new Float32Array(BAR_N);` line (~line 41)
       - The peaks-related lines inside draw(): `const displayLevel = Math.min(1.0, state.audioLevel * 4.0);` and the wobble/decay/peaks[i] math (~lines 115-135). Replace the bars-rendering block with the §7 RESEARCH version (using N_BANDS=24, bands[] state, colorForLevel).
       - The `for (let i = 0; i < BAR_N; i++) peaks[i] = 0;` line inside voice_loop_stopped handler (~line 242)

    2. ADD near the top of createWakeMeter closure:
       - `const N_BANDS = 24;`
       - `const bands = new Float32Array(N_BANDS);`
       - Color helpers (GREEN/YELLOW/RED arrays, lerp, rgbBlend, colorForLevel) — choose closure-local placement to keep all logic in one file.

    3. ADD on state object:
       - `colorYellowAt: 0.6,`
       - `colorRedAt: 0.85,`

    4. ADD a mount-time config fetch (right before the subscribeEvents call):
       ```
       fetch('/api/config').then(r => r.ok ? r.json() : null).then(cfg => {
         if (!cfg) return;
         const a = (cfg.media && cfg.media.audio) || {};
         if (typeof a.spectrum_color_yellow_at === 'number') state.colorYellowAt = a.spectrum_color_yellow_at;
         if (typeof a.spectrum_color_red_at === 'number')    state.colorRedAt    = a.spectrum_color_red_at;
       }).catch(() => {});
       ```
       This MUST NOT block the subscribe; defaults are usable until the fetch resolves.

    5. REWRITE the audio_level branch of the handler (~lines 215-227):
       - Keep the existing `state.audioLevel = (typeof lvl === 'number') ? lvl : 0;` line (chat.js may not depend on it but VU-meter via other path uses payload.level directly; this widget no longer renders audioLevel, but leaving the assignment is harmless and gives developers a backup mid-rollout).
       - Add the bands consumer:
         ```
         if (Array.isArray(p.bands) && p.bands.length === N_BANDS) {
           for (let i = 0; i < N_BANDS; i++) bands[i] = +p.bands[i] || 0;
         }
         ```
       - Keep the pipelineReady gating lines unchanged.

    6. REWRITE the bars-rendering section of draw() per RESEARCH §7. Concretely:
       - Compute barW from canvas width and gap=2.
       - Optional thin floor strip (RESEARCH §7 first loop).
       - Main bars loop: `for (let i = 0; i < N_BANDS; i++) { const v = bands[i]; if (v < 0.01) continue; const bh = v * (h - 3); ctx.fillStyle = colorForLevel(v, state.colorYellowAt, state.colorRedAt); ctx.fillRect(Math.round(i * (barW + gap)), Math.round(h - 2 - bh), Math.max(1, Math.round(barW)), Math.max(1, Math.round(bh))); }`

    7. PRESERVE all other draw-loop code: OWW score cyan line, threshold orange dashed line, pipelineReady placeholder, dragging handling, score decay 0.86. Do not touch these lines.

    8. Keep the existing voice_loop_stopped handler shape: instead of `for (let i = 0; i < BAR_N; i++) peaks[i] = 0;`, write `bands.fill(0);`.

    9. If a stale `BAR_N` constant remains anywhere referenced, replace with N_BANDS. Otherwise leave BAR_N if it was only used for the deleted peaks/EQ_SHAPE.

    Do NOT modify the dispose() function in this task — Task 2 handles it.
  </action>
  <verify>
    <automated>node -e "const fs=require('fs'); const s=fs.readFileSync('System/WebUI/static/js/widgets/wakeMeter.js','utf8'); const bad=['EQ_SHAPE','audioLevel * 4.0','peaks[i] * 0.87','Date.now() * 0.0015']; for (const t of bad) { if (s.includes(t)) { console.error('STILL PRESENT:', t); process.exit(1); } } if (!s.includes('colorForLevel')) { console.error('colorForLevel missing'); process.exit(1); } if (!s.includes('N_BANDS = 24')) { console.error('N_BANDS=24 missing'); process.exit(1); } if (!s.includes('Array.isArray(p.bands)') && !s.includes('Array.isArray(p?.bands)')) { console.error('bands guard missing'); process.exit(1); } console.log('refactor markers ok');"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "EQ_SHAPE" System/WebUI/static/js/widgets/wakeMeter.js` returns 0
    - `grep -c "audioLevel \* 4" System/WebUI/static/js/widgets/wakeMeter.js` returns 0
    - `grep -c "peaks\[i\] \* 0.87" System/WebUI/static/js/widgets/wakeMeter.js` returns 0
    - `grep -c "Date.now() \* 0.0015" System/WebUI/static/js/widgets/wakeMeter.js` returns 0
    - `grep -nE "function colorForLevel|const colorForLevel" System/WebUI/static/js/widgets/wakeMeter.js` returns at least one match
    - `grep -nE "N_BANDS = 24" System/WebUI/static/js/widgets/wakeMeter.js` returns at least one match
    - `grep -nE "Array\\.isArray\\(p\\.bands\\)" System/WebUI/static/js/widgets/wakeMeter.js` returns at least one match (with optional chaining variant also acceptable)
    - The OWW-score draw path is intact: `grep -nE "decay.*0\\.86|score \\* 0\\.86" System/WebUI/static/js/widgets/wakeMeter.js` returns at least one match (existing math preserved)
    - The threshold draw path is intact: `grep -nE "setLineDash|\\[4, 4\\]|dashed" System/WebUI/static/js/widgets/wakeMeter.js` returns at least one match
    - File parses as JS — load it in Node with `node --check System/WebUI/static/js/widgets/wakeMeter.js` exits 0
  </acceptance_criteria>
  <done>EQ_SHAPE removed, bands[] consumed directly, color-by-level rendering working, OWW/threshold paths preserved, no peak-hold/decay/wobble.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Make dispose() idempotent and guard draw() against post-dispose RAF re-entry</name>
  <read_first>
    - System/WebUI/static/js/widgets/wakeMeter.js — locate dispose() at ~line 258 and the RAF-rescheduling line at ~line 181 (end of draw)
    - 21A-RESEARCH.md §8 "SSE Leak Fix in wakeMeter.js" — verbatim fix code
    - 21A-CONTEXT.md D-14
  </read_first>
  <files>System/WebUI/static/js/widgets/wakeMeter.js</files>
  <behavior>
    - A `disposed` boolean flag is declared at top of createWakeMeter closure (alongside bands and rafId).
    - dispose() function: returns immediately if disposed is true; otherwise sets disposed=true, cancels RAF, calls unsub() inside try/catch.
    - draw() function: returns immediately if disposed is true (BEFORE calling requestAnimationFrame(draw)) — prevents the race where a mid-flight RAF reschedules after dispose has cancelled the original.
    - Existing API (canvas, dispose, state return tuple) unchanged. No new exports.
  </behavior>
  <action>
    1. In the createWakeMeter closure, near other top-level let/const declarations (close to where rafId is declared), ADD: `let disposed = false;`

    2. Update dispose() to:
       ```
       function dispose() {
         if (disposed) return;
         disposed = true;
         if (rafId) cancelAnimationFrame(rafId);
         rafId = null;
         if (typeof unsub === "function") {
           try { unsub(); } catch (_) {}
         }
       }
       ```

    3. Update draw() to early-return when disposed. Add as the FIRST line inside the function body:
       `if (disposed) return;`
       This MUST come before any ctx ops AND before the `rafId = requestAnimationFrame(draw);` line at the end — otherwise the RAF re-schedule still runs once after dispose.

    4. Do NOT touch the initial `rafId = requestAnimationFrame(draw);` line outside the function (the one that starts the loop) — that fires before disposed can be true, since the closure is freshly constructed. Only the in-loop self-reschedule needs the guard.

    5. No external API change. The returned object `{ canvas, dispose, state }` is identical.
  </action>
  <verify>
    <automated>node -e "const fs=require('fs'); const s=fs.readFileSync('System/WebUI/static/js/widgets/wakeMeter.js','utf8'); if (!s.includes('let disposed = false')) { console.error('disposed flag missing'); process.exit(1); } if (!/if \(disposed\) return/.test(s)) { console.error('disposed guard missing'); process.exit(1); } const idx=s.indexOf('function dispose'); const dispBody=s.slice(idx, idx+400); if (!/if \(disposed\) return/.test(dispBody)) { console.error('dispose() does not check disposed flag'); process.exit(1); } if (!/disposed = true/.test(dispBody)) { console.error('dispose() does not set disposed=true'); process.exit(1); } console.log('idempotent dispose markers ok');" &amp;&amp; node --check System/WebUI/static/js/widgets/wakeMeter.js</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "let disposed = false" System/WebUI/static/js/widgets/wakeMeter.js` returns at least 1
    - `grep -c "if (disposed) return" System/WebUI/static/js/widgets/wakeMeter.js` returns at least 2 (one in dispose, one at top of draw)
    - `grep -nE "disposed = true" System/WebUI/static/js/widgets/wakeMeter.js` returns at least 1 match (inside dispose)
    - `node --check System/WebUI/static/js/widgets/wakeMeter.js` exits 0 (no syntax errors)
    - Manual: opening the page and toggling Chat ↔ Settings ↔ Chat in DevTools Network tab shows a single active EventSource per visible page (verified in Plan 07 smoke test)
  </acceptance_criteria>
  <done>dispose() idempotent; draw() guarded; double-dispose is a no-op; mid-flight RAF after dispose aborts cleanly.</done>
</task>

</tasks>

<verification>
- `node --check System/WebUI/static/js/widgets/wakeMeter.js` exits 0
- All delete-list markers absent from the file (EQ_SHAPE, audioLevel*4.0, peaks*0.87, Date.now()*0.0015)
- N_BANDS=24, colorForLevel, Array.isArray(p.bands), disposed flag, "if (disposed) return" all present
- Manual: after launching Orchestrator + opening chat panel, bars track real audio with no smoothing; loud sustained tone → red bars on the appropriate frequency band; silence → all bars at floor
</verification>

<success_criteria>
- UI-EQ-03 satisfied: no smoothing, no peak-hold, no decay, no wobble — direct render of bands[24]
- UI-EQ-04 satisfied: per-bar gradient green→yellow→red with Config-tuned thresholds
- UI-EQ-05 satisfied: dispose() is idempotent and post-dispose RAFs abort
- No regression to OWW score (cyan) and threshold (orange dashed) rendering
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-05-SUMMARY.md`
</output>
