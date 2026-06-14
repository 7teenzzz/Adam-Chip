---
phase: 42-webui-reorganization
plan: "01"
subsystem: WebUI
tags: [router, navigation, marked, 3-level-nav]
dependency_graph:
  requires: []
  provides: [nested-hash-routing, 3-level-nav, marked-js]
  affects: [System/WebUI/static/js/router.js, System/WebUI/static/js/main.js, System/WebUI/index.html]
tech_stack:
  added: [marked.js CDN (jsdelivr)]
  patterns: [collapsible-nav-L1-L2-L3, localStorage-persistence, parseHash-nested-routes]
key_files:
  created: []
  modified:
    - System/WebUI/static/js/router.js
    - System/WebUI/static/js/main.js
    - System/WebUI/index.html
decisions:
  - "parseHash() splits only on '?' (not [/?]) — preserves nested keys like 'agent/persona' intact"
  - "Legacy flat routes kept in ROUTES until Wave 4 (plan 42-08) migration"
  - "buildCollapsible() helper extracted from buildNav() for reuse at L1 and L2 levels"
  - "navLink() extended with paddingLeft string param instead of boolean indent flag"
  - "marked.js loaded from CDN with offline guard (if window.marked) — raw text fallback"
metrics:
  duration_minutes: 3
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
  completed_date: "2026-06-14"
---

# Phase 42 Plan 01: Navigation Foundation — router + nav + marked.js

Foundation layer for 3-level WebUI navigation: nested hash routing, collapsible 3-level sidebar, and markdown rendering library.

## What Was Built

### Task 1: router.js — parseHash() fix + nested ROUTES (c3cf56d)

`parseHash()` was changed from `.split(/[/?]/)[0]` to `.split("?")[0]`. The old split took only the first path segment, so `#/agent/persona` yielded `"agent"` (not in ROUTES) and always fell through to DEFAULT_ROUTE. The new split preserves the full path before `?`, making `"agent/persona"` a valid ROUTES key.

ROUTES expanded with 9 nested keys:
- `agent/persona`, `agent/instructions`, `agent/memory`
- `system/audio`, `system/services`, `system/esp32`
- `diagnostics/metrics`, `diagnostics/system`, `diagnostics/esp32`

Duplicate `prompts` key (was declared twice) reduced to one entry. Legacy flat routes (`settings`, `tuning`, `prompts`, `scene`, `subsystem`, etc.) kept intact for Wave 4 migration.

### Task 2: main.js — 3-level NAV_STRUCTURE + buildNav() (5869f05)

NAV_STRUCTURE replaced from 2-level flat structure to 3-level hierarchy:
```
Чат                          (top-level direct)
Настройки → Агент → Личность / Инструкции / Память   (L1→L2→L3)
Система → Аудио и видео / Сервисы и модели / Подсистема ESP32  (L1→L2)
Технофлора                   (top-level direct)
Диагностика → Метрики и логи / Система / Подсистема   (L1→L2)
```

`buildNav()` refactored with two helpers:
- `buildCollapsible(storageKey, label, paddingLeft)` — creates collapsible header + body, handles localStorage persistence
- `navLink(key, label, paddingLeft)` — extended from boolean `indent` to CSS value string

L1 groups: `navGroup_${item.id}` localStorage key
L2 subgroups: `navGroup_${parentId}_${subId}` localStorage key
L3 leaf links: `padding-left:40px`
L2 direct links: `padding-left:24px`

### Task 3: index.html — marked.js CDN (a2b7502)

Added `<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js">` before main.js. Added inline `<script>` with `marked.setOptions({breaks:true, gfm:true})` wrapped in `if (window.marked)` guard for offline/CDN-blocked environments — panels using `marked.parse()` show raw text instead of crashing.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None in this plan. Panel files referenced by new routes (`agent/persona.js`, etc.) do not exist yet — router shows error card for missing panels. This is by design: panels are created in Waves 2-4.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: script-external | System/WebUI/index.html | marked.min.js loaded from cdn.jsdelivr.net — external script in operator UI context |

Accepted per T-42-01: UI runs in isolated Jetson network; CDN script is MIT-licensed with no runtime network calls; offline guard prevents crash.

## Self-Check: PASSED

Files exist:
- System/WebUI/static/js/router.js: FOUND
- System/WebUI/static/js/main.js: FOUND
- System/WebUI/index.html: FOUND

Commits exist:
- c3cf56d: FOUND (feat(42-01): fix parseHash()...)
- 5869f05: FOUND (feat(42-01): 3-level NAV_STRUCTURE...)
- a2b7502: FOUND (feat(42-01): add marked.js CDN...)
