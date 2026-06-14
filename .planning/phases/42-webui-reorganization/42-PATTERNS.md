# Phase 42: WebUI Reorganization — Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 16 (11 modified, 2 deleted with migration, 3 new)
**Analogs found:** 15 / 16

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `System/WebUI/static/js/router.js` | router | request-response | self (modify) | exact |
| `System/WebUI/static/js/main.js` | layout/nav | event-driven | self (modify) | exact |
| `System/WebUI/static/js/panels/settings.js` | config panel | CRUD | self (dismantle) | exact |
| `System/WebUI/static/js/panels/persona.js` | persona editor | request-response | self (restructure) | exact |
| `System/WebUI/static/js/panels/flora.js` | flora panel | CRUD | self (rewrite table) | exact |
| `System/WebUI/static/js/panels/audioInput.js` | input panel | CRUD+SSE | self (fix) | exact |
| `System/WebUI/static/js/panels/services.js` | services panel | request-response | self (merge) | exact |
| `System/WebUI/static/js/panels/models.js` | models panel | request-response | `services.js` | role-match |
| `System/WebUI/static/js/panels/metrics.js` | metrics panel | request-response | self (receive migration) | exact |
| `System/WebUI/static/js/panels/subsystem.js` | subsystem panel | request-response | self (split) | exact |
| `System/WebUI/static/js/panels/tuning.js` | DELETE (migrate content) | — | `settings.js` SCHEMA pattern | exact |
| `System/WebUI/static/js/panels/prompts.js` | DELETE (migrate inlineList) | — | `metrics.js` promptTurnRow | exact |
| `System/WebUI/static/js/panels/scene.js` | DELETE immediately | — | none (stub) | N/A |
| NEW: `System/WebUI/static/js/panels/memory.js` | memory panel | CRUD | `settings.js` + `persona.js` | role-match |
| NEW: agent/persona.js (or renamed) | persona editor | request-response | `persona.js` + `tuning.js` patterns | exact |
| NEW: agent/instructions.js | markdown editor | request-response | `persona.js` (textarea pattern) | role-match |

---

## Pattern Assignments

### 1. `router.js` — add nested routes, remove dead routes

**Analog:** self

**Current ROUTES map** (`router.js` lines 3-21):
```js
const ROUTES = {
  chat:      { file: "chat",      label: "Чат" },
  settings:  { file: "settings",  label: "Конфигурация" },
  audioInput:{ file: "audioInput",label: "Аудио-вход" },
  // ...
  scene:     { file: "scene",     label: "Сцена" },   // DELETE
  tuning:    { file: "tuning",    label: "Тюнинг" },  // DELETE
  prompts:   { file: "prompts",   label: "Промты" },  // DELETE
};
```

**New pattern — nested key with `/` delimiter** (`router.js` lines 28-31 show how hash is parsed):
```js
// parseHash() strips "#/" and splits on [/?] taking first segment.
// BUT for nested routes #/agent/persona, we need to take the full path.
// Change parseHash to: hash.replace(/^#\/?/, "") without split
// Then route keys like "agent/persona" work as JS object keys.

const ROUTES = {
  chat:                   { file: "chat",                   label: "Чат" },
  "agent/persona":        { file: "agent/persona",          label: "Личность" },
  "agent/instructions":   { file: "agent/instructions",     label: "Инструкции" },
  "agent/memory":         { file: "agent/memory",           label: "Память" },
  "system/audio":         { file: "system/audioAndVideo",   label: "Аудио и видео" },
  "system/services":      { file: "system/servicesModels",  label: "Сервисы и модели" },
  "system/esp32":         { file: "system/esp32",           label: "Подсистема ESP32" },
  flora:                  { file: "flora",                  label: "Технофлора" },
  "diagnostics/metrics":  { file: "diagnostics/metricsLogs",label: "Метрики и логи" },
  "diagnostics/system":   { file: "diagnostics/systemHealth",label: "Система" },
  "diagnostics/esp32":    { file: "diagnostics/esp32Health", label: "Подсистема" },
};
```

**Import path in `activate()`** (`router.js` lines 39-46 — dynamic import):
```js
// cfg.file = "agent/persona" → import("./panels/agent/persona.js")
// This already works if subdirectories exist under panels/
const module = await import(`./panels/${cfg.file}.js`);
```

---

### 2. `main.js` — 3-level NAV_STRUCTURE + buildNav()

**Analog:** self

**Current NAV_STRUCTURE** (`main.js` lines 75-94 — 2-level, single group with flat children):
```js
const NAV_STRUCTURE = [
  { key: "chat", label: "Чат" },
  {
    group: "Настройки", id: "config",
    children: [
      { sectionLabel: "Система" },
      { key: "settings",   label: "Настройки" },
      // ...
    ],
  },
  { key: "metrics", label: "Метрики" },
  { key: "logs",    label: "Логи" },
];
```

**navLink() function** (`main.js` lines 96-106 — reuse as-is for L2/L3 links):
```js
function navLink(key, label, indent = false) {
  return el("a", {
    class: "nav-link",
    href: `#/${key}`,
    "data-route": key,
    style: indent ? "padding-left:24px" : "",
  }, [
    el("span", { class: "mono", style: "color:var(--accent)" }, "▸"),
    el("span", null, label),
  ]);
}
```

**Current group collapse pattern** (`main.js` lines 118-154 — extend this for subgroups):
```js
// localStorage key for open state:
const storageKey = `navGroup_${item.id}`;
const isOpen = localStorage.getItem(storageKey) !== "false";

const body = el("div", {
  id: `nav-group-${item.id}`,
  style: `display:${isOpen ? "flex" : "none"}; flex-direction:column`,
});

const arrowSpan = el("span", { class: "mono", style: "color:var(--accent); width:14px; text-align:center" }, isOpen ? "▾" : "▸");
const header = el("button", {
  class: "nav-link",
  style: "width:100%; text-align:left; background:none; border:none; cursor:pointer; ...",
  onclick: () => {
    const open = body.style.display !== "none";
    body.style.display = open ? "none" : "flex";
    arrowSpan.textContent = open ? "▸" : "▾";
    localStorage.setItem(storageKey, String(!open));
  },
}, [arrowSpan, el("span", null, item.group)]);
```

**New 3-level NAV_STRUCTURE shape** (extend current pattern):
```js
// New item type: { type: "subgroup", label, id, children: [{key, label}] }
// Storage key pattern for subgroups: `navGroup_${parentId}_${subId}`
// L3 link indent: padding-left:40px (add 16px to current L2 indent of 24px)

const NAV_STRUCTURE = [
  { key: "chat", label: "Чат" },
  {
    group: "Настройки", id: "settings",
    children: [
      {
        subgroup: "Агент", id: "agent",
        children: [
          { key: "agent/persona",      label: "Личность" },
          { key: "agent/instructions", label: "Инструкции" },
          { key: "agent/memory",       label: "Память" },
        ],
      },
    ],
  },
  {
    group: "Система", id: "system",
    children: [
      { key: "system/audio",    label: "Аудио и видео" },
      { key: "system/services", label: "Сервисы и модели" },
      { key: "system/esp32",    label: "Подсистема ESP32" },
    ],
  },
  { key: "flora", label: "Технофлора" },
  {
    group: "Диагностика", id: "diagnostics",
    children: [
      { key: "diagnostics/metrics", label: "Метрики и логи" },
      { key: "diagnostics/system",  label: "Система" },
      { key: "diagnostics/esp32",   label: "Подсистема" },
    ],
  },
];
```

---

### 3. `panels/settings.js` — DISMANTLE (source of SCHEMA pattern)

**This file is dismantled into 3.1/3.2/3.3. Copy these patterns into new panels.**

**SCHEMA group structure** (`settings.js` lines 46-445 — the complete pattern):
```js
const SCHEMA = [
  {
    source: "config",           // "config" or "tuning"
    section: "services.asr",   // dot-path for config; OR:
    tuningSectionPath: "llm",  // dot-path for tuning
    title: "ASR · WhisperX",
    fields: [
      { key: "model", label: "Модель WhisperX", type: "select",
        choices: ["tiny","base","small","medium","large-v2","large-v3"],
        hint: "..." },
      { key: "vad_onset", label: "VAD onset", type: "number",
        min: 0.01, max: 0.99, step: 0.05, hint: "..." },
      { key: "timeout_sec", label: "Таймаут HTTP (с)", type: "number" },
    ],
  },
];
```

**renderFieldRow()** (`settings.js` lines 816-829 — copy verbatim):
```js
function renderFieldRow(field, value, buildInput) {
  const status = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
  const input = buildInput(field, status);
  return el("label", { style: "display:flex; flex-direction:column; gap:0" }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
      el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
        el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, field.label),
        status,
      ]),
      field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
    ]),
    input,
  ]);
}
```

**saveConfigField()** (`settings.js` lines 598-614 — copy verbatim):
```js
async function saveConfigField(section, key, value, status) {
  status.classList.remove("ok", "warn", "bad");
  status.classList.add("warn");
  status.textContent = "сохранение…";
  try {
    const res = await api.patch("/api/config", { section, patch: { [key]: value } });
    status.classList.remove("warn");
    status.classList.add("ok");
    status.textContent = `ok · ${(res.restarted || []).join(", ") || "сохранено"}`;
    setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2500);
  } catch (e) {
    status.classList.remove("warn");
    status.classList.add("bad");
    status.textContent = "ошибка";
    toast(`${section}.${key}: ${e.message}`, "bad", 5000);
  }
}
```

**saveTuningField()** (`settings.js` lines 616-634 — copy verbatim):
```js
async function saveTuningField(tuningSectionPath, key, value, status) {
  status.classList.remove("ok", "warn", "bad");
  status.classList.add("warn");
  status.textContent = "сохранение…";
  try {
    const patch = {};
    setNested(patch, `${tuningSectionPath}.${key}`, value);
    await api.raw("/api/tuning", { method: "PUT", body: patch });
    status.classList.remove("warn");
    status.classList.add("ok");
    status.textContent = "сохранено ✓";
    setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2500);
  } catch (e) {
    status.classList.remove("warn");
    status.classList.add("bad");
    status.textContent = "ошибка";
    toast(`${tuningSectionPath}.${key}: ${e.message}`, "bad", 5000);
  }
}
```

**Card assembly in SCHEMA loop** (`settings.js` lines 930-993 — the render loop):
```js
SCHEMA.forEach((group) => {
  let sectionData;
  if (group.source === "config") {
    sectionData = getNested(config, group.section) || {};
  } else {
    sectionData = getNested(tuning, group.tuningSectionPath) || {};
  }

  const grid = el("div", { class: "field-grid" });
  group.fields.forEach((field) => {
    const effectiveSection = (group.source === "config" && field.sourceSection)
      ? field.sourceSection : group.section;
    const value = sectionData[field.key];
    const row = renderFieldRow(field, value, (f, st) => {
      if (group.source === "config") {
        return fieldInput(f, value, (v) => saveConfigField(effectiveSection, field.key, v, st), ctx);
      } else {
        return fieldInput(f, value, (v) => saveTuningField(group.tuningSectionPath, field.key, v, st), ctx);
      }
    });
    if (isWide) row.classList.add("field-wide");
    grid.appendChild(row);
  });

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, group.title),
      badge,  // "config/section" or "tuning:path"
    ]),
    el("div", { class: "card-body" }, [grid]),
  ]);
  if (hasTextarea) card.classList.add("card-full");
  cardGrid.appendChild(card);
});
```

**mount() teardown with disposables** (`settings.js` lines 833-1017):
```js
export function mount(target) {
  const disposables = [];
  // ... build DOM ...
  
  async function renderAll() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
    // ... re-render ...
    // Register disposable: if (typeof extra._dispose === "function") disposables.push(extra._dispose);
  }
  
  renderAll();
  return () => {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}
```

---

### 4. `panels/flora.js` — STATE TABLE REWRITE

**Analog:** self (in-place rewrite of state cards → compact table)

**STATE_SPEED constant** (`flora.js` lines 149-155 — keep verbatim):
```js
const STATE_SPEED = {
  breathe:     { key: "period_ms",      min: 1000, max: 10000, label: "Период дыхания, мс" },
  accent:      { key: "period_ms",      min: 300,  max: 3000,  label: "Период акцента, мс" },
  attentive:   { key: "wave_period_ms", min: 100,  max: 2000,  label: "Период волны, мс" },
  think_pulse: { key: "flash_ms",       min: 100,  max: 3000,  label: "Интервал вспышки, мс" },
  wake_bloom:  { key: "period_ms",      min: 1000, max: 8000,  label: "Период расцвета, мс" },
};
```

**STATE_LABELS** (`flora.js` lines 158-164 — keep verbatim):
```js
const STATE_LABELS = {
  breathe:     "breathe — покой",
  accent:      "accent — детекция",
  attentive:   "attentive — слушание",
  think_pulse: "think_pulse — раздумье",
  wake_bloom:  "wake_bloom — пробуждение",
};
const STATE_KEYS = ["breathe", "accent", "attentive", "think_pulse", "wake_bloom"];
```

**makeSlider() helper** (`flora.js` lines 22-74 — copy verbatim into new table implementation):
```js
function makeSlider({ label, hint, min, max, step, initValue, decimals = 0 }) {
  const slider = el("input", { type: "range", class: "input", style: "flex:1; ...", min, max, step, value: initValue ?? min });
  const valueLabel = el("span", { class: "mono", style: "min-width:42px; ..." }, fmt(initValue ?? min));
  slider.addEventListener("input", () => { valueLabel.textContent = fmt(slider.value); });
  // Returns { root, getValue, setValue }
}
```

**makeToggle() helper** (`flora.js` lines 77-105 — copy for Вибро column):
```js
function makeToggle({ label, hint, initValue, disabled, disabledHint }) {
  const select = el("select", { class: "select", disabled: disabled || false }, [...]);
  // Returns { root, getValue: () => disabled ? initValue : (select.value === "true") }
}
```

**"Показать сейчас" save+preview pattern** (`flora.js` lines 284-300):
```js
previewBtn.addEventListener("click", async () => {
  previewBtn.disabled = true;
  try {
    const statePatch = getValues();
    await api.patch("/api/config", {
      section: "flora",
      patch: { states: { [stateKey]: statePatch } },
    });
    await api.post("/api/flora/state", { state: stateKey });
    toast(`Показан пресет: ${stateKey}`, "ok");
  } catch (e) {
    toast(`Ошибка предпросмотра ${stateKey}: ${e.message}`, "bad", 5000);
  } finally {
    previewBtn.disabled = false;
  }
});
```

**Table row structure for D-11** (new pattern — derive from `makeSlider` + `makeToggle`):
```js
// For each stateKey: build <tr> with:
//   Col 1: STATE_LABELS[key]
//   Col 2: base_pct slider (max=100) — disabled/empty for accent/attentive/wake_bloom
//   Col 3: peak_pct slider (HARD CAP: max=71, not 100)
//   Col 4: speed input — makeSlider(STATE_SPEED[key]) + sub-label showing STATE_SPEED[key].key
//   Col 5: vibro toggle — disabled for "attentive"; "double_pulse"↔bool for "think_pulse"
//   Col 6: "Показать сейчас" button (saves state then POST /api/flora/state)

// CRITICAL: peak_pct slider max must be 71, not 100.
// D-11: speed cell shows speed value input PLUS a small label with the exact field name:
el("td", null, [
  speedSlider.root,
  el("span", { style: "font-size:10px; color:var(--muted); font-family:var(--font-mono)" }, STATE_SPEED[key].key),
]);
```

---

### 5. `panels/persona.js` — RESTRUCTURE for block editors

**Analog:** self (restructure) + `tuning.js` AIIM patterns

**Current GET/PUT pattern** (`persona.js` lines 35-44, 66-72):
```js
// GET returns: { base_prompt, files: [{name, path, content}] }
data = await api.get("/api/persona");

// PUT — CRITICAL: use "path" not "file"
const res = await api.raw("/api/persona", {
  method: "PUT",
  body: { path: file.path, content: ta.value }   // NOT { file, content }
});
```

**File card pattern** (`persona.js` lines 60-94 — adapt for markdown render/edit toggle):
```js
(data.files || []).forEach((file) => {
  const ta = el("textarea", { class: "textarea", rows: 18, style: "font-size:12px" });
  ta.value = file.content || "";
  const st = el("span", { class: "badge", style: "margin-left:8px" });
  const saveBtn = el("button", {
    class: "btn btn-primary",
    style: "font-size:12px; padding:4px 12px",
    onclick: async () => {
      try {
        const res = await api.raw("/api/persona", { method: "PUT", body: { path: file.path, content: ta.value } });
        st.textContent = `ok · ${res.bytes} б`;
        st.classList.add("ok");
      } catch (e) {
        st.classList.add("bad");
      }
    },
  }, "Сохранить");

  container.appendChild(el("div", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, file.name),
      el("span", { class: "dim", style: "font-size:11px" }, file.path),
      el("span", { class: "spacer" }),
      st, saveBtn,
    ]),
    el("div", { class: "card-body" }, [ta]),
  ]));
});
```

**Markdown render/edit toggle for Инструкции (new pattern)**:
```js
// Two states: view mode (marked.parse(content) innerHTML) vs edit mode (textarea)
function buildMarkdownEditor(file, onSave) {
  let isEditing = false;
  const content = file.content || "";

  const renderedView = el("div", { class: "markdown-body", html: marked.parse(content) });
  const editTextarea = el("textarea", { class: "textarea", rows: 18, style: "display:none; font-size:12px" });
  editTextarea.value = content;

  const editBtn = el("button", { class: "btn btn-ghost", onclick: () => {
    isEditing = !isEditing;
    renderedView.style.display = isEditing ? "none" : "";
    editTextarea.style.display = isEditing ? "" : "none";
    editBtn.textContent = isEditing ? "Отмена" : "Редактировать";
    saveBtn.style.display = isEditing ? "" : "none";
  }}, "Редактировать");

  const saveBtn = el("button", {
    class: "btn btn-primary", style: "display:none",
    onclick: () => onSave(file.path, editTextarea.value),
  }, "Сохранить");

  return el("div", { class: "card" }, [...]);
}
```

**Identity.md section extractor (from RESEARCH.md)**:
```js
// Identity.md section headers confirmed: "## Интенции" (line 71), "## Голос" (line 97)
function extractSection(markdown, sectionName) {
  const lines = markdown.split('\n');
  const startIdx = lines.findIndex(l => l.trim() === `## ${sectionName}`);
  if (startIdx === -1) return null;
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith('## '));
  const sectionLines = endIdx === -1 ? lines.slice(startIdx + 1) : lines.slice(startIdx + 1, endIdx);
  return sectionLines.join('\n').trim();
}

function reconstructFile(original, sectionName, newContent) {
  const lines = original.split('\n');
  const startIdx = lines.findIndex(l => l.trim() === `## ${sectionName}`);
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith('## '));
  const before = lines.slice(0, startIdx);
  const after = endIdx === -1 ? [] : lines.slice(endIdx);
  return [...before, `## ${sectionName}`, '', ...newContent.split('\n'), '', ...after].join('\n');
}
// PUT /api/persona { path: 'Agent-Adam-Chip/About/Identity.md', content: reconstructed }
```

---

### 6. `panels/audioInput.js` — FIX card-full bug (D-15)

**Analog:** self

**Bug location** (`audioInput.js` line 820 — Card 1: Volume):
```js
// CURRENT (wrong): single slider gets full-width card
grid.appendChild(el("section", { class: "card card-full" }, [    // ← remove "card-full"
  el("div", { class: "card-header" }, [
    el("span", { class: "card-title" }, "Громкость входа"),
    el("span", { class: "caps mono dim" }, "media.audio.input_gain"),
  ]),
  el("div", { class: "card-body" }, buildVolumeSection(inputGain)),
]));

// FIX: remove "card-full" from Volume card only
grid.appendChild(el("section", { class: "card" }, [...]))  // Cards 2-5 keep "card-full"
```

**Cards 2-5 legitimately use `card-full`** (`audioInput.js` lines 840, 851, 864, 876):
```js
// Card 2 (EQ canvas), Card 3 (OWW meter), Card 4 (Monitor), Card 5 (Presets) — keep card-full
grid.appendChild(el("section", { class: "card card-full" }, [...]))
```

**disposables pattern** (`audioInput.js` lines 793-896 — copy for all new panels with SSE):
```js
export function mount(target) {
  const disposables = [];
  // ...
  async function renderAll() {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
    // ... build widgets ...
    if (typeof owwWrapper._dispose === "function") disposables.push(owwWrapper._dispose);
    if (typeof monitorWrapper._dispose === "function") disposables.push(monitorWrapper._dispose);
  }
  renderAll();
  return () => {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
  };
}
```

---

### 7. `panels/services.js` — MERGE with models.js, add VLM card

**Analog:** self

**SERVICE_META pattern** (`services.js` lines 20-24 — extend to include VLM):
```js
const SERVICE_META = {
  llm: { label: "LLM (llama-server)",    unit: "adam-llm.service",            desc: "Inference на GPU, порт :8081" },
  tts: { label: "TTS (Silero)",           unit: "adam-tts-silero.service",    desc: "Синтез речи, порт :8082" },
  asr: { label: "ASR (WhisperX)",          unit: "adam-asr-whisperx.service", desc: "Распознавание речи, порт :8095" },
  vlm: { label: "VLM (Cosmos-Reason2-2B)", unit: "adam-vlm.service",          desc: "Описание сцены, порт :8051" },
  // Add adam-vlm.service — same buildServiceCard() pattern as others
};
// REMOVE buildVlmCard() entirely (dead Docker card for VILA1.5-3b)
```

**buildServiceCard() pattern** (`services.js` lines 98-173 — copy verbatim for all services):
```js
function buildServiceCard(name, meta) {
  let busy = false;
  const statusDot  = dot("muted");
  const statusText = el("span", { class: "muted", text: "загрузка…" });

  async function action(verb) {
    if (busy) return;
    busy = true;
    [btnStart, btnStop, btnRestart].forEach(b => b.disabled = true);
    try {
      await api.post(`/api/services/${name}/${verb}`);
      toast(`${meta.label}: ${verb}`, "ok");
    } catch (err) {
      toast(`${meta.label}: ${err.message || err}`, "error");
    } finally {
      busy = false;
      await refresh();
    }
  }
  // ...
  async function refresh() {
    try {
      const [svcData, statusData] = await Promise.all([
        api.get("/api/services"),
        api.get("/api/agent/status"),
      ]);
      // Update dot, text, buttons based on health
    } catch { /* fallback */ }
  }

  const card = el("div", { class: "card" }, [...]);
  return { card, refresh };
}
```

**setInterval teardown** (`services.js` lines 198-201):
```js
const interval = setInterval(refreshAll, 5000);
return () => clearInterval(interval);
```

---

### 8. `panels/metrics.js` — RECEIVE inlineList migration from prompts.js

**Analog:** self + prompts.js

**Unique content to migrate from prompts.js** — `inlineList()` function:
```js
// Source: prompts.js ~line 82, inside turnRow()
function inlineList(items) {
  if (!items || !items.length) return null;
  return el("div",
    { style: "color:var(--muted); font-size:12px; margin-top:4px; font-family:var(--font-mono)" },
    items.join(" · ")
  );
}
```

**Where to insert in metrics.js** — inside `promptTurnRow()` (`metrics.js` lines 95-124), after `injectionsBadges` div:
```js
function promptTurnRow(item, onShow) {
  // ...
  return el("div", { class: "card", style: "margin-bottom:8px" }, [
    el("div", { class: "card-header", ... }, [...]),
    el("div", { class: "card-body", style: "display:flex; flex-direction:column; gap:8px" }, [
      item.reply ? el("div", { style: "color:var(--accent); font-size:13px; white-space:pre-wrap" }, "→ " + item.reply) : null,
      el("div", { style: "display:flex; flex-wrap:wrap; gap:4px; align-items:center" }, injectionsBadges(item)),
      inlineList(item.recent_episodic),    // ← ADD HERE
      item.llm_error ? el("div", ...) : null,
    ]),
    detailsBox,
  ]);
}
```

**tab row structure** (`metrics.js` lines 54-68 — copy for table row building pattern):
```js
function turnRow(t) {
  return el("tr", { class: "fade-in" }, [
    el("td", { class: "mono dim", style: "padding:6px 8px; white-space:nowrap" }, ts),
    el("td", { class: "mono",     style: "padding:6px 8px; color:var(--muted)" }, t.source || "—"),
    el("td", { style: "padding:6px 8px; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" }, t.transcript || ""),
    // ...
  ]);
}
```

---

### 9. `panels/subsystem.js` — SPLIT into ESP32 Общие (3.3) + Диагностика (5.3)

**Analog:** self

**moduleGrid() function** (`subsystem.js` lines 37-58 — move to diagnostics/esp32Health.js):
```js
function moduleGrid(modules) {
  const items = MODULE_ORDER.map((key) => {
    const m = modules?.[key];
    const ok = m?.ok === true;
    const kind = unknown ? "warn" : ok ? "ok" : "bad";
    return el("div", {
      style: "display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--bg-3)",
    }, [
      dot(kind),
      el("span", { style: "font-size:13px" }, MODULE_LABELS[key] || key),
      ...
    ]);
  });
  const grid = el("div", { style: "display:grid; grid-template-columns:1fr 1fr; gap:0 24px" });
  items.forEach((it) => grid.appendChild(it));
  return grid;
}
```

**addrRow() function** (`subsystem.js` lines 61-75 — keep in ESP32 Общие):
```js
function addrRow(label, value) {
  return el("div", {
    style: "display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid var(--bg-3); font-size:12px",
  }, [
    el("span", { class: "caps", style: "color:var(--muted)" }, label),
    el("a", {
      href: value.startsWith("http") ? value : "#",
      target: "_blank", rel: "noopener",
      class: "mono",
      style: "color:var(--accent); text-decoration:none; word-break:break-all",
    }, value),
  ]);
}
```

**configSection() read-only display** (`subsystem.js` lines 91-103 — for Общие настройки 3.3.1):
```js
function configSection(title, obj) {
  const grid = el("div", { class: "field-grid" });
  Object.entries(obj).forEach(([k, v]) => {
    if (typeof v === "object" && !Array.isArray(v)) return; // skip nested
    grid.appendChild(configKv(k, v));
  });
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, title)),
    el("div", { class: "card-body" }, [grid]),
  ]);
}
```

**mount() no-SSE teardown** (`subsystem.js` lines 106+):
```js
export function mount(target) {
  // No SSE subscriptions in this panel — no disposables needed
  // ... build DOM ...
  refresh();
  return () => {};   // or return undefined if no cleanup
}
```

---

### 10. NEW `panels/agent/memory.js` — Память section

**Analog:** `settings.js` (SCHEMA pattern) + `persona.js` (file GET pattern)

**Pool file display pattern** (derive from `persona.js` lines 60-94):
```js
// Echoes.md / Jokes.md / Chinese_lines.md loaded via /api/persona GET
// These appear in data.files[] filtered by path
const poolFiles = (data.files || []).filter(f =>
  f.path.includes("Echoes.md") || f.path.includes("Jokes.md") || f.path.includes("Chinese_lines.md")
);
// Render as read-only card with content preview
```

**Memory settings via SCHEMA/tuning** (reuse `settings.js` saveTuningField + SCHEMA groups):
```js
// From tuning.js — migrate these SPEC groups to memory.js:
// memory.episodic, memory.episodic.weights, memory.semantic, memory.recent_injection, memory.consolidator
// Use same SCHEMA format + schemaFields rendering from settings.js
```

**mount() + disposables** (no SSE needed, use simple teardown):
```js
export function mount(target) {
  const disposables = [];
  const container = el("div", { class: "col" });
  // ...
  async function renderAll() { ... }
  renderAll();
  return () => {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
  };
}
```

---

## Shared Patterns

### el() DOM Builder
**Source:** All panel files (identical implementation in each file)
**Apply to:** ALL new panel files — copy verbatim, do NOT import from elsewhere

```js
function el(tag, attrs, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v != null && v !== false) node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null || c === false) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}
```

### mount() → teardown Contract
**Source:** `settings.js` lines 833-1017, `audioInput.js` lines 779-897, `services.js` lines 175-201
**Apply to:** ALL new panel files — non-negotiable

```js
export function mount(target) {
  const disposables = [];
  // ... build DOM, subscribe events ...
  // For widgets with _dispose: disposables.push(widget._dispose);
  // For setInterval: const id = setInterval(...); disposables.push(() => clearInterval(id));
  // For SSE: const unsub = subscribeEvents(...); disposables.push(unsub);

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}
```

### SSE subscription via subscribeEvents
**Source:** `api.js` lines 49-80, `audioInput.js` lines 442-454
**Apply to:** Any panel that shows live data

```js
import { api, subscribeEvents } from "../api.js";

// Returns dispose function — MUST add to disposables[]
const unsub = subscribeEvents((ev) => {
  if (ev.type === "oww_score") { ... }
  if (ev.type === "wake_word_detected") { ... }
}, () => { /* reconnect callback — optional */ });
disposables.push(unsub);
```

### Status badge flash pattern
**Source:** `audioInput.js` lines 42-61 (flashOk/flashBad/flashBusy)
**Apply to:** Any panel with save/action buttons

```js
function statusBadge() {
  return el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
}
function flashOk(badge, text = "ok") {
  badge.classList.remove("warn", "bad");
  badge.classList.add("ok");
  badge.textContent = text;
  setTimeout(() => { badge.textContent = ""; badge.classList.remove("ok"); }, 2200);
}
function flashBad(badge, text = "ошибка") {
  badge.classList.remove("warn", "ok");
  badge.classList.add("bad");
  badge.textContent = text;
  setTimeout(() => { badge.textContent = ""; badge.classList.remove("bad"); }, 3500);
}
```

### card > card-header + card-body structure
**Source:** All panel files
**Apply to:** ALL cards in all panels

```js
el("section", { class: "card" }, [
  el("div", { class: "card-header" }, [
    el("span", { class: "card-title" }, "Card Title"),
    el("span", { class: "caps mono dim" }, "config/path"),  // badge
  ]),
  el("div", { class: "card-body" }, [
    el("div", { class: "field-grid" }, [...fields]),
  ]),
]);
// card-full: span full grid width (for canvas/complex content)
// card-grid: parent for multiple cards (auto-fill, minmax)
```

### getNested / setNested helpers
**Source:** `settings.js` lines 22-35
**Apply to:** All panels reading/writing nested config paths

```js
function getNested(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}
function setNested(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (cur[keys[i]] == null || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return obj;
}
```

### localStorage nav group open/close
**Source:** `main.js` lines 118-148
**Apply to:** buildNav() when adding 3-level support

```js
// Extend existing pattern:
// Level 1 group: `navGroup_${item.id}` (existing)
// Level 2 subgroup: `navGroup_${parentId}_${subId}` (new)
const storageKey = `navGroup_${parentId}_${subId}`;
const isOpen = localStorage.getItem(storageKey) !== "false";
// Toggle: localStorage.setItem(storageKey, String(!open));
```

### dot() status indicator
**Source:** `subsystem.js` lines 30-35, `services.js` lines 94-96
**Apply to:** ESP32 health panel, services panel

```js
// subsystem.js style (with inline color):
function dot(kind) {
  const colors = { ok: "var(--ok, #4caf50)", bad: "var(--bad, #f44336)", warn: "var(--warn, #ff9800)" };
  return el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%; background:${colors[kind] || "var(--muted)"}; flex-shrink:0`,
  });
}
// services.js style (CSS class):
// el("span", { class: `dot ${kind}` })
```

---

## No Analog Found

Files with no close match in the codebase:

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `panels/agent/instructions.js` (new) | persona editor | request-response | Markdown render+edit toggle does not exist yet; `persona.js` gives the file load/save base, but the view/edit toggle with marked.js is new |

For `instructions.js`, use `persona.js` for GET/PUT patterns + implement the render/edit toggle as described in Pattern Assignment #5.

---

## Critical Pitfalls Extracted from RESEARCH.md

1. **`/api/persona` PUT body**: always `{ path: file.path, content: ta.value }` — never `{ file, content }` (confirmed from `persona.js` line 71)

2. **vad_onset/vad_offset duplication**: `settings.js` ASR group has these fields TWICE (lines 208-213 and lines 219-226) — when migrating to 3.2, keep only the first occurrence with fuller hint text

3. **`reply_absolute_deadline_sec`**: invalid field in settings.js ASR group (line 198-200) — do NOT migrate to 3.2

4. **flora peak_pct hard cap**: slider max MUST be `71`, not `100` — enforced by `flora.py _build_params()` via `max_duty_pct`; current `buildStateCard()` incorrectly uses `max: 100` (line 199)

5. **dead VLM card**: `buildVlmCard()` in `services.js` calls `/api/live_vlm/*` (Docker, removed) — delete entirely, add `vlm` to SERVICE_META with `adam-vlm.service`

6. **VLM stale hint**: settings.js "VLM · описание сцены" card has `"http://127.0.0.1:8084"` hint — update to `:8051` when migrating

7. **audioInput.js volume card**: line 820 — remove `card-full` from Volume card (Card 1); Cards 2-5 legitimately use `card-full`

8. **parseHash() in router.js** (line 29): currently splits on `[/?]` taking first segment — must change to NOT split when implementing nested routes `#/agent/persona`

---

## Metadata

**Analog search scope:** `System/WebUI/static/js/panels/` + `System/WebUI/static/js/`
**Files scanned:** 10 panel files + `router.js` + `main.js` + `api.js`
**Pattern extraction date:** 2026-06-14
