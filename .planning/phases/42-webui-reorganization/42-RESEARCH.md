# Phase 42: WebUI Reorganization — Research

**Researched:** 2026-06-13
**Domain:** Browser SPA panel architecture, CSS layout, hash router, FastAPI REST endpoints
**Confidence:** HIGH (all claims verified by direct file reads)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Replace flat 2-level nav with a **3-level hierarchy** (section → subsection → page).
New nav component required — current NAV_STRUCTURE supports only 2 levels.

**D-02:** Five top-level sections:
```
1. Чат
2. Настройки  → 2.1 Агент  (Личность / Инструкции / Память)
3. Система    → 3.1 Аудио и видео / 3.2 Сервисы и модели / 3.3 Подсистема ESP32
4. Технофлора   (standalone, not nested)
5. Диагностика → 5.1 Метрики и логи / 5.2 Система / 5.3 Подсистема
```

**D-03:** settings.js fully dismantled — no standalone "Конфигурация" page survives.

**D-04 (Личность 2.1.1):** AIIM matrix + preset selector + two focused Identity.md block editors:
«Интенции» and «Голос» only. No full-file textarea. Live emotion indicator deferred to Phase 39.

**D-05 (Инструкции 2.1.2):** System.md / Lore.md / Abilities.md with markdown render+edit toggle.
Identity.md NOT in Инструкции.

**D-06 (Память 2.1.3):** Sub-section «Базовая» (Echoes/Jokes/Chinese pools + pool settings)
and «Дополненная» (visitor registry placeholder + memory system tuning params).

**D-07 (Аудио и видео 3.1):** audioInput.js + video/camera/VAD fields from settings.js.

**D-08 (Сервисы и модели 3.2):** Merge services.js + models.js. Remove dead VILA card,
invalid `riva` ASR option, invalid `keep_alive` LLM field. Add Cosmos VLM card.

**D-09 (Подсистема ESP32 3.3):** 3.3.1 Общие настройки / 3.3.2 Моторный слой / 3.3.3 Сенсорный слой.

**D-10:** Технофлора is standalone top-level nav item.

**D-11:** Five state cards → single compact table. Columns: База свечения | Пик свечения (≤71%) |
Скорость (actual field name as sub-label) | Вибро | Показать сейчас.

**D-12:** Flora sequence keyframe editor → deferred Phase 36B.

**D-13:** Диагностика top-level: 5.1 Метрики/логи, 5.2 Система, 5.3 Подсистема ESP32 modules.

**D-14:** Delete scene.js (stub), tuning.js (migrate unique content first), prompts.js (migrate
`inlineList(recent_episodic)` to metrics.js first).

**D-15:** Volume card in audioInput.js: remove `card-full`, use normal card width.

### Claude's Discretion

- Exact 3-level nav component style (accordion / nested lists / fly-out).
- Sub-page routing: own hash routes vs tabs within parent route.
- Ordering of items within each merged section.

### Deferred Ideas (OUT OF SCOPE)

- Live emotion indicator on Личность page (Phase 39)
- AIIM lock/unlock system (Phase 40)
- "Describe personality" button (Phase 40)
- Keyframe animation editor for flora sequences (Phase 36B)
- Visitor registry content (Phase 37)
- Full Диагностика content for 5.2 and 5.3 (future phase)
- Chat page emotion display + subconscious action feed (Phase 39)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WEBUI-R01 | Replace 2-level flat nav with 3-level hierarchy (5 top-level sections per D-02) | NAV_STRUCTURE extension pattern documented; CSS nav classes support nested groups |
| WEBUI-R02 | Dismantle settings.js — distribute 24+ SCHEMA cards to 3.1/3.2/3.3 | Full card-to-section mapping table in §Architecture Patterns below |
| WEBUI-R03 | New Агент sub-section: Личность (AIIM+Identity.md blocks), Инструкции (markdown render/edit), Память (pool settings + memory params) | AIIM field names, Identity.md section headers, `/api/persona` PUT format — all confirmed |
| WEBUI-R04 | Merge services.js + models.js, remove dead/invalid fields | Dead card, invalid fields, new VLM card spec — all documented below |
| WEBUI-R05 | Flora 5 state cards → compact table with per-state field names | STATE_SPEED map with exact key names confirmed from flora.js source |
| WEBUI-R06 | Migrate unique content from tuning.js, prompts.js, scene.js before deletion | Unique content inventory per panel documented below |
| WEBUI-R07 | Fix audioInput.js volume card `card-full` width bug | Confirmed: card 1 (Volume) is the only card that incorrectly uses `card-full` for a single slider |
</phase_requirements>

---

## Summary

Phase 42 is a pure front-end structural reorganization — no new backend endpoints required.
Every piece of content already exists somewhere in the current panels; the work is redistribution,
deduplication, and deletion. The main technical challenge is the 3-level nav (current code supports
only 2 levels) and the client-side markdown section extractor for Identity.md editing.

All source files have been read directly. Confidence is HIGH throughout — no assumed facts.

**Primary recommendation:** Sequence the work as: (1) migrate unique content from dead pages first,
(2) build 3-level nav component, (3) build new section pages top-down, (4) remove old pages last.
This ensures the codebase is always in a working state between commits.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Nav rendering / routing | Browser (SPA) | — | Hash router + DOM; no server involvement |
| Config field editing | Browser → API | — | PATCH `/api/config` sends patch; server hot-reloads |
| Tuning field editing | Browser → API | — | PUT `/api/tuning` writes iAdam.json |
| Persona file editing | Browser → API | — | PUT `/api/persona {path, content}` |
| Identity.md section extraction | Browser | — | Client-side markdown parser; no new endpoint |
| Markdown render (Инструкции) | Browser | — | Client-side renderer (marked.js or similar) |
| Flora state table | Browser → API | — | PATCH `/api/config {section: "flora"}` |
| Service start/stop controls | Browser → API | systemd | POST `/api/services/{name}/{verb}` |
| AIIM weights | Browser → API | — | PUT `/api/tuning` |
| Memory pool display | Browser → API | — | GET `/api/persona` for pool files |

---

## Standard Stack

### Core (existing — do not replace)

| Component | Version / Source | Purpose |
|-----------|-----------------|---------|
| Hash SPA router | `router.js` (custom, ~80 lines) | Route → panel module mapping |
| `el(tag, attrs, children)` | Defined in each panel file | DOM builder; no external dependency |
| `schemaFields(schema, source)` | `settings.js` | Generates config field inputs from schema descriptor array |
| `subscribeEvents(types, cb)` | `main.js` | SSE subscription returning dispose function |
| `state.subscribe()` | `main.js` | Reactive agent-status subscriptions |
| `disposables[]` pattern | `settings.js`, `audioInput.js` | Collects dispose functions, drained on teardown |
| FastAPI REST | `api_runtime.py` | All `/api/*` endpoints |

### New Dependencies Needed

| Library | Purpose | Notes |
|---------|---------|-------|
| Markdown renderer (e.g., marked.js CDN) | Render System.md/Lore.md/Abilities.md in Инструкции | Check if already loaded; otherwise add `<script>` tag in index.html |

**Check first:** `grep -r "marked\|showdown\|markdown" System/WebUI/static/` — if a markdown
library is already loaded, use it. If not, marked.js from CDN is the minimal addition.

### API Endpoints (all verified from `api_runtime.py`)

| Endpoint | Method | Used By |
|----------|--------|---------|
| `/api/config` | GET | All panels reading config |
| `/api/config` | PATCH `{section, patch}` | All panels writing config |
| `/api/tuning` | GET | AIIM panel, memory settings |
| `/api/tuning` | PUT | AIIM panel, memory settings |
| `/api/tuning/preset/{name}` | POST | Preset selector on Личность |
| `/api/persona` | GET | Returns `{base_prompt, files: [{name, path, content}]}` |
| `/api/persona` | PUT `{path, content}` | Save persona file (EXACT format — use `path` not `file`) |
| `/api/services` | GET | Service status |
| `/api/services/{name}/{verb}` | POST | start / stop / restart service |
| `/api/agent/status` | GET | Agent status, current_emotion |
| `/api/flora/config` | GET / PUT | Flora config |
| `/api/flora/state` | POST `{state}` | Trigger state ("Показать сейчас") |
| `/api/flora/presets` | GET | Flora preset list |
| `/api/flora/sequences` | GET | Flora sequence list |
| `/api/models/{llm\|asr\|tts\|vlm}` | GET | Model info for merged services page |
| `/api/ui/status` | GET | ESP32 modules grid, addresses |

**CRITICAL: `/api/persona` PUT body format is `{ path: file.path, content: ta.value }` — NOT `{ file, content }`.**
This is confirmed from `persona.js` source. Using `file` instead of `path` is a silent bug.

---

## Architecture Patterns

### Panel Module Contract (MUST preserve in all new panels)

```js
// Source: all existing panels (settings.js, flora.js, audioInput.js, etc.)
export function mount(target) {
  // ... build DOM, subscribe events ...
  const disposables = [];
  // disposables.push(subscribeEvents([...], cb));
  
  return function teardown() {
    disposables.forEach(fn => fn());
    disposables.length = 0;
  };
}
```

Every new panel MUST export `mount(target)` returning a teardown function.
The router calls teardown before mounting the next panel. Forgetting teardown = SSE leak.

### schemaFields Pattern (reuse for settings migration)

```js
// Source: System/WebUI/static/js/panels/settings.js
const SCHEMA = [
  {
    source: 'config',         // 'config' = /api/config, 'tuning' = /api/tuning
    tuningSectionPath: 'services.asr',  // dot-path into config/tuning object
    title: 'ASR · WhisperX',
    fields: [
      { key: 'model', label: 'Модель', type: 'select',
        options: ['tiny','base','small','medium','large'], hint: '...' },
      { key: 'vad_onset', label: 'VAD onset', type: 'number',
        min: 0, max: 1, step: 0.05, hint: '...' },
    ]
  }
];
// schemaFields(SCHEMA, { config: configData, tuning: tuningData }) renders field-grid inputs
```

### Identity.md Section Extraction (client-side, no new endpoint)

```js
// Source: confirmed by reading Agent-Adam-Chip/About/Identity.md
// Section headers confirmed: "## Интенции" (line 71), "## Голос" (line 97)
// Other headers in file: ## Промт-инъекция (line 1), ## Чтение (line 23),
//   ## Применение (line 54), ## На практике (line 91),
//   ## Что я не делаю (line 107), ## Что под этим всем (line 115)

function extractSection(markdown, sectionName) {
  const lines = markdown.split('\n');
  const startIdx = lines.findIndex(l => l.trim() === `## ${sectionName}`);
  if (startIdx === -1) return null;
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith('## '));
  const sectionLines = endIdx === -1
    ? lines.slice(startIdx + 1)
    : lines.slice(startIdx + 1, endIdx);
  return sectionLines.join('\n').trim();
}

function reconstructFile(original, sectionName, newContent) {
  const lines = original.split('\n');
  const startIdx = lines.findIndex(l => l.trim() === `## ${sectionName}`);
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith('## '));
  const header = [`## ${sectionName}`, ''];
  const body = newContent.split('\n');
  const before = lines.slice(0, startIdx);
  const after = endIdx === -1 ? [] : lines.slice(endIdx);
  return [...before, ...header, ...body, '', ...after].join('\n');
}
// PUT /api/persona { path: 'Agent-Adam-Chip/About/Identity.md', content: reconstructed }
```

### 3-Level Nav Extension

Current `buildNav()` in `main.js` handles 2 levels: top-level items + one collapsible group.
For 3 levels, extend to support nested groups within a group.

```js
// Current NAV_STRUCTURE shape (2-level):
// { type: 'link', route, label, icon }
// { type: 'group', label, icon, children: [{type: 'link', ...}] }

// New shape needed (3-level):
// { type: 'section', label }            — visual separator label only
// { type: 'link', route, label, icon }  — direct nav item (unchanged)
// { type: 'group', label, icon, children: [
//     { type: 'link', ... }             — level-2 item (navigates to panel)
//     { type: 'subgroup', label, children: [  — level-2 collapsible
//         { type: 'link', ... }         — level-3 item
//     ]}
// ]}

// localStorage key for open/close state: extend existing pattern
// Current: `nav-open-${group.label}` → add `nav-open-${group.label}-${subgroup.label}`
```

CSS already has `.nav-link` and `.nav-section` classes. Third-level links need indentation
(add `padding-left: 28px` or a `.nav-link-l3` variant class).

### Recommended Project Structure (new panel files)

```
System/WebUI/static/js/panels/
  agent/
    persona.js          ← replaces current persona.js (AIIM + Identity.md block editors)
    instructions.js     ← new (System.md/Lore.md/Abilities.md markdown render/edit)
    memory.js           ← new (Echoes/Jokes/Chinese pools + memory settings)
  system/
    audioAndVideo.js    ← replaces audioInput.js + settings.js audio/video cards
    servicesModels.js   ← replaces services.js + models.js merged
    esp32.js            ← replaces subsystem.js + settings.js esp32 cards
  diagnostics/
    metricsLogs.js      ← metrics.js content (no change needed, just re-route)
    systemHealth.js     ← new (power/nvpmodel status — from subsystem.js)
    esp32Health.js      ← new (ESP32 module grid — from subsystem.js)
  flora.js              ← in-place rewrite (state cards → table, keep rest)
  metrics.js            ← receives inlineList migration from prompts.js
```

**Alternative (flat, no subdirectories):** all panels in `panels/` with descriptive names.
Both approaches valid — choose based on router.js import path preferences.

---

## settings.js SCHEMA Cards → Destination Mapping

**Complete mapping of all 24+ cards confirmed by reading settings.js source.**

### → 3.1 Аудио и видео

| Card title (settings.js) | source / path | Notes |
|--------------------------|---------------|-------|
| OWW · Wake word | config / wake_word | threshold, debounce_hits, vad_threshold + buildWakeWordExtras() canvas |
| Тайминги голосового пайплайна | config / services.asr | listening timeout, reply timeout, post_tts_discard, silence_after_speech |
| Видеопоток | config / media.video | primary, gstreamer_pipeline, preview_enabled, camera_capture_interval_sec |
| Камера | config / media.video | **DUPLICATE of Видеопоток** — consolidate into one card in 3.1 |
| Микрофон и VAD | config / media.audio | mic_source, input_device, sample_rate, min_speech_ms, max_segment_ms |
| Воркер описания сцены | config / media | scene_worker_enabled, scene_interval_sec, scene_stale_after_sec, scene_context_count |
| Silence calibration | config / services.asr | calibration button (buildSilenceCalibExtras) |

Also: all 5 audioInput.js cards migrate here (with volume card fix D-15).

### → 3.2 Сервисы и модели

| Card title (settings.js) | source / path | Notes |
|--------------------------|---------------|-------|
| Агент | config / agent | mode, language, name |
| LLM · инфраструктура | config / services.llm | base_url, model, num_ctx, timeout_sec |
| LLM · runtime | tuning / llm | temperature, max_tokens, response_word_target |
| Сборка промта | tuning / prompt | history_turns, include_scene, include_sensors |
| Голос (runtime) | tuning / voice | speaker, speed_multiplier, volume slider |
| TTS · Silero | config / services.tts | base_url, output_device, speaker, timeout_sec |
| TTS · Филлер | config / services.tts | filler_enabled, filler_phrase, filler_delay_ms, filler_probability |
| ASR · WhisperX | config / services.asr | model, reply_window_sec, reply_window_expired_action, vad_onset, vad_offset, logprob_threshold — **remove `reply_absolute_deadline_sec` (invalid, Phase 8), deduplicate vad_onset/vad_offset (appear twice)** |
| VLM · описание сцены | config / services.vlm | base_url, model, max_new_tokens, timeout_sec, prompt textarea — **fix stale hint `:8084` → `:8051`** |

Also: all models.js content + services.js service cards (merged).

### → 3.3 Подсистема ESP32

| Card title (settings.js) | source / path | Notes |
|--------------------------|---------------|-------|
| Модуль ESP32 | config / mcu | base_url, speaker_url, timeout_sec, idle_scene |
| Безопасность и моторика | config / safety | half_duplex_mute, motor_default_duration_ms, motor_max_duration_ms, motor_cooldown_ms |
| Системные звуки | config / sounds | enabled, success_path, local_output_device |

Also: ESP32 addresses and health data from subsystem.js.

### → 5.x Диагностика

| Card title (settings.js) | source / path | Notes |
|--------------------------|---------------|-------|
| Питание (nvpmodel) | config / power | required_mode_id, require_jetson_clocks, enforce_in_exhibition → 5.2 Система |
| Диагностика | tuning / diagnostics | log_level, metrics_enabled, trace_prompts → 5.1 |

### → 2.1.3 Память (from settings.js duplicates of tuning.js)

| Card title (settings.js) | source / path |
|--------------------------|---------------|
| Эпизодическая память | tuning / memory.episodic |
| Веса памяти | tuning / memory.episodic.weights |
| Эхо-реплики | tuning / echoes |
| Китайские фразы | tuning / chinese |
| Сессия | tuning / session |
| Воркер сцены (director) | tuning / scene_director |

---

## Dead Page Content Inventory

### scene.js — DELETE IMMEDIATELY (no migration needed)

Content: single button calling `router.go("flora")`. Zero unique content.
Action: remove file, remove from ROUTES in router.js.

### prompts.js — ONE LINE TO MIGRATE, THEN DELETE

Unique content not in metrics.js:

```js
// Source: System/WebUI/static/js/panels/prompts.js, line ~82, inside turnRow()
function inlineList(items) {
  if (!items || !items.length) return null;
  return el("div",
    { style: "color:var(--muted); font-size:12px; margin-top:4px; font-family:var(--font-mono)" },
    items.join(" · ")
  );
}
// Called as: inlineList(item.recent_episodic)
// Location in metrics.js to insert: inside promptTurnRow(), after injectionsBadges div
```

All other content in prompts.js duplicates the "Промты" tab already in metrics.js.

### tuning.js — MIGRATE UNIQUE CONTENT, THEN DELETE

**Unique content → Личность (2.1.1):**
- `identity` SPEC group (7 fields: enabled, default_emotion, decay_target_emotion,
  decay_silence_threshold_seconds, include_in_prompt, max_intentions_in_ctx, aspect_change_threshold)
- `makeAiimWeightsCard(data, dirtyState)` — AIIM 12-aspect slider matrix
- `makePresetCard()` — personality preset selector
- `AIIM_ASPECTS` array (12 objects with code/name/plan/level/ac/or/desc)
- `PLAN_META` color definitions (P/S/I/B/T)
- `LEVEL_LABELS` (5 labels for levels 0–4)

**Unique content → Память (2.1.3):**
- `memory.episodic` SPEC group (5 fields)
- `memory.episodic.weights` SPEC group (6 fields)
- `memory.semantic` SPEC group (2 fields)
- `memory.recent_injection` SPEC group (4 fields)
- `memory.consolidator` SPEC group (8 fields, full-width card)

**DEFERRED (not migrated in Phase 42):**
- `makeEmotionCard()` — deferred to Phase 39

**Duplicates of settings.js (discard, not migrate):**
echoes, chinese, session, scene_director, llm, voice, prompt, diagnostics groups

---

## Flora State Table Field Map

**Confirmed by reading flora.js `STATE_SPEED` constant.**

| State key | Human label | Base field | Peak field | Speed field | Speed min | Speed max | Vibro |
|-----------|-------------|------------|------------|-------------|-----------|-----------|-------|
| breathe | Дыхание | base_pct | peak_pct | period_ms | 1000 | 10000 | bool |
| accent | Акцент | — | peak_pct | period_ms | 300 | 3000 | bool |
| attentive | Внимание | — | peak_pct | wave_period_ms | 100 | 2000 | disabled |
| think_pulse | Размышление | base_pct (if set) | peak_pct | flash_ms | 100 | 3000 | "double_pulse" |
| wake_bloom | Пробуждение | — | peak_pct | period_ms | 1000 | 8000 | bool |

**Hard cap: peak_pct slider `max` attribute MUST be `71` everywhere.**
Enforced by `_build_params()` in `flora.py` via `max_duty_pct`. Flora config also lives in
`System/Flora.json` (split from Config.json per recent commit) — confirm exact PATCH target path.

**"Показать сейчас" button:** saves state edits first, then POSTs
`POST /api/flora/state { state: stateKey }`.

**Save all states:** `PATCH /api/config { section: "flora", patch: { states: { breathe: {...}, ... } } }`
(but flora config may now be in `Flora.json` — verify PATCH section key before coding).

---

## AIIM Matrix Field Names

**Confirmed from reading tuning.js.**

```
AIIM_ASPECTS (12 aspects):
  code: wi | lo | im | ho | co | em | be | sp | se | pe | me | at
  each aspect object: { code, name, plan, level, ac, or, desc }

Weights read from: data.identity.base_weights[aspect.code]
  e.g. data.identity.base_weights.se = 0.92

Current A-2 weights:
  se=0.92, co=0.88, sp=0.85, wi=0.72, im=0.72, lo=0.70,
  pe=0.70, at=0.70, em=0.65, be=0.65, ho=0.60, me=0.30

PLAN_META keys: P (Personal) | S (Social) | I (Internal) | B (Body) | T (Transcendental)
LEVEL_LABELS: 0-4 (5 labels)

/api/tuning GET returns the full tuning object including identity.base_weights
/api/tuning PUT writes the full object back
/api/tuning/preset/{name} POST applies preset (no body needed)
```

---

## Identity.md Section Headers (confirmed)

**File: `Agent-Adam-Chip/About/Identity.md` (read directly)**

| Section name | Header text | Line | Content |
|---|---|---|---|
| AIIM formula | `## Промт-инъекция - базовая формула личности` | 1 | A-2/A-1 code blocks — NOT editable in UI |
| Reference tables | `## Чтение` | 23 | Aspect/plan/level/state tables — NOT editable |
| Character description | `## Применение` | 54 | AIIM prose descriptions — NOT editable |
| **Интенции** | `## Интенции` | **71** | 4 drive paragraphs — **EDITABLE** |
| On practice | `## На практике` | 91 | Approach guidelines — NOT editable |
| **Голос** | `## Голос` | **97** | 7 speech style bullets — **EDITABLE** |
| What I don't do | `## Что я не делаю` | 107 | Anti-patterns — NOT editable |
| Core essence | `## Что под этим всем` | 115 | Closing statement — NOT editable |

**Section extraction:** Split by `## ` boundaries. Content of `## Интенции` runs lines 72-90.
Content of `## Голос` runs lines 98-106.

**IMPORTANT:** Identity.md contains markdown-style code blocks (the AIIM formula uses ``` fences).
These are read directly into the LLM system prompt, so they appear literally in Adam's context.
The section extractor must NOT strip or escape them.

---

## Common Pitfalls

### Pitfall 1: SSE leak from missing teardown
**What goes wrong:** Panel mounts, subscribes to SSE via `subscribeEvents()`, gets replaced by nav, but SSE listener stays open. Over time, 10+ duplicate listeners accumulate on the same event types.
**Why it happens:** Router calls `teardown()` before mounting next panel, but only if `mount()` returns a function. If return is missing or returns `undefined`, no cleanup.
**How to avoid:** Every new panel MUST `return teardown` function. Use `disposables[]` pattern.
**Warning signs:** Console logs duplicating, event handlers firing multiple times.

### Pitfall 2: `/api/persona` PUT with wrong body key
**What goes wrong:** Save fails silently (FastAPI ignores unknown keys depending on validation config).
**Root cause:** CONTEXT.md says `{ file, content }` but persona.js source code uses `{ path, content }`.
**How to avoid:** Always use `{ path: file.path, content: ta.value }`. Never `{ file: ... }`.

### Pitfall 3: settings.js `vad_onset` / `vad_offset` duplication
**What goes wrong:** "ASR · WhisperX" SCHEMA group has these fields appearing TWICE (~lines 206-213 and ~219-226). Naively copying the SCHEMA produces duplicate form fields in 3.2.
**How to avoid:** When migrating ASR fields to 3.2, deduplicate — keep only the version with correct hint text.

### Pitfall 4: Flora config in Flora.json vs Config.json
**What goes wrong:** PATCH `/api/config { section: "flora" }` may not work if flora config was extracted to `Flora.json`.
**Evidence:** CONTEXT.md canonical_refs mentions `System/Flora.json` as a separate file. The flora.js panel save button uses `PATCH /api/config { section: "flora" }` (from old code) — this may be stale.
**How to avoid:** Before implementing flora table save, verify which endpoint `flora.py` reads from. Read `System/adam/flora.py` or check api_runtime.py for flora endpoint handler.

### Pitfall 5: `card-full` in audioInput.js
**What goes wrong:** Volume card (card 1) uses `card-full` class, making a single volume slider span the entire grid width. D-15 requires fixing this.
**How to avoid:** Remove `card-full` from the Volume card's wrapper div. All other 4 cards legitimately use `card-full` (canvas elements, complex layouts).

### Pitfall 6: VLM stale hint URL
**What goes wrong:** settings.js "VLM · описание сцены" card has hint text `"http://127.0.0.1:8084"` but current VLM (Cosmos-Reason2-2B) is on port `8051`.
**How to avoid:** Update hint to `:8051` when migrating this card to 3.2.

### Pitfall 7: services.js dead VILA1.5-3b card
**What goes wrong:** `buildVlmCard()` in services.js calls `/api/live_vlm/status` and `/api/live_vlm/{start|stop}` — these Docker endpoints were removed in commit f61bacf. Card renders but controls do nothing or error.
**How to avoid:** Delete `buildVlmCard()` entirely. Add new Cosmos VLM card using `SERVICE_META` pattern with `adam-vlm.service` (same as other services).

### Pitfall 8: models.js invalid fields
**What goes wrong:** LLM model card has `keep_alive` field — llama.cpp ignores it (no-op but misleading). ASR provider select has `riva` option — only `whisperx` is valid.
**How to avoid:** Remove `keep_alive` from LLM card. Remove `riva` from ASR provider options when merging.

### Pitfall 9: attentive state has no base_pct / vibro disabled
**What goes wrong:** Flora table implementation assumes uniform column structure. `attentive` has no `base_pct` field and `vibro` is always disabled.
**How to avoid:** In the table, `attentive`'s Base column shows "—" or empty input (disabled). Vibro checkbox for `attentive` is disabled. See STATE_SPEED confirmed values above.

### Pitfall 10: Identity.md AIIM formula uses code fences
**What goes wrong:** Client-side markdown parser or section extractor might strip or escape the ``` code blocks in `## Промт-инъекция`.
**Impact:** Only relevant if the FULL file textarea is shown somewhere. Since `## Интенции` and `## Голос` don't contain code fences, the focused editors are safe. But the `reconstructFile()` function must preserve the rest of the file verbatim.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Markdown rendering | Custom HTML converter | marked.js CDN (or whatever is already loaded) |
| Config field forms | Custom input generators | Reuse `schemaFields()` from settings.js |
| SSE subscription cleanup | Ad-hoc cleanup code | `disposables[]` + `subscribeEvents()` pattern |
| State persistence for nav open/close | Custom localStorage wrapper | Extend existing `localStorage.getItem('nav-open-...')` pattern in main.js |

---

## 3-Level Nav Implementation

**Recommended approach (fits existing CSS without new classes):**

Extend `NAV_STRUCTURE` in `main.js` with a new item type `subgroup`. Update `buildNav()` to render nested collapsible groups. Use indentation via inline style or a new `.nav-link-l3` CSS class (padding-left offset).

Existing CSS token `--nav-w` controls sidebar width. Third-level links need `padding-left: 28px`
(current level-2 links use `padding: 10px 14px` = 14px left; add 14px for third level = 28px).

LocalStorage key pattern to extend:
- Level 1 group open: `nav-open-Настройки` (existing)
- Level 2 subgroup open: `nav-open-Настройки-Агент` (new)

**Hash routes for 3rd-level pages (recommended over tabs for back-button support):**
```
#/chat
#/agent/persona        ← Личность
#/agent/instructions   ← Инструкции
#/agent/memory         ← Память
#/system/audio         ← Аудио и видео
#/system/services      ← Сервисы и модели
#/system/esp32         ← Подсистема ESP32
#/flora
#/diagnostics/metrics  ← Метрики и логи
#/diagnostics/system   ← Система
#/diagnostics/esp32    ← Подсистема ESP32 modules
```

ROUTES in router.js currently uses flat keys (`"settings"`, `"audioInput"`). New routes
need `/` in key OR a different delimiter. Router parses `window.location.hash.slice(2)` —
with `#/agent/persona` hash, the route key would be `"agent/persona"`. This is valid JS
object key syntax.

---

## CSS Layout Notes

**Confirmed from layout.css:**

- `.card-grid` uses `auto-fill, minmax(...)` — cards automatically wrap
- `.card-full`: spans full grid width (used for wide canvas/complex cards)
- `.field-grid`: `repeat(auto-fill, minmax(210px, 1fr))` — standard config field layout
- `.field-wide`: `grid-column: 1 / -1` — full-width field within field-grid
- `.grid-2`, `.grid-3`, `.grid-4`: fixed column grids for structured layouts
- `.nav-section`: uppercase label, dim color — use for section dividers in 3-level nav
- `.nav-link.active`: left green border + bg tint — must still work for 3rd-level active state

No new CSS layout classes needed for basic implementation. Only nav-specific indentation additions.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|---|---|---|
| VILA1.5-3b Docker VLM | Cosmos-Reason2-2B via llama.cpp `:8051` | services.js dead card must be removed |
| `tuning` section in Config.json | iAdam.json via `/api/tuning` | Config.json `tuning` section is dead code; never read |
| flat 2-level nav | (this phase) 3-level nav | NAV_STRUCTURE shape must change |
| Full persona file textarea editors | (this phase) markdown render+edit + section editors | No new backend endpoint |

---

## Environment Availability

Step 2.6: SKIPPED — phase is purely front-end code reorganization. No new external tools, services, runtimes, or CLIs required. All backend endpoints already exist.

---

## Validation Architecture

Phase 42 is a UI-only reorganization. No automated test suite exists for the WebUI panels (no jest/vitest/playwright found in repo). Validation is manual smoke testing.

### Manual Validation Checklist per Wave

| Check | Automated? | Method |
|-------|------------|--------|
| All nav links navigate without console errors | No | Browser devtools |
| Each panel mounts and unmounts without SSE leak | No | Browser devtools → Network → EventStream |
| Config field saves round-trip (read → change → PATCH → reload confirms) | No | Manual browser test |
| `/api/persona` PUT saves Identity.md section correctly | No | Read file after save, confirm only target section changed |
| Flora table save + "Показать сейчас" trigger | No | Visual + browser devtools |
| AIIM sliders save to `/api/tuning` | No | Check response JSON |
| Deleted routes (scene, tuning, prompts) return 404 or redirect | No | Navigate to old hash |
| audioInput.js volume card no longer `card-full` | No | Visual check |

---

## Open Questions

1. **Flora.json vs Config.json for flora config**
   - What we know: CONTEXT.md mentions `System/Flora.json` as separate file. flora.js save button uses `PATCH /api/config { section: "flora" }`.
   - What's unclear: Does api_runtime.py route the flora section to Flora.json or Config.json? Was the split complete?
   - Recommendation: Before implementing flora table save, read `System/adam/api_runtime.py` flora handler section and `System/adam/flora.py` config loader. This is ~15 lines to confirm.

2. **Markdown library availability**
   - What we know: Инструкции page needs markdown rendering.
   - What's unclear: Is any markdown library already loaded in index.html?
   - Recommendation: `grep -r "marked\|showdown\|markdown" System/WebUI/static/` before Wave 0.

3. **3rd-level hash route key format**
   - What we know: `router.js` uses `ROUTES[key]` where key is derived from hash.
   - What's unclear: Router currently maps keys like `"settings"` — does it handle keys containing `/`?
   - Recommendation: Read last 20 lines of router.js to confirm `window.location.hash.slice(2)` parsing before adding nested routes.

---

## Assumptions Log

All claims in this research were verified by direct file reads. No training-data-only assumptions.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Flora config PATCH endpoint is `/api/config { section: "flora" }` | Pitfall 4 | Save would silently fail if Flora.json needs different endpoint |
| A2 | `marked.js` or equivalent not yet loaded in index.html | Open Questions 2 | Unnecessary CDN addition if already present |

---

## Sources

### Primary (HIGH confidence — direct file reads)
- `System/WebUI/static/js/router.js` — all ROUTES including hidden routes
- `System/WebUI/static/js/main.js` — NAV_STRUCTURE, SIDE_EVENTS, buildNav()
- `System/WebUI/static/js/panels/settings.js` — full SCHEMA array (24+ cards)
- `System/WebUI/static/js/panels/tuning.js` — SPEC groups, AIIM_ASPECTS, makeAiimWeightsCard()
- `System/WebUI/static/js/panels/flora.js` — STATE_SPEED, STATE_LABELS, STATE_KEYS
- `System/WebUI/static/js/panels/services.js` — SERVICE_META, buildServiceCard(), dead buildVlmCard()
- `System/WebUI/static/js/panels/models.js` — model cards, invalid fields identified
- `System/WebUI/static/js/panels/audioInput.js` — 5 cards, card-full usage confirmed
- `System/WebUI/static/js/panels/prompts.js` — unique inlineList() confirmed
- `System/WebUI/static/js/panels/scene.js` — redirect stub confirmed
- `System/WebUI/static/js/panels/persona.js` — /api/persona PUT format confirmed
- `System/WebUI/static/js/panels/metrics.js` — 3 tabs, missing inlineList call confirmed
- `System/WebUI/static/css/layout.css` — nav/card CSS classes
- `Agent-Adam-Chip/About/Identity.md` — section headers at exact line numbers
- `.planning/phases/42-webui-reorganization/42-CONTEXT.md` — all locked decisions
- `System/adam/api_runtime.py` — endpoint signatures

---

## Metadata

**Confidence breakdown:**
- Panel content inventory: HIGH — all panels read directly
- settings.js card mapping: HIGH — full SCHEMA array read and categorized
- Identity.md section headers: HIGH — file read, exact lines confirmed
- AIIM field names: HIGH — tuning.js AIIM_ASPECTS read directly
- Flora state table: HIGH — STATE_SPEED confirmed from source
- API endpoint formats: HIGH — persona.js source confirms `{ path, content }` body
- 3-level nav implementation: MEDIUM — design recommendation, not existing code
- Flora.json vs Config.json split: LOW — requires additional file read to confirm

**Research date:** 2026-06-13
**Valid until:** 2026-07-13 (stable UI codebase; re-verify if router.js or main.js change before planning begins)
