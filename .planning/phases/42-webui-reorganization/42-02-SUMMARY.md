---
phase: 42-webui-reorganization
plan: "02"
subsystem: WebUI
tags: [panel, aiim, identity, preset-selector, block-editor, persona]
dependency_graph:
  requires: [42-01-PLAN]
  provides: [agent/persona-panel, extractSection, reconstructFile, aiim-matrix]
  affects:
    - System/WebUI/static/js/panels/agent/persona.js
tech_stack:
  added: []
  patterns:
    - mount(target)->teardown contract
    - el() local DOM builder (copy-paste, no barrel export)
    - extractSection/reconstructFile verbatim from PATTERNS.md §5
    - 4×3 CSS grid-3 for AIIM aspects
    - render/edit toggle for markdown sections
key_files:
  created:
    - System/WebUI/static/js/panels/agent/persona.js
  modified: []
decisions:
  - "extractSection returns null for missing sections (not empty string) — callers can distinguish missing vs empty"
  - "reconstructFile inserts a blank line before and after new content to maintain markdown formatting consistency"
  - "PLAN_META colors updated to UI-SPEC §4 values: P=#a78bfa, S=#60a5fa, I=var(--accent), B=#f97316, T=var(--cyan)"
  - "matrixCard reference kept mutable so preset-apply callback can replaceWith() updated card in-place"
  - "Both tasks (scaffold and matrix/editors) implemented as one file write — Task 2 had zero additional changes"
metrics:
  duration_minutes: 8
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
  completed_date: "2026-06-14"
---

# Phase 42 Plan 02: Личность panel — AIIM matrix + Identity.md block editors

New panel `panels/agent/persona.js` implementing the Личность page (#/agent/persona): preset selector, AIIM matrix (12 aspects, 4×3 grid), and two focused block editors for Identity.md sections.

## What Was Built

### Task 1: scaffold + extractSection + preset selector + AIIM skeleton (5db234a)

Created `System/WebUI/static/js/panels/agent/persona.js` (480 lines). Both tasks were implemented atomically in one file since the matrix/editors were integral to the scaffold.

**extractSection(md, sectionName)** — splits markdown on `\n`, finds `## SectionName` header by exact `trim()` match, slices to next `## ` header (or end of file if last section). Returns `null` for missing sections. Used by block editors to show only the relevant section content.

**reconstructFile(original, sectionName, newContent)** — rebuilds full file with one section replaced verbatim. Before-section and after-section content untouched (T-42-03 mitigated: code fences in `## Промт-инъекция` not modified). Handles last-section edge case (endIdx === -1 → after = []).

**AIIM_ASPECTS** — 12 aspects with codes wi/lo/im/ho/co/em/be/sp/se/pe/me/at, copied from tuning.js. **PLAN_META** — inline colors per UI-SPEC §4 (P=#a78bfa, S=#60a5fa, I=var(--accent), B=#f97316, T=var(--cyan)), no new CSS variables.

**makePresetCard()** — row of `.badge` buttons (one per preset from `/api/tuning`). Active preset shown with `.badge.ok` + accent border. Click: all badges → opacity:0.5+disabled → POST `/api/tuning/preset/{name}` → reload tuning → re-render badges + call `onPresetApplied(newTuning)` to re-render AIIM matrix in-place via `replaceWith()`.

**makeAiimMatrixCard(tuningData)** — `.card.card-full` with `.grid-3` (4 rows × 3 columns). Each aspect cell has: header row (code mono dim + name weight-500 + plan dot inline color), weight range slider (0-1 step 0.01 + live value display), level range slider (0-4 step 1 + L0..L4 label). "Сохранить матрицу" `.btn-primary` below grid: collects all getters → PUT `/api/tuning` with `{identity: {base_weights, levels}}`.

**makeBlockEditor(sectionName, ...)** — view/edit toggle per section. View: `marked.parse()` if `window.marked` available, else raw `<pre>`. Edit: `.textarea.field-wide` with `min-height:120px`. Save: `reconstructFile()` → PUT `/api/persona {path: 'Agent-Adam-Chip/About/Identity.md', content: reconstructed}` → update local `identityContent` copy → re-render view.

**mount(target)** — loads `/api/tuning` and `/api/persona` in parallel, finds Identity.md file by path substring, builds preset card + AIIM matrix + two block editors (Интенции, Голос). Teardown function drains `disposables[]` (empty in this panel — no SSE).

## Deviations from Plan

None — plan executed exactly as written.

Both tasks (Task 1: scaffold/extractor/preset/skeleton; Task 2: matrix/editors) were implemented in one atomic file write. The separation existed in the plan to structure the work, but the implementations were interdependent enough to write together. No behavioral difference.

## Known Stubs

None. All three sections (preset selector, AIIM matrix, block editors) are wired to live API endpoints:
- Preset selector: GET/POST `/api/tuning`
- AIIM matrix: GET `/api/tuning`, PUT `/api/tuning`
- Block editors: GET `/api/persona`, PUT `/api/persona`

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: content-injection | System/WebUI/static/js/panels/agent/persona.js | PUT /api/persona writes to Identity.md which is loaded as LLM system prompt — T-42-03 mitigated by reconstructFile preserving all non-edited sections verbatim |

T-42-03 mitigation confirmed: `reconstructFile` slices `before` (lines up to `## SectionName`) and `after` (lines from next `## ` header) verbatim, joining with only the new section body. Code fences in other sections (e.g. `## Промт-инъекция`) are not parsed or modified.

## Self-Check: PASSED

Files exist:
- System/WebUI/static/js/panels/agent/persona.js: FOUND

Commits exist:
- 5db234a: FOUND (feat(42-02): scaffold agent/persona.js...)

Content checks:
- extractSection: FOUND (3 usages)
- reconstructFile: FOUND (2 usages)
- tuning/preset/: FOUND
- base_weights: FOUND
- Сохранить матрицу: FOUND
- Agent-Adam-Chip/About/Identity.md: FOUND
- min-height:120px: FOUND
- AIIM_ASPECTS 12 codes: FOUND (12/12)
- Syntax (ESM): PASSED
- Line count: 480 (minimum 200 required)
