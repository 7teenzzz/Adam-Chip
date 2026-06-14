// Panel: #/agent/memory
// Two sub-tabs:
//   Базовая  — pool files (Echoes.md / Jokes.md / Chinese_lines.md) + pool settings (echoes/chinese tuning)
//   Дополненная — memory system settings (episodic/weights/semantic/recent_injection/consolidator) + visitor registry placeholder

import { api } from "../../api.js";
import { toast } from "../../widgets/toast.js";

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

// ── Nested helpers ────────────────────────────────────────────────────────────

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

// ── Save helpers (verbatim from settings.js) ─────────────────────────────────

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

// ── Field row renderer (verbatim from settings.js) ────────────────────────────

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

// Build a single field input element for a tuning field.
function buildTuningInput(field, value, onSave, disposables) {
  const type = field.type;
  const isNum = type === "int" || type === "float";

  if (type === "bool") {
    const cb = el("input", { type: "checkbox" });
    cb.checked = !!value;
    cb.addEventListener("change", () => onSave(cb.checked));
    return cb;
  }

  if (type === "enum") {
    const sel = el("select", { class: "input mono" },
      (field.options || []).map((opt) => {
        const o = el("option", { value: opt }, opt);
        if (opt === value) o.setAttribute("selected", "selected");
        return o;
      })
    );
    sel.addEventListener("change", () => onSave(sel.value));
    return sel;
  }

  if (isNum && field.min != null && field.max != null) {
    const step = field.step ?? (type === "int" ? 1 : 0.05);
    const slider = el("input", {
      type: "range",
      class: "input",
      style: "flex:1; min-width:120px; cursor:pointer",
      min: field.min,
      max: field.max,
      step,
      value: value ?? field.min,
    });
    const init = value ?? field.min;
    const valueLabel = el("span", {
      class: "mono",
      style: "min-width:48px; text-align:right; color:var(--accent); font-size:12px; font-weight:600",
    }, type === "int" ? String(Math.round(Number(init))) : Number(init).toFixed(2));
    slider.addEventListener("input", () => {
      valueLabel.textContent = type === "int"
        ? String(Math.round(Number(slider.value)))
        : Number(slider.value).toFixed(2);
    });
    slider.addEventListener("change", () => {
      const v = type === "int" ? parseInt(slider.value, 10) : parseFloat(slider.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onSave(v);
    });
    return el("div", { style: "display:flex; align-items:center; gap:10px; padding:4px 0" }, [
      slider, valueLabel,
    ]);
  }

  const attrs = { class: "input", type: isNum ? "number" : "text" };
  if (isNum) {
    if (field.min != null) attrs.min = field.min;
    if (field.max != null) attrs.max = field.max;
    if (field.step != null) attrs.step = field.step;
    else if (type === "int") attrs.step = "1";
    else attrs.step = "any";
  }
  const input = el("input", attrs);
  input.value = value ?? "";
  input.addEventListener("change", () => {
    if (isNum) {
      const v = type === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onSave(v);
    } else {
      onSave(input.value);
    }
  });
  return input;
}

// Render a SCHEMA group as a card using tuning data.
function renderTuningCard(group, tuning, disposables) {
  const sectionData = getNested(tuning, group.tuningSectionPath) || {};
  const grid = el("div", { class: "field-grid" });
  const isFullWidth = group.full || false;

  group.fields.forEach((field) => {
    const value = sectionData[field.key];
    const row = renderFieldRow(field, value, (f, statusEl) => {
      return buildTuningInput(f, value, (v) => saveTuningField(group.tuningSectionPath, f.key, v, statusEl), disposables);
    });
    if (isFullWidth) row.classList.add("field-wide");
    grid.appendChild(row);
  });

  const card = el("section", {
    class: isFullWidth ? "card card-full" : "card",
  }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, group.title),
      el("span", { class: "caps mono dim", style: "font-size:10px" }, `tuning/${group.tuningSectionPath}`),
    ]),
    el("div", { class: "card-body" }, [grid]),
  ]);

  return card;
}

// ── SCHEMA for Базовая pool settings ─────────────────────────────────────────

const POOL_SCHEMA = [
  {
    title: "Эхо · настройки пула",
    tuningSectionPath: "echoes",
    fields: [
      { key: "enabled",               label: "Активны",                        type: "bool" },
      { key: "global_cooldown_turns", label: "Перерыв между эхо (ходов)",      type: "int",   min: 0, max: 100,
        hint: "не чаще раза в N диалоговых ходов" },
      { key: "per_echo_cooldown_days", label: "Перерыв для одного эхо (дней)", type: "int",   min: 0, max: 365,
        hint: "конкретное эхо не чаще раза в N дней" },
      { key: "match_threshold",        label: "Порог совпадения",              type: "float", min: 0, max: 1, step: 0.05 },
      { key: "weight_multiplier",      label: "Множитель весов",               type: "float", min: 0, max: 5, step: 0.1,
        hint: "общий множитель для всех весов эхо" },
      { key: "matcher_type",           label: "Метод сравнения",               type: "enum",  options: ["tag", "tfidf"] },
    ],
  },
  {
    title: "Китайские вкрапления · настройки пула",
    tuningSectionPath: "chinese",
    fields: [
      { key: "enabled",               label: "Активны",                 type: "bool" },
      { key: "global_cooldown_turns", label: "Перерыв (ходов)",         type: "int",   min: 0, max: 100 },
      { key: "match_threshold",       label: "Порог совпадения",        type: "float", min: 0, max: 1, step: 0.05 },
      { key: "weight_multiplier",     label: "Множитель весов",         type: "float", min: 0, max: 5, step: 0.1 },
      { key: "audio_mode",            label: "Режим аудио",             type: "enum",
        options: ["prerendered_only", "prerendered_with_text_fallback", "text_only"] },
    ],
  },
];

// ── SCHEMA for Дополненная memory settings ─────────────────────────────────

const MEMORY_SCHEMA = [
  {
    title: "Эпизодическая память",
    tuningSectionPath: "memory.episodic",
    fields: [
      { key: "enabled",                   label: "Запись эпизодов",              type: "bool",
        hint: "включить или отключить сохранение эпизодов" },
      { key: "salience_threshold",        label: "Порог значимости",             type: "float", min: 0, max: 1, step: 0.05,
        hint: "0–1 · минимальный балл для записи эпизода" },
      { key: "decay_days",                label: "Дней до забывания",            type: "int",   min: 1, max: 365,
        hint: "через сколько дней эпизод удаляется" },
      { key: "duration_normalize_seconds", label: "Норматив длительности (с)",   type: "int",   min: 30, max: 3600,
        hint: "знаменатель нормализации длины сессии" },
      { key: "highlights_max_per_episode", label: "Макс. маркеров на эпизод",   type: "int",   min: 1, max: 50 },
    ],
  },
  {
    title: "Веса формулы значимости",
    tuningSectionPath: "memory.episodic.weights",
    fields: [
      { key: "introduced_name", label: "Имя зрителя",           type: "float", min: 0, max: 1, step: 0.05 },
      { key: "duration",        label: "Длительность",           type: "float", min: 0, max: 1, step: 0.05 },
      { key: "themes",          label: "Темы",                   type: "float", min: 0, max: 1, step: 0.05 },
      { key: "tone",            label: "Тональность",            type: "float", min: 0, max: 1, step: 0.05 },
      { key: "echoes_used",     label: "Использованные эхо",     type: "float", min: 0, max: 1, step: 0.05 },
      { key: "new_question",    label: "Новый вопрос",           type: "float", min: 0, max: 1, step: 0.05 },
    ],
  },
  {
    title: "Семантическая память",
    tuningSectionPath: "memory.semantic",
    fields: [
      { key: "enabled",   label: "Активна",        type: "bool" },
      { key: "max_chars", label: "Макс. символов", type: "int",   min: 200, max: 20000,
        hint: "сколько символов резюме хранится в промте" },
    ],
  },
  {
    title: "Инъекция недавних эпизодов",
    tuningSectionPath: "memory.recent_injection",
    fields: [
      { key: "enabled",      label: "Активна",                type: "bool" },
      { key: "limit",        label: "Лимит эпизодов",         type: "int",   min: 0, max: 10,
        hint: "сколько эпизодов добавлять в промт" },
      { key: "strategy",     label: "Стратегия отбора",       type: "enum",  options: ["by_name", "by_theme", "by_name_or_theme"] },
      { key: "max_age_days", label: "Макс. возраст (дней)",   type: "int",   min: 1, max: 365 },
    ],
  },
  {
    title: "Консолидатор (ночное обновление)",
    tuningSectionPath: "memory.consolidator",
    full: true,
    fields: [
      { key: "enabled",               label: "Активен",                     type: "bool" },
      { key: "model",                 label: "Модель LLM",                   type: "string",
        hint: "модель для консолидации, null = как у LLM" },
      { key: "window_start",          label: "Начало окна",                  type: "string",
        hint: "формат ЧЧ:ММ" },
      { key: "window_end",            label: "Конец окна",                   type: "string",
        hint: "формат ЧЧ:ММ" },
      { key: "max_episodes_per_run",  label: "Макс. эпизодов за прогон",    type: "int",   min: 1 },
      { key: "temperature",           label: "Температура",                   type: "float", min: 0, max: 2, step: 0.05 },
      { key: "max_runtime_minutes",   label: "Макс. время работы (мин)",     type: "int",   min: 1, max: 240 },
      { key: "retry_on_invalid_patch", label: "Повтор при ошибке патча",    type: "bool" },
    ],
  },
];

// ── Pool files display ────────────────────────────────────────────────────────

const POOL_FILE_NAMES = ["Echoes.md", "Jokes.md", "Chinese_lines.md"];

function isPoolFile(path) {
  return POOL_FILE_NAMES.some((name) => path.includes(name));
}

function renderPoolCard(file) {
  const content = file.content || "";
  const lines = content.split("\n").filter((l) => l.trim().length > 0);

  let body;
  if (lines.length === 0) {
    // T-42-06 mitigation: empty pool shows graceful empty-state.
    body = el("div", { style: "padding:12px 0" }, [
      el("p", { style: "color:var(--muted); font-size:13px; margin:0 0 4px" }, "Пул пуст"),
      el("p", { style: "color:var(--dim); font-size:11px; margin:0" }, "Файл пула не содержит записей."),
    ]);
  } else {
    // Show first ~10 lines as a read-only preview.
    const preview = lines.slice(0, 10).join("\n") + (lines.length > 10 ? "\n…" : "");
    const pre = el("pre", {
      style: "font-size:12px; color:var(--text); white-space:pre-wrap; margin:0; font-family:var(--font-mono); overflow:auto; max-height:200px",
    });
    pre.textContent = preview;
    body = el("div", { style: "padding:8px 0" }, [
      el("span", { style: "font-size:10px; color:var(--muted); font-family:var(--font-mono)" }, `${lines.length} строк · только просмотр`),
      pre,
    ]);
  }

  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, file.name),
      el("span", { class: "dim", style: "font-size:11px; margin-left:8px" }, file.path),
    ]),
    el("div", { class: "card-body" }, [body]),
  ]);
}

// ── Tab bar ───────────────────────────────────────────────────────────────────

function buildTabBar(tabs, onChange) {
  const buttons = tabs.map((tab) => {
    const btn = el("button", {
      class: "btn btn-ghost",
      style: "font-size:13px; border-radius:0; padding:8px 16px; border-bottom:2px solid transparent; background:none; cursor:pointer",
      text: tab.label,
      onclick: () => {
        buttons.forEach((b, i) => {
          const isActive = i === tabs.indexOf(tab);
          b.style.borderBottomColor = isActive ? "var(--accent)" : "transparent";
          b.style.color = isActive ? "var(--accent)" : "";
        });
        onChange(tab.id);
      },
    });
    return btn;
  });

  // Activate first tab by default.
  buttons[0].style.borderBottomColor = "var(--accent)";
  buttons[0].style.color = "var(--accent)";

  return el("div", {
    class: "row",
    style: "border-bottom:1px solid var(--border); gap:0; margin-bottom:16px",
  }, buttons);
}

// ── Main mount ────────────────────────────────────────────────────────────────

export function mount(target) {
  const disposables = [];

  const container = el("div", { class: "col", style: "gap:0" });
  target.appendChild(container);

  // Content divs for each tab — only one is visible at a time.
  const basicContent  = el("div", { class: "col", style: "gap:12px; display:block" });
  const advancedContent = el("div", { class: "col", style: "gap:12px; display:none" });

  const tabBar = buildTabBar(
    [
      { id: "basic",    label: "Базовая" },
      { id: "advanced", label: "Дополненная" },
    ],
    (id) => {
      basicContent.style.display    = id === "basic"    ? "block" : "none";
      advancedContent.style.display = id === "advanced" ? "block" : "none";
    }
  );

  container.appendChild(tabBar);
  container.appendChild(basicContent);
  container.appendChild(advancedContent);

  async function renderBasic(personaData, tuningData) {
    basicContent.innerHTML = "";

    const cardGrid = el("div", { class: "card-grid" });

    // Pool file display cards (read-only).
    const poolFiles = (personaData.files || []).filter((f) => isPoolFile(f.path));
    if (poolFiles.length === 0) {
      cardGrid.appendChild(el("div", {
        class: "card",
        style: "grid-column:1/-1",
      }, [
        el("div", { class: "card-body" }, [
          el("p", { style: "color:var(--muted); font-size:13px; margin:0 0 4px" }, "Пулы не найдены"),
          el("p", { style: "color:var(--dim); font-size:11px; margin:0" },
            "Echoes.md / Jokes.md / Chinese_lines.md не обнаружены среди файлов персоны."),
        ]),
      ]));
    } else {
      poolFiles.forEach((f) => cardGrid.appendChild(renderPoolCard(f)));
    }

    // Pool settings cards from tuning (echoes/chinese).
    POOL_SCHEMA.forEach((group) => {
      cardGrid.appendChild(renderTuningCard(group, tuningData, disposables));
    });

    basicContent.appendChild(cardGrid);
  }

  function renderAdvanced(tuningData) {
    advancedContent.innerHTML = "";

    const cardGrid = el("div", { class: "card-grid" });

    // Memory settings cards.
    MEMORY_SCHEMA.forEach((group) => {
      cardGrid.appendChild(renderTuningCard(group, tuningData, disposables));
    });

    // Visitor registry placeholder (Phase 37 deferred, D-06).
    cardGrid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Реестр посетителей"),
        el("span", { class: "caps mono dim", style: "font-size:10px" }, "deferred · Phase 37"),
      ]),
      el("div", { class: "card-body" }, [
        el("p", { style: "color:var(--muted); font-size:13px; margin:0 0 4px" }, "Данные недоступны"),
        el("p", { style: "color:var(--dim); font-size:11px; margin:0" },
          "Реестр посетителей будет доступен после Phase 37."),
      ]),
    ]));

    advancedContent.appendChild(cardGrid);
  }

  async function renderAll() {
    // Drain previous disposables.
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }

    basicContent.innerHTML = "";
    basicContent.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:12px 0", text: "Загрузка…" }));
    advancedContent.innerHTML = "";

    let personaData, tuningData;
    try {
      [personaData, tuningData] = await Promise.all([
        api.get("/api/persona"),
        api.get("/api/tuning"),
      ]);
    } catch (e) {
      basicContent.innerHTML = "";
      basicContent.appendChild(el("div", {
        class: "muted",
        style: "font-size:12px; padding:12px 0",
        text: "Ошибка загрузки: " + e.message,
      }));
      return;
    }

    renderBasic(personaData, tuningData);
    renderAdvanced(tuningData);
  }

  renderAll();

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}
