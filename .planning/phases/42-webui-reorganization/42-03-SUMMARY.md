---
phase: 42-webui-reorganization
plan: "03"
subsystem: WebUI
tags: [panel, markdown-editor, memory, instructions, persona, tuning]
dependency_graph:
  requires: [42-01-PLAN]
  provides: [agent/instructions-panel, agent/memory-panel]
  affects:
    - System/WebUI/static/js/panels/agent/instructions.js
    - System/WebUI/static/js/panels/agent/memory.js
tech_stack:
  added: []
  patterns:
    - mount(target)->teardown contract
    - el() local DOM builder (copy-paste, no barrel export)
    - render/edit toggle via marked.parse with window.marked guard
    - sub-tab pattern (display none/block, no persistence)
key_files:
  created:
    - System/WebUI/static/js/panels/agent/instructions.js
    - System/WebUI/static/js/panels/agent/memory.js
  modified: []
decisions:
  - "instructions.js: PUT body { path, content } written across two lines (body: { path, content }) — functionally identical to plan's single-line pattern"
  - "memory.js Дополненная tab: memory settings (episodic/weights/semantic/recent_injection/consolidator) sourced from /api/tuning via saveTuningField, per SPEC-groups in tuning.js — matches plan requirement"
  - "memory.js Базовая tab: pool files (Echoes/Jokes/Chinese) rendered read-only from /api/persona, with echoes/chinese tuning settings cards alongside"
  - "Visitor registry placeholder includes literal 'Phase 37' deferred text per D-06"
requirements_completed: [WEBUI-R03, WEBUI-R06]
metrics:
  duration_minutes: 12
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  completed_date: "2026-06-14"
---

# Phase 42 Plan 03: Инструкции + Память panels

Two new Агент-section pages: Инструкции (System.md/Lore.md/Abilities.md markdown render+edit) and Память (Базовая/Дополненная sub-tabs covering pool files, pool settings, and memory tuning groups).

## What Was Built

### Task 1: panels/agent/instructions.js (223 lines, commit 99bef9f)

`mount(target)` loads `/api/persona`, filters files to `System.md` / `Lore.md` / `Abilities.md` (Identity.md explicitly excluded — comment at top of file documents this belongs to the Личность panel). Each file gets a `buildMarkdownEditor()` card:
- View mode: `window.marked.parse(content)` into `.md-render` div, with `<pre>` fallback if marked is unavailable.
- Edit mode: `.textarea.field-wide` (min-height 240px), autofocus, Save/Cancel buttons.
- Save: `api.raw("/api/persona", { method: "PUT", body: { path, content } })` → toast on success/error, returns to view on success.

### Task 2: panels/agent/memory.js (481 lines, uncommitted by prior agent — committed now)

`mount(target)` builds a tab bar (Базовая / Дополненная) with `display:none/block` toggling, no persistence (opens on Базовая).

**Базовая tab:**
- Read-only pool cards for Echoes.md / Jokes.md / Chinese_lines.md (from `/api/persona` files, filtered by path), with empty-state copy if a pool is missing/empty.
- Pool settings cards (echoes/chinese tuning groups) via `saveTuningField` → PUT `/api/tuning`.

**Дополненная tab:**
- Memory tuning groups: `memory.episodic` (5 fields), `memory.episodic.weights` (6), `memory.semantic` (2), `memory.recent_injection` (4), `memory.consolidator` (8, card-full) — all via `saveTuningField`.
- Visitor registry placeholder card: "Реестр посетителей" / "Данные недоступны" / "Реестр посетителей будет доступен после Phase 37." (D-06 deferred).

## Deviations from Plan

None functionally. The prior agent run completed both files but left `memory.js` untracked (uncommitted) and did not write this SUMMARY — both gaps closed in this pass (file staged + SUMMARY written), no code changes made.

## Known Stubs

- Visitor registry (Памяти → Дополненная) is an explicit placeholder per D-06, deferred to Phase 37 — not a gap, by design.

## Threat Flags

| Flag | File | Description |
|------|------|--------------|
| threat_flag: content-injection | System/WebUI/static/js/panels/agent/instructions.js | PUT /api/persona writes System.md/Lore.md/Abilities.md, loaded into LLM system prompt — T-42-05 accepted (operator-only network, marked.js escapes HTML by default) |

## Self-Check: PASSED

Files exist:
- System/WebUI/static/js/panels/agent/instructions.js: FOUND (223 lines)
- System/WebUI/static/js/panels/agent/memory.js: FOUND (481 lines)

Commits exist:
- 99bef9f: FOUND (feat(42-03): add agent/instructions.js...)
- memory.js: staged + committed in this pass

Content checks:
- instructions.js: marked FOUND, System.md/Lore.md/Abilities.md FOUND, Identity.md excluded (comment-only reference), PUT {path, content} FOUND, `node --check` (ESM) PASSED
- memory.js: Базовая FOUND, Дополненная FOUND, consolidator FOUND, "Phase 37" FOUND, Echoes/Jokes/Chinese FOUND, `node --check` (ESM) PASSED
