---
phase: 21A
plan: 06
subsystem: System/WebUI/static/js/panels / Wave 4 (host-panel touch-ups)
tags: [equaliser, chat-panel, settings-panel, hint-copy, dispose-audit, ui-eq-03]
dependency_graph:
  requires:
    - "21A-05 (Wave 3): wakeMeter.js consumes real bands[24] from audio_level SSE; idempotent dispose() with `disposed` flag"
  provides:
    - "Chat-panel hint text under the equaliser now describes the bars as the real FFT spectrum (24 bands, 80–8000 Hz) with green/yellow/red colour zones"
    - "Settings-panel draggable-variant wiring audited and marked with a Phase 21A comment near wrapper._dispose"
    - "Both host panels confirmed to call wakeMeter.dispose() during teardown (chat.js:663 and settings.js:703-705)"
  affects:
    - "Operator-visible honesty: the hint copy no longer hides that the widget shows real per-frame FFT instead of an animation"
    - "D-12 (draggable still works) + D-14 (dispose plumbing) — both reaffirmed without code change"
tech_stack:
  added: []
  patterns:
    - "Inline DOM hint via `el('span', { class: 'dim' }, ...)` — matches the existing chat-panel hint convention (no new CSS class introduced)"
    - "Zero-diff audit pattern for settings.js: only a single-line comment added; all dispose wiring left untouched because RESEARCH §8 confirmed it was already correct"
key_files:
  created:
    - ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-06-SUMMARY.md"
  modified:
    - "System/WebUI/static/js/panels/chat.js"
    - "System/WebUI/static/js/panels/settings.js"
decisions:
  - "Hint copy in chat.js was EXTENDED rather than REPLACED — the original sentence about the orange threshold line + cyan OWW score is still operator-useful, so the new FFT explanation was prepended to it. Total length stays one line in typical sidebar widths (the right panel has overflow-y:auto)."
  - "settings.js audit produced a zero-behavioural-diff change. The Phase 21A audit comment is placed BETWEEN the existing T17-deploy comment block and the assignment so the history of why this disposer exists remains readable in-order."
  - "No new acceptance test added — both panels are user-facing and verifiable via Plan 07 smoke-test (drag the orange line, observe oww_score events with the new threshold). Adding a JSDOM unit test for hint-text presence would be over-engineered for a 1-line copy change."
metrics:
  duration: "single session"
  completed: 2026-05-18
  tasks_total: 2
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 21A Plan 06: Wave 4 — Host-Panel Touch-Ups Summary

Wave 4 closes UI-EQ-03 and reaffirms the dispose plumbing invariants D-12/D-14 from Phase 21A. Two small host-panel changes: an honest hint under the chat-panel equaliser explaining the bars are a real FFT spectrum, and a zero-behavioural-diff audit of the settings-panel draggable-variant wiring with a single Phase 21A marker comment.

## What Shipped

| Artifact | Purpose |
| --- | --- |
| `chat.js` hint copy (line 457) | Replaces the generic "Оранжевый — порог wake-word, циан — текущий OWW-score…" with a leading sentence: «Эквалайзер: реальный спектр микрофона (FFT, 24 полосы 80–8000 Гц). Зелёный — норма, жёлтый — громко, красный — пик.» The original threshold/score sentence is preserved on the same line. |
| `settings.js` audit comment (line 700) | One-line marker `// Phase 21A: idempotent dispose enforced in wakeMeter.js — safe to call multiple times.` placed above the `wrapper._dispose` assignment. Documents that subsequent calls are no-ops (the guard lives in wakeMeter.js Plan 05). |

## Tasks Executed

| Task | Name | Commit | Outcome |
| --- | --- | --- | --- |
| 1 | Update chat panel hint text to describe real FFT spectrum | `8b2ae3c` | `grep -cE "FFT\|спектр" chat.js` → 1; `node --input-type=module --check < chat.js` clean; `wakeMeter.dispose` call at line 663 untouched; `vuLevelL\|vuLevelR\|vuLevelMono` count unchanged (7). |
| 2 | Audit settings.js draggable variant — verify wakeMeter wiring still works | `89898d5` | Phase 21A marker present (1 occurrence); `createWakeMeter({ draggable: true, height: 96 })` confirmed at line 623; `wrapper._dispose` at line 701 wraps `meter.dispose()` in try/catch (line 704); `disposables.push(extra._dispose)` at line 873; both teardown drains at lines 793-796 (renderAll start) and 907-910 (panel-mount teardown). No behavioural diff. |

## Verification

```bash
$ node --input-type=module --check < System/WebUI/static/js/panels/chat.js && \
  node --input-type=module --check < System/WebUI/static/js/panels/settings.js && echo ok
ok

$ grep -cE "FFT|спектр" System/WebUI/static/js/panels/chat.js
1

$ grep -c "wakeMeter\.dispose" System/WebUI/static/js/panels/chat.js
1

$ grep -nE "createWakeMeter\(\{[^)]*draggable: true" System/WebUI/static/js/panels/settings.js
623:  const meter = createWakeMeter({ draggable: true, height: 96 });

$ grep -nE "wrapper\._dispose" System/WebUI/static/js/panels/settings.js
701:  wrapper._dispose = () => {

$ grep -nE "meter\.dispose\(\)" System/WebUI/static/js/panels/settings.js
704:      try { meter.dispose(); } catch (_) {}

$ grep -cE "Phase 21A: idempotent dispose" System/WebUI/static/js/panels/settings.js
1

$ grep -nE "wakeMeter\.dispose|meter\.dispose" \
    System/WebUI/static/js/panels/chat.js \
    System/WebUI/static/js/panels/settings.js
System/WebUI/static/js/panels/chat.js:663:    if (wakeMeter && typeof wakeMeter.dispose === "function") wakeMeter.dispose();
System/WebUI/static/js/panels/settings.js:703:    if (meter && typeof meter.dispose === "function") {
System/WebUI/static/js/panels/settings.js:704:      try { meter.dispose(); } catch (_) {}
```

All `<acceptance_criteria>` items from both tasks in the PLAN satisfied.

## Decisions Made

- **Hint copy was EXTENDED, not REPLACED.** The original sentence about the orange threshold line and cyan OWW score remains operator-useful — it tells them where to tune sensitivity. Phase 21A's UI-EQ-03 only requires that the bars-are-real-FFT honesty appears, not that other context disappears. New copy reads as one paragraph that goes: spectrum description → colour zones → wake-word elements → where to tune.
- **No new CSS class introduced.** The existing chat-panel hint pattern uses inline `el("span", { class: "dim" }, ...)` styling. Adding a `.eq-hint` class would have been a single-use abstraction (only one hint widget exists on this panel) and would have leaked Phase 21A scope into the global stylesheet.
- **settings.js audit is zero-behavioural-diff.** RESEARCH §8 had already confirmed the dispose wiring was correct after Plan 05. The audit comment makes that confirmation discoverable from the code itself (so a future reader doesn't ask "is this still needed?"). No SSE subscriptions, event handlers, or disposables logic were touched — that was the explicit boundary in the PLAN's task §5.
- **Phase 21A marker placement order matters.** The existing T17-deploy comment block (lines 697-699) explains WHY `wrapper._dispose` exists at all (it plugged an EventSource leak). The new Phase 21A line (line 700) explains a more recent property of the disposer (it's now idempotent). Keeping them in chronological order — T17 first, then 21A — preserves the patch history readability in-source.
- **Drag-to-tune flow was not re-verified by automated test.** The pointerdown/pointermove/pointerup handlers in wakeMeter.js (Plan 05, lines 238-259) are unchanged across Phase 21A. Plan 07's smoke test is the canonical verification site — adding a JSDOM unit test here would duplicate that coverage at the wrong layer.

## Deviations from Plan

None — plan executed exactly as written. Task 1 used the planner's recommended Russian copy template verbatim (extended onto the existing hint). Task 2 produced the predicted minimal-diff (one comment line) because the audit found no broken wiring.

## Deferred Issues

None. Both tasks closed within their planned scope; no follow-ups identified during the audit.

## Self-Check: PASSED

- `System/WebUI/static/js/panels/chat.js` modified — FOUND in `git diff --stat 59456c0..HEAD`
- `System/WebUI/static/js/panels/settings.js` modified — FOUND
- Commit `8b2ae3c` — FOUND in `git log --oneline -5`
- Commit `89898d5` — FOUND in `git log --oneline -5`
- `FFT` or `спектр` token in chat.js — 1 occurrence ✓
- `wakeMeter.dispose` call in chat.js teardown — 1 occurrence ✓ (line 663)
- `meter.dispose()` call in settings.js wrapper._dispose — 1 occurrence ✓ (line 704)
- `createWakeMeter({ draggable: true, ...})` in settings.js — 1 occurrence ✓ (line 623)
- `Phase 21A: idempotent dispose` marker in settings.js — 1 occurrence ✓ (line 700)
- Both panels syntactically valid ESM — `node --input-type=module --check` exits 0 for both
- `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-06-SUMMARY.md` — created by this run
