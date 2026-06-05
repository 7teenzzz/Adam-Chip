---
phase: 21A
plan: 06
type: execute
wave: 4
depends_on: [05]
files_modified:
  - System/WebUI/static/js/panels/chat.js
  - System/WebUI/static/js/panels/settings.js
autonomous: true
requirements:
  - UI-EQ-03
must_haves:
  truths:
    - "The hint text under the equalizer in the chat panel mentions that bars show the real microphone spectrum (FFT), not an animation"
    - "The draggable wake-meter variant in settings.js continues to work: drag-to-tune threshold persists, dispose is wired through wrapper._dispose"
    - "Both host panels (chat.js, settings.js) call wakeMeter.dispose() during their teardown path — verified, not assumed"
  artifacts:
    - path: "System/WebUI/static/js/panels/chat.js"
      provides: "Hint text updated; existing dispose call preserved"
      contains: "wakeMeter.dispose"
    - path: "System/WebUI/static/js/panels/settings.js"
      provides: "wrapper._dispose wiring untouched"
      contains: "wrapper._dispose"
  key_links:
    - from: "chat.js panel cleanup"
      to: "wakeMeter.dispose()"
      via: "if-typeof-function call"
      pattern: "wakeMeter\\.dispose"
    - from: "settings.js wrapper._dispose"
      to: "meter.dispose()"
      via: "captured closure"
      pattern: "meter\\.dispose"
---

<objective>
Two small host-panel touch-ups: (1) update the chat panel hint under the equaliser so users know the bars are a real FFT spectrum, not animation; (2) audit settings.js draggable-variant wiring to confirm the threshold drag-handler still functions and `wrapper._dispose → meter.dispose()` is wired correctly.

Purpose: UI-EQ-03 completion (user-visible honesty), D-14 verification (dispose plumbing), no broken draggable.
Output: chat.js hint string + settings.js audit (likely zero-diff if already wired correctly — explicit verification step).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@System/WebUI/static/js/panels/chat.js
@System/WebUI/static/js/panels/settings.js
@System/WebUI/static/js/widgets/wakeMeter.js

<interfaces>
chat.js current state (from grep):
  Line 94: `const wakeMeter = createWakeMeter({ draggable: false, height: 96 });`
  Line 95: `const eqCanvas = wakeMeter.canvas;`
  Line 663: `if (wakeMeter && typeof wakeMeter.dispose === "function") wakeMeter.dispose();`
  Hint text is rendered somewhere in panels/chat.js near the equaliser mount — exact line numbers not pre-captured; search for "эквалайзер" or "спектр" or whatever placeholder text exists.

settings.js current state (from grep):
  Line 622: `function buildWakeWordExtras() {`
  Line 697-705: comment block + `wrapper._dispose = () => { ... if (meter && typeof meter.dispose === "function") { try { meter.dispose(); } catch (_) {} } };`
  Lines 732-735: `const disposables = [];`
  Lines 793-794: panel-reset path drains disposables
  Lines 872-873: when extras has _dispose, push to disposables
  Lines 903-910: teardown drains disposables (second site)

No new functions, no new exports. Hint text becomes user-facing Russian copy.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Update chat panel hint text to describe real FFT spectrum</name>
  <read_first>
    - System/WebUI/static/js/panels/chat.js lines 80-200 — locate the equaliser mount + any hint/caption rendering near it
    - 21A-CONTEXT.md decisions block: "Подсказка под виджетом в chat.js обновлена: текст объясняет, что зелёные бары — реальный спектр микрофона"
  </read_first>
  <files>System/WebUI/static/js/panels/chat.js</files>
  <behavior>
    The hint text (Russian) under the equaliser canvas reads something like: "Бары показывают реальный спектр FFT микрофона. Цвет: зелёный — норма, жёлтый — громко, красный — пик." The exact wording is up to the implementer but MUST mention "FFT" or "спектр", MUST distinguish color zones, and MUST be Russian (CLAUDE.md communication-style rule).
  </behavior>
  <action>
    1. Open System/WebUI/static/js/panels/chat.js. Search for the equaliser mount near line 94 (`createWakeMeter`). Look for sibling DOM creation that produces hint/caption text. Likely patterns:
       - A &lt;div&gt; or &lt;span&gt; with `.eq-hint`, `.hint`, `.caption` class
       - Inline `textContent = "..."` assignments
       - Russian text strings like "эквалайзер", "уровень", "микрофон"

       If existing hint text is found near the equaliser: REPLACE it with the new Russian copy described in `<behavior>`.

       If no hint text exists currently (Phase 9 may have removed labels per STATE.md), ADD a new &lt;div&gt; element immediately after the canvas mount with class `eq-hint` (or whatever the existing chat-panel hint convention is — grep for `.hint` className usages in chat.js to match). Style/className must match the existing chat-panel hint conventions; do NOT introduce a new CSS class without precedent.

       Recommended Russian copy (planner's discretion):
       `"Эквалайзер: реальный спектр микрофона (FFT, 24 полосы 80–8000 Гц). Зелёный — норма, жёлтый — громко, красный — пик."`

       Keep it ≤ 120 characters so it fits a single line under the equaliser.

    2. Do NOT touch any other chat.js logic: existing VU-meter path (vuColorTriplet, vuLevelL/R/Mono at line 558+) remains unchanged. dispose call at line 663 remains unchanged.

    3. If the chat.js hint is rendered via a templating system (e.g. it lives in an HTML file), check whether System/WebUI/static/html/chat.html or similar exists. If so, update the HTML template instead and add a comment in chat.js pointing to it. (Most likely it's inline in chat.js per the existing pattern in this project — verify with grep before editing.)
  </action>
  <verify>
    <automated>node --check System/WebUI/static/js/panels/chat.js &amp;&amp; grep -nE "FFT|спектр" System/WebUI/static/js/panels/chat.js | head -5</automated>
  </verify>
  <acceptance_criteria>
    - `node --check System/WebUI/static/js/panels/chat.js` exits 0
    - `grep -cE "FFT|спектр" System/WebUI/static/js/panels/chat.js` returns at least 1 (new hint mentioning FFT or "спектр")
    - The dispose call at the cleanup path still present: `grep -c "wakeMeter\\.dispose" System/WebUI/static/js/panels/chat.js` returns at least 1
    - VU-meter wiring unchanged: `grep -c "vuLevelL\\|vuLevelR\\|vuLevelMono" System/WebUI/static/js/panels/chat.js` matches the pre-edit count (verify with `git diff` showing only hint-text changes)
  </acceptance_criteria>
  <done>Hint text updated; chat.js parses; dispose path preserved; VU-meter unchanged.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Audit settings.js draggable variant — verify wakeMeter wiring still works</name>
  <read_first>
    - System/WebUI/static/js/panels/settings.js lines 622-720 (buildWakeWordExtras + wrapper._dispose wiring)
    - System/WebUI/static/js/panels/settings.js lines 780-920 (disposables drain paths)
    - 21A-CONTEXT.md D-12 (draggable still works), D-14 (dispose plumbing)
    - 21A-RESEARCH.md §8 "Mount-site audit (final)"
  </read_first>
  <files>System/WebUI/static/js/panels/settings.js</files>
  <behavior>
    settings.js is functionally UNCHANGED in this task. The intent is an explicit audit + zero-or-minimal-diff change:
    - Confirm `createWakeMeter({ draggable: true, ... })` mount still occurs in buildWakeWordExtras
    - Confirm `wrapper._dispose` wraps `meter.dispose()` inside try/catch
    - Confirm `disposables` queue drains `wrapper._dispose` during panel teardown AND during inter-render reset
    - If anything is missing or broken, fix it with the minimal diff matching the existing pattern
    - Add a one-line comment near the wrapper._dispose definition: `// Phase 21A: idempotent dispose enforced in wakeMeter.js — safe to call multiple times.`
  </behavior>
  <action>
    1. Open System/WebUI/static/js/panels/settings.js. Read lines 622-720 carefully.

    2. Verify the following invariants. If any is missing, add or fix it minimally.
       - `createWakeMeter({ draggable: true, ... })` is called inside buildWakeWordExtras (or wherever the settings panel mounts the meter).
       - The returned `meter` object is captured in a closure variable.
       - `wrapper._dispose` is assigned to a function that calls `meter.dispose()` inside try/catch.
       - When buildWakeWordExtras returns, the wrapper element with `_dispose` attached is pushed to the panel's `disposables` array (or equivalent).
       - The panel's teardown / reset paths call every `disposables` entry.

    3. Add the single comment line above wrapper._dispose assignment (near line 700):
       `// Phase 21A: idempotent dispose enforced in wakeMeter.js — safe to call multiple times.`

    4. If the threshold drag-to-tune flow is NOT functioning end-to-end (Phase 21A added no logic that should break it, but verify) — check that the events `oww_score`, `wake_sensitivity_updated`, `state.threshold` field, and the pointer-up persist call (`pushThreshold(state.threshold, { persist: true })`) all still exist in wakeMeter.js. If a regression slipped in during Plan 05, file an issue note in the SUMMARY for this plan and FIX it. Otherwise, no changes here.

    5. Do NOT add new SSE subscriptions, do NOT add new event handlers, do NOT refactor disposables logic.
  </action>
  <verify>
    <automated>node --check System/WebUI/static/js/panels/settings.js &amp;&amp; grep -nE "createWakeMeter\(\{[^)]*draggable: true" System/WebUI/static/js/panels/settings.js &amp;&amp; grep -nE "wrapper\._dispose" System/WebUI/static/js/panels/settings.js &amp;&amp; grep -nE "meter\.dispose\(\)" System/WebUI/static/js/panels/settings.js &amp;&amp; grep -nE "Phase 21A: idempotent dispose" System/WebUI/static/js/panels/settings.js</automated>
  </verify>
  <acceptance_criteria>
    - `node --check System/WebUI/static/js/panels/settings.js` exits 0
    - `grep -c "createWakeMeter" System/WebUI/static/js/panels/settings.js` returns at least 1
    - `grep -c "wrapper\\._dispose" System/WebUI/static/js/panels/settings.js` returns at least 1
    - `grep -c "meter\\.dispose" System/WebUI/static/js/panels/settings.js` returns at least 1
    - `grep -c "Phase 21A: idempotent dispose" System/WebUI/static/js/panels/settings.js` returns 1
    - Manual: in browser, open Settings panel → wake-word section → drag the threshold line; verify the orange dashed line moves and `oww_score` events arrive with new threshold (covered by Plan 07 smoke test)
  </acceptance_criteria>
  <done>settings.js audit complete; wiring confirmed or fixed; comment marker added; draggable still works.</done>
</task>

</tasks>

<verification>
- `node --check System/WebUI/static/js/panels/chat.js && node --check System/WebUI/static/js/panels/settings.js` exits 0
- chat.js hint text mentions FFT or "спектр"
- settings.js dispose wiring intact and marked with Phase 21A audit comment
- No behavioral changes outside the hint text and the audit comment
</verification>

<success_criteria>
- UI-EQ-03 user-facing completion: visible hint explains the bars are real FFT
- D-12 / D-14 reaffirmed: draggable variant still works; dispose plumbing audited
- Both host panels remain syntactically valid JS
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-06-SUMMARY.md`
</output>
