---
phase: 42
slug: webui-reorganization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual browser smoke tests + Python health checks |
| **Config file** | none — WebUI is vanilla JS, no build step |
| **Quick run command** | `curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status` |
| **Full suite command** | Open browser → navigate all 5 sections → verify no console errors |
| **Estimated runtime** | ~2 minutes (manual) |

---

## Sampling Rate

- **After every task commit:** Reload page in browser, navigate to affected section, confirm no JS errors in console.
- **After each wave:** Full navigation walkthrough — all 5 sections must load without errors.

---

## Validation Dimensions

### Dimension 1: Navigation Structure (D-01/D-02)
- 3-level nav renders in sidebar with correct hierarchy
- Collapsing/expanding sections works and persists
- Active page is highlighted correctly
- All routes resolve without 404/blank page

### Dimension 2: Dead Code Removal (D-14/WEBUI-R01)
- `#/tuning`, `#/prompts`, `#/scene` return 404 or redirect
- No console errors for removed routes
- `inlineList(recent_episodic)` visible on Метрики page before deletion

### Dimension 3: Content Migration
- All unique content from tuning.js visible on Личность/Память pages
- All settings.js content distributed into 3.1/3.2/3.3 sections
- services.js + models.js merged — no duplicate entries, no dead VILA card

### Dimension 4: Flora Table (D-11/WEBUI-R07)
- Single table replaces 5 cards
- Peak slider max=71 enforced
- Speed sub-label shows correct field name per state
- "Показать сейчас" triggers flora state on ESP32

### Dimension 5: Инструкции Markdown Toggle (D-05)
- Files render as HTML markdown by default
- "Редактировать" switches to textarea
- Save POSTs to `/api/persona` and returns to rendered view
- Identity.md NOT present on Инструкции page

### Dimension 6: AIIM Matrix (D-04/WEBUI-R05)
- 12 aspect sliders visible on Личность page
- Preset selector functional
- «Интенции» and «Голос» block editors only (Identity.md sections by name)

### Dimension 7: Audio Input Fix (D-15/WEBUI-R06)
- Volume card is normal card width (not `card-full`)
- No duplicate wake-word threshold field

---

## Validation Architecture

Validation for this phase is manual/visual — there is no automated test suite for the WebUI. Each task acceptance criterion includes a specific browser check.

**Pre-execution check:**
```bash
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
```
Orchestrator must be running before WebUI validation.

**Post-task check pattern:**
1. Hard refresh browser (Ctrl+Shift+R)
2. Navigate to the modified page
3. Open DevTools → Console → confirm no uncaught errors
4. Verify the specific acceptance criteria for the completed task

---

## Risk Areas

| Risk | Mitigation |
|------|-----------|
| 3-level nav breaks existing route keys | Test all existing routes before/after nav refactor |
| settings.js SCHEMA migration leaves orphaned fields | Grep for `schemaFields(` calls in new pages |
| Dead page deletion breaks any remaining internal link | Grep for `#/tuning`, `#/prompts`, `#/scene` in all JS before deletion |
| marked.js CDN load failure | Check browser network tab; add fallback plain-text mode |
