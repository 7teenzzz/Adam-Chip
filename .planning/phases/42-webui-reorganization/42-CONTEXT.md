# Phase 42: WebUI Reorganization — рефакторинг интерфейса оператора - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete structural rework of the operator WebUI: replace the current flat navigation
with a 3-level hierarchy (section → subsection → page), dismantle the catch-all
"Конфигурация" page into semantically grouped sections, remove dead/duplicate pages,
and restructure the Persona/Identity editing experience.

The result is a UI where every page has a single clear purpose, navigation maps to
the operator's mental model (Agent / System / Technofora / Diagnostics), and the
codebase has no duplicate logic or dead routes.

</domain>

<decisions>
## Implementation Decisions

### Navigation Structure

- **D-01:** Replace flat 2-level nav with a **3-level hierarchy** — section → subsection → page.
  Requires a new nav component with collapsible sections. Current NAV_STRUCTURE in main.js
  and the sidebar in layout.css support only 2 levels; new component needed.

- **D-02:** Final top-level structure (5 sections):
  ```
  1. Чат
  2. Настройки → 2.1 Агент (Личность / Инструкции / Память)
  3. Система   → 3.1 Аудио и видео / 3.2 Сервисы и модели / 3.3 Подсистема ESP32
  4. Технофлора  (top-level, not nested under Система)
  5. Диагностика → 5.1 Метрики и логи / 5.2 Система / 5.3 Подсистема
  ```

- **D-03:** The current "Конфигурация" page (settings.js) is **fully dismantled** — its
  content distributes into Аудио и видео (3.1), Сервисы и модели (3.2), and Подсистема (3.3).
  No standalone "Конфигурация" page survives.

### Agent Section (2.1)

- **D-04 — Личность (2.1.1):**
  - AIIM matrix: 12 aspect sliders with weights and levels + preset selector
    (выставочный / творческий modes via `/api/tuning/preset/{name}`)
  - **Two focused block editors extracted from Identity.md by section name:**
    - «Интенции» — the intentions/drives block
    - «Голос» — the voice/tone/speaking style block
  - Identity.md is NOT shown as a full file textarea. Only these two named sections
    are editable here. Researcher must identify exact section headers in Identity.md.
  - Live emotion indicator (current_emotion) is **deferred to Phase 39** — backend
    fix required (`_status_payload()` doesn't expose `aiim_state.emotion` yet).
  - AIIM lock/unlock system, "describe personality" button, change logging → **deferred to Phase 40**.

- **D-05 — Инструкции (2.1.2):**
  - Three persona text files: System.md, Lore.md, Abilities.md
  - Format: **Markdown rendered view by default + "Редактировать" button** that switches
    to an editable textarea. Save returns to rendered view. Not plain textarea.
  - Identity.md is NOT in Инструкции — it's handled on the Личность page (D-04).

- **D-06 — Память (2.1.3):**
  Two sub-tabs or sub-pages:
  - **Базовая** — curated content pools: Echoes (Agent-Adam-Chip/About/Echoes.md),
    Jokes (Agent-Adam-Chip/About/Jokes.md), Chinese lines (Agent-Adam-Chip/About/Chinese_lines.md).
    Read-only display or light editor for these pools; settings for each pool
    (cooldown, thresholds, match settings).
  - **Дополненная** — accumulated memory: visitor registry (Phase 37 data, read-only in Phase 42),
    important facts / semantic diary. Memory system settings (episodic thresholds,
    salience weights, consolidator schedule) live here, not under Система.

### Система Section (3)

- **D-07 — Аудио и видео (3.1):** Combines current audioInput.js (mic calibration, wake-word
  sensitivity, VAD, EQ, presets) with video/camera config fields from current settings.js.
  Hidden camera.js page content may also integrate here or link from here.

- **D-08 — Сервисы и модели (3.2):** Merge of current services.js + models.js.
  Remove: dead VILA1.5-3b card (removed in commit f61bacf), invalid `riva` ASR option,
  invalid `keep_alive` LLM field. Add: current VLM (Cosmos-Reason2-2B, port 8051) representation.

- **D-09 — Подсистема ESP32 (3.3):** Three sub-sections:
  - **Общие настройки (3.3.1):** ESP32 addresses (base_url, speaker_url, camera_url),
    mcu/power/safety config fields from current settings.js.
  - **Моторный слой (3.3.2):** Direct PCA9685 channel control (manual PWM commands
    for testing/diagnostics). Currently not a dedicated page — new content.
  - **Сенсорный слой (3.3.3):** ESP32 camera stream, ESP32 mic, TEMT6000 light sensor,
    PIR sensor status/readings. Mix of what's currently in subsystem.js health grid
    and audioInput.js ESP32 mic section.

### Технофлора (4) — Top-Level Section

- **D-10:** Технофлора is a **standalone top-level nav item** (same level as Чат, Настройки,
  Система, Диагностика), not nested under Система. Reflects its complexity and artistic
  importance to the installation.

- **D-11:** Five state cards → **single compact table**:
  - Rows: breathe / accent / attentive / think_pulse / wake_bloom
  - Columns: База свечения | Пик свечения (hard cap ≤71%) | Скорость | Вибро | Показать сейчас
  - Speed column header = «Скорость», cell shows **actual field name as sub-label**
    (period_ms / flash_ms / wave_period_ms depending on state) — chosen for precision
    over generic labeling.
  - Hard cap enforcement: peak_pct slider max = 71% (matches `max_duty_pct` validation
    in flora.py `_build_params()`).

- **D-12:** Keyframe-based animation editor for sequences → **deferred to Phase 36B extension**
  (current SmartFlora branch). Phase 42 keeps the existing step-based sequence editor as-is.

### Диагностика (5) — Top-Level Section

- **D-13:** Fully separate top-level section (was previously deferred, now included in Phase 42
  navigation structure at minimum as placeholder pages):
  - **Метрики и логи (5.1):** Current metrics.js (3 tabs) + logs.js (Log Viewer proxy).
  - **Система (5.2):** Jetson health (nvpmodel, jetson_clocks), systemd service status
    for all adam-* units. Partially exists in subsystem.js power section.
  - **Подсистема (5.3):** ESP32 module health grid (mic/cam/pcm5102/pca9685/temt600/pir)
    currently in subsystem.js. Moved here as diagnostics.

### Dead Code Removal

- **D-14:** Remove routes + files:
  - `scene.js` — pure redirect stub to `#/flora`, no content
  - `tuning.js` (hidden `#/tuning`) — 10/14 groups duplicate settings.js;
    unique groups migrated: memory groups → Память (2.1.3), AIIM/emotion/preset → Личность (2.1.1)
  - `prompts.js` (hidden `#/prompts`) — near-duplicate of metrics.js "Промты" tab;
    unique: `inlineList(recent_episodic)` must be ported to metrics.js before deletion

- **D-15:** Audio input page fix: volume block currently uses `card-full` (full-width)
  for a single slider — reduce to normal card width. Remove duplicate wake-word threshold
  field (keep only in calibration block, `audioInput.js` lines ~400-450).

### Claude's Discretion

- Exact implementation of 3-level nav component (accordion, nested lists, fly-out) —
  choose whatever fits the existing CSS token system and works on the narrow sidebar.
- Sub-page routing strategy: whether 3rd-level pages get their own hash routes
  (`#/agent/persona`, `#/agent/instructions`) or are rendered as tabs within a parent route.
- Ordering of items within each merged section.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Navigation & Routing
- `System/WebUI/static/js/router.js` — ROUTES map (all current routes including hidden ones to delete)
- `System/WebUI/static/js/main.js` — NAV_STRUCTURE (current visible nav items) and SIDE_EVENTS set (~lines 302-342)

### UI Patterns & CSS
- `System/WebUI/static/css/layout.css` — nav/sidebar CSS classes, `.card-grid`, `.grid-2/3/4`, `.field-grid`, `.row`, `.col`
- `System/WebUI/static/css/components.css` — `.card`, `.card-header`, `.card-body`, `.badge`, `.dot`, `.kv` patterns

### Current Pages (all to be restructured or deleted)
- `System/WebUI/static/js/panels/settings.js` — catch-all config page (SCHEMA array, ~22-25 cards); source of content for 3.1/3.2/3.3
- `System/WebUI/static/js/panels/persona.js` — current Личность page (full file textarea editors)
- `System/WebUI/static/js/panels/tuning.js` — hidden page to delete; TUNING_GROUPS for migration reference
- `System/WebUI/static/js/panels/flora.js` — Технофлора page (STATE_LABELS, state card structure, sequences editor)
- `System/WebUI/static/js/panels/audioInput.js` — current audio input page (5 cards, volume card fix needed)
- `System/WebUI/static/js/panels/services.js` — to merge with models.js (dead VILA card inside)
- `System/WebUI/static/js/panels/models.js` — to merge with services.js (invalid fields)
- `System/WebUI/static/js/panels/subsystem.js` — ESP32 health + addresses + mcu config
- `System/WebUI/static/js/panels/metrics.js` — 3 tabs; must receive `inlineList(recent_episodic)` from prompts.js before deletion
- `System/WebUI/static/js/panels/prompts.js` — hidden page to delete after migration
- `System/WebUI/static/js/panels/scene.js` — dead stub to delete immediately

### Persona Content (for Инструкции page)
- `Agent-Adam-Chip/About/System.md` — system prompt / base instructions
- `Agent-Adam-Chip/About/Identity.md` — identity file; researcher must find section headers for «Интенции» and «Голос» blocks
- `Agent-Adam-Chip/About/Lore.md` — backstory
- `Agent-Adam-Chip/About/Abilities.md` — capabilities

### Memory Content Pools (for Базовая память)
- `Agent-Adam-Chip/About/Echoes.md` — echo phrase pool (yaml-frontmatter block format)
- `Agent-Adam-Chip/About/Jokes.md` — joke pool (same format)
- `Agent-Adam-Chip/About/Chinese_lines.md` — Chinese phrase pool

### Backend Config & Flora
- `System/Config.json` — runtime config (all non-flora numeric params)
- `System/Flora.json` — flora config (extracted from Config.json, per refactor commit)
- `System/adam/flora.py` — flora backend; `_build_params()` enforces peak_pct≤71% via `max_duty_pct`
- `System/adam/tuning.py` — hot-reload backing store for `/api/tuning` (iAdam.json)
- `System/adam/api_runtime.py` — all `/api/*` endpoints; `/api/persona` GET/PUT, `/api/tuning` GET/PUT, `/api/flora/*`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `el()` DOM builder pattern (used in all panels) — use for all new panel code
- `schemaFields(schema, source)` in settings.js — generates config field inputs from schema; reuse when migrating settings fields to new pages
- `subscribeEvents(types, cb)` / `state.subscribe()` in main.js — SSE subscription pattern for live data
- `.card > .card-header(.card-title) + .card-body` structure — standard card template
- `.field-grid` with `minmax(210px, 1fr)` + `.field-wide` — standard config layout inside cards

### Established Patterns
- Each panel = `export function mount(target) { ...; return teardown; }` — MUST preserve in all new/refactored pages
- Hash router maps route-key → `panels/<name>.js` — any new routes follow this pattern
- SCHEMA array in settings.js (`{ source, tuningSectionPath, title, fields[] }`) — existing pattern for config rendering; reuse when migrating cards
- Persona files loaded via `/api/persona` GET (returns `{ files: [{name, content}] }`) PUT per file

### Integration Points
- `ROUTES` in router.js — add new routes, remove deleted ones
- `NAV_STRUCTURE` in main.js — new 3-level structure requires extending this object shape
- `/api/persona` — GET returns all persona files; PUT `{ file, content }` saves one file;
  new block-based editing (Интенции/Голос) needs server-side section extraction OR
  client-side markdown section parser
- `/api/tuning` GET/PUT — backs iAdam.json (AIIM weights, emotion, presets)
- `/api/flora/config` GET/PUT, `/api/flora/presets`, `/api/flora/sequences` — flora CRUD

### Key Constraint
- `peak_pct` hard cap ≤ 71% everywhere flora values appear in UI (enforced by `_build_params()` in flora.py via `max_duty_pct`). New flora table must enforce this in slider `max` attribute.

</code_context>

<specifics>
## Specific Ideas

- **Инструкции page:** Markdown rendered view by default, "Редактировать" button switches
  to editable textarea, Save returns to rendered view. Not a plain textarea editor.

- **Flora state table speed column:** show actual backend field name as sub-label in each cell
  (e.g., header «Скорость», cell shows value input + small label «period_ms» or «flash_ms»
  or «wave_period_ms»). User chose precision over generic naming.

- **Identity.md section editors:** Only «Интенции» and «Голос» named sections extracted
  and shown as focused block editors. Researcher must identify exact markdown section
  headers in Identity.md for these two blocks.

- **Технофлора at top level:** Визуально равноправна с «Чат», «Настройки», «Система»,
  «Диагностика» — подчёркивает её роль как художественного инструмента, а не просто конфига.

</specifics>

<deferred>
## Deferred Ideas

- **Live emotion indicator on Личность page** → Phase 39 (requires backend fix: expose
  `aiim_state.emotion` in `_status_payload()` in Orchestrator.py)

- **AIIM lock/unlock system** (блокировка аспекта с верификацией) → Phase 40

- **"Describe personality" button** (генерация описания после редактирования матрицы,
  логирование изменений матрицы, сохранение описаний в пресет, переключатель источника
  сознание/подсознание) → Phase 40

- **Keyframe-based animation editor for flora sequences** → Phase 36B extension (SmartFlora branch)

- **Visitor registry page (Дополненная память — content)** → Phase 37. Phase 42 creates
  the placeholder/structure; Phase 37 fills it with real visitor data.

- **Full Диагностика content** (Система 5.2, Подсистема 5.3 with real diagnostics) →
  Phase 42 creates nav structure and moves existing health grid; full diagnostic panels
  are a future phase. Phase 42 just relocates what exists now.

- **Chat page: emotion display + subconscious action feed** → Phase 39

</deferred>

---

*Phase: 42-WebUI Reorganization*
*Context gathered: 2026-06-13*
